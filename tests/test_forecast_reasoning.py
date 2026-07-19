from __future__ import annotations

import pytest

from forecasting.confidence import ForecastConfidence
from forecasting.context import EventSummary, ForecastContext
from forecasting.evidence import ForecastEvidence, ForecastEvidenceBuilder
from forecasting.knowledge import ForecastPackage
from forecasting.models import ForecastPoint, ForecastResult
from forecasting.provenance import ForecastProvenance
from forecasting.reasoning import ForecastAssessment, ForecastReasoning

_PINNED_TS = "2026-07-18T12:00:00+00:00"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _provenance() -> ForecastProvenance:
    return ForecastProvenance(
        source="CPI",
        model_version="2",
        training_window="24 obs",
        registry_version="2",
        git_commit="abc123",
        data_hash="a1b2c3d4",
        created_at=_PINNED_TS,
    )


def _context(
    regime_conf: float = 0.85,
    news_conf: float = 0.72,
    fomc_conf: float = 0.65,
    regime: str | None = "EXPANSION",
    news_mood: str | None = "positive",
    fomc_mood: str | None = "hawkish",
    num_events: int = 1,
) -> ForecastContext:
    events = tuple(
        EventSummary("CPI", f"2026-06-{10+i:02d}", "high", "UP", 1.5)
        for i in range(num_events)
    )
    return ForecastContext(
        current_regime=regime,
        regime_confidence=regime_conf,
        recent_events=events,
        news_mood=news_mood,
        news_confidence=news_conf,
        fomc_mood=fomc_mood,
        fomc_confidence=fomc_conf,
        context_timestamp=_PINNED_TS,
        source_variable="CPI",
        data_date_range=("2020-01-01", "2026-06-30"),
    )


def _confidence(
    spread: float = 0.80,
    agreement: float = 0.90,
    coherence: float = 0.70,
) -> ForecastConfidence:
    overall = 0.30 * spread + 0.40 * agreement + 0.30 * coherence
    return ForecastConfidence(
        spread_score=spread,
        agreement_score=agreement,
        context_coherence=coherence,
        overall=overall,
    )


def _package(num_models: int = 2, horizon: int = 6) -> ForecastPackage:
    results: dict[str, ForecastResult] = {}
    for i in range(num_models):
        name = f"Model{i}"
        results[name] = ForecastResult(
            model_name=name,
            confidence_level=0.95,
            points=(
                ForecastPoint("2026-07-31", 105.0 + i, 100.0, 110.0),
                ForecastPoint("2026-08-31", 106.0 + i, 101.0, 111.0),
            ),
            metadata={},
        )
    return ForecastPackage(
        target_variable="CPI",
        context=_context(),
        results=results,
        provenance=_provenance(),
        model_specs=(),
        horizon=horizon,
    )


def _evidence(
    package: ForecastPackage | None = None,
    context: ForecastContext | None = None,
    confidence: ForecastConfidence | None = None,
    provenance: ForecastProvenance | None = None,
) -> ForecastEvidence:
    builder = ForecastEvidenceBuilder()
    return builder.build(
        package or _package(),
        context or _context(),
        confidence or _confidence(),
        provenance or _provenance(),
    )


# ---------------------------------------------------------------------------
# ForecastAssessment dataclass
# ---------------------------------------------------------------------------


class TestForecastAssessment:

    def test_frozen_dataclass(self) -> None:
        a = _assessment()
        with pytest.raises(AttributeError):
            a.overall_assessment = "WEAK"  # type: ignore[misc]

    def test_all_fields(self) -> None:
        a = _assessment()
        assert isinstance(a.overall_assessment, str)
        assert isinstance(a.confidence_level, float)
        assert isinstance(a.supporting_evidence, tuple)
        assert isinstance(a.conflicting_evidence, tuple)
        assert isinstance(a.reasoning_summary, str)
        assert isinstance(a.reasoning_metadata, dict)

    def test_to_dict_keys(self) -> None:
        a = _assessment()
        d = a.to_dict()
        expected = {
            "overall_assessment", "confidence_level", "supporting_evidence",
            "conflicting_evidence", "reasoning_summary", "reasoning_metadata",
        }
        assert set(d) == expected


# ---------------------------------------------------------------------------
# ForecastReasoning — assessment classification
# ---------------------------------------------------------------------------


