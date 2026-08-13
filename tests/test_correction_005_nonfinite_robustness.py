""" Correction 005: non-finite historical values must not leak NaN or a
misleading 0.0 into W3-W8 decision material.

Regression for the DFII10 (US10Y Real Yield) runtime case: near-zero 2011
readings produce +/-inf pct_change values (NaN std) that previously poisoned
change_sigma; the strict 0.0 fallback also silently misrepresented
unavailable measurements as zero-movement.
"""

import math

import numpy as np
import pandas as pd
import pytest

from evidence_collection.collector import EvidenceCollector
from evidence_collection.contracts import Evidence
from evidence_collection.strength import EvidenceStrengthComputer
from evidence_reasoning.contracts import EvidenceSet
from evidence_reasoning.weighter import EvidenceWeighter
from pre_market.overnight_fetcher import OvernightDataFetcher
from signal_assessment.contracts import (
    ClassifiedObservation,
    CriterionScore,
    SignalAssessment,
)


def _real_yield_style_series():
    """DFII10-like closes; the zero row forces pct_change -> +inf."""
    return pd.Series([2.47, 2.43, 2.40, 2.41, 2.43, 0.0, 2.43, 2.43])


def _observation(change_sigma):
    return ClassifiedObservation(
        observation_id="obs_corr005",
        source="overnight_price",
        classification="Signal",
        confidence=0.85,
        regime="NORMAL_GROWTH",
        reason="correction-005",
        evidence=(
            CriterionScore("persistence", 0.8, 0.5, True, "persistent"),
            CriterionScore("breadth", 0.7, 0.5, True, "broad"),
            CriterionScore("magnitude", 0.0, 2.0, False, "z=nan"),
            CriterionScore("narrative_fit", 0.4, 0.3, True, "match"),
            CriterionScore("volume_flow", 0.0, 0.5, False, "no volume"),
        ),
        instrument="US10Y Real Yield",
        value=2.43,
        change_pct=0.0,
        change_sigma=change_sigma,
    )


def _assessment(change_sigma):
    return SignalAssessment(
        assessment_id="sa_corr005",
        briefing_id="briefing_corr005",
        timestamp="2026-07-29T06:00:00",
        regime="NORMAL_GROWTH",
        regime_confidence=0.85,
        observations=(_observation(change_sigma),),
    )


def _evidence(recency):
    return Evidence(
        evidence_id="ev_corr005",
        source_kr_id="KR-001",
        source_kr_node_id="KR-001",
        event_type="REAL_YIELD",
        condition={"instrument": "US10Y Real Yield"},
        bias="bullish",
        base_confidence=0.6,
        regime_weight=1.0,
        composite_weight=0.6,
        explanation="correction-005",
        regime="NORMAL_GROWTH",
        source_label="overnight_price",
        supporting_observation_ids=("obs_corr005",),
        temporal_recency=recency,
    )


class TestSigmaFiniteUnderInfHistory:
    def test_inf_history_sigma_is_finite(self):
        sigma = OvernightDataFetcher._compute_sigma(_real_yield_style_series(), 2.43, 2.43)
        assert math.isfinite(sigma)

    def test_zero_move_zero_sigma_finite(self):
        series = pd.Series([2.47, 2.43, 2.40, 2.41, 2.43, 2.40, 2.43, 2.43])
        sigma = OvernightDataFetcher._compute_sigma(series, 2.43, 2.43)
        assert sigma == 0.0

    def test_finite_history_identical_to_previous_formula(self):
        series = pd.Series([100.0, 101.0, 99.0, 102.0, 100.5, 103.0, 101.5])
        prev, curr = 100.0, 101.0
        single_return = (curr - prev) / abs(prev)
        expected = float(single_return / series.pct_change().dropna().std())
        sigma = OvernightDataFetcher._compute_sigma(series, prev, curr)
        assert sigma == pytest.approx(expected)


class TestSigmaUnavailableState:
    def test_insufficient_observations_unavailable(self):
        sigma = OvernightDataFetcher._compute_sigma(pd.Series([92.1, 92.5]), 92.1, 92.5)
        assert math.isnan(sigma)

    def test_degenerate_variance_unavailable(self):
        series = pd.Series([100.0, 100.0, 100.0, 100.0, 100.0])
        sigma = OvernightDataFetcher._compute_sigma(series, 100.0, 100.0)
        assert math.isnan(sigma)

    def test_insufficient_finite_returns_unavailable(self):
        series = pd.Series([100.0, 0.0, 102.0, 103.0, 104.0])
        sigma = OvernightDataFetcher._compute_sigma(series, 103.0, 104.0)
        assert math.isnan(sigma)


