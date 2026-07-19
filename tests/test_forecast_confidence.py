from __future__ import annotations

import pytest

from forecasting.confidence import ForecastConfidence, ForecastConfidenceComputer
from forecasting.context import EventSummary, ForecastContext
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
        model_version="1",
        training_window="24 obs",
        registry_version="1",
        git_commit="abc123",
        data_hash="def456",
        created_at=_PINNED_TS,
    )


def _context(
    regime_conf: float = 0.8,
    news_conf: float = 0.7,
    fomc_conf: float = 0.6,
) -> ForecastContext:
    return ForecastContext(
        current_regime="EXPANSION",
        regime_confidence=regime_conf,
        recent_events=(),
        news_mood="positive",
        news_confidence=news_conf,
        fomc_mood="hawkish",
        fomc_confidence=fomc_conf,
        context_timestamp=_PINNED_TS,
        source_variable="CPI",
        data_date_range=("2020-01-01", "2026-06-30"),
    )


def _empty_context() -> ForecastContext:
    return ForecastContext(
        current_regime=None,
        regime_confidence=0.0,
        recent_events=(),
        news_mood=None,
        news_confidence=0.0,
        fomc_mood=None,
        fomc_confidence=0.0,
        context_timestamp=_PINNED_TS,
        source_variable="CPI",
        data_date_range=("", ""),
    )


def _package(
    results: dict[str, ForecastResult] | None = None,
    horizon: int = 3,
) -> ForecastPackage:
    return ForecastPackage(
        target_variable="CPI",
        context=_empty_context(),
        results=results or {},
        provenance=_provenance(),
        model_specs=(),
        horizon=horizon,
    )


# ---------------------------------------------------------------------------
# ForecastConfidence dataclass
# ---------------------------------------------------------------------------


class TestForecastConfidence:

    def test_frozen_dataclass(self) -> None:
        fc = ForecastConfidence(spread_score=0.5, agreement_score=0.6, context_coherence=0.7, overall=0.6)
        with pytest.raises(AttributeError):
            fc.spread_score = 0.9  # type: ignore[misc]

    def test_all_fields(self) -> None:
        fc = ForecastConfidence(spread_score=0.3, agreement_score=0.4, context_coherence=0.5, overall=0.4)
        assert fc.spread_score == 0.3
        assert fc.agreement_score == 0.4
        assert fc.context_coherence == 0.5
        assert fc.overall == 0.4

    def test_to_dict_keys(self) -> None:
        fc = ForecastConfidence(spread_score=0.1, agreement_score=0.2, context_coherence=0.3, overall=0.2)
        d = fc.to_dict()
        assert set(d) == {"spread_score", "agreement_score", "context_coherence", "overall"}

    def test_to_dict_values(self) -> None:
        fc = ForecastConfidence(spread_score=0.1, agreement_score=0.2, context_coherence=0.3, overall=0.2)
        d = fc.to_dict()
        assert d["spread_score"] == 0.1
        assert d["agreement_score"] == 0.2
        assert d["context_coherence"] == 0.3
        assert d["overall"] == 0.2


# ---------------------------------------------------------------------------
# ForecastConfidenceComputer — edge cases
# ---------------------------------------------------------------------------


class TestComputerEdgeCases:

    def test_empty_results(self) -> None:
        computer = ForecastConfidenceComputer()
        fc = computer.compute(_package(), _empty_context())
        assert fc.spread_score == 0.0
        assert fc.agreement_score == 0.0
        assert fc.context_coherence == 0.0
        assert fc.overall == 0.0

    def test_single_model(self) -> None:
        result = ForecastResult(
            model_name="AutoARIMA",
            confidence_level=0.95,
            points=(
                ForecastPoint(ds="2026-07-31", y=105.0, y_lo=100.0, y_hi=110.0),
            ),
            metadata={},
        )
        computer = ForecastConfidenceComputer()
        fc = computer.compute(_package({"AutoARIMA": result}), _empty_context())
        assert fc.agreement_score == 1.0
        assert fc.spread_score >= 0

    def test_single_point_per_model(self) -> None:
        r1 = ForecastResult("m1", 0.95, (ForecastPoint("d1", 100.0, 90.0, 110.0),), {})
        r2 = ForecastResult("m2", 0.95, (ForecastPoint("d1", 101.0, 91.0, 111.0),), {})
        computer = ForecastConfidenceComputer()
        fc = computer.compute(_package({"m1": r1, "m2": r2}), _empty_context())
        assert fc.spread_score >= 0
        assert fc.agreement_score >= 0

    def test_deterministic(self) -> None:
        r1 = ForecastResult("m1", 0.95, (ForecastPoint("d1", 100.0, 90.0, 110.0),), {})
        r2 = ForecastResult("m2", 0.95, (ForecastPoint("d1", 102.0, 92.0, 112.0),), {})
        pkg = _package({"m1": r1, "m2": r2})
        computer = ForecastConfidenceComputer()
        fc1 = computer.compute(pkg, _empty_context())
        fc2 = computer.compute(pkg, _empty_context())
        assert fc1 == fc2

    def test_overall_clamped_to_zero_one(self) -> None:
        result = ForecastResult(
            model_name="m",
            confidence_level=0.95,
            points=(
                ForecastPoint(ds="d1", y=1.0, y_lo=-1e6, y_hi=1e6),
            ),
            metadata={},
        )
        computer = ForecastConfidenceComputer()
        fc = computer.compute(_package({"m": result}), _empty_context())
        assert 0.0 <= fc.overall <= 1.0


