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

    def test_anomaly_distinct_template_violations_get_distinct_ids(self):
        briefing = self._make_briefing(
            anomaly_flags=(
                AnomalyFlag(
                    "template_violation", "high", "XAU/USD",
                    "Gold and DXY moving opposite (negative correlation expected)",
                    1.9, 0.0,
                ),
                AnomalyFlag(
                    "template_violation", "high", "XAU/USD",
                    "Gold and real yields co-move (negative correlation expected)",
                    1.5, 0.0,
                ),
            ),
        )
        assembler = SignalAssessmentAssembler()
        assessment = assembler.assemble(briefing)
        anomaly_obs = [o for o in assessment.observations if o.source == "anomaly_flag"]
        assert len(anomaly_obs) == 2
        assert len({o.observation_id for o in anomaly_obs}) == 2
        assert {o.observation_id for o in anomaly_obs} == {
            "obs_anomaly_XAU/USD_template_violation_gold_and_dxy_moving_opposite_negative_correlation_expected",
            "obs_anomaly_XAU/USD_template_violation_gold_and_real_yields_co_move_negative_correlation_expected",
        }

    def test_anomaly_identical_flags_share_observation_id(self):
        flag = AnomalyFlag(
            "template_violation", "high", "XAU/USD",
            "Gold and DXY moving opposite (negative correlation expected)",
            1.9, 0.0,
        )
        briefing = self._make_briefing(anomaly_flags=(flag, flag))
        assembler = SignalAssessmentAssembler()
        assessment = assembler.assemble(briefing)
        anomaly_obs = [o for o in assessment.observations if o.source == "anomaly_flag"]
        assert len(anomaly_obs) == 2
        assert len({o.observation_id for o in anomaly_obs}) == 1

    def test_anomaly_classification_and_criteria_unchanged(self):
        briefing = self._make_briefing(
            anomaly_flags=(
                AnomalyFlag(
                    "template_violation", "high", "XAU/USD",
                    "Gold and DXY moving opposite (negative correlation expected)",
                    1.9, 0.0,
                ),
            ),
        )
        assembler = SignalAssessmentAssembler()
        assessment = assembler.assemble(briefing)
        obs = next(o for o in assessment.observations if o.source == "anomaly_flag")
        assert obs.observation_id == (
            "obs_anomaly_XAU/USD_template_violation_"
            "gold_and_dxy_moving_opposite_negative_correlation_expected"
        )
        assert obs.classification == ClassificationLabel.WATCH.value
        assert obs.confidence == 0.3
        criteria = {c.criterion: c for c in obs.evidence}
        assert criteria["persistence"].passed
        assert criteria["persistence"].score == 1.0
        assert criteria["magnitude"].score == pytest.approx(min(1.9 / 3.0, 1.0))
        assert not criteria["magnitude"].passed
        assert criteria["breadth"].score == 0.0
        assert not criteria["breadth"].passed
        assert criteria["narrative_fit"].score == 0.0
        assert not criteria["narrative_fit"].passed
        assert criteria["volume_flow"].score == 0.0
        assert not criteria["volume_flow"].passed

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

    def test_positioning_stub_classified_ignore(self):
        briefing = self._make_briefing(
            positioning_snapshot=PositioningSnapshot(
                cot_z_score=0.0, cot_regime="neutral",
                etf_flow_momentum="stable", etf_flow_change_pct=0.0,
                open_interest_change_pct=0.0, gofo_rate=0.0,
            ),
        )
        assembler = SignalAssessmentAssembler()
        assessment = assembler.assemble(briefing)
        positioning_obs = next(o for o in assessment.observations if o.source == "positioning")
        assert positioning_obs.classification == ClassificationLabel.IGNORE.value

    def test_positioning_genuine_etf_flow_not_ignored(self):
        briefing = self._make_briefing(
            positioning_snapshot=PositioningSnapshot(
                cot_z_score=1.5, cot_regime="bullish",
                etf_flow_momentum="accumulating", etf_flow_change_pct=2.3,
                open_interest_change_pct=0.5, gofo_rate=0.12,
            ),
        )
        assembler = SignalAssessmentAssembler()
        assessment = assembler.assemble(briefing)
        positioning_obs = next(o for o in assessment.observations if o.source == "positioning")
        assert positioning_obs.classification != ClassificationLabel.IGNORE.value

    def test_persistence_uses_real_days(self):
        briefing = self._make_briefing(
            overnight_changes=(
                OvernightPriceChange("XAU/USD", 1900.0, 1912.0, 0.63, 3.0, "APAC", 16.0),
            ),
            news_items=(),
        )
        assembler = SignalAssessmentAssembler()
        assessment = assembler.assemble(briefing)
        obs = next(o for o in assessment.observations if o.source == "overnight_price")
        persistence = next(c for c in obs.evidence if c.criterion == "persistence")
        assert persistence.passed
        assert "16d" in persistence.detail

    def test_signal_reachable_with_persistent_move(self):
        briefing = self._make_briefing(
            overnight_changes=(
                OvernightPriceChange("XAU/USD", 1900.0, 1950.0, 2.63, 3.0, "APAC", 16.0),
                OvernightPriceChange("DXY", 100.0, 98.0, -2.0, 1.5, "APAC"),
            ),
            news_items=(),
        )
        assembler = SignalAssessmentAssembler()
        assessment = assembler.assemble(briefing)
        xau_obs = next(o for o in assessment.observations if o.instrument == "XAU/USD")
        assert xau_obs.classification == ClassificationLabel.SIGNAL.value
        # 4/5 criteria pass (persistence, breadth, magnitude, and now the
        # wired ETF flow volume_flow) -> confidence 0.9.
        assert xau_obs.confidence == 0.9

    def test_one_day_noise_remains_watch(self):
        briefing = self._make_briefing(
            overnight_changes=(
                OvernightPriceChange("XAU/USD", 1900.0, 1950.0, 2.63, 1.2, "APAC", 1.0),
                OvernightPriceChange("DXY", 100.0, 98.0, -2.0, 1.5, "APAC"),
            ),
            # No volume/flow producer data -> the wire presents no data
            # and the one-day move stays a Watch, never a Signal.
            positioning_snapshot=None,
            news_items=(),
        )
        assembler = SignalAssessmentAssembler()
        assessment = assembler.assemble(briefing)
        xau_obs = next(o for o in assessment.observations if o.instrument == "XAU/USD")
        assert xau_obs.classification == ClassificationLabel.WATCH.value
        assert xau_obs.confidence == 0.3

    # ------------------------------------------------------------------
    # Correction #1 regression tests: overnight volume_flow wiring
    # (the existing PositioningDataFetcher data must reach the existing
    # VolumeFlowConfirmator for gold-class overnight observations).
    # ------------------------------------------------------------------

    def test_overnight_volume_producer_reaches_confirmator(self):
        briefing = self._make_briefing(
            overnight_changes=(
                OvernightPriceChange("XAU/USD", 1900.0, 1910.0, 0.53, 1.2, "APAC"),
            ),
            news_items=(),
        )
        mock_volume = MagicMock(spec=VolumeFlowConfirmator)
        mock_volume.evaluate.return_value = CriterionScore("volume_flow", 0.5, 0.5, False, "mock")
        assembler = SignalAssessmentAssembler(volume_confirmator=mock_volume)
        assembler.assemble(briefing)
        flow_calls = [
            call for call in mock_volume.evaluate.call_args_list
            if "change_sigma" in call.kwargs and "etf_flow_change_pct" in call.kwargs
        ]
        assert len(flow_calls) == 1
        assert flow_calls[0].kwargs["change_sigma"] == 1.2
        assert flow_calls[0].kwargs["etf_flow_change_pct"] == 2.3
        assert flow_calls[0].kwargs["etf_flow_momentum"] == "accumulating"
        assert flow_calls[0].kwargs["open_interest_change_pct"] == 0.5

    def test_overnight_volume_flow_not_forced_false_with_valid_data(self):
        briefing = self._make_briefing(
            overnight_changes=(
                OvernightPriceChange("XAU/USD", 1900.0, 1910.0, 0.53, 1.2, "APAC"),
            ),
            news_items=(),
        )
        assembler = SignalAssessmentAssembler()
        assessment = assembler.assemble(briefing)
        obs = next(o for o in assessment.observations if o.source == "overnight_price")
        volume = next(c for c in obs.evidence if c.criterion == "volume_flow")
        assert volume.passed is True
        assert volume.score >= 0.5
        assert "ETF" in volume.detail

    def test_overnight_volume_flow_unchanged_without_snapshot(self):
        briefing = self._make_briefing(
            overnight_changes=(
                OvernightPriceChange("XAU/USD", 1900.0, 1910.0, 0.53, 1.2, "APAC"),
            ),
            positioning_snapshot=None,
            news_items=(),
        )
        assembler = SignalAssessmentAssembler()
        assessment = assembler.assemble(briefing)
        obs = next(o for o in assessment.observations if o.source == "overnight_price")
        volume = next(c for c in obs.evidence if c.criterion == "volume_flow")
        assert volume.passed is False
        assert volume.score == 0.0
        assert "no volume/flow data available" in volume.detail

    def test_overnight_volume_flow_unchanged_with_stub_level_data(self):
        briefing = self._make_briefing(
            overnight_changes=(
                OvernightPriceChange("XAU/USD", 1900.0, 1910.0, 0.53, 1.2, "APAC"),
            ),
            positioning_snapshot=PositioningSnapshot(
                cot_z_score=0.0, cot_regime="neutral",
                etf_flow_momentum="stable", etf_flow_change_pct=0.0,
                open_interest_change_pct=0.0, gofo_rate=0.0,
            ),
            news_items=(),
        )
        assembler = SignalAssessmentAssembler()
        assessment = assembler.assemble(briefing)
        obs = next(o for o in assessment.observations if o.source == "overnight_price")
        volume = next(c for c in obs.evidence if c.criterion == "volume_flow")
        assert volume.passed is False
        assert volume.score == 0.0
        assert "no volume/flow data available" in volume.detail

    def test_overnight_volume_flow_not_misapplied_to_non_gold(self):
        briefing = self._make_briefing(
            overnight_changes=(
                OvernightPriceChange("EUR/USD", 1.09, 1.088, -0.3, 1.2, "APAC"),
            ),
            news_items=(),
        )
        assembler = SignalAssessmentAssembler()
        assessment = assembler.assemble(briefing)
        obs = next(o for o in assessment.observations if o.source == "overnight_price")
        volume = next(c for c in obs.evidence if c.criterion == "volume_flow")
        assert volume.passed is False
        assert volume.score == 0.0
        assert "no volume/flow data available" in volume.detail

    def test_volume_wiring_leaves_other_criteria_unchanged(self):
        def non_volume_criteria(snapshot):
            briefing = self._make_briefing(
                overnight_changes=(
                    OvernightPriceChange("XAU/USD", 1900.0, 1910.0, 0.53, 1.2, "APAC"),
                ),
                positioning_snapshot=snapshot,
                news_items=(),
            )
            assessment = SignalAssessmentAssembler().assemble(briefing)
            obs = next(o for o in assessment.observations if o.source == "overnight_price")
            return {
                c.criterion: (c.score, c.passed, c.detail)
                for c in obs.evidence if c.criterion != "volume_flow"
            }

        with_snapshot = non_volume_criteria(self._make_briefing().positioning_snapshot)
        without_snapshot = non_volume_criteria(None)
        assert with_snapshot == without_snapshot
        assert set(with_snapshot) == {"persistence", "breadth", "magnitude", "narrative_fit"}


