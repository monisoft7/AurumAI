from __future__ import annotations

import datetime
from typing import Any

import pandas as pd
import pytest

from forecasting.confidence import ForecastConfidenceComputer
from forecasting.context import EventSummary, ForecastContext, ForecastContextBuilder
from forecasting.evidence import ForecastEvidenceBuilder
from forecasting.knowledge import ForecastKnowledge, ForecastPackage
from forecasting.models import ForecastPoint, ForecastResult
from forecasting.provenance import ForecastProvenance
from forecasting.reasoning import ForecastReasoning
from forecasting.registry import ForecastModelSpec, ForecastRegistry
from forecasting.validation import ForecastValidator

try:
    from statsforecast.models import AutoARIMA, AutoETS, AutoTheta
    HAS_STATSFORECAST = True
except ImportError:
    HAS_STATSFORECAST = False

_PINNED_TS = "2026-07-18T12:00:00+00:00"

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _reset_and_seed_registry() -> None:
    ForecastRegistry._reset()
    _seed_registry()
    yield
    ForecastRegistry._reset()


def _seed_registry() -> None:
    ForecastRegistry.register(
        ForecastModelSpec(
            name="cpi_arima",
            model_cls=AutoARIMA,
            model_kwargs={"season_length": 12},
            target_variable="CPI",
            freq="ME",
            default_horizon=12,
            max_horizon=24,
            training_window="2y",
            validation_strategy="backtest",
            validation_split=0.2,
            approval_status="approved",
            approved_by="admin",
            approval_date="2026-07-01",
            description="AutoARIMA for CPI",
        ),
    )
    ForecastRegistry.register(
        ForecastModelSpec(
            name="cpi_ets",
            model_cls=AutoETS,
            model_kwargs={"season_length": 12, "model": "ZZZ"},
            target_variable="CPI",
            freq="ME",
            default_horizon=12,
            max_horizon=24,
            training_window="2y",
            validation_strategy="backtest",
            validation_split=0.2,
            approval_status="approved",
            approved_by="admin",
            approval_date="2026-07-01",
            description="AutoETS for CPI",
        ),
    )
    ForecastRegistry.register(
        ForecastModelSpec(
            name="cpi_theta",
            model_cls=AutoTheta,
            model_kwargs={"season_length": 12},
            target_variable="CPI",
            freq="ME",
            default_horizon=12,
            max_horizon=24,
            training_window="2y",
            validation_strategy="backtest",
            validation_split=0.2,
            approval_status="approved",
            approved_by="admin",
            approval_date="2026-07-01",
            description="AutoTheta for CPI",
        ),
    )


@pytest.fixture
def training_data() -> pd.DataFrame:
    return pd.DataFrame({
        "ds": pd.date_range("2020-01-01", periods=36, freq="ME"),
        "y": [100.0 + i * 0.5 + (i % 12) * 0.3 for i in range(36)],
    })


@pytest.fixture
def event_summaries() -> list[EventSummary]:
    return [
        EventSummary(
            event_type="CPI",
            date="2026-06-15",
            condition="moderate_increase",
            gold_direction="up",
            gold_return_pct=0.5,
        ),
        EventSummary(
            event_type="GDP",
            date="2026-07-01",
            condition="expansion",
            gold_direction="up",
            gold_return_pct=0.3,
        ),
    ]


@pytest.fixture
def full_pipeline() -> dict[str, Any]:
    """Run the complete Forecast Intelligence pipeline and return all artifacts."""
    knowledge = ForecastKnowledge()
    pkg = knowledge.forecast(
        target_variable="CPI",
        training_data=pd.DataFrame({
            "ds": pd.date_range("2020-01-01", periods=36, freq="ME"),
            "y": [100.0 + i * 0.5 + (i % 12) * 0.3 for i in range(36)],
        }),
        horizon=6,
        event_summaries=[
            EventSummary(
                event_type="CPI",
                date="2026-06-15",
                condition="moderate_increase",
                gold_direction="up",
                gold_return_pct=0.5,
            ),
        ],
    )

    computer = ForecastConfidenceComputer()
    confidence = computer.compute(package=pkg, context=pkg.context)

    builder = ForecastEvidenceBuilder()
    evidence = builder.build(
        package=pkg,
        context=pkg.context,
        confidence=confidence,
        provenance=pkg.provenance,
    )

    reasoning = ForecastReasoning()
    assessment = reasoning.assess(evidence)

    return {
        "package": pkg,
        "confidence": confidence,
        "evidence": evidence,
        "assessment": assessment,
    }


