from __future__ import annotations

import re

import pytest

from forecasting.confidence import ForecastConfidence
from forecasting.context import EventSummary, ForecastContext
from forecasting.evidence import ForecastEvidence, ForecastEvidenceBuilder
from forecasting.knowledge import ForecastPackage
from forecasting.models import ForecastPoint, ForecastResult
from forecasting.provenance import ForecastProvenance

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
        git_commit="abc123def456",
        data_hash="a1b2c3d4e5f6",
        created_at=_PINNED_TS,
    )


def _context() -> ForecastContext:
    return ForecastContext(
        current_regime="EXPANSION",
        regime_confidence=0.85,
        recent_events=(
            EventSummary("CPI", "2026-06-10", "cpi_pressure=high", "UP", 1.5),
        ),
        news_mood="positive",
        news_confidence=0.72,
        fomc_mood="hawkish",
        fomc_confidence=0.65,
        context_timestamp=_PINNED_TS,
        source_variable="CPI",
        data_date_range=("2020-01-01", "2026-06-30"),
    )


def _confidence() -> ForecastConfidence:
    return ForecastConfidence(
        spread_score=0.80,
        agreement_score=0.90,
        context_coherence=0.70,
        overall=0.82,
    )


def _package(results: dict[str, ForecastResult] | None = None) -> ForecastPackage:
    return ForecastPackage(
        target_variable="CPI",
        context=_context(),
        results=results or {},
        provenance=_provenance(),
        model_specs=(),
        horizon=6,
    )


def _full_results() -> dict[str, ForecastResult]:
    return {
        "AutoARIMA": ForecastResult(
            model_name="AutoARIMA",
            confidence_level=0.95,
            points=(
                ForecastPoint("2026-07-31", 105.0, 100.0, 110.0),
                ForecastPoint("2026-08-31", 106.0, 101.0, 111.0),
            ),
            metadata={"h": 2},
        ),
        "AutoETS": ForecastResult(
            model_name="AutoETS",
            confidence_level=0.95,
            points=(
                ForecastPoint("2026-07-31", 104.0, 99.0, 109.0),
                ForecastPoint("2026-08-31", 105.5, 100.5, 110.5),
            ),
            metadata={"h": 2},
        ),
    }


# ---------------------------------------------------------------------------
# ForecastEvidence dataclass
# ---------------------------------------------------------------------------


class TestForecastEvidence:

    def test_frozen_dataclass(self) -> None:
        ev = _create_evidence()
        with pytest.raises(AttributeError):
            ev.evidence_id = "other"  # type: ignore[misc]

    def test_all_fields(self) -> None:
        ev = _create_evidence()
        assert isinstance(ev.evidence_id, str)
        assert isinstance(ev.evidence_strength, float)
        assert isinstance(ev.evidence_sources, tuple)
        assert isinstance(ev.supporting_context, dict)
        assert isinstance(ev.confidence_snapshot, dict)
        assert isinstance(ev.provenance_snapshot, dict)
        assert isinstance(ev.metadata, dict)

    def test_evidence_id_is_uuid(self) -> None:
        ev = _create_evidence()
        pattern = r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"
        assert re.match(pattern, ev.evidence_id)

    def test_evidence_strength_matches_confidence_overall(self) -> None:
        confidence = _confidence()
        ev = _create_evidence(confidence=confidence)
        assert ev.evidence_strength == confidence.overall

    def test_evidence_sources_sorted(self) -> None:
        results = _full_results()
        pkg = _package(results)
        builder = ForecastEvidenceBuilder()
        ev = builder.build(pkg, _context(), _confidence(), _provenance())
        assert ev.evidence_sources == ("AutoARIMA", "AutoETS")

    def test_evidence_sources_empty(self) -> None:
        ev = _create_evidence(package=_package())
        assert ev.evidence_sources == ()

    def test_to_dict_keys(self) -> None:
        ev = _create_evidence()
        d = ev.to_dict()
        expected = {
            "evidence_id", "evidence_strength", "evidence_sources",
            "supporting_context", "confidence_snapshot", "provenance_snapshot",
            "metadata",
        }
        assert set(d) == expected

    def test_to_dict_values(self) -> None:
        ev = _create_evidence()
        d = ev.to_dict()
        assert d["evidence_id"] == ev.evidence_id
        assert d["evidence_strength"] == ev.evidence_strength
        assert d["evidence_sources"] == list(ev.evidence_sources)
        assert d["confidence_snapshot"]["overall"] == ev.confidence_snapshot["overall"]


# ---------------------------------------------------------------------------
# ForecastEvidenceBuilder
# ---------------------------------------------------------------------------


