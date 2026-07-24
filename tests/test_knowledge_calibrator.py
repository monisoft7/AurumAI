from __future__ import annotations

from knowledge.integrity.knowledge_record import KnowledgeRecord
from knowledge.integrity.provenance import Provenance
from knowledge.learning.feedback import KnowledgeFeedback
from knowledge.evolution.knowledge_calibrator import KnowledgeCalibrator


def _make_record(confidence: float = 0.8, provenance: Provenance | None = None) -> KnowledgeRecord:
    return KnowledgeRecord(
        knowledge_id="cpi_gold_high_5D",
        event_type="CPI",
        asset="GOLD",
        condition={"pressure": "high"},
        horizon_days=5,
        sample_count=100,
        positive_return_rate_pct=60.0,
        negative_return_rate_pct=40.0,
        up_direction_rate_pct=50.0,
        down_direction_rate_pct=30.0,
        flat_direction_rate_pct=20.0,
        average_return_pct=1.5,
        median_return_pct=1.0,
        min_return_pct=-2.0,
        max_return_pct=5.0,
        first_event_date="2026-01-01",
        last_event_date="2026-06-01",
        bias="bullish",
        confidence=confidence,
        explanation="For CPI condition pressure=high, 100 historical lessons...",
        provenance=provenance,
    )


def _make_feedback(
    suggested: float = 0.85,
    accuracy_rate: float = 0.75,
    feedback_id: str = "fb_cpi_1",
) -> KnowledgeFeedback:
    return KnowledgeFeedback(
        feedback_id=feedback_id,
        source_record_ids=("learn_1", "learn_2"),
        event_type="CPI",
        condition={"pressure": "high"},
        horizon_days=5,
        current_confidence=0.8,
        suggested_confidence=suggested,
        accuracy_rate=accuracy_rate,
        correct_count=3,
        sample_count=4,
        explanation="Feedback for CPI: 3/4 records correct (accuracy: 75.0%, trend: improving).",
    )


class TestKnowledgeCalibrator:
    def test_calibrate_updates_confidence(self) -> None:
        cal = KnowledgeCalibrator()
        kr = _make_record(confidence=0.8)
        fb = _make_feedback(suggested=0.85)

        result = cal.calibrate(kr, fb)

        assert result.confidence == 0.85

    def test_calibrate_creates_provenance(self) -> None:
        cal = KnowledgeCalibrator()
        kr = _make_record()
        fb = _make_feedback()

        result = cal.calibrate(kr, fb)

        assert result.provenance is not None
        assert result.provenance.created_by == "knowledge_calibrator"
        assert result.provenance.previous_version_id == "cpi_gold_high_5D"

    def test_calibrate_bumps_version(self) -> None:
        cal = KnowledgeCalibrator()
        prov = Provenance(
            created_at="2026-01-01T00:00:00",
            created_by="lesson_summary",
            entity_version="1.0.0",
        )
        kr = _make_record(provenance=prov)
        fb = _make_feedback()

        result = cal.calibrate(kr, fb)

        assert result.provenance is not None
        assert result.provenance.entity_version == "1.0.1"
        assert result.provenance.previous_version_id == "cpi_gold_high_5D"

    def test_calibrate_preserves_other_fields(self) -> None:
        cal = KnowledgeCalibrator()
        kr = _make_record(confidence=0.8)
        fb = _make_feedback(suggested=0.75)

        result = cal.calibrate(kr, fb)

        assert result.knowledge_id == "cpi_gold_high_5D"
        assert result.event_type == "CPI"
        assert result.asset == "GOLD"
        assert result.horizon_days == 5
        assert result.sample_count == 100
        assert result.average_return_pct == 1.5
        assert result.bias == "bullish"

    def test_calibrate_updates_explanation(self) -> None:
        cal = KnowledgeCalibrator()
        kr = _make_record()
        fb = _make_feedback(suggested=0.90, accuracy_rate=0.80, feedback_id="fb_test")

        result = cal.calibrate(kr, fb)

        assert "[Calibrated via fb_test:" in result.explanation
        assert "0.8" in result.explanation
        assert "0.9" in result.explanation
        assert "accuracy_rate=0.8" in result.explanation

    def test_calibrate_does_not_mutate_original(self) -> None:
        cal = KnowledgeCalibrator()
        kr = _make_record(confidence=0.8)
        fb = _make_feedback(suggested=0.90)

        original_confidence = kr.confidence
        original_explanation = kr.explanation

        cal.calibrate(kr, fb)

        assert kr.confidence == original_confidence
        assert kr.explanation == original_explanation

    def test_calibrate_without_provenance_starts_v1(self) -> None:
        cal = KnowledgeCalibrator()
        kr = _make_record(provenance=None)
        fb = _make_feedback()

        result = cal.calibrate(kr, fb)

        assert result.provenance is not None
        assert result.provenance.entity_version == "0.0.1"

    def test_calibrate_same_confidence_still_creates_new_record(self) -> None:
        cal = KnowledgeCalibrator()
        kr = _make_record(confidence=0.8)
        fb = _make_feedback(suggested=0.8)

        result = cal.calibrate(kr, fb)

        assert result.confidence == 0.8
        assert result.provenance is not None
        assert result.knowledge_id == kr.knowledge_id
        assert result is not kr

    def test_calibrate_stores_feedback_id_in_provenance_metadata(self) -> None:
        cal = KnowledgeCalibrator()
        kr = _make_record()
        fb = _make_feedback(feedback_id="fb_cpi_2026")

        result = cal.calibrate(kr, fb)

        assert result.provenance is not None
        assert result.provenance.metadata.get("calibration_source") == "fb_cpi_2026"

    def test_calibrate_bump_version_no_dot_uses_default(self) -> None:
        cal = KnowledgeCalibrator()
        prov = Provenance(
            created_at="2026-01-01T00:00:00",
            created_by="test",
            entity_version="1",
        )
        kr = _make_record(provenance=prov)
        fb = _make_feedback()

        result = cal.calibrate(kr, fb)

        assert result.provenance is not None
        assert result.provenance.entity_version == "1.0.0"