# ---------------------------------------------------------------------------
# Pipeline: object flow
# ---------------------------------------------------------------------------


class TestPipelineObjectFlow:

    def test_knowledge_returns_forecast_package(self, training_data: pd.DataFrame) -> None:
        knowledge = ForecastKnowledge()
        pkg = knowledge.forecast(target_variable="CPI", training_data=training_data, horizon=6)
        assert isinstance(pkg, ForecastPackage)

    def test_package_contains_results(self, full_pipeline: dict[str, Any]) -> None:
        pkg = full_pipeline["package"]
        assert len(pkg.results) > 0
        for name, result in pkg.results.items():
            assert isinstance(result, ForecastResult)
            assert len(result.points) > 0

    def test_package_contains_context(self, full_pipeline: dict[str, Any]) -> None:
        pkg = full_pipeline["package"]
        assert isinstance(pkg.context, ForecastContext)

    def test_package_contains_provenance(self, full_pipeline: dict[str, Any]) -> None:
        pkg = full_pipeline["package"]
        assert isinstance(pkg.provenance, ForecastProvenance)
        assert pkg.provenance.source == "CPI"
        assert pkg.provenance.training_window == "36 obs"

    def test_package_contains_model_specs(self, full_pipeline: dict[str, Any]) -> None:
        pkg = full_pipeline["package"]
        assert len(pkg.model_specs) > 0
        for spec in pkg.model_specs:
            assert spec.target_variable == "CPI"
            assert spec.approval_status == "approved"

    def test_confidence_is_computed(self, full_pipeline: dict[str, Any]) -> None:
        confidence = full_pipeline["confidence"]
        assert 0.0 <= confidence.spread_score <= 1.0
        assert 0.0 <= confidence.agreement_score <= 1.0
        assert 0.0 <= confidence.context_coherence <= 1.0
        assert 0.0 <= confidence.overall <= 1.0

    def test_evidence_is_built(self, full_pipeline: dict[str, Any]) -> None:
        evidence = full_pipeline["evidence"]
        assert evidence.evidence_id
        assert evidence.evidence_strength == full_pipeline["confidence"].overall

    def test_assessment_is_produced(self, full_pipeline: dict[str, Any]) -> None:
        assessment = full_pipeline["assessment"]
        assert assessment.overall_assessment in ("STRONG", "MODERATE", "UNCERTAIN", "WEAK", "INSUFFICIENT")
        assert 0.0 <= assessment.confidence_level <= 1.0
        assert isinstance(assessment.reasoning_summary, str)
        assert len(assessment.reasoning_summary) > 0


# ---------------------------------------------------------------------------
# Registry usage
# ---------------------------------------------------------------------------


class TestRegistryUsage:

    def test_selects_approved_only(self, training_data: pd.DataFrame) -> None:
        knowledge = ForecastKnowledge()
        pkg = knowledge.forecast(target_variable="CPI", training_data=training_data, horizon=6)
        for spec in pkg.model_specs:
            assert spec.approval_status == "approved"

    def test_selects_correct_target(self, training_data: pd.DataFrame) -> None:
        knowledge = ForecastKnowledge()
        pkg = knowledge.forecast(target_variable="CPI", training_data=training_data, horizon=6)
        for spec in pkg.model_specs:
            assert spec.target_variable == "CPI"

    def test_selects_specific_model_names(self, training_data: pd.DataFrame) -> None:
        knowledge = ForecastKnowledge()
        pkg = knowledge.forecast(
            target_variable="CPI",
            training_data=training_data,
            horizon=6,
            model_names=["cpi_arima"],
        )
        assert len(pkg.model_specs) == 1
        assert pkg.model_specs[0].name == "cpi_arima"
        assert list(pkg.results.keys()) == ["AutoARIMA"]

    def test_registry_version_in_provenance(self, training_data: pd.DataFrame) -> None:
        knowledge = ForecastKnowledge()
        pkg = knowledge.forecast(target_variable="CPI", training_data=training_data, horizon=6)
        assert int(pkg.provenance.registry_version) >= 3


