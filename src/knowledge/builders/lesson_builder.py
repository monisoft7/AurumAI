from __future__ import annotations

import dataclasses
import hashlib
import shutil
import pandas as pd
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from knowledge.context.dxy import DXYContextConfig, DXYContextEnricher
from knowledge.context.yields import YieldContextConfig, YieldContextEnricher
from knowledge.events.base import MacroEvent, ReleaseCalendar
from knowledge.events.cpi import CPIEvent, DEFAULT_CPI_RELEASE_CALENDAR


DEFAULT_HORIZONS = (1, 5, 20)

# Correction 026: canonical enrichment defaults mirroring the runtime
# configuration (run.py DEFAULT_CONFIG) used by
# ``InferencePipeline._stage_build_lessons``.
DEFAULT_YIELD_DATA_PATH = Path("data/economic/DFII10.csv")
DEFAULT_DXY_DATA_PATH = Path("data/context/dxy/dxy.csv")
DEFAULT_CONTEXT_LOOKBACK_DAYS = 30


@dataclass(frozen=True)
class LessonBuilderConfig:
    event_data_path: Path = Path("data/economic/CPIAUCSL.csv")
    gold_path: Path = Path("data/history/gold/gold.csv")
    output_path: Path = Path("data/lessons/cpi_gold_lessons.csv")
    horizons: tuple[int, ...] = DEFAULT_HORIZONS
    min_abs_move_pct: float = 0.10
    release_calendar_path: str | None = None
    institutional_context: tuple[str, ...] = ("macro_regime",)


