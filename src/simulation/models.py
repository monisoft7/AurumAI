from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class EconomicReturnStats:
    """Economic performance for a subset of decisions (e.g. a single decision type)."""
    count: int
    correct_count: int
    incorrect_count: int
    total_return_pct: float
    mean_return_pct: float | None = None
    min_return_pct: float | None = None
    max_return_pct: float | None = None


@dataclass(frozen=True)
class EconomicSummary:
    """Economic value metrics derived from scored EventRunResult objects.

    All metrics assume a normalized position size of 1.
    No leverage, commissions, slippage, or execution costs.
    """

    total_scored: int
    correct_count: int
    incorrect_count: int
    avg_return_correct_pct: float | None = None
    avg_return_incorrect_pct: float | None = None
    expectancy_pct: float | None = None
    profit_factor: float | None = None
    payoff_ratio: float | None = None
    max_consecutive_wins: int = 0
    max_consecutive_losses: int = 0
    return_min_pct: float | None = None
    return_median_pct: float | None = None
    return_mean_pct: float | None = None
    return_max_pct: float | None = None
    return_by_decision_type: dict[str, EconomicReturnStats] | None = None
    positive_expected_value: bool | None = None

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "total_scored": self.total_scored,
            "correct_count": self.correct_count,
            "incorrect_count": self.incorrect_count,
        }
        for fld in (
            "avg_return_correct_pct", "avg_return_incorrect_pct",
            "expectancy_pct", "profit_factor", "payoff_ratio",
            "return_min_pct", "return_median_pct", "return_mean_pct",
            "return_max_pct",
        ):
            val = getattr(self, fld, None)
            if val is not None:
                d[fld] = round(val, 6) if isinstance(val, float) else val
        d["max_consecutive_wins"] = self.max_consecutive_wins
        d["max_consecutive_losses"] = self.max_consecutive_losses
        if self.return_by_decision_type:
            d["return_by_decision_type"] = {
                k: {
                    "count": v.count,
                    "correct_count": v.correct_count,
                    "incorrect_count": v.incorrect_count,
                    "total_return_pct": round(v.total_return_pct, 6),
                    "mean_return_pct": round(v.mean_return_pct, 6) if v.mean_return_pct is not None else None,
                }
                for k, v in self.return_by_decision_type.items()
            }
        if self.positive_expected_value is not None:
            d["positive_expected_value"] = self.positive_expected_value
        return d


@dataclass(frozen=True)
class EventRunResult:
    event_type: str
    event_date_min: str
    event_date_max: str
    event_count: int
    success: bool
    execution_time_ms: float
    cache_hits: int
    checkpoints_used: int
    decision: str | None = None
    risk_decision: str | None = None
    forecast_model: str | None = None
    forecast_confidence: float | None = None
    validation_passed: bool | None = None
    validation_metrics: dict[str, float] | None = None
    var_95: float | None = None
    cvar_95: float | None = None
    tail_index: float | None = None
    position_scaling: float | None = None
    risk_gate_action: str | None = None
    risk_gate_score: float | None = None
    decision_correct: bool | None = None
    decision_actual_return_pct: float | None = None
    attribution: dict[str, float] = field(default_factory=dict)
    error: str | None = None
    errors: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "event_type": self.event_type,
            "event_date_min": self.event_date_min,
            "event_date_max": self.event_date_max,
            "event_count": self.event_count,
            "success": self.success,
            "execution_time_ms": round(self.execution_time_ms, 2),
            "cache_hits": self.cache_hits,
            "checkpoints_used": self.checkpoints_used,
        }
        for fld in (
            "decision", "risk_decision", "forecast_model",
            "forecast_confidence", "validation_passed",
            "var_95", "cvar_95", "tail_index", "position_scaling",
            "risk_gate_action", "risk_gate_score", "error",
            "decision_correct", "decision_actual_return_pct",
        ):
            val = getattr(self, fld, None)
            if val is not None:
                d[fld] = val
        if self.validation_metrics:
            d["validation_metrics"] = dict(self.validation_metrics)
        if self.attribution:
            d["attribution"] = dict(self.attribution)
        return d