# ---------------------------------------------------------------------------
# Spread Score
# ---------------------------------------------------------------------------


class TestSpreadScore:

    def test_zero_when_empty(self) -> None:
        assert ForecastConfidenceComputer._compute_spread_score(_package()) == 0.0

    def test_tight_intervals_high_score(self) -> None:
        r = ForecastResult("m", 0.95, (ForecastPoint("d1", 100.0, 99.0, 101.0),), {})
        fc = ForecastConfidenceComputer._compute_spread_score(_package({"m": r}))
        assert fc > 0.95

    def test_wide_intervals_low_score(self) -> None:
        r = ForecastResult("m", 0.95, (ForecastPoint("d1", 100.0, 0.0, 200.0),), {})
        fc = ForecastConfidenceComputer._compute_spread_score(_package({"m": r}))
        assert fc < 0.5

    def test_narrower_interval_higher_score(self) -> None:
        wide = ForecastResult("m1", 0.95, (ForecastPoint("d1", 100.0, 50.0, 150.0),), {})
        tight = ForecastResult("m2", 0.95, (ForecastPoint("d1", 100.0, 95.0, 105.0),), {})
        f_wide = ForecastConfidenceComputer._compute_spread_score(_package({"m1": wide}))
        f_tight = ForecastConfidenceComputer._compute_spread_score(_package({"m2": tight}))
        assert f_tight > f_wide

    def test_averages_across_points(self) -> None:
        r = ForecastResult(
            "m", 0.95,
            (
                ForecastPoint("d1", 100.0, 99.0, 101.0),
                ForecastPoint("d2", 200.0, 190.0, 210.0),
            ),
            {},
        )
        fc = ForecastConfidenceComputer._compute_spread_score(_package({"m": r}))
        assert 0.0 < fc < 1.0


# ---------------------------------------------------------------------------
# Agreement Score
# ---------------------------------------------------------------------------


class TestAgreementScore:

    def test_zero_when_empty(self) -> None:
        assert ForecastConfidenceComputer._compute_agreement_score(_package()) == 0.0

    def test_perfect_when_single_model(self) -> None:
        r = ForecastResult("m", 0.95, (ForecastPoint("d1", 100.0, 90.0, 110.0),), {})
        assert ForecastConfidenceComputer._compute_agreement_score(_package({"m": r})) == 1.0

    def test_identical_predictions_perfect(self) -> None:
        pt = ForecastPoint("d1", 100.0, 90.0, 110.0)
        r1 = ForecastResult("m1", 0.95, (pt,), {})
        r2 = ForecastResult("m2", 0.95, (pt,), {})
        fc = ForecastConfidenceComputer._compute_agreement_score(_package({"m1": r1, "m2": r2}))
        assert fc == 1.0

    def test_divergent_predictions_lower(self) -> None:
        r1 = ForecastResult("m1", 0.95, (ForecastPoint("d1", 100.0, 90.0, 110.0),), {})
        r2 = ForecastResult("m2", 0.95, (ForecastPoint("d1", 200.0, 190.0, 210.0),), {})
        fc = ForecastConfidenceComputer._compute_agreement_score(_package({"m1": r1, "m2": r2}))
        assert fc < 1.0

    def test_more_models_more_agreement_higher(self) -> None:
        pt = ForecastPoint("d1", 100.0, 90.0, 110.0)
        pt_out = ForecastPoint("d1", 500.0, 490.0, 510.0)
        high_agree = ForecastConfidenceComputer._compute_agreement_score(
            _package({"m1": ForecastResult("m1", 0.95, (pt,), {}),
                       "m2": ForecastResult("m2", 0.95, (pt,), {}),
                       "m3": ForecastResult("m3", 0.95, (pt,), {})})
        )
        low_agree = ForecastConfidenceComputer._compute_agreement_score(
            _package({"m1": ForecastResult("m1", 0.95, (pt,), {}),
                       "m2": ForecastResult("m2", 0.95, (pt_out,), {})})
        )
        assert high_agree > low_agree

    def test_averages_across_points(self) -> None:
        pt_close = ForecastPoint("d1", 100.0, 90.0, 110.0)
        pt_far = ForecastPoint("d2", 100.0, 90.0, 110.0)
        r1 = ForecastResult("m1", 0.95, (pt_close, pt_far), {})
        r2 = ForecastResult("m2", 0.95, (ForecastPoint("d1", 101.0, 91.0, 111.0),
                                          ForecastPoint("d2", 500.0, 490.0, 510.0)), {})
        fc = ForecastConfidenceComputer._compute_agreement_score(_package({"m1": r1, "m2": r2}))
        assert 0.0 < fc < 1.0