class TestClassification:

    def test_strong_assessment(self) -> None:
        ev = _evidence()
        reasoner = ForecastReasoning()
        a = reasoner.assess(ev)
        assert a.overall_assessment == "STRONG"
        assert a.confidence_level > 0.65

    def test_moderate_assessment(self) -> None:
        conf = _confidence(spread=0.50, agreement=0.40, coherence=0.50)
        ev = _evidence(confidence=conf)
        reasoner = ForecastReasoning()
        a = reasoner.assess(ev)
        assert a.overall_assessment in ("MODERATE", "UNCERTAIN")

    def test_weak_assessment(self) -> None:
        conf = _confidence(spread=0.10, agreement=0.10, coherence=0.10)
        ev = _evidence(confidence=conf)
        reasoner = ForecastReasoning()
        a = reasoner.assess(ev)
        assert a.overall_assessment == "WEAK"

    def test_insufficient_assessment(self) -> None:
        conf = _confidence(spread=0.0, agreement=0.0, coherence=0.0)
        ev = _evidence(confidence=conf)
        reasoner = ForecastReasoning()
        a = reasoner.assess(ev)
        assert a.overall_assessment == "INSUFFICIENT"

    def test_deterministic(self) -> None:
        ev = _evidence()
        reasoner = ForecastReasoning()
        a1 = reasoner.assess(ev)
        a2 = reasoner.assess(ev)
        assert a1 == a2


# ---------------------------------------------------------------------------
# Supporting evidence
# ---------------------------------------------------------------------------


class TestSupportingEvidence:

    def test_ensemble_size(self) -> None:
        ev = _evidence(package=_package(num_models=3))
        reasoner = ForecastReasoning()
        a = reasoner.assess(ev)
        factors = a.supporting_evidence
        assert any("3 models" in f for f in factors)

    def test_tight_intervals(self) -> None:
        conf = _confidence(spread=0.95, agreement=0.50, coherence=0.50)
        ev = _evidence(confidence=conf)
        reasoner = ForecastReasoning()
        a = reasoner.assess(ev)
        assert any("tight" in f.lower() for f in a.supporting_evidence)

    def test_high_agreement(self) -> None:
        conf = _confidence(spread=0.50, agreement=0.95, coherence=0.50)
        ev = _evidence(confidence=conf)
        reasoner = ForecastReasoning()
        a = reasoner.assess(ev)
        assert any("agreement" in f.lower() for f in a.supporting_evidence)

    def test_strong_regime(self) -> None:
        ctx = _context(regime_conf=0.90, regime="RECOVERY")
        ev = _evidence(context=ctx)
        reasoner = ForecastReasoning()
        a = reasoner.assess(ev)
        assert any("RECOVERY" in f for f in a.supporting_evidence)

    def test_strong_news(self) -> None:
        ctx = _context(news_conf=0.85, news_mood="negative")
        ev = _evidence(context=ctx)
        reasoner = ForecastReasoning()
        a = reasoner.assess(ev)
        assert any("negative" in f for f in a.supporting_evidence)

    def test_strong_fomc(self) -> None:
        ctx = _context(fomc_conf=0.80, fomc_mood="dovish")
        ev = _evidence(context=ctx)
        reasoner = ForecastReasoning()
        a = reasoner.assess(ev)
        assert any("dovish" in f for f in a.supporting_evidence)

    def test_multiple_events(self) -> None:
        ctx = _context(num_events=3)
        ev = _evidence(context=ctx)
        reasoner = ForecastReasoning()
        a = reasoner.assess(ev)
        assert any("3 recent" in f.lower() for f in a.supporting_evidence)


# ---------------------------------------------------------------------------
# Conflicting evidence
# ---------------------------------------------------------------------------