class TestCollectorWiring:
    def test_unavailable_sigma_maps_to_nan_recency(self):
        collection = EvidenceCollector().collect(_assessment(float("nan")))
        assert collection.evidence_count == 1
        assert math.isnan(collection.items[0].temporal_recency)

    def test_finite_sigma_maps_to_finite_recency(self):
        collection = EvidenceCollector().collect(_assessment(2.0))
        assert collection.evidence_count == 1
        recency = collection.items[0].temporal_recency
        assert math.isfinite(recency)
        assert recency == pytest.approx(1.0 / (1.0 + 2.0))


class TestUnavailableStateNotSilentlyZeroed:
    def test_weight_finite_and_positive(self):
        ev = _evidence(float("nan"))
        ev_set = EvidenceSet(
            set_id="es_corr005",
            event_type="REAL_YIELD",
            bias="bullish",
            evidence_ids=(ev.evidence_id,),
        )
        result = EvidenceWeighter().weight_set(ev_set, [ev])
        assert math.isfinite(result.net_institutional_weight)
        assert result.net_institutional_weight > 0.0
        assert result.net_institutional_weight != 0.0

    def test_strength_finite(self):
        strength = EvidenceStrengthComputer.compute_strength(_evidence(float("nan")))
        assert math.isfinite(strength)
        assert strength > 0.0


class TestAssemblerMagnitudeGuard:
    def test_magnitude_score_finite_when_sigma_unavailable(self):
        from pre_market.contracts import OvernightPriceChange, PreMarketBriefing
        from signal_assessment.assembler import SignalAssessmentAssembler

        change = OvernightPriceChange(
            instrument="US10Y Real Yield",
            previous_close=2.43,
            current_price=2.43,
            change_pct=0.0,
            change_sigma=float("nan"),
            session="asia",
        )
        briefing = PreMarketBriefing(
            briefing_id="b_corr005",
            timestamp="2026-07-29T06:00:00",
            regime="NORMAL_GROWTH",
            regime_confidence=0.85,
            overnight_changes=(change,),
        )
        assessment = SignalAssessmentAssembler(regime="NORMAL_GROWTH").assemble(briefing)
        mag = next(
            c for o in assessment.observations for c in o.evidence
            if c.criterion == "magnitude"
        )
        assert math.isfinite(mag.score)
        assert mag.passed is False
        assert mag.threshold == pytest.approx(2.0)

    def test_magnitude_passed_true_for_big_finite_sigma(self):
        from pre_market.contracts import OvernightPriceChange, PreMarketBriefing
        from signal_assessment.assembler import SignalAssessmentAssembler

        change = OvernightPriceChange(
            instrument="XAU/USD",
            previous_close=100.0,
            current_price=103.0,
            change_pct=3.0,
            change_sigma=2.5,
            session="asia",
        )
        briefing = PreMarketBriefing(
            briefing_id="b_corr005b",
            timestamp="2026-07-29T06:00:00",
            regime="NORMAL_GROWTH",
            regime_confidence=0.85,
            overnight_changes=(change,),
        )
        assessment = SignalAssessmentAssembler(regime="NORMAL_GROWTH").assemble(briefing)
        mag = next(
            c for o in assessment.observations for c in o.evidence
            if c.criterion == "magnitude"
        )
        assert math.isfinite(mag.score)
        assert mag.passed is True
        assert mag.score == pytest.approx(min(2.5 / 3.0, 1.0))


class TestThresholdsAndContractsUnchanged:
    def test_weighting_factors_unchanged(self):
        assert EvidenceWeighter.WEIGHT_RECENCY_FACTOR == pytest.approx(0.3)
        assert EvidenceWeighter.WEIGHT_CONFIDENCE_FACTOR == pytest.approx(0.5)
        assert EvidenceWeighter.WEIGHT_PROVENANCE_FACTOR == pytest.approx(0.2)

    def test_persistence_thresholds_unchanged(self):
        from signal_assessment.persistence import NOISE_FILTERS, PERSISTENCE_THRESHOLDS
        assert NOISE_FILTERS["gold_real_yield"]["signal_days"] == 30
        assert PERSISTENCE_THRESHOLDS["gold_real_yield"] == pytest.approx(0.6)

    def test_volume_threshold_unchanged(self):
        from signal_assessment.volume import ETF_FLOW_THRESHOLD_PCT
        assert ETF_FLOW_THRESHOLD_PCT == pytest.approx(1.0)

    def test_change_sigma_remains_plain_float(self):
        assert isinstance(_observation(1.2).change_sigma, float)
        assert isinstance(_observation(float("nan")).change_sigma, float)