class LessonBuilder:
    """Canonical institutional LessonBuilder.

    Requires a release calendar. All lessons are anchored on the release
    timestamp, never on the reference-period Date.  This is the default
    path for production institutional pipelines.

    Raises ``ValueError`` if the release calendar is missing or if the
    event data lacks a ``release_timestamp`` column.
    """

    _is_institutional: bool = True

    def __init__(
        self,
        config: LessonBuilderConfig,
        event: MacroEvent | None = None,
    ):
        if config.release_calendar_path is None:
            raise ValueError(
                "release_calendar_path is required in LessonBuilderConfig "
                "for the canonical institutional LessonBuilder.  "
                "Use LegacyLessonBuilder for the non-institutional path."
            )
        self.config = config
        self._release_calendar = ReleaseCalendar.from_csv(config.release_calendar_path)
        self.event = event or CPIEvent(
            release_calendar_path=config.release_calendar_path
        )

    def build(self) -> pd.DataFrame:
        event_data = self.event.load_and_extract_with_calendar(
            self.config.event_data_path, self._release_calendar
        )
        gold = self._load_gold(self.config.gold_path)
        lessons = self._build_lessons(event_data, gold, self.config.horizons)
        return pd.DataFrame(lessons)

    def build_and_save(self) -> pd.DataFrame:
        lessons = self.build()
        self.config.output_path.parent.mkdir(parents=True, exist_ok=True)
        lessons.to_csv(self.config.output_path, index=False)
        return lessons

    def _load_gold(self, path: Path) -> pd.DataFrame:
        df = pd.read_csv(path)
        required = {"Date", "Close"}
        self._require_columns(df, required, path)

        df = df.copy()
        df["Date"] = pd.to_datetime(df["Date"], errors="raise")
        df["Close"] = pd.to_numeric(df["Close"], errors="raise")
        df = df.sort_values("Date").drop_duplicates("Date", keep="last")
        return df.reset_index(drop=True)

    def _build_lessons(
        self,
        event_data: pd.DataFrame,
        gold: pd.DataFrame,
        horizons: Iterable[int],
    ) -> list[dict[str, object]]:
        if "release_timestamp" not in event_data.columns:
            raise ValueError(
                "Institutional LessonBuilder requires a release_timestamp "
                "column in event data.  Use load_and_extract_with_calendar "
                "or use LegacyLessonBuilder for the non-institutional path."
            )

        lessons: list[dict[str, object]] = []
        gold_dates = gold["Date"]
        first_gold_date = gold_dates.iloc[0]
        source_sha256 = hashlib.sha256(
            self.config.event_data_path.read_bytes()
        ).hexdigest()

        for _, row in event_data.iterrows():
            release_ts = row["release_timestamp"]
            anchor_time = pd.Timestamp(release_ts).normalize()
            if anchor_time < first_gold_date:
                continue

            anchor_index = self._first_gold_index_on_or_after(
                gold_dates, anchor_time
            )
            if anchor_index is None:
                continue

            max_horizon = max(horizons)
            if anchor_index + max_horizon >= len(gold):
                continue

            anchor = gold.iloc[anchor_index]
            event_date = row["Date"].date().isoformat()
            anchor_date = anchor["Date"].date().isoformat()

            lesson: dict[str, Any] = {
                "lesson_id": f"{self.event.event_type}_GOLD_{event_date}",
                "lesson_version": self.event.lesson_version,
                "event_type": self.event.event_type,
                "event_date": event_date,
                "anchor_gold_date": anchor_date,
                "alignment_method": "first_gold_session_on_or_after_release_timestamp",
                "gold_close_at_event": round(float(anchor["Close"]), 6),
                "release_timestamp": str(release_ts),
                "source_artifact_path": str(self.config.event_data_path),
                "source_artifact_sha256": source_sha256,
            }
            lesson.update(self.event.build_lesson_fields(row, anchor_date))
            self._add_institutional_context(lesson, row)

            for horizon in horizons:
                future = gold.iloc[anchor_index + horizon]
                return_pct = self._pct_return(anchor["Close"], future["Close"])
                lesson[f"gold_close_t_plus_{horizon}d"] = round(float(future["Close"]), 6)
                lesson[f"gold_return_{horizon}d_pct"] = round(return_pct, 6)
                lesson[f"gold_direction_{horizon}d"] = self._direction(return_pct)

            lesson["primary_horizon_days"] = self._primary_horizon(lesson, horizons)
            lesson["lesson_text"] = self.event.lesson_text(lesson)
            lessons.append(lesson)

        return lessons

    def _add_institutional_context(
        self, lesson: dict[str, Any], row: pd.Series
    ) -> None:
        for ctx_col in self.config.institutional_context:
            if ctx_col in row.index:
                lesson[ctx_col] = str(row[ctx_col])

    def _first_gold_index_on_or_after(
        self,
        gold_dates: pd.Series,
        event_date: pd.Timestamp,
    ) -> int | None:
        positions = gold_dates.searchsorted(event_date, side="left")
        if positions >= len(gold_dates):
            return None
        return int(positions)

    def _primary_horizon(self, lesson: dict[str, object], horizons: Iterable[int]) -> int:
        return max(
            horizons,
            key=lambda horizon: abs(float(lesson[f"gold_return_{horizon}d_pct"])),
        )

    def _direction(self, return_pct: float) -> str:
        if return_pct > self.config.min_abs_move_pct:
            return "UP"
        if return_pct < -self.config.min_abs_move_pct:
            return "DOWN"
        return "FLAT"

    def _pct_return(self, start: float, end: float) -> float:
        if start == 0:
            raise ValueError("Cannot calculate return from a zero start price.")
        return ((float(end) - float(start)) / float(start)) * 100.0

    def _require_columns(self, df: pd.DataFrame, required: set[str], path: Path) -> None:
        missing = required.difference(df.columns)
        if missing:
            missing_text = ", ".join(sorted(missing))
            raise ValueError(f"{path} is missing required columns: {missing_text}")


# ---------------------------------------------------------------------------
# Correction 026: canonical enriched lesson artifact
# ---------------------------------------------------------------------------


def _register_macro_regime_extractor() -> None:
    """Idempotently register the existing global MacroRegimeFeatureExtractor.

    Mirrors ``stages._ensure_macro_regime_initialized``: the detector is fit
    once per process with the existing deterministic ``random_state=42`` and
    registered through the existing ``FeatureExtractionEngine.register_global``
    mechanism, so ``CPIEvent`` extraction attaches ``macro_regime`` to every
    event row before ``LessonBuilder`` copies it into the lesson.
    """
    from knowledge.features.engine import FeatureExtractionEngine
    from knowledge.features.extractors.macro_regime import (
        MacroRegimeFeatureExtractor,
    )
    from knowledge.regime.composite_score import CompositeScoreBuilder
    from knowledge.regime.macro_regime_detector import MacroRegimeDetector

    if any(
        isinstance(extractor, MacroRegimeFeatureExtractor)
        for extractor in FeatureExtractionEngine._global_extractors
    ):
        return

    composite_data = CompositeScoreBuilder().build()
    detector = MacroRegimeDetector(random_state=42).fit(composite_data)
    FeatureExtractionEngine.register_global(MacroRegimeFeatureExtractor(detector))