class TestForecastEvidenceBuilder:

    def test_build_returns_evidence(self) -> None:
        builder = ForecastEvidenceBuilder()
        ev = builder.build(_package(_full_results()), _context(), _confidence(), _provenance())
        assert isinstance(ev, ForecastEvidence)

    def test_build_empty_results(self) -> None:
        builder = ForecastEvidenceBuilder()
        ev = builder.build(_package(), _context(), _confidence(), _provenance())
        assert ev.evidence_sources == ()
        assert ev.metadata["num_models"] == 0

    def test_evidence_id_deterministic(self) -> None:
        builder = ForecastEvidenceBuilder()
        prov = _provenance()
        ev1 = builder.build(_package(_full_results()), _context(), _confidence(), prov)
        ev2 = builder.build(_package(_full_results()), _context(), _confidence(), prov)
        assert ev1.evidence_id == ev2.evidence_id

    def test_different_provenance_different_id(self) -> None:
        builder = ForecastEvidenceBuilder()
        prov1 = _provenance()
        prov2 = ForecastProvenance(
            source="GDP",
            model_version="1",
            training_window="12 obs",
            registry_version="1",
            git_commit="xyz789",
            data_hash="different_hash",
            created_at=_PINNED_TS,
        )
        ev1 = builder.build(_package(_full_results()), _context(), _confidence(), prov1)
        ev2 = builder.build(_package(_full_results()), _context(), _confidence(), prov2)
        assert ev1.evidence_id != ev2.evidence_id

    def test_supporting_context_contains_regime(self) -> None:
        builder = ForecastEvidenceBuilder()
        ev = builder.build(_package(_full_results()), _context(), _confidence(), _provenance())
        assert ev.supporting_context["current_regime"] == "EXPANSION"
        assert ev.supporting_context["regime_confidence"] == 0.85

    def test_supporting_context_contains_sentiment(self) -> None:
        builder = ForecastEvidenceBuilder()
        ev = builder.build(_package(_full_results()), _context(), _confidence(), _provenance())
        assert ev.supporting_context["news_mood"] == "positive"
        assert ev.supporting_context["fomc_mood"] == "hawkish"

    def test_supporting_context_contains_events(self) -> None:
        builder = ForecastEvidenceBuilder()
        ev = builder.build(_package(_full_results()), _context(), _confidence(), _provenance())
        assert ev.supporting_context["num_recent_events"] == 1

    def test_confidence_snapshot_matches(self) -> None:
        confidence = _confidence()
        builder = ForecastEvidenceBuilder()
        ev = builder.build(_package(_full_results()), _context(), confidence, _provenance())
        assert ev.confidence_snapshot == confidence.to_dict()

    def test_provenance_snapshot_matches(self) -> None:
        prov = _provenance()
        builder = ForecastEvidenceBuilder()
        ev = builder.build(_package(_full_results()), _context(), _confidence(), prov)
        assert ev.provenance_snapshot == prov.to_dict()

    def test_metadata_target_variable(self) -> None:
        builder = ForecastEvidenceBuilder()
        ev = builder.build(_package(_full_results()), _context(), _confidence(), _provenance())
        assert ev.metadata["target_variable"] == "CPI"

    def test_metadata_horizon(self) -> None:
        builder = ForecastEvidenceBuilder()
        ev = builder.build(_package(_full_results()), _context(), _confidence(), _provenance())
        assert ev.metadata["horizon"] == 6

    def test_metadata_num_models(self) -> None:
        builder = ForecastEvidenceBuilder()
        ev = builder.build(_package(_full_results()), _context(), _confidence(), _provenance())
        assert ev.metadata["num_models"] == 2

    def test_metadata_forecast_points(self) -> None:
        builder = ForecastEvidenceBuilder()
        ev = builder.build(_package(_full_results()), _context(), _confidence(), _provenance())
        assert ev.metadata["num_forecast_points"] == 4

    def test_builder_deterministic(self) -> None:
        builder = ForecastEvidenceBuilder()
        pkg = _package(_full_results())
        ctx = _context()
        conf = _confidence()
        prov = _provenance()
        ev1 = builder.build(pkg, ctx, conf, prov)
        ev2 = builder.build(pkg, ctx, conf, prov)
        assert ev1 == ev2


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


class TestEdgeCases:

    def test_zero_confidence(self) -> None:
        conf = ForecastConfidence(spread_score=0.0, agreement_score=0.0, context_coherence=0.0, overall=0.0)
        builder = ForecastEvidenceBuilder()
        ev = builder.build(_package(), _context(), conf, _provenance())
        assert ev.evidence_strength == 0.0
        assert ev.evidence_sources == ()

    def test_max_confidence(self) -> None:
        conf = ForecastConfidence(spread_score=1.0, agreement_score=1.0, context_coherence=1.0, overall=1.0)
        builder = ForecastEvidenceBuilder()
        ev = builder.build(_package(_full_results()), _context(), conf, _provenance())
        assert ev.evidence_strength == 1.0

    def test_empty_context(self) -> None:
        ctx = ForecastContext(
            current_regime=None,
            regime_confidence=0.0,
            recent_events=(),
            news_mood=None,
            news_confidence=0.0,
            fomc_mood=None,
            fomc_confidence=0.0,
            context_timestamp=_PINNED_TS,
            source_variable="",
            data_date_range=("", ""),
        )
        builder = ForecastEvidenceBuilder()
        ev = builder.build(_package(), ctx, _confidence(), _provenance())
        assert ev.supporting_context["current_regime"] is None
        assert ev.supporting_context["news_mood"] is None
        assert ev.supporting_context["num_recent_events"] == 0


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _create_evidence(
    package: ForecastPackage | None = None,
    context: ForecastContext | None = None,
    confidence: ForecastConfidence | None = None,
    provenance: ForecastProvenance | None = None,
) -> ForecastEvidence:
    builder = ForecastEvidenceBuilder()
    return builder.build(
        package or _package(_full_results()),
        context or _context(),
        confidence or _confidence(),
        provenance or _provenance(),
    )
