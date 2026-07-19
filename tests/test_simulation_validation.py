"""Tests for the InstitutionalValidator and InstitutionalValidationReport."""

from __future__ import annotations

from simulation.models import EventRunResult, ForecastAccuracySummary, RiskSummary, SimulationReport
from simulation.validation import InstitutionalValidator, _parse_stage_id


def _make_result(
    event_type: str = "CPI",
    success: bool = True,
    decision: str | None = "POSITIVE",
    risk_decision: str | None = "POSITIVE",
    forecast_model: str | None = "prophet",
    forecast_confidence: float | None = 0.85,
    validation_passed: bool | None = True,
    risk_gate_action: str | None = "proceed",
    risk_gate_score: float | None = 0.75,
    errors: tuple[str, ...] = (),
    execution_time_ms: float = 100.0,
    cache_hits: int = 0,
    var_95: float | None = -0.02,
    cvar_95: float | None = -0.03,
    tail_index: float | None = 3.0,
) -> EventRunResult:
    return EventRunResult(
        event_type=event_type,
        event_date_min="2026-01-01",
        event_date_max="2026-01-31",
        event_count=1,
        success=success,
        execution_time_ms=execution_time_ms,
        cache_hits=cache_hits,
        checkpoints_used=2,
        decision=decision,
        risk_decision=risk_decision,
        forecast_model=forecast_model,
        forecast_confidence=forecast_confidence,
        validation_passed=validation_passed,
        validation_metrics={"mae": 0.5},
        var_95=var_95,
        cvar_95=cvar_95,
        tail_index=tail_index,
        position_scaling=1.0,
        risk_gate_action=risk_gate_action,
        risk_gate_score=risk_gate_score,
        error=errors[0] if errors else None,
        errors=errors,
    )


def _make_report(results: tuple[EventRunResult, ...]) -> SimulationReport:
    successful = sum(1 for r in results if r.success)
    return SimulationReport(
        timestamp="2026-01-01T00:00:00",
        data_dir="/tmp",
        gold_data_path="/tmp/gold.csv",
        total_events=len(results),
        successful_runs=successful,
        failed_runs=len(results) - successful,
        avg_execution_time_ms=sum(r.execution_time_ms for r in results) / len(results) if results else 0.0,
        cache_hit_ratio=0.0,
        checkpoints_total=sum(r.checkpoints_used for r in results),
        events_processed=tuple(r.event_type for r in results),
        results=results,
        forecast_accuracy=ForecastAccuracySummary(
            total_forecasts=len(results),
            passed_validations=sum(1 for r in results if r.validation_passed is True),
            failed_validations=sum(1 for r in results if r.validation_passed is False),
            avg_confidence=sum(r.forecast_confidence or 0.0 for r in results) / len(results) if results else None,
            models_used=tuple({r.forecast_model for r in results if r.forecast_model}),
        ),
        risk=RiskSummary(
            total_evaluations=len(results),
            actions={},
            avg_var_95=sum(r.var_95 or 0.0 for r in results) / len(results) if results else None,
            avg_cvar_95=sum(r.cvar_95 or 0.0 for r in results) / len(results) if results else None,
            avg_tail_index=sum(r.tail_index or 0.0 for r in results) / len(results) if results else None,
        ),
        errors=tuple(e for r in results for e in r.errors),
    )


# ---------------------------------------------------------------------------
# Tests: _parse_stage_id
# ---------------------------------------------------------------------------


def test_parse_stage_id_standard():
    assert _parse_stage_id("build_feature_pipeline: ModuleNotFoundError") == "build_feature_pipeline"


def test_parse_stage_id_unknown():
    assert _parse_stage_id("some random error without prefix") == "unknown"


# ---------------------------------------------------------------------------
# Tests: empty report
# ---------------------------------------------------------------------------


def test_empty_report_produces_defaults():
    report = _make_report(())
    validator = InstitutionalValidator()
    v = validator.validate(report)
    assert v.accuracy.forecast_risk_agreement_rate == 0.0
    assert v.bottlenecks.most_failed_stage is None
    assert v.models.best_model is None
    assert v.recommendations == ["No simulation data available for validation"]


# ---------------------------------------------------------------------------
# Q1: forecast-risk agreement
# ---------------------------------------------------------------------------


def test_q1_full_agreement():
    results = (
        _make_result(event_type="CPI", decision="POSITIVE", risk_decision="POSITIVE"),
        _make_result(event_type="NFP", decision="NEUTRAL", risk_decision="NEUTRAL"),
    )
    v = InstitutionalValidator().validate(_make_report(results))
    assert v.accuracy.forecast_risk_agreement_rate == 1.0


def test_q1_partial_agreement():
    results = (
        _make_result(event_type="CPI", decision="POSITIVE", risk_decision="POSITIVE"),
        _make_result(event_type="NFP", decision="POSITIVE", risk_decision="NEUTRAL"),
    )
    v = InstitutionalValidator().validate(_make_report(results))
    assert v.accuracy.forecast_risk_agreement_rate == 0.5


# ---------------------------------------------------------------------------
# Q2: risk overrides
# ---------------------------------------------------------------------------


def test_q2_no_overrides():
    results = (
        _make_result(decision="POSITIVE", risk_gate_action="proceed"),
        _make_result(decision="NEUTRAL", risk_gate_action="proceed"),
    )
    v = InstitutionalValidator().validate(_make_report(results))
    assert v.accuracy.risk_override_rate == 0.0
    assert v.risk.total_overrides == 0