# ---------------------------------------------------------------------------
# Context immutability
# ---------------------------------------------------------------------------


class TestContextImmutability:

    def test_context_is_frozen(self, full_pipeline: dict[str, Any]) -> None:
        ctx = full_pipeline["package"].context
        with pytest.raises(AttributeError):
            ctx.current_regime = "RECESSION"  # type: ignore[misc]

    def test_context_unchanged_after_confidence(self, full_pipeline: dict[str, Any]) -> None:
        ctx = full_pipeline["package"].context
        ctx_repr = repr(ctx)
        _ = full_pipeline["confidence"]
        assert repr(ctx) == ctx_repr

    def test_context_unchanged_after_evidence(self, full_pipeline: dict[str, Any]) -> None:
        ctx = full_pipeline["package"].context
        ctx_repr = repr(ctx)
        _ = full_pipeline["evidence"]
        assert repr(ctx) == ctx_repr

    def test_context_unchanged_after_assessment(self, full_pipeline: dict[str, Any]) -> None:
        ctx = full_pipeline["package"].context
        ctx_repr = repr(ctx)
        _ = full_pipeline["assessment"]
        assert repr(ctx) == ctx_repr


# ---------------------------------------------------------------------------
# Confidence propagation
# ---------------------------------------------------------------------------


class TestConfidencePropagation:

    def test_evidence_strength_matches_overall_confidence(self, full_pipeline: dict[str, Any]) -> None:
        confidence = full_pipeline["confidence"]
        evidence = full_pipeline["evidence"]
        assert evidence.evidence_strength == confidence.overall

    def test_confidence_snapshot_in_evidence(self, full_pipeline: dict[str, Any]) -> None:
        evidence = full_pipeline["evidence"]
        confidence = full_pipeline["confidence"]
        assert evidence.confidence_snapshot == {
            "spread_score": confidence.spread_score,
            "agreement_score": confidence.agreement_score,
            "context_coherence": confidence.context_coherence,
            "overall": confidence.overall,
        }

    def test_assessment_confidence_equals_evidence_strength(self, full_pipeline: dict[str, Any]) -> None:
        evidence = full_pipeline["evidence"]
        assessment = full_pipeline["assessment"]
        assert assessment.confidence_level == evidence.evidence_strength


# ---------------------------------------------------------------------------
# Evidence consistency
# ---------------------------------------------------------------------------


class TestEvidenceConsistency:

    def test_evidence_sources_match_model_names(self, full_pipeline: dict[str, Any]) -> None:
        pkg = full_pipeline["package"]
        evidence = full_pipeline["evidence"]
        expected_sources = tuple(sorted(pkg.results.keys()))
        assert evidence.evidence_sources == expected_sources

    def test_supporting_context_contains_context_fields(self, full_pipeline: dict[str, Any]) -> None:
        evidence = full_pipeline["evidence"]
        ctx = full_pipeline["package"].context
        sc = evidence.supporting_context
        assert sc["current_regime"] == ctx.current_regime
        assert sc["regime_confidence"] == ctx.regime_confidence
        assert sc["news_mood"] == ctx.news_mood
        assert sc["news_confidence"] == ctx.news_confidence
        assert sc["fomc_mood"] == ctx.fomc_mood
        assert sc["fomc_confidence"] == ctx.fomc_confidence
        assert sc["num_recent_events"] == len(ctx.recent_events)
        assert sc["data_date_range"] == list(ctx.data_date_range)

    def test_evidence_metadata_matches_package(self, full_pipeline: dict[str, Any]) -> None:
        pkg = full_pipeline["package"]
        evidence = full_pipeline["evidence"]
        md = evidence.metadata
        assert md["target_variable"] == pkg.target_variable
        assert md["horizon"] == pkg.horizon
        assert md["num_models"] == len(pkg.results)
        assert md["model_spec_count"] == len(pkg.model_specs)
        num_points = sum(len(r.points) for r in pkg.results.values())
        assert md["num_forecast_points"] == num_points

    def test_provenance_snapshot_matches(self, full_pipeline: dict[str, Any]) -> None:
        pkg = full_pipeline["package"]
        evidence = full_pipeline["evidence"]
        expected = pkg.provenance.to_dict()
        assert evidence.provenance_snapshot == expected


