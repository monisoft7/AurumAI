"""Unit + integration tests for W5 Signal vs Noise Classification."""

import json
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from pre_market.contracts import (
    AnomalyFlag,
    NewsItem,
    OvernightPriceChange,
    PositioningSnapshot,
    PreMarketBriefing,
    RiskSnapshot,
    WatchlistItem,
)
from signal_assessment.assembler import SignalAssessmentAssembler
from signal_assessment.breadth import BreadthChecker
from signal_assessment.classifier import NoiseSignalClassifier
from signal_assessment.contracts import (
    ClassificationLabel,
    ClassifiedObservation,
    CriterionScore,
    SignalAssessment,
)
from signal_assessment.narrative import NarrativeFitScorer
from signal_assessment.persistence import PersistenceTracker
from signal_assessment.volume import VolumeFlowConfirmator


# =========================================================================
# Contract tests
# =========================================================================


class TestCriterionScore:
    def test_to_dict_from_dict_roundtrip(self):
        obj = CriterionScore(
            criterion="persistence",
            score=0.85,
            threshold=0.5,
            passed=True,
            detail="persisted 21d >= signal threshold 21d",
        )
        d = obj.to_dict()
        restored = CriterionScore.from_dict(d)
        assert restored.criterion == obj.criterion
        assert restored.score == obj.score
        assert restored.passed == obj.passed

    def test_from_dict_defaults(self):
        restored = CriterionScore.from_dict({})
        assert restored.criterion == ""
        assert restored.score == 0.0


class TestClassifiedObservation:
    def test_to_dict_from_dict_roundtrip(self):
        obj = ClassifiedObservation(
            observation_id="obs_XAU/USD_20260729",
            source="overnight_price",
            classification="Signal",
            confidence=0.85,
            regime="NORMAL_GROWTH",
            reason="3/5 criteria met",
            evidence=(
                CriterionScore("persistence", 0.8, 0.5, True, "test"),
                CriterionScore("breadth", 0.7, 0.5, True, "test"),
            ),
            instrument="XAU/USD",
            value=1910.0,
            change_pct=0.53,
            change_sigma=1.2,
        )
        d = obj.to_dict()
        restored = ClassifiedObservation.from_dict(d)
        assert restored.observation_id == obj.observation_id
        assert restored.classification == obj.classification
        assert len(restored.evidence) == 2


class TestSignalAssessment:
    def test_minimal_assessment(self):
        sa = SignalAssessment(
            assessment_id="sa_test",
            briefing_id="premarket_test",
            timestamp="2026-07-29T06:00:00",
            regime="NORMAL_GROWTH",
            regime_confidence=0.85,
        )
        assert sa.assessment_id == "sa_test"
        assert sa.signal_count == 0
        assert sa.noise_count == 0

    def test_to_dict_from_dict_roundtrip(self):
        sa = SignalAssessment(
            assessment_id="sa_20260729",
            briefing_id="premarket_20260729",
            timestamp="2026-07-29T06:00:00",
            regime="NORMAL_GROWTH",
            regime_confidence=0.85,
            observations=(
                ClassifiedObservation(
                    observation_id="obs_1",
                    source="overnight_price",
                    classification="Signal",
                    confidence=0.85,
                    regime="NORMAL_GROWTH",
                    reason="test",
                ),
                ClassifiedObservation(
                    observation_id="obs_2",
                    source="news",
                    classification="Noise",
                    confidence=0.7,
                    regime="NORMAL_GROWTH",
                    reason="test",
                ),
            ),
        )
        d = sa.to_dict()
        restored = SignalAssessment.from_dict(d)
        assert restored.assessment_id == sa.assessment_id
        assert restored.signal_count == 1
        assert restored.noise_count == 1

    def test_json_serializable(self):
        sa = SignalAssessment(
            assessment_id="sa_json",
            briefing_id="pm_json",
            timestamp="2026-07-29T06:00:00",
            regime="INFLATIONARY",
            regime_confidence=0.72,
        )
        serialized = json.dumps(sa.to_dict())
        restored = SignalAssessment.from_dict(json.loads(serialized))
        assert restored.regime == "INFLATIONARY"


class TestLabelValues:
    def test_all_labels_valid(self):
        assert ClassificationLabel.SIGNAL.value == "Signal"
        assert ClassificationLabel.NOISE.value == "Noise"
        assert ClassificationLabel.WEAK_SIGNAL.value == "Weak Signal"
        assert ClassificationLabel.WATCH.value == "Watch"
        assert ClassificationLabel.IGNORE.value == "Ignore"


# =========================================================================
# PersistenceTracker tests
# =========================================================================