def build_canonical_lesson_artifact(
    config: LessonBuilderConfig,
    yield_data_path: str | Path | None = None,
    dxy_data_path: str | Path | None = None,
    yield_context_lookback_days: int = DEFAULT_CONTEXT_LOOKBACK_DAYS,
    dxy_context_lookback_days: int = DEFAULT_CONTEXT_LOOKBACK_DAYS,
) -> pd.DataFrame:
    """Build the canonical lesson artifact with full context enrichment.

    Correction 026: the canonical ``data/lessons/cpi_gold_lessons.csv``
    regenerates through the exact same enrichment composition already proven
    in ``InferencePipeline._stage_build_lessons``:

        LessonBuilder
        -> YieldContextEnricher (us10y_level / us10y_trend)
        -> DXYContextEnricher (dxy_level / dxy_trend)

    with the existing global ``MacroRegimeFeatureExtractor`` registered so
    each lesson row also carries ``macro_regime``.  The enrichers are invoked
    in their output-path-safe form (explicit ``output_path``), never with the
    destructive in-place default.  Every reused component is existing; no
    provider, subsystem, aggregation, or lesson identity semantics change.
    """
    _register_macro_regime_extractor()

    lessons = LessonBuilder(config).build_and_save()
    output = Path(config.output_path)

    if yield_data_path is not None:
        lessons = YieldContextEnricher(
            YieldContextConfig(
                yield_path=Path(yield_data_path),
                lookback_days=yield_context_lookback_days,
            )
        ).enrich_csv(output, output)
    if dxy_data_path is not None:
        lessons = DXYContextEnricher(
            DXYContextConfig(
                dxy_path=Path(dxy_data_path),
                lookback_days=dxy_context_lookback_days,
            )
        ).enrich_csv(output, output)

    return lessons


def compare_lesson_identity_sets(
    current_path: str | Path,
    candidate_path: str | Path,
) -> dict[str, Any]:
    """Compare lesson identity sets between two artifacts.

    Identities are ``(lesson_id, event_date)``; per-id event dates must also
    be unchanged, since ``event_date`` is part of the lesson identity.
    """
    def load(path: Path) -> pd.DataFrame:
        df = pd.read_csv(path)
        required = {"lesson_id", "event_date"}
        missing = required.difference(df.columns)
        if missing:
            raise ValueError(
                f"{path} is missing identity columns: {sorted(missing)}"
            )
        return df

    current = load(Path(current_path))
    candidate = load(Path(candidate_path))

    current_map: dict[str, str] = dict(
        zip(current["lesson_id"], current["event_date"].astype(str))
    )
    candidate_map: dict[str, str] = dict(
        zip(candidate["lesson_id"], candidate["event_date"].astype(str))
    )
    current_ids = set(current_map)
    candidate_ids = set(candidate_map)

    added = sorted(candidate_ids - current_ids)
    removed = sorted(current_ids - candidate_ids)
    unchanged = sorted(current_ids & candidate_ids)
    date_drift = sorted(
        lesson_id
        for lesson_id in unchanged
        if current_map[lesson_id] != candidate_map[lesson_id]
    )

    return {
        "current_count": len(current_ids),
        "candidate_count": len(candidate_ids),
        "added_lesson_ids": added,
        "removed_lesson_ids": removed,
        "unchanged_lesson_ids": unchanged,
        "event_date_drift_lesson_ids": date_drift,
        "identity_set_match": not added and not removed and not date_drift,
    }


def replace_canonical_after_gate(
    current_path: str | Path,
    candidate_path: str | Path,
) -> dict[str, Any]:
    """Replace the canonical artifact only when identity sets match exactly.

    Correction 026 safety gate: the enriched candidate may only overwrite the
    canonical ``cpi_gold_lessons.csv`` when the ``(lesson_id, event_date)``
    identity sets are identical.  Any added/removed lesson or per-id event
    date drift blocks replacement -- canonical history is never silently
    rewritten.
    """
    report = compare_lesson_identity_sets(current_path, candidate_path)
    current = Path(current_path)
    candidate = Path(candidate_path)
    report["replaced"] = False
    if report["identity_set_match"]:
        shutil.copy2(candidate, current)
        report["replaced"] = True
    return report


# ---------------------------------------------------------------------------
# Legacy (non-institutional) path
# ---------------------------------------------------------------------------