# ---------------------------------------------------------------------------
# Context Coherence
# ---------------------------------------------------------------------------


class TestContextCoherence:

    def test_zero_when_all_zeros(self) -> None:
        assert ForecastConfidenceComputer._compute_context_coherence(_empty_context()) == 0.0

    def test_average_of_three(self) -> None:
        ctx = _context(regime_conf=0.8, news_conf=0.7, fomc_conf=0.6)
        fc = ForecastConfidenceComputer._compute_context_coherence(ctx)
        assert fc == pytest.approx(0.7)

    def test_full_confidence(self) -> None:
        ctx = _context(regime_conf=1.0, news_conf=1.0, fomc_conf=1.0)
        fc = ForecastConfidenceComputer._compute_context_coherence(ctx)
        assert fc == 1.0

    def test_mixed_confidence(self) -> None:
        ctx = _context(regime_conf=0.0, news_conf=1.0, fomc_conf=0.5)
        fc = ForecastConfidenceComputer._compute_context_coherence(ctx)
        assert fc == pytest.approx(0.5)


# ---------------------------------------------------------------------------
# Overall formula
# ---------------------------------------------------------------------------


class TestOverallFormula:

    def test_formula_correct(self) -> None:
        ctx = _context(regime_conf=0.8, news_conf=0.7, fomc_conf=0.6)
        r1 = ForecastResult("m1", 0.95, (ForecastPoint("d1", 100.0, 95.0, 105.0),), {})
        r2 = ForecastResult("m2", 0.95, (ForecastPoint("d1", 101.0, 96.0, 106.0),), {})
        pkg = _package({"m1": r1, "m2": r2})
        computer = ForecastConfidenceComputer()
        fc = computer.compute(pkg, ctx)

        expected = 0.30 * fc.spread_score + 0.40 * fc.agreement_score + 0.30 * fc.context_coherence
        assert fc.overall == pytest.approx(expected)

    def test_full_scores(self) -> None:
        ctx = _context(regime_conf=1.0, news_conf=1.0, fomc_conf=1.0)
        pt = ForecastPoint("d1", 100.0, 99.9, 100.1)
        r1 = ForecastResult("m1", 0.95, (pt,), {})
        r2 = ForecastResult("m2", 0.95, (pt,), {})
        computer = ForecastConfidenceComputer()
        fc = computer.compute(_package({"m1": r1, "m2": r2}), ctx)
        assert fc.spread_score > 0.99
        assert fc.agreement_score == 1.0
        assert fc.context_coherence == 1.0
        assert fc.overall > 0.99

    def test_zero_scores(self) -> None:
        computer = ForecastConfidenceComputer()
        fc = computer.compute(_package(), _empty_context())
        assert fc.overall == 0.0


# ---------------------------------------------------------------------------
# Integration — via ForecastKnowledge
# ---------------------------------------------------------------------------


class TestIntegration:

    def test_compute_with_forecast_package(self) -> None:
        ctx = _context(regime_conf=0.9, news_conf=0.8, fomc_conf=0.7)
        r1 = ForecastResult("m1", 0.95, (ForecastPoint("d1", 100.0, 95.0, 105.0),
                                          ForecastPoint("d2", 102.0, 97.0, 107.0)), {})
        r2 = ForecastResult("m2", 0.95, (ForecastPoint("d1", 101.0, 96.0, 106.0),
                                          ForecastPoint("d2", 103.0, 98.0, 108.0)), {})
        pkg = ForecastPackage(
            target_variable="CPI",
            context=ctx,
            results={"m1": r1, "m2": r2},
            provenance=_provenance(),
            model_specs=(),
            horizon=2,
        )
        computer = ForecastConfidenceComputer()
        fc = computer.compute(pkg, ctx)
        assert 0.0 <= fc.overall <= 1.0
        assert fc.spread_score > 0
        assert fc.agreement_score > 0
        assert fc.context_coherence == pytest.approx(0.8)