class TestPersistenceTracker:
    def test_noise_duration_returns_not_passed(self):
        result = PersistenceTracker.evaluate(deviation_days=0.5, instrument_type="ETF")
        assert result.passed is False
        assert result.score <= 0.5

    def test_signal_duration_returns_passed(self):
        result = PersistenceTracker.evaluate(deviation_days=21.0, instrument_type="ETF")
        assert result.passed is True
        assert result.score >= 0.7

    def test_between_noise_and_signal(self):
        result = PersistenceTracker.evaluate(deviation_days=7.0, instrument_type="ETF")
        assert result.criterion == "persistence"

    def test_comex_different_thresholds(self):
        noise = PersistenceTracker.evaluate(deviation_days=5.0, instrument_type="COMEX")
        assert noise.passed is False
        signal = PersistenceTracker.evaluate(deviation_days=25.0, instrument_type="COMEX")
        assert signal.passed is True


# =========================================================================
# BreadthChecker tests
# =========================================================================


class TestBreadthChecker:
    def test_gold_up_dxy_down_confirms(self):
        result = BreadthChecker.evaluate(
            instrument="XAU/USD",
            changes={"XAU/USD": 1.0, "DXY": -0.5, "US10Y Real Yield": -0.3},
        )
        assert result.passed is True

    def test_gold_up_dxy_up_violation(self):
        result = BreadthChecker.evaluate(
            instrument="XAU/USD",
            changes={"XAU/USD": 1.0, "DXY": 0.5, "US10Y Real Yield": -0.3},
        )
        assert result.score < 0.6

    def test_no_correlated_instruments(self):
        result = BreadthChecker.evaluate(
            instrument="UNKNOWN",
            changes={"UNKNOWN": 1.0},
        )
        assert result.passed is False
        assert result.score == 0.0


# =========================================================================
# NarrativeFitScorer tests
# =========================================================================


class TestNarrativeFitScorer:
    def test_matching_headlines_returns_passed(self):
        result = NarrativeFitScorer.evaluate(
            instrument="XAU/USD",
            change_pct=1.5,
            news_headlines=["Gold surges on inflation concerns", "Fed signals rate cut"],
        )
        assert result.passed is True
        assert result.score >= 0.3

    def test_no_matching_headlines(self):
        result = NarrativeFitScorer.evaluate(
            instrument="XAU/USD",
            change_pct=1.5,
            news_headlines=["Tech stocks rally", "Apple releases new iPhone"],
        )
        assert result.passed is False

    def test_no_headlines_available(self):
        result = NarrativeFitScorer.evaluate(
            instrument="XAU/USD",
            change_pct=1.5,
            news_headlines=[],
        )
        assert result.passed is False
        assert "no news headlines" in result.detail

    def test_negligible_move_skips_narrative(self):
        result = NarrativeFitScorer.evaluate(
            instrument="XAU/USD",
            change_pct=0.05,
            news_headlines=["Gold surges"],
        )
        assert result.passed is True


# =========================================================================
# VolumeFlowConfirmator tests
# =========================================================================


class TestVolumeFlowConfirmator:
    def test_no_data_returns_not_passed(self):
        result = VolumeFlowConfirmator.evaluate()
        assert result.passed is False
        assert "no volume/flow data" in result.detail

    def test_volume_surge_confirms(self):
        result = VolumeFlowConfirmator.evaluate(
            change_sigma=2.0,
            volume_change_pct=80.0,
        )
        assert result.passed is True

    def test_etf_accumulating_confirms(self):
        result = VolumeFlowConfirmator.evaluate(
            etf_flow_change_pct=2.5,
            etf_flow_momentum="accumulating",
        )
        assert result.passed is True

    def test_mixed_signals(self):
        result = VolumeFlowConfirmator.evaluate(
            volume_change_pct=5.0,
            open_interest_change_pct=1.0,
            etf_flow_change_pct=-0.5,
        )
        assert isinstance(result.score, float)


# =========================================================================
# NoiseSignalClassifier tests
# =========================================================================