# ---------------------------------------------------------------------------
# Reasoning consistency
# ---------------------------------------------------------------------------


class TestReasoningConsistency:

    def test_assessment_classification(self, full_pipeline: dict[str, Any]) -> None:
        assessment = full_pipeline["assessment"]
        confidence = assessment.confidence_level
        if confidence >= 0.65:
            assert assessment.overall_assessment == "STRONG"
        elif confidence >= 0.35:
            assert assessment.overall_assessment in ("MODERATE", "UNCERTAIN")
        elif confidence >= 0.10:
            assert assessment.overall_assessment == "WEAK"
        else:
            assert assessment.overall_assessment == "INSUFFICIENT"

    def test_supporting_evidence_factors(self, full_pipeline: dict[str, Any]) -> None:
        assessment = full_pipeline["assessment"]
        evidence = full_pipeline["evidence"]
        expected_supporting = sorted(assessment.supporting_evidence)
        assert list(assessment.supporting_evidence) == expected_supporting

    def test_num_models_at_least_one(self, full_pipeline: dict[str, Any]) -> None:
        pkg = full_pipeline["package"]
        assert len(pkg.results) >= 1

    def test_reasoning_metadata_has_evidence_id(self, full_pipeline: dict[str, Any]) -> None:
        assessment = full_pipeline["assessment"]
        evidence = full_pipeline["evidence"]
        assert assessment.reasoning_metadata["evidence_id"] == evidence.evidence_id

    def test_reasoning_metadata_thresholds(self, full_pipeline: dict[str, Any]) -> None:
        assessment = full_pipeline["assessment"]
        th = assessment.reasoning_metadata["thresholds"]
        assert th["strong"] == 0.65
        assert th["moderate"] == 0.35
        assert th["weak"] == 0.10

    def test_assessment_is_deterministic(self, training_data: pd.DataFrame) -> None:
        knowledge = ForecastKnowledge()
        pkg1 = knowledge.forecast(target_variable="CPI", training_data=training_data, horizon=6)
        pkg2 = knowledge.forecast(target_variable="CPI", training_data=training_data, horizon=6)
        computer = ForecastConfidenceComputer()
        c1 = computer.compute(pkg1, pkg1.context)
        c2 = computer.compute(pkg2, pkg2.context)
        assert c1 == c2
        assert pkg1.results.keys() == pkg2.results.keys()
        for name in pkg1.results:
            assert pkg1.results[name].points == pkg2.results[name].points


# ---------------------------------------------------------------------------
# Serialization compatibility
# ---------------------------------------------------------------------------


class TestSerialization:

    def test_package_to_dict(self, full_pipeline: dict[str, Any]) -> None:
        pkg = full_pipeline["package"]
        d = pkg.to_dict()
        assert d["target_variable"] == "CPI"
        assert d["horizon"] == 6
        assert "context" in d
        assert "results" in d
        assert "provenance" in d
        assert "model_specs" in d

    def test_context_to_dict(self, full_pipeline: dict[str, Any]) -> None:
        ctx = full_pipeline["package"].context
        d = ctx.to_dict()
        assert d["source_variable"] == "CPI"
        assert "current_regime" in d
        assert "recent_events" in d

    def test_confidence_to_dict(self, full_pipeline: dict[str, Any]) -> None:
        confidence = full_pipeline["confidence"]
        d = confidence.to_dict()
        assert set(d) == {"spread_score", "agreement_score", "context_coherence", "overall"}

    def test_evidence_to_dict(self, full_pipeline: dict[str, Any]) -> None:
        evidence = full_pipeline["evidence"]
        d = evidence.to_dict()
        assert set(d) == {
            "evidence_id",
            "evidence_strength",
            "evidence_sources",
            "supporting_context",
            "confidence_snapshot",
            "provenance_snapshot",
            "metadata",
        }

    def test_assessment_to_dict(self, full_pipeline: dict[str, Any]) -> None:
        assessment = full_pipeline["assessment"]
        d = assessment.to_dict()
        assert set(d) == {
            "overall_assessment",
            "confidence_level",
            "supporting_evidence",
            "conflicting_evidence",
            "reasoning_summary",
            "reasoning_metadata",
        }

    def test_provenance_to_dict(self, full_pipeline: dict[str, Any]) -> None:
        pkg = full_pipeline["package"]
        d = pkg.provenance.to_dict()
        assert set(d) == {
            "source",
            "model_version",
            "training_window",
            "registry_version",
            "git_commit",
            "data_hash",
            "created_at",
        }

    def test_context_round_trip_from_dict(self, full_pipeline: dict[str, Any]) -> None:
        ctx = full_pipeline["package"].context
        d = ctx.to_dict()
        restored = ForecastContext.from_dict(d)
        assert restored == ctx


