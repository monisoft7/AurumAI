from __future__ import annotations

import datetime
import re
from dataclasses import dataclass, field
from typing import Any

from .models import EventRunResult, SimulationReport


# ---------------------------------------------------------------------------
# Helper to parse stage id from error strings like "build_feature_pipeline: ..."
# ---------------------------------------------------------------------------

_STAGE_ERROR_RE = re.compile(r"^([a-zA-Z_][a-zA-Z0-9_]*):")


def _parse_stage_id(error: str) -> str:
    m = _STAGE_ERROR_RE.match(error)
    return m.group(1) if m else "unknown"


# ---------------------------------------------------------------------------
#  Simple classification helpers
# ---------------------------------------------------------------------------

_POSITIVE_DECISIONS = frozenset({"POSITIVE", "STRONG_POSITIVE", "LONG", "STRONG_LONG"})

_RISK_OVERRIDE_ACTIONS = frozenset({"halt", "scale_down", "reject"})


def _is_positive_decision(decision: str | None) -> bool:
    return decision is not None and decision.upper() in _POSITIVE_DECISIONS


def _is_risk_override(decision: str | None, risk_action: str | None) -> bool:
    if not risk_action:
        return False
    return risk_action.lower() in _RISK_OVERRIDE_ACTIONS and _is_positive_decision(decision)


# ---------------------------------------------------------------------------
#  Output model
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ValidationAccuracy:
    forecast_risk_agreement_rate: float  # Q1
    risk_override_rate: float            # Q2
    validation_pass_rate: float
    pipeline_success_rate: float


@dataclass(frozen=True)
class ConfidenceDistribution:
    by_event_type: dict[str, float]  # avg forecast_confidence per event type  # Q3
    overall_avg: float
    highest_event: str | None
    lowest_event: str | None


@dataclass(frozen=True)
class ReasoningDistribution:
    by_event_type: dict[str, float]  # validation pass rate per event type  # Q4
    overall_pass_rate: float
    weakest_events: list[str]


@dataclass(frozen=True)
class RiskDistribution:
    actions: dict[str, int]                     # Q7
    overrides_by_event: dict[str, int]          # Q2 detail
    total_overrides: int
    avg_var_95: float | None
    avg_cvar_95: float | None


@dataclass(frozen=True)
class BottleneckAnalysis:
    stage_failures: dict[str, int]    # Q5
    total_failures: int
    most_failed_stage: str | None
    failure_rate: float


@dataclass(frozen=True)
class ModelEntry:
    runs: int
    success_rate: float
    avg_confidence: float | None
    validation_pass_rate: float | None


@dataclass(frozen=True)
class ModelPerformance:
    by_model: dict[str, ModelEntry]    # Q6
    best_model: str | None


@dataclass(frozen=True)
class ComponentContribution:
    """Aggregated component-level contribution indicators across all events."""
    total_execution_time_ms: float
    total_cache_hits: int
    avg_checkpoints_per_event: float
    avg_execution_time_by_event_type: dict[str, float]
    cache_hit_ratio_by_event_type: dict[str, float]


@dataclass(frozen=True)
class InstitutionalValidationReport:
    timestamp: str
    simulation_timestamp: str

    # eight questions
    accuracy: ValidationAccuracy
    confidence: ConfidenceDistribution
    reasoning: ReasoningDistribution
    risk: RiskDistribution
    bottlenecks: BottleneckAnalysis
    models: ModelPerformance
    contributions: ComponentContribution

    # cross-cutting summaries
    recommendations: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
#  Validation Engine
# ---------------------------------------------------------------------------