class TestNoiseSignalClassifier:
    def test_signal_with_3_criteria(self):
        classifier = NoiseSignalClassifier()
        label, conf, reason = classifier.classify(
            criteria_scores={
                "persistence": CriterionScore("persistence", 0.8, 0.5, True, "persistent"),
                "breadth": CriterionScore("breadth", 0.7, 0.5, True, "broad"),
                "magnitude": CriterionScore("magnitude", 1.0, 2.0, True, "z=3.0"),
                "narrative_fit": CriterionScore("narrative_fit", 0.0, 0.3, False, ""),
                "volume_flow": CriterionScore("volume_flow", 0.0, 0.5, False, ""),
            },
        )
        assert label == ClassificationLabel.SIGNAL.value
        assert conf >= 0.7

    def test_weak_signal_with_2_criteria(self):
        classifier = NoiseSignalClassifier()
        label, conf, reason = classifier.classify(
            criteria_scores={
                "persistence": CriterionScore("persistence", 0.0, 0.5, False, "not persistent"),
                "breadth": CriterionScore("breadth", 0.7, 0.5, True, "broad"),
                "magnitude": CriterionScore("magnitude", 1.0, 2.0, True, "z=3.0"),
                "narrative_fit": CriterionScore("narrative_fit", 0.0, 0.3, False, ""),
                "volume_flow": CriterionScore("volume_flow", 0.0, 0.5, False, ""),
            },
        )
        assert label == ClassificationLabel.WEAK_SIGNAL.value

    def test_watch_with_1_criteria(self):
        classifier = NoiseSignalClassifier()
        label, conf, reason = classifier.classify(
            criteria_scores={
                "persistence": CriterionScore("persistence", 0.0, 0.5, False, ""),
                "breadth": CriterionScore("breadth", 0.0, 0.5, False, ""),
                "magnitude": CriterionScore("magnitude", 0.67, 2.0, True, "z=2.0"),
                "narrative_fit": CriterionScore("narrative_fit", 0.0, 0.3, False, ""),
                "volume_flow": CriterionScore("volume_flow", 0.0, 0.5, False, ""),
            },
        )
        assert label == ClassificationLabel.WATCH.value

    def test_noise_with_zero_criteria_but_nonzero_z(self):
        classifier = NoiseSignalClassifier()
        label, conf, reason = classifier.classify(
            criteria_scores={
                "persistence": CriterionScore("persistence", 0.0, 0.5, False, ""),
                "breadth": CriterionScore("breadth", 0.0, 0.5, False, ""),
                "magnitude": CriterionScore("magnitude", 0.3, 2.0, False, "z=0.9"),
                "narrative_fit": CriterionScore("narrative_fit", 0.0, 0.3, False, ""),
                "volume_flow": CriterionScore("volume_flow", 0.0, 0.5, False, ""),
            },
        )
        assert label == ClassificationLabel.NOISE.value

    def test_ignore_with_zero_criteria_and_tiny_z(self):
        classifier = NoiseSignalClassifier()
        label, conf, reason = classifier.classify(
            criteria_scores={
                "persistence": CriterionScore("persistence", 0.0, 0.5, False, ""),
                "breadth": CriterionScore("breadth", 0.0, 0.5, False, ""),
                "magnitude": CriterionScore("magnitude", 0.1, 2.0, False, "z=0.3"),
                "narrative_fit": CriterionScore("narrative_fit", 0.0, 0.3, False, ""),
                "volume_flow": CriterionScore("volume_flow", 0.0, 0.5, False, ""),
            },
        )
        assert label == ClassificationLabel.IGNORE.value
        assert conf == 0.9

    def test_signal_with_2_criteria_and_persistence(self):
        classifier = NoiseSignalClassifier()
        label, conf, reason = classifier.classify(
            criteria_scores={
                "persistence": CriterionScore("persistence", 0.8, 0.5, True, "persistent"),
                "breadth": CriterionScore("breadth", 0.0, 0.5, False, ""),
                "magnitude": CriterionScore("magnitude", 1.0, 2.0, True, "z=3.0"),
                "narrative_fit": CriterionScore("narrative_fit", 0.0, 0.3, False, ""),
                "volume_flow": CriterionScore("volume_flow", 0.0, 0.5, False, ""),
            },
        )
        assert label == ClassificationLabel.SIGNAL.value


# =========================================================================
# SignalAssessmentAssembler tests
# =========================================================================