# ---------------------------------------------------------------------------
# Validation metrics
# ---------------------------------------------------------------------------


class TestValidation:

    def test_validation_with_own_forecasts(self, full_pipeline: dict[str, Any]) -> None:
        pkg = full_pipeline["package"]
        validator = ForecastValidator()
        first_result = next(iter(pkg.results.values()))
        forecast_ds = [pt.ds for pt in first_result.points]
        actual_data = pd.DataFrame({
            "ds": forecast_ds,
            "y": [105.0 + i * 0.6 for i in range(len(forecast_ds))],
        })
        report = validator.validate(
            actual_data=actual_data,
            forecast_results=pkg.results,
            strategy="walk_forward",
            horizon=6,
        )
        assert report.sample_size == len(forecast_ds)
        assert report.validation_strategy == "walk_forward"
        assert report.horizon == 6
        assert 0.0 <= report.metrics["rmse"]
        assert 0.0 <= report.metrics["mae"]
        assert 0.0 <= report.metrics["coverage"] <= 1.0
        assert isinstance(report.passed, bool)
        assert len(report.notes) > 0

    def test_validation_empty_actuals(self, full_pipeline: dict[str, Any]) -> None:
        pkg = full_pipeline["package"]
        validator = ForecastValidator()
        empty_data = pd.DataFrame(columns=["ds", "y"])
        report = validator.validate(actual_data=empty_data, forecast_results=pkg.results)
        assert report.sample_size == 0
        assert report.passed is False

    def test_validation_serialization(self, full_pipeline: dict[str, Any]) -> None:
        pkg = full_pipeline["package"]
        validator = ForecastValidator()
        first_result = next(iter(pkg.results.values()))
        forecast_ds = [pt.ds for pt in first_result.points]
        actual_data = pd.DataFrame({
            "ds": forecast_ds,
            "y": [105.0 + i * 0.6 for i in range(len(forecast_ds))],
        })
        report = validator.validate(actual_data=actual_data, forecast_results=pkg.results)
        d = report.to_dict()
        assert set(d) == {
            "validation_strategy",
            "metrics",
            "horizon",
            "sample_size",
            "passed",
            "notes",
        }


# ---------------------------------------------------------------------------
# End-to-end: full pipeline with events
# ---------------------------------------------------------------------------