class LegacyLessonBuilder(LessonBuilder):
    """Non-institutional legacy lesson builder.

    Uses the reference-period ``Date`` column for gold-session anchoring
    and does **not** require a release calendar or a ``release_timestamp``
    column.

    Intended for backward-compatibility verification and migration testing
    only.  **Never use in production institutional pipelines.**
    """

    _is_institutional: bool = False

    def __init__(
        self,
        config: LessonBuilderConfig,
        event: MacroEvent | None = None,
    ):
        self.config = config
        self.event = event or CPIEvent()
        self._release_calendar = None

    def build(self) -> pd.DataFrame:
        event_data = self.event.load_and_extract(self.config.event_data_path)
        gold = self._load_gold(self.config.gold_path)
        lessons = self._build_lessons_legacy(event_data, gold, self.config.horizons)
        return pd.DataFrame(lessons)

    def build_and_save(self) -> pd.DataFrame:
        lessons = self.build()
        self.config.output_path.parent.mkdir(parents=True, exist_ok=True)
        lessons.to_csv(self.config.output_path, index=False)
        return lessons

    def _build_lessons_legacy(
        self,
        event_data: pd.DataFrame,
        gold: pd.DataFrame,
        horizons: Iterable[int],
    ) -> list[dict[str, object]]:
        lessons: list[dict[str, object]] = []
        gold_dates = gold["Date"]
        first_gold_date = gold_dates.iloc[0]

        for _, row in event_data.iterrows():
            if row["Date"] < first_gold_date:
                continue

            anchor_index = self._first_gold_index_on_or_after(
                gold_dates, row["Date"]
            )
            if anchor_index is None:
                continue

            max_horizon = max(horizons)
            if anchor_index + max_horizon >= len(gold):
                continue

            anchor = gold.iloc[anchor_index]
            event_date = row["Date"].date().isoformat()
            anchor_date = anchor["Date"].date().isoformat()

            lesson: dict[str, Any] = {
                "lesson_id": f"{self.event.event_type}_GOLD_{event_date}",
                "lesson_version": self.event.lesson_version,
                "event_type": self.event.event_type,
                "event_date": event_date,
                "anchor_gold_date": anchor_date,
                "alignment_method": "first_gold_session_on_or_after_event_date",
                "gold_close_at_event": round(float(anchor["Close"]), 6),
            }
            lesson.update(self.event.build_lesson_fields(row, anchor_date))
            self._add_institutional_context(lesson, row)

            for horizon in horizons:
                future = gold.iloc[anchor_index + horizon]
                return_pct = self._pct_return(anchor["Close"], future["Close"])
                lesson[f"gold_close_t_plus_{horizon}d"] = round(float(future["Close"]), 6)
                lesson[f"gold_return_{horizon}d_pct"] = round(return_pct, 6)
                lesson[f"gold_direction_{horizon}d"] = self._direction(return_pct)

            lesson["primary_horizon_days"] = self._primary_horizon(lesson, horizons)
            lesson["lesson_text"] = self.event.lesson_text(lesson)
            lessons.append(lesson)

        return lessons


if __name__ == "__main__":

    import tempfile

    config = LessonBuilderConfig(
        release_calendar_path=DEFAULT_CPI_RELEASE_CALENDAR,
    )
    with tempfile.TemporaryDirectory() as tmp:
        candidate_path = Path(tmp) / "cpi_gold_lessons_enriched.csv"
        candidate_config = dataclasses.replace(config, output_path=candidate_path)
        enriched = build_canonical_lesson_artifact(
            candidate_config,
            yield_data_path=DEFAULT_YIELD_DATA_PATH,
            dxy_data_path=DEFAULT_DXY_DATA_PATH,
        )
        print(enriched.head())
        print()
        print("Lessons:", len(enriched))

        gate = replace_canonical_after_gate(
            config.output_path, candidate_path
        )
        print()
        print("Canonical replacement gate:")
        print("  current rows:", gate["current_count"])
        print("  candidate rows:", gate["candidate_count"])
        print("  added lesson_ids:", gate["added_lesson_ids"])
        print("  removed lesson_ids:", gate["removed_lesson_ids"])
        print("  event_date drift:", gate["event_date_drift_lesson_ids"])
        if gate["replaced"]:
            print("  -> candidate adopted (identity sets identical)")
        else:
            print("  -> NOT replaced: identity drift blocks replacement")