class InstitutionalValidator:
    """Produces an InstitutionalValidationReport from a SimulationReport."""

    def validate(self, report: SimulationReport) -> InstitutionalValidationReport:
        results = report.results
        if not results:
            return self._empty_report(report)

        # Q1 + Q2: forecast-risk agreement & overrides
        agree_count = 0
        override_count = 0
        overrides_by_event: dict[str, int] = {}
        total_decision_pairs = 0

        for r in results:
            if r.decision and r.risk_decision:
                total_decision_pairs += 1
                if r.decision.upper() == r.risk_decision.upper():
                    agree_count += 1
            if _is_risk_override(r.decision, r.risk_gate_action):
                override_count += 1
                overrides_by_event[r.event_type] = overrides_by_event.get(r.event_type, 0) + 1

        # Q3: confidence by event type
        conf_by_et: dict[str, list[float]] = {}
        for r in results:
            if r.forecast_confidence is not None:
                conf_by_et.setdefault(r.event_type, []).append(r.forecast_confidence)

        conf_data: dict[str, float] = {}
        overall_conf_sum = 0.0
        overall_conf_n = 0
        for et, vals in conf_by_et.items():
            avg = sum(vals) / len(vals)
            conf_data[et] = round(avg, 6)
            overall_conf_sum += sum(vals)
            overall_conf_n += len(vals)

        overall_avg_conf = round(overall_conf_sum / overall_conf_n, 6) if overall_conf_n else None
        highest_event = max(conf_data, key=conf_data.get) if conf_data else None
        lowest_event = min(conf_data, key=conf_data.get) if conf_data else None

        # Q4: reasoning quality (validation pass rate) by event type
        valid_by_et: dict[str, list[bool]] = {}
        for r in results:
            if r.validation_passed is not None:
                valid_by_et.setdefault(r.event_type, []).append(r.validation_passed)

        reason_data: dict[str, float] = {}
        overall_valid_n = 0
        overall_valid_pass = 0
        for et, vals in valid_by_et.items():
            n = len(vals)
            passed = sum(1 for v in vals if v)
            rate = passed / n if n else 0.0
            reason_data[et] = round(rate, 6)
            overall_valid_n += n
            overall_valid_pass += passed

        overall_pass_rate = round(overall_valid_pass / overall_valid_n, 6) if overall_valid_n else 0.0

        # Sort events by pass rate ascending to find weakest (below overall average)
        sorted_reason = sorted(reason_data.items(), key=lambda x: x[1])
        weakest = [et for et, rate in sorted_reason if rate < overall_pass_rate]

        # Q5: pipeline stage failures
        stage_fail_counts: dict[str, int] = {}
        for r in results:
            for err in r.errors:
                sid = _parse_stage_id(err)
                stage_fail_counts[sid] = stage_fail_counts.get(sid, 0) + 1

        total_failures = sum(stage_fail_counts.values())
        most_failed_stage = max(stage_fail_counts, key=stage_fail_counts.get) if stage_fail_counts else None
        failure_rate = total_failures / len(results) if results else 0.0

        # Q6: model performance
        model_data: dict[str, dict[str, Any]] = {}
        for r in results:
            mdl = r.forecast_model or "unknown"
            entry = model_data.setdefault(mdl, {"runs": 0, "successes": 0, "conf": [], "valid_pass": [], "valid_total": 0})
            entry["runs"] += 1
            if r.success:
                entry["successes"] += 1
            if r.forecast_confidence is not None:
                entry["conf"].append(r.forecast_confidence)
            if r.validation_passed is not None:
                entry["valid_pass"].append(1 if r.validation_passed else 0)
                entry["valid_total"] += 1

        model_perf: dict[str, ModelEntry] = {}
        best_model: str | None = None
        best_score = -1.0
        for mdl, d in model_data.items():
            sr = d["successes"] / d["runs"] if d["runs"] else 0.0
            ac = sum(d["conf"]) / len(d["conf"]) if d["conf"] else None
            vpr = sum(d["valid_pass"]) / d["valid_total"] if d["valid_total"] else None
            model_perf[mdl] = ModelEntry(
                runs=d["runs"],
                success_rate=round(sr, 6),
                avg_confidence=round(ac, 6) if ac is not None else None,
                validation_pass_rate=round(vpr, 6) if vpr is not None else None,
            )
            # Composite score: success_rate * (avg_confidence or 0.5)
            score = sr * (ac if ac is not None else 0.5)
            if score > best_score:
                best_score = score
                best_model = mdl

        # Q7: risk distribution
        risk_actions: dict[str, int] = {}
        for r in results:
            act = r.risk_gate_action or "none"
            risk_actions[act] = risk_actions.get(act, 0) + 1

        risk_counts = list(r.risk_gate_score for r in results if r.risk_gate_score is not None)
        avg_var = report.risk.avg_var_95
        avg_cvar = report.risk.avg_cvar_95

        # Q8: component contributions
        total_exec = sum(r.execution_time_ms for r in results)
        total_cache = sum(r.cache_hits for r in results)
        exec_by_et: dict[str, list[float]] = {}
        cache_by_et: dict[str, list[int]] = {}
        event_counts: dict[str, int] = {}
        for r in results:
            exec_by_et.setdefault(r.event_type, []).append(r.execution_time_ms)
            cache_by_et.setdefault(r.event_type, []).append(r.cache_hits)
            event_counts[r.event_type] = event_counts.get(r.event_type, 0) + 1

        avg_exec_et = {
            et: round(sum(v) / len(v), 2)
            for et, v in exec_by_et.items()
        }
        cache_ratio_et = {
            et: round(sum(cache_by_et[et]) / event_counts[et], 4)
            for et in event_counts
        }

        contributions = ComponentContribution(
            total_execution_time_ms=round(total_exec, 2),
            total_cache_hits=total_cache,
            avg_checkpoints_per_event=round(report.checkpoints_total / len(results), 4) if results else 0.0,
            avg_execution_time_by_event_type=avg_exec_et,
            cache_hit_ratio_by_event_type=cache_ratio_et,
        )

        accuracy = ValidationAccuracy(
            forecast_risk_agreement_rate=round(agree_count / total_decision_pairs, 6) if total_decision_pairs else 0.0,
            risk_override_rate=round(override_count / len(results), 6) if results else 0.0,
            validation_pass_rate=overall_pass_rate,
            pipeline_success_rate=round(report.successful_runs / report.total_events, 6) if report.total_events else 0.0,
        )

        confidence = ConfidenceDistribution(
            by_event_type=conf_data,
            overall_avg=overall_avg_conf if overall_avg_conf is not None else 0.0,
            highest_event=highest_event,
            lowest_event=lowest_event,
        )

        reasoning = ReasoningDistribution(
            by_event_type=reason_data,
            overall_pass_rate=overall_pass_rate,
            weakest_events=weakest,
        )

        risk = RiskDistribution(
            actions=risk_actions,
            overrides_by_event=overrides_by_event,
            total_overrides=override_count,
            avg_var_95=avg_var,
            avg_cvar_95=avg_cvar,
        )

        bottlenecks = BottleneckAnalysis(
            stage_failures=stage_fail_counts,
            total_failures=total_failures,
            most_failed_stage=most_failed_stage,
            failure_rate=round(failure_rate, 6),
        )

        models = ModelPerformance(
            by_model=model_perf,
            best_model=best_model,
        )

        # Generate recommendations based on findings
        recommendations = self._generate_recommendations(
            accuracy, confidence, reasoning, risk, bottlenecks, models,
        )

        return InstitutionalValidationReport(
            timestamp=datetime.datetime.now(datetime.timezone.utc).isoformat(),
            simulation_timestamp=report.timestamp,
            accuracy=accuracy,
            confidence=confidence,
            reasoning=reasoning,
            risk=risk,
            bottlenecks=bottlenecks,
            models=models,
            contributions=contributions,
            recommendations=recommendations,
            metadata={
                "total_events": report.total_events,
                "event_types": list(report.events_processed),
            },
        )

    # ------------------------------------------------------------------
    #  heuristics for recommendations
    # ------------------------------------------------------------------

    @staticmethod
    def _generate_recommendations(
        accuracy: ValidationAccuracy,
        confidence: ConfidenceDistribution,
        reasoning: ReasoningDistribution,
        risk: RiskDistribution,
        bottlenecks: BottleneckAnalysis,
        models: ModelPerformance,
    ) -> list[str]:
        recs: list[str] = []

        if accuracy.forecast_risk_agreement_rate < 0.5:
            recs.append("Low forecast-risk agreement — consider recalibrating forecast vs risk decision boundaries")
        if accuracy.risk_override_rate > 0.3:
            recs.append(f"Risk override rate is {accuracy.risk_override_rate:.1%} — review risk gate thresholds for false positives")
        if accuracy.validation_pass_rate < 0.7:
            recs.append(f"Validation pass rate is {accuracy.validation_pass_rate:.1%} — investigate forecast validation criteria")
        if accuracy.pipeline_success_rate < 0.8:
            recs.append(f"Pipeline success rate is {accuracy.pipeline_success_rate:.1%} — check for systemic execution failures")

        if reasoning.weakest_events:
            recs.append(f"Weakest reasoning in: {', '.join(reasoning.weakest_events)} — review feature quality for these types")

        if bottlenecks.most_failed_stage:
            recs.append(f"Most frequent pipeline failure at stage '{bottlenecks.most_failed_stage}' — investigate stability")

        if risk.total_overrides > 0:
            recs.append(f"{risk.total_overrides} risk overrides detected — verify risk model calibration")

        has_issues = (
            accuracy.forecast_risk_agreement_rate < 0.5
            or accuracy.risk_override_rate > 0.3
            or accuracy.validation_pass_rate < 0.7
            or accuracy.pipeline_success_rate < 0.8
            or bool(reasoning.weakest_events)
            or bottlenecks.most_failed_stage is not None
            or risk.total_overrides > 0
        )

        if not has_issues:
            recs.append("No critical issues detected — system appears healthy")

        return recs

    # ------------------------------------------------------------------
    #  empty report helper
    # ------------------------------------------------------------------

    @staticmethod
    def _empty_report(report: SimulationReport) -> InstitutionalValidationReport:
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        return InstitutionalValidationReport(
            timestamp=now,
            simulation_timestamp=report.timestamp,
            accuracy=ValidationAccuracy(0.0, 0.0, 0.0, 0.0),
            confidence=ConfidenceDistribution({}, 0.0, None, None),
            reasoning=ReasoningDistribution({}, 0.0, []),
            risk=RiskDistribution({}, {}, 0, None, None),
            bottlenecks=BottleneckAnalysis({}, 0, None, 0.0),
            models=ModelPerformance({}, None),
            contributions=ComponentContribution(0.0, 0, 0.0, {}, {}),
            recommendations=["No simulation data available for validation"],
            metadata={"total_events": 0, "event_types": []},
        )