# =========================================================================
# Integration test: W3 -> W5 pipeline
# =========================================================================


class _StubOvernightFetcher:
    def fetch_all(self, session="APAC"):
        return {
            "overnight_changes": [
                OvernightPriceChange(
                    instrument="XAU/USD",
                    previous_close=1900.0,
                    current_price=1910.0,
                    change_pct=0.5263,
                    change_sigma=1.2,
                    session=session,
                    persistence_days=2.0,
                )
            ],
            "yield_freshness": {},
            "fetch_errors": {},
        }


class _StubPositioningFetcher:
    def fetch(self):
        return PositioningSnapshot(
            cot_z_score=0.0,
            cot_regime="unavailable",
            etf_flow_momentum="stable",
            etf_flow_change_pct=0.0,
            open_interest_change_pct=0.0,
            gofo_rate=0.0,
            timestamp="2026-08-25T12:00:00+00:00",
            availability={
                "cot": "unavailable_no_data_source",
                "etf_flow": "available",
                "open_interest": "available",
                "gofo": "unavailable_no_data_source",
            },
        )


class _StubNewsIngestion:
    def ingest_with_status(self):
        return [], "no_articles"


def test_w3_to_w4_integration():
    from pre_market.briefing_assembler import PreMarketBriefingAssembler

    briefing = PreMarketBriefingAssembler(
        overnight_fetcher=_StubOvernightFetcher(),
        news_ingestion=_StubNewsIngestion(),
        positioning_fetcher=_StubPositioningFetcher(),
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