class TestConflictingEvidence:

    def test_no_models(self) -> None:
        package = _package(num_models=0)
        ev = _evidence(package=package)
        reasoner = ForecastReasoning()
        a = reasoner.assess(ev)
        assert any("no forecast" in f.lower() for f in a.conflicting_evidence)

    def test_wide_intervals(self) -> None:
        conf = _confidence(spread=0.05, agreement=0.80, coherence=0.80)
        ev = _evidence(confidence=conf)
        reasoner = ForecastReasoning()
        a = reasoner.assess(ev)
        assert any("wide" in f.lower() for f in a.conflicting_evidence)

    def test_low_agreement(self) -> None:
        conf = _confidence(spread=0.80, agreement=0.05, coherence=0.80)
        ev = _evidence(confidence=conf)
        reasoner = ForecastReasoning()
        a = reasoner.assess(ev)
        assert any("low" in f.lower() for f in a.conflicting_evidence)

    def test_low_regime(self) -> None:
        ctx = _context(regime_conf=0.05)
        ev = _evidence(context=ctx)
        reasoner = ForecastReasoning()
        a = reasoner.assess(ev)
        assert any("low confidence" in f.lower() for f in a.conflicting_evidence)

    def test_no_regime(self) -> None:
        ctx = _context(regime=None, regime_conf=0.0)
        ev = _evidence(context=ctx)
        reasoner = ForecastReasoning()
        a = reasoner.assess(ev)
        assert any("no regime" in f.lower() for f in a.conflicting_evidence)

    def test_no_sentiment(self) -> None:
        ctx = _context(news_mood=None, news_conf=0.0, fomc_mood=None, fomc_conf=0.0)
        ev = _evidence(context=ctx)
        reasoner = ForecastReasoning()
        a = reasoner.assess(ev)
        assert any("no sentiment" in f.lower() for f in a.conflicting_evidence)

    def test_low_news(self) -> None:
        ctx = _context(news_conf=0.0, news_mood="positive")
        ev = _evidence(context=ctx)
        reasoner = ForecastReasoning()
        a = reasoner.assess(ev)
        assert any("weak news" in f.lower() for f in a.conflicting_evidence)

    def test_low_fomc(self) -> None:
        ctx = _context(fomc_conf=0.0, fomc_mood="hawkish")
        ev = _evidence(context=ctx)
        reasoner = ForecastReasoning()
        a = reasoner.assess(ev)
        assert any("weak fomc" in f.lower() for f in a.conflicting_evidence)


# ---------------------------------------------------------------------------
# Reasoning summary
# ---------------------------------------------------------------------------


class TestReasoningSummary:

    def test_includes_assessment(self) -> None:
        ev = _evidence()
        reasoner = ForecastReasoning()
        a = reasoner.assess(ev)
        assert "Assessment:" in a.reasoning_summary
        assert a.overall_assessment in a.reasoning_summary

    def test_includes_confidence(self) -> None:
        ev = _evidence()
        reasoner = ForecastReasoning()
        a = reasoner.assess(ev)
        assert "confidence=" in a.reasoning_summary

    def test_includes_supporting_when_present(self) -> None:
        ev = _evidence()
        reasoner = ForecastReasoning()
        a = reasoner.assess(ev)
        if a.supporting_evidence:
            assert "Supporting:" in a.reasoning_summary

    def test_includes_conflicting_when_present(self) -> None:
        ev = _evidence()
        reasoner = ForecastReasoning()
        a = reasoner.assess(ev)
        if a.conflicting_evidence:
            assert "Conflicting:" in a.reasoning_summary


# ---------------------------------------------------------------------------
# Reasoning metadata
# ---------------------------------------------------------------------------


class TestReasoningMetadata:

    def test_includes_thresholds(self) -> None:
        ev = _evidence()
        reasoner = ForecastReasoning()
        a = reasoner.assess(ev)
        assert "thresholds" in a.reasoning_metadata
        assert "strong" in a.reasoning_metadata["thresholds"]

    def test_includes_evidence_id(self) -> None:
        ev = _evidence()
        reasoner = ForecastReasoning()
        a = reasoner.assess(ev)
        assert a.reasoning_metadata["evidence_id"] == ev.evidence_id

    def test_includes_method(self) -> None:
        ev = _evidence()
        reasoner = ForecastReasoning()
        a = reasoner.assess(ev)
        assert "rule-based" in a.reasoning_metadata["assessment_method"]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _assessment() -> ForecastAssessment:
    return ForecastAssessment(
        overall_assessment="STRONG",
        confidence_level=0.82,
        supporting_evidence=("Tight intervals", "High agreement"),
        conflicting_evidence=(),
        reasoning_summary="Assessment: STRONG (confidence=0.82).",
        reasoning_metadata={"method": "rule-based"},
    )