class TestEndToEnd:

    def test_full_pipeline_with_events(self, full_pipeline: dict[str, Any]) -> None:
        pkg = full_pipeline["package"]
        confidence = full_pipeline["confidence"]
        evidence = full_pipeline["evidence"]
        assessment = full_pipeline["assessment"]

        assert len(pkg.results) >= 2
        assert pkg.horizon == 6
        assert pkg.target_variable == "CPI"
        assert len(pkg.context.recent_events) == 1
        assert pkg.context.recent_events[0].event_type == "CPI"
        assert confidence.spread_score >= 0
        assert confidence.agreement_score >= 0
        assert evidence.evidence_strength == confidence.overall
        assert assessment.confidence_level == evidence.evidence_strength
        assert "deterministic" in assessment.reasoning_metadata["assessment_method"]

    def test_pipeline_without_events(self, training_data: pd.DataFrame) -> None:
        knowledge = ForecastKnowledge()
        pkg = knowledge.forecast(target_variable="CPI", training_data=training_data, horizon=6)
        assert len(pkg.context.recent_events) == 0
        computer = ForecastConfidenceComputer()
        confidence = computer.compute(pkg, pkg.context)
        builder = ForecastEvidenceBuilder()
        evidence = builder.build(pkg, pkg.context, confidence, pkg.provenance)
        reasoning = ForecastReasoning()
        assessment = reasoning.assess(evidence)
        assert assessment.overall_assessment
        assert evidence.evidence_strength == confidence.overall

    def test_deterministic_full_pipeline(self, training_data: pd.DataFrame) -> None:
        def run() -> tuple:
            knowledge = ForecastKnowledge()
            pkg = knowledge.forecast(target_variable="CPI", training_data=training_data, horizon=6)
            computer = ForecastConfidenceComputer()
            confidence = computer.compute(pkg, pkg.context)
            builder = ForecastEvidenceBuilder()
            evidence = builder.build(pkg, pkg.context, confidence, pkg.provenance)
            reasoning = ForecastReasoning()
            assessment = reasoning.assess(evidence)
            return (pkg, confidence, evidence, assessment)

        r1 = run()
        r2 = run()
        assert r1[1] == r2[1]
        assert r1[0].context.source_variable == r2[0].context.source_variable
        assert r1[0].target_variable == r2[0].target_variable
        assert r1[0].horizon == r2[0].horizon
        assert r1[0].results.keys() == r2[0].results.keys()
        for name in r1[0].results:
            assert r1[0].results[name].points == r2[0].results[name].points
        assert r1[0].provenance.data_hash == r2[0].provenance.data_hash
        assert r1[0].provenance.source == r2[0].provenance.source
        assert r1[0].provenance.training_window == r2[0].provenance.training_window
        assert r1[3].overall_assessment == r2[3].overall_assessment
        assert r1[3].confidence_level == r2[3].confidence_level
        assert r1[3].supporting_evidence == r2[3].supporting_evidence
        assert r1[3].conflicting_evidence == r2[3].conflicting_evidence


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


class TestEdgeCases:

    def test_no_models_in_registry(self, training_data: pd.DataFrame) -> None:
        ForecastRegistry._reset()
        knowledge = ForecastKnowledge()
        pkg = knowledge.forecast(target_variable="CPI", training_data=training_data, horizon=6)
        assert pkg.results == {}
        assert len(pkg.model_specs) == 0
        computer = ForecastConfidenceComputer()
        confidence = computer.compute(pkg, pkg.context)
        assert confidence.overall == 0.0
        builder = ForecastEvidenceBuilder()
        evidence = builder.build(pkg, pkg.context, confidence, pkg.provenance)
        assert evidence.evidence_sources == ()
        assert evidence.evidence_strength == 0.0
        reasoning = ForecastReasoning()
        assessment = reasoning.assess(evidence)
        assert "No forecast models" in " ".join(assessment.conflicting_evidence)

    def test_all_context_signals_null(self, training_data: pd.DataFrame) -> None:
        knowledge = ForecastKnowledge()
        pkg = knowledge.forecast(target_variable="CPI", training_data=training_data, horizon=6)
        ctx = pkg.context
        assert ctx.current_regime is None
        assert ctx.news_mood is None
        assert ctx.fomc_mood is None
        assert ctx.regime_confidence == 0.0
        assert ctx.news_confidence == 0.0
        assert ctx.fomc_confidence == 0.0

    def test_context_coherence_zero_when_no_signals(self, training_data: pd.DataFrame) -> None:
        knowledge = ForecastKnowledge()
        pkg = knowledge.forecast(target_variable="CPI", training_data=training_data, horizon=6)
        computer = ForecastConfidenceComputer()
        confidence = computer.compute(pkg, pkg.context)
        assert confidence.context_coherence == 0.0

    def test_unknown_target_returns_empty(self, training_data: pd.DataFrame) -> None:
        knowledge = ForecastKnowledge()
        pkg = knowledge.forecast(target_variable="UNKNOWN", training_data=training_data, horizon=6)
        assert pkg.results == {}
        assert pkg.context.source_variable == "UNKNOWN"
