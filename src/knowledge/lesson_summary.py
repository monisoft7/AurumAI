import json
import hashlib
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from knowledge.memory import Memory


DEFAULT_HORIZONS = (1, 5, 20)


@dataclass(frozen=True)
class LessonSummaryConfig:
    lessons_path: Path = Path("data/lessons/cpi_gold_lessons.csv")
    output_path: Path = Path("data/knowledge/cpi_gold_summary.json")
    memory_path: Path = Path("data/memory/memory.json")
    condition_columns: tuple[str, ...] = ("cpi_pressure",)
    knowledge_prefix: str = "cpi_gold_summary_v1"
    event_type: str = "CPI"
    asset: str = "GOLD"
    horizons: tuple[int, ...] = DEFAULT_HORIZONS
    min_samples_for_confidence: int = 12


class LessonSummaryAggregator:
    """Aggregate lessons into reusable market knowledge records."""

    def __init__(self, config: LessonSummaryConfig | None = None):
        self.config = config or LessonSummaryConfig()

    def build(self) -> dict[str, object]:
        lessons = self._load_lessons(self.config.lessons_path)
        records = []

        for condition_values, group in lessons.groupby(
            list(self.config.condition_columns), sort=True
        ):
            if not isinstance(condition_values, tuple):
                condition_values = (condition_values,)
            condition_dict = dict(zip(self.config.condition_columns, condition_values))
            for horizon in self.config.horizons:
                records.append(self._summarize_group(condition_dict, group, horizon))

        return {
            "knowledge_version": self.config.knowledge_prefix,
            "source_lessons": str(self.config.lessons_path),
            "source_artifact_sha256": self._sha256(self.config.lessons_path),
            "event_type": self.config.event_type,
            "asset": self.config.asset,
            "record_count": len(records),
            "records": records,
        }

    def build_and_save(self) -> dict[str, object]:
        summary = self.build()
        self.config.output_path.parent.mkdir(parents=True, exist_ok=True)
        self.config.output_path.write_text(json.dumps(summary, indent=4, sort_keys=True))
        return summary

    def build_save_and_ingest_memory(self) -> dict[str, object]:
        summary = self.build_and_save()
        Memory(self.config.memory_path).set_namespace(self.config.knowledge_prefix, summary)
        return summary

    def _load_lessons(self, path: Path) -> pd.DataFrame:
        df = pd.read_csv(path)
        required = {
            "lesson_id",
            "event_type",
            "event_date",
        }
        for col in self.config.condition_columns:
            required.add(col)
        for horizon in self.config.horizons:
            required.add(f"gold_return_{horizon}d_pct")
            required.add(f"gold_direction_{horizon}d")

        missing = required.difference(df.columns)
        if missing:
            missing_text = ", ".join(sorted(missing))
            raise ValueError(f"{path} is missing required columns: {missing_text}")

        df = df[df["event_type"] == self.config.event_type].copy()
        if df.empty:
            raise ValueError(
                f"{path} contains no {self.config.event_type} lessons."
            )

        for horizon in self.config.horizons:
            df[f"gold_return_{horizon}d_pct"] = pd.to_numeric(
                df[f"gold_return_{horizon}d_pct"],
                errors="raise",
            )

        return df

    def _summarize_group(
        self,
        condition: dict[str, str],
        group: pd.DataFrame,
        horizon: int,
    ) -> dict[str, object]:
        returns = group[f"gold_return_{horizon}d_pct"]
        directions = group[f"gold_direction_{horizon}d"]
        source_lesson_ids = tuple(str(v) for v in sorted(group["lesson_id"].tolist()))
        sample_count = int(len(group))
        up_count = int((directions == "UP").sum())
        down_count = int((directions == "DOWN").sum())
        flat_count = int((directions == "FLAT").sum())
        positive_count = int((returns > 0).sum())
        negative_count = int((returns < 0).sum())
        positive_rate = self._rate(positive_count, sample_count)
        negative_rate = self._rate(negative_count, sample_count)

        condition_suffix = "_".join(str(v) for v in condition.values())

        return {
            "knowledge_id": f"{self.config.event_type}_{self.config.asset}_{condition_suffix}_{horizon}D",
            "event_type": self.config.event_type,
            "asset": self.config.asset,
            "source_lesson_ids": list(source_lesson_ids),
            "source_artifact_path": str(self.config.lessons_path),
            "source_artifact_sha256": self._sha256(self.config.lessons_path),
            "condition": dict(condition),
            "horizon_days": horizon,
            "sample_count": sample_count,
            "positive_return_rate_pct": positive_rate,
            "negative_return_rate_pct": negative_rate,
            "up_direction_rate_pct": self._rate(up_count, sample_count),
            "down_direction_rate_pct": self._rate(down_count, sample_count),
            "flat_direction_rate_pct": self._rate(flat_count, sample_count),
            "average_return_pct": round(float(returns.mean()), 6),
            "median_return_pct": round(float(returns.median()), 6),
            "min_return_pct": round(float(returns.min()), 6),
            "max_return_pct": round(float(returns.max()), 6),
            "first_event_date": str(group["event_date"].min()),
            "last_event_date": str(group["event_date"].max()),
            "bias": self._bias(positive_rate),
            "confidence": self._confidence(sample_count, positive_rate, returns.mean()),
            "explanation": self._explanation(
                condition,
                horizon,
                sample_count,
                positive_rate,
                returns.mean(),
            ),
        }

    def _rate(self, count: int, total: int) -> float:
        if total == 0:
            return 0.0
        return round((count / total) * 100.0, 6)

    def _bias(self, positive_rate: float) -> str:
        if positive_rate >= 60.0:
            return "gold_positive_bias"
        if positive_rate <= 40.0:
            return "gold_negative_bias"
        return "mixed_or_context_dependent"

    def _confidence(
        self,
        sample_count: int,
        positive_rate: float,
        average_return: float,
    ) -> float:
        sample_score = min(sample_count / self.config.min_samples_for_confidence, 1.0)
        edge_score = min(abs(positive_rate - 50.0) / 50.0, 1.0)
        move_score = min(abs(float(average_return)) / 5.0, 1.0)
        confidence = (0.50 * sample_score) + (0.30 * edge_score) + (0.20 * move_score)
        return round(confidence, 6)

    def _explanation(
        self,
        condition: dict[str, str],
        horizon: int,
        sample_count: int,
        positive_rate: float,
        average_return: float,
    ) -> str:
        condition_desc = "; ".join(
            f"{k}={v}" for k, v in condition.items()
        )
        return (
            f"For {self.config.event_type} condition {condition_desc}, "
            f"{sample_count} historical lessons show "
            f"{self.config.asset} had a positive {horizon}-day return "
            f"in {positive_rate}% of cases, "
            f"with an average return of {round(float(average_return), 6)}%."
        )

    def _sha256(self, path: Path) -> str:
        return hashlib.sha256(path.read_bytes()).hexdigest()