class TestSignalAssessmentAssembler:
    def _make_briefing(self, **overrides) -> PreMarketBriefing:
        return PreMarketBriefing(
            briefing_id=overrides.get("briefing_id", "premarket_test"),
            timestamp=overrides.get("timestamp", "2026-07-29T06:00:00"),
            regime=overrides.get("regime", "NORMAL_GROWTH"),
            regime_confidence=overrides.get("regime_confidence", 0.85),
            overnight_changes=overrides.get("overnight_changes", (
                OvernightPriceChange("XAU/USD", 1900.0, 1910.0, 0.53, 1.2, "APAC"),
                OvernightPriceChange("DXY", 100.0, 99.5, -0.5, 0.8, "APAC"),
            )),
            news_items=overrides.get("news_items", (
                NewsItem("Gold rally continues", "Reuters", "2026-07-29", "positive", 0.85, 0.9),
            )),
            risk_snapshot=overrides.get("risk_snapshot", None),
            positioning_snapshot=overrides.get("positioning_snapshot", PositioningSnapshot(
                cot_z_score=1.5, cot_regime="bullish",
                etf_flow_momentum="accumulating", etf_flow_change_pct=2.3,
                open_interest_change_pct=0.5, gofo_rate=0.12,
            )),
            anomaly_flags=overrides.get("anomaly_flags", ()),
            watchlist=overrides.get("watchlist", ()),
        )

    def test_assemble_returns_assessment(self):
        briefing = self._make_briefing()
        assembler = SignalAssessmentAssembler(regime="NORMAL_GROWTH")
        assessment = assembler.assemble(briefing)
        assert isinstance(assessment, SignalAssessment)
        assert assessment.briefing_id == "premarket_test"
        assert assessment.regime == "NORMAL_GROWTH"

    def test_assemble_creates_observations_for_all_sources(self):
        briefing = self._make_briefing()
        assembler = SignalAssessmentAssembler()
        assessment = assembler.assemble(briefing)
        sources = {o.source for o in assessment.observations}
        assert "overnight_price" in sources
        assert "news" in sources
        assert "positioning" in sources

    def test_assemble_classifies_anomaly_flags(self):
        briefing = self._make_briefing(
            anomaly_flags=(
                AnomalyFlag("two_sigma_move", "medium", "XAU/USD", "2.5sigma move", 2.5, 2.0),
            ),
        )
        assembler = SignalAssessmentAssembler()
        assessment = assembler.assemble(briefing)
        assert "anomaly_flag" in {o.source for o in assessment.observations}

    def test_assemble_returns_some_signals(self):
        briefing = self._make_briefing(
            overnight_changes=(
                OvernightPriceChange("XAU/USD", 1900.0, 1950.0, 2.63, 3.0, "APAC"),
                OvernightPriceChange("DXY", 100.0, 98.0, -2.0, 1.5, "APAC"),
                OvernightPriceChange("US10Y Real Yield", 0.5, 0.48, -4.0, 1.2, "APAC"),
            ),
            news_items=(
                NewsItem("Gold at record high on dollar weakness", "Reuters", "2026-07-29", "positive", 0.9, 0.95),
                NewsItem("DXY falls on Fed rate cut expectations", "Bloomberg", "2026-07-29", "positive", 0.8, 0.9),
            ),
        )
        assembler = SignalAssessmentAssembler(regime="NORMAL_GROWTH")
        assessment = assembler.assemble(briefing)
        assert assessment.signal_count + assessment.weak_signal_count > 0

    def test_json_roundtrip(self):
        briefing = self._make_briefing()
        assembler = SignalAssessmentAssembler()
        assessment = assembler.assemble(briefing)
        serialized = json.dumps(assessment.to_dict())
        restored = SignalAssessment.from_dict(json.loads(serialized))
        assert restored.assessment_id == assessment.assessment_id
        assert len(restored.observations) == len(assessment.observations)


# =========================================================================
# Integration test: W3 -> W5 pipeline
# =========================================================================


def test_w3_to_w4_integration():
    from pre_market.briefing_assembler import PreMarketBriefingAssembler

    briefing = PreMarketBriefingAssembler(
        regime="NORMAL_GROWTH",
        regime_confidence=0.85,
    ).assemble()

    assembler = SignalAssessmentAssembler(regime=briefing.regime)
    assessment = assembler.assemble(briefing)

    assert isinstance(assessment, SignalAssessment)
    assert assessment.briefing_id == briefing.briefing_id
    assert assessment.regime == briefing.regime
    assert len(assessment.observations) > 0

    for obs in assessment.observations:
        assert obs.classification in {
            ClassificationLabel.SIGNAL.value,
            ClassificationLabel.WEAK_SIGNAL.value,
            ClassificationLabel.WATCH.value,
            ClassificationLabel.NOISE.value,
            ClassificationLabel.IGNORE.value,
        }
        assert 0.0 <= obs.confidence <= 1.0
        assert obs.regime == briefing.regime
        assert obs.reason
        assert isinstance(obs.evidence, tuple)


def test_w4_orchestration_stage():
    from orchestration.stages import _signal_assessment
    from pre_market.contracts import PreMarketBriefing

    params: dict = {}
    briefing = PreMarketBriefing(
        briefing_id="stage_test",
        timestamp="2026-07-29T06:00:00",
        regime="NORMAL_GROWTH",
        regime_confidence=0.85,
        overnight_changes=(
            OvernightPriceChange("XAU/USD", 1900.0, 1910.0, 0.53, 1.2, "APAC"),
        ),
        news_items=(
            NewsItem("Gold steady", "Reuters", "2026-07-29", "neutral", 0.5, 0.3),
        ),
    )

    result = _signal_assessment(params, {"pre_market_scan": briefing.to_dict()})
    assert isinstance(result, SignalAssessment)
    assert result.briefing_id == "stage_test"
    assert len(result.observations) > 0