def test_q2_detects_override():
    results = (
        _make_result(decision="POSITIVE", risk_gate_action="halt"),
        _make_result(decision="NEUTRAL", risk_gate_action="proceed"),
    )
    v = InstitutionalValidator().validate(_make_report(results))
    assert v.risk.total_overrides == 1
    assert v.risk.overrides_by_event.get("CPI") == 1
    assert v.accuracy.risk_override_rate > 0


def test_q2_not_override_when_decision_not_positive():
    results = (
        _make_result(decision="NEUTRAL", risk_gate_action="halt"),
    )
    v = InstitutionalValidator().validate(_make_report(results))
    assert v.risk.total_overrides == 0


# ---------------------------------------------------------------------------
# Q3: highest confidence event types
# ---------------------------------------------------------------------------


def test_q3_confidence_ranking():
    results = (
        _make_result(event_type="CPI", forecast_confidence=0.9),
        _make_result(event_type="CPI", forecast_confidence=0.8),
        _make_result(event_type="NFP", forecast_confidence=0.5),
    )
    v = InstitutionalValidator().validate(_make_report(results))
    assert v.confidence.highest_event == "CPI"
    assert v.confidence.lowest_event == "NFP"
    assert v.confidence.by_event_type["CPI"] == 0.85
    assert v.confidence.by_event_type["NFP"] == 0.5


# ---------------------------------------------------------------------------
# Q4: weakest reasoning
# ---------------------------------------------------------------------------


def test_q4_weakest_reasoning():
    results = (
        _make_result(event_type="CPI", validation_passed=True),
        _make_result(event_type="NFP", validation_passed=False),
    )
    v = InstitutionalValidator().validate(_make_report(results))
    assert "NFP" in v.reasoning.weakest_events


# ---------------------------------------------------------------------------
# Q5: pipeline stage failures
# ---------------------------------------------------------------------------


def test_q5_stage_failure_counting():
    results = (
        _make_result(errors=("build_feature_pipeline: timeout",)),
        _make_result(errors=("build_feature_pipeline: oom", "inference_runner: crash")),
    )
    v = InstitutionalValidator().validate(_make_report(results))
    assert v.bottlenecks.stage_failures.get("build_feature_pipeline") == 2
    assert v.bottlenecks.stage_failures.get("inference_runner") == 1
    assert v.bottlenecks.most_failed_stage == "build_feature_pipeline"


# ---------------------------------------------------------------------------
# Q6: model performance
# ---------------------------------------------------------------------------


def test_q6_model_performance():
    results = (
        _make_result(forecast_model="prophet", forecast_confidence=0.9, success=True, validation_passed=True),
        _make_result(forecast_model="prophet", forecast_confidence=0.7, success=True, validation_passed=True),
        _make_result(forecast_model="lstm", forecast_confidence=0.5, success=False, validation_passed=False),
    )
    v = InstitutionalValidator().validate(_make_report(results))
    assert v.models.best_model == "prophet"
    assert v.models.by_model["prophet"].runs == 2
    assert v.models.by_model["prophet"].success_rate == 1.0
    assert v.models.by_model["lstm"].success_rate == 0.0


# ---------------------------------------------------------------------------
# Q7: risk distribution
# ---------------------------------------------------------------------------


def test_q7_risk_action_distribution():
    results = (
        _make_result(risk_gate_action="proceed"),
        _make_result(risk_gate_action="proceed"),
        _make_result(risk_gate_action="halt"),
    )
    v = InstitutionalValidator().validate(_make_report(results))
    assert v.risk.actions["proceed"] == 2
    assert v.risk.actions["halt"] == 1


# ---------------------------------------------------------------------------
# Q8: component contributions
# ---------------------------------------------------------------------------


def test_q8_component_contributions():
    results = (
        _make_result(event_type="CPI", execution_time_ms=100.0, cache_hits=2),
        _make_result(event_type="NFP", execution_time_ms=200.0, cache_hits=0),
    )
    v = InstitutionalValidator().validate(_make_report(results))
    assert v.contributions.total_execution_time_ms == 300.0
    assert v.contributions.total_cache_hits == 2
    assert v.contributions.cache_hit_ratio_by_event_type["CPI"] == 2.0
    assert v.contributions.avg_execution_time_by_event_type["CPI"] == 100.0
    assert v.contributions.avg_execution_time_by_event_type["NFP"] == 200.0


# ---------------------------------------------------------------------------
# recommendations
# ---------------------------------------------------------------------------


def test_recommendations_generated_when_problems():
    results = (
        _make_result(decision="POSITIVE", risk_gate_action="halt"),
    )
    v = InstitutionalValidator().validate(_make_report(results))
    assert len(v.recommendations) >= 1


def test_recommendations_healthy():
    results = (
        _make_result(decision="POSITIVE", risk_decision="POSITIVE"),
    )
    v = InstitutionalValidator().validate(_make_report(results))
    assert any("healthy" in r.lower() or "Best" in r for r in v.recommendations), v.recommendations


# ---------------------------------------------------------------------------
# full report serialization
# ---------------------------------------------------------------------------


def test_report_dataclass_fields():
    results = (
        _make_result(event_type="CPI"),
        _make_result(event_type="NFP"),
    )
    v = InstitutionalValidator().validate(_make_report(results))
    assert v.simulation_timestamp == "2026-01-01T00:00:00"
    assert v.timestamp is not None
    assert v.metadata["total_events"] == 2
    assert len(v.metadata["event_types"]) == 2
