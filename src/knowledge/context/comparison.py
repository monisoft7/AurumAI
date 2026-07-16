from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class ContextComparisonConfig:
    baseline_path: Path
    contextual_path: Path
    output_path: Path | None = None
    base_condition_columns: tuple[str, ...] = ("cpi_pressure",)
    context_condition_columns: tuple[str, ...] = ("us10y_trend",)
    min_context_samples: int = 3
    min_confidence_delta: float = 0.05


class ContextComparisonReport:
    """Compare single-factor knowledge with context-conditioned knowledge."""

    def __init__(self, config: ContextComparisonConfig):
        self.config = config

    def build(self) -> dict[str, Any]:
        baseline = self._load_summary(self.config.baseline_path)
        contextual = self._load_summary(self.config.contextual_path)
        baseline_index = {
            self._baseline_key(record): record
            for record in baseline.get("records", [])
        }

        comparisons = []
        for contextual_record in contextual.get("records", []):
            key = self._contextual_base_key(contextual_record)
            baseline_record = baseline_index.get(key)
            if baseline_record is None:
                comparisons.append(
                    self._missing_baseline_comparison(contextual_record)
                )
                continue
            comparisons.append(
                self._compare_records(baseline_record, contextual_record)
            )

        decision_counts: dict[str, int] = {}
        for comparison in comparisons:
            decision = comparison["decision"]
            decision_counts[decision] = decision_counts.get(decision, 0) + 1

        report = {
            "report_type": "context_comparison",
            "baseline_knowledge_version": baseline.get("knowledge_version"),
            "contextual_knowledge_version": contextual.get("knowledge_version"),
            "event_type": contextual.get("event_type", baseline.get("event_type")),
            "asset": contextual.get("asset", baseline.get("asset")),
            "base_condition_columns": list(self.config.base_condition_columns),
            "context_condition_columns": list(self.config.context_condition_columns),
            "comparison_count": len(comparisons),
            "decision_counts": decision_counts,
            "overall_assessment": self._overall_assessment(decision_counts),
            "comparisons": comparisons,
        }
        return report

    def build_and_save(self) -> dict[str, Any]:
        report = self.build()
        if self.config.output_path is not None:
            self.config.output_path.parent.mkdir(parents=True, exist_ok=True)
            self.config.output_path.write_text(
                json.dumps(report, indent=2, sort_keys=True)
            )
        return report

    def _load_summary(self, path: Path) -> dict[str, Any]:
        payload = json.loads(path.read_text())
        if "records" not in payload:
            raise ValueError(f"{path} is missing required key: records")
        return payload

    def _baseline_key(self, record: dict[str, Any]) -> tuple[Any, ...]:
        return (
            record.get("event_type"),
            record.get("asset"),
            record.get("horizon_days"),
            *self._base_condition_values(record),
        )

    def _contextual_base_key(self, record: dict[str, Any]) -> tuple[Any, ...]:
        return self._baseline_key(record)

    def _base_condition_values(self, record: dict[str, Any]) -> tuple[Any, ...]:
        condition = record.get("condition", {})
        return tuple(condition.get(column) for column in self.config.base_condition_columns)

    def _context_condition_values(self, record: dict[str, Any]) -> dict[str, Any]:
        condition = record.get("condition", {})
        return {
            column: condition.get(column)
            for column in self.config.context_condition_columns
        }

    def _compare_records(
        self,
        baseline: dict[str, Any],
        contextual: dict[str, Any],
    ) -> dict[str, Any]:
        confidence_delta = round(
            float(contextual.get("confidence", 0.0))
            - float(baseline.get("confidence", 0.0)),
            6,
        )
        sample_ratio = self._sample_ratio(
            int(contextual.get("sample_count", 0)),
            int(baseline.get("sample_count", 0)),
        )
        avg_return_delta = round(
            float(contextual.get("average_return_pct", 0.0))
            - float(baseline.get("average_return_pct", 0.0)),
            6,
        )
        decision = self._decision(contextual, confidence_delta)

        return {
            "baseline_knowledge_id": baseline.get("knowledge_id"),
            "contextual_knowledge_id": contextual.get("knowledge_id"),
            "horizon_days": contextual.get("horizon_days"),
            "base_condition": {
                column: contextual.get("condition", {}).get(column)
                for column in self.config.base_condition_columns
            },
            "context_condition": self._context_condition_values(contextual),
            "baseline_sample_count": baseline.get("sample_count"),
            "contextual_sample_count": contextual.get("sample_count"),
            "sample_ratio": sample_ratio,
            "baseline_confidence": baseline.get("confidence"),
            "contextual_confidence": contextual.get("confidence"),
            "confidence_delta": confidence_delta,
            "baseline_bias": baseline.get("bias"),
            "contextual_bias": contextual.get("bias"),
            "baseline_average_return_pct": baseline.get("average_return_pct"),
            "contextual_average_return_pct": contextual.get("average_return_pct"),
            "average_return_delta_pct": avg_return_delta,
            "decision": decision,
            "explanation": self._explanation(
                contextual,
                confidence_delta,
                sample_ratio,
                decision,
            ),
        }

    def _missing_baseline_comparison(
        self,
        contextual: dict[str, Any],
    ) -> dict[str, Any]:
        return {
            "baseline_knowledge_id": None,
            "contextual_knowledge_id": contextual.get("knowledge_id"),
            "horizon_days": contextual.get("horizon_days"),
            "base_condition": {
                column: contextual.get("condition", {}).get(column)
                for column in self.config.base_condition_columns
            },
            "context_condition": self._context_condition_values(contextual),
            "decision": "missing_baseline",
            "explanation": "No matching single-factor baseline record was found.",
        }

    def _decision(
        self,
        contextual: dict[str, Any],
        confidence_delta: float,
    ) -> str:
        if int(contextual.get("sample_count", 0)) < self.config.min_context_samples:
            return "context_fragments_evidence"
        if confidence_delta >= self.config.min_confidence_delta:
            return "context_improves_explanation"
        if confidence_delta <= -self.config.min_confidence_delta:
            return "context_weakens_explanation"
        return "context_neutral"

    def _sample_ratio(self, contextual_count: int, baseline_count: int) -> float:
        if baseline_count == 0:
            return 0.0
        return round(contextual_count / baseline_count, 6)

    def _overall_assessment(self, decision_counts: dict[str, int]) -> str:
        if not decision_counts:
            return "no_context_comparisons"
        if decision_counts.get("context_improves_explanation", 0) > decision_counts.get(
            "context_weakens_explanation", 0
        ):
            return "context_adds_value"
        if decision_counts.get("context_fragments_evidence", 0) >= max(
            1, sum(decision_counts.values()) / 2
        ):
            return "context_too_fragmented"
        if decision_counts.get("context_weakens_explanation", 0) > decision_counts.get(
            "context_improves_explanation", 0
        ):
            return "context_not_helpful_yet"
        return "context_mixed_or_neutral"

    def _explanation(
        self,
        contextual: dict[str, Any],
        confidence_delta: float,
        sample_ratio: float,
        decision: str,
    ) -> str:
        return (
            f"Context record {contextual.get('knowledge_id')} has decision "
            f"{decision}, confidence delta {confidence_delta}, and sample ratio "
            f"{sample_ratio} versus its single-factor baseline."
        )