@dataclass(frozen=True)
class ForecastAccuracySummary:
    total_forecasts: int
    passed_validations: int
    failed_validations: int
    avg_confidence: float | None = None
    models_used: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_forecasts": self.total_forecasts,
            "passed_validations": self.passed_validations,
            "failed_validations": self.failed_validations,
            "avg_confidence": self.avg_confidence,
            "models_used": list(self.models_used),
        }


@dataclass(frozen=True)
class RiskSummary:
    total_evaluations: int
    actions: dict[str, int] = field(default_factory=dict)
    avg_var_95: float | None = None
    avg_cvar_95: float | None = None
    avg_tail_index: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_evaluations": self.total_evaluations,
            "actions": dict(self.actions),
            "avg_var_95": round(self.avg_var_95, 6) if self.avg_var_95 is not None else None,
            "avg_cvar_95": round(self.avg_cvar_95, 6) if self.avg_cvar_95 is not None else None,
            "avg_tail_index": round(self.avg_tail_index, 4) if self.avg_tail_index is not None else None,
        }


@dataclass(frozen=True)
class OOSSummary:
    """Out-of-sample validation summary — pure aggregation of
    per-event correctness into institutional metrics.

    All metrics are derived from ``decision_correct``,
    ``decision_actual_return_pct``, ``forecast_confidence``, and
    ``decision`` fields on |EventRunResult|.
    """

    total_events: int
    scored_events: int
    abstained_events: int
    directional_accuracy: float | None = None
    macro_precision: float | None = None
    macro_recall: float | None = None
    precision_up: float | None = None
    precision_down: float | None = None
    precision_flat: float | None = None
    recall_up: float | None = None
    recall_down: float | None = None
    recall_flat: float | None = None
    coverage: float | None = None
    abstention_rate: float | None = None
    strong_error_rate: float | None = None
    ece: float | None = None
    decision_distribution: dict[str, int] | None = None

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "total_events": self.total_events,
            "scored_events": self.scored_events,
            "abstained_events": self.abstained_events,
        }
        for fld in (
            "directional_accuracy", "macro_precision", "macro_recall",
            "precision_up", "precision_down", "precision_flat",
            "recall_up", "recall_down", "recall_flat",
            "coverage", "abstention_rate", "strong_error_rate", "ece",
        ):
            val = getattr(self, fld, None)
            if val is not None:
                d[fld] = round(val, 6) if isinstance(val, float) else val
        if self.decision_distribution:
            d["decision_distribution"] = dict(self.decision_distribution)
        return d


@dataclass(frozen=True)
class SimulationReport:
    timestamp: str
    data_dir: str
    gold_data_path: str
    total_events: int
    successful_runs: int
    failed_runs: int
    avg_execution_time_ms: float
    cache_hit_ratio: float
    checkpoints_total: int
    events_processed: tuple[str, ...]
    results: tuple[EventRunResult, ...]
    forecast_accuracy: ForecastAccuracySummary
    risk: RiskSummary
    errors: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "data_dir": self.data_dir,
            "gold_data_path": self.gold_data_path,
            "total_events": self.total_events,
            "successful_runs": self.successful_runs,
            "failed_runs": self.failed_runs,
            "avg_execution_time_ms": round(self.avg_execution_time_ms, 2),
            "cache_hit_ratio": round(self.cache_hit_ratio, 4),
            "checkpoints_total": self.checkpoints_total,
            "events_processed": list(self.events_processed),
            "event_details": [r.to_dict() for r in self.results],
            "forecast_accuracy": self.forecast_accuracy.to_dict(),
            "risk": self.risk.to_dict(),
            "errors": list(self.errors),
        }
