from __future__ import annotations

from pathlib import Path

from knowledge.integrity.knowledge_record import KnowledgeRecord
from knowledge.evolution.applicator import FeedbackApplicator
from simulation.models import EventRunResult


def _make_result(
    event_type: str = "CPI",
    decision: str | None = "POSITIVE",
    confidence: float = 0.75,
    correct: bool | None = True,
    actual_return: float | None = 2.0,
) -> EventRunResult:
    return EventRunResult(
        event_type=event_type,
        event_date_min="2026-01-01",
        event_date_max="2026-01-01",
        event_count=1,
        success=True,
        execution_time_ms=10.0,
        cache_hits=0,
        checkpoints_used=0,
        decision=decision,
        forecast_confidence=confidence,
        decision_correct=correct,
        decision_actual_return_pct=actual_return,
    )


def _make_knowledge_record(event_type: str = "CPI") -> KnowledgeRecord:
    return KnowledgeRecord(
        knowledge_id=f"{event_type}_gold_high_5D",
        event_type=event_type,
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
        confidence=0.8,
        explanation=f"For {event_type} condition pressure=high, 100 historical lessons...",
    )


class TestFeedbackApplicator:
    def test_empty_results_returns_empty(self) -> None:
        app = FeedbackApplicator()
        result = app.apply([], [_make_knowledge_record()])

        assert result == []

    def test_no_scored_results_returns_empty(self) -> None:
        app = FeedbackApplicator()
        results = [_make_result(decision=None, correct=None, actual_return=None)]
        result = app.apply(results, [_make_knowledge_record()])

        assert result == []

    def test_single_type_single_result(self) -> None:
        app = FeedbackApplicator()
        results = [_make_result()]
        krs = [_make_knowledge_record()]

        updated = app.apply(results, krs)

        assert len(updated) == 1
        assert updated[0].event_type == "CPI"
        expected = round(0.6 * 0.75 + 0.4 * 1.0, 6)
        assert updated[0].confidence == expected

    def test_matching_event_type_only(self) -> None:
        app = FeedbackApplicator()
        results = [_make_result(event_type="CPI")]
        krs = [
            _make_knowledge_record(event_type="CPI"),
            _make_knowledge_record(event_type="FOMC"),
        ]

        updated = app.apply(results, krs)

        assert len(updated) == 1
        assert updated[0].event_type == "CPI"

    def test_multiple_event_types(self) -> None:
        app = FeedbackApplicator()
        results = [
            _make_result(event_type="CPI", correct=True, actual_return=2.0),
            _make_result(event_type="FOMC", correct=False, actual_return=-1.0),
        ]
        krs = [
            _make_knowledge_record(event_type="CPI"),
            _make_knowledge_record(event_type="FOMC"),
        ]

        updated = app.apply(results, krs)

        assert len(updated) == 2
        types = {r.event_type for r in updated}
        assert types == {"CPI", "FOMC"}

    def test_multiple_records_per_event_type(self) -> None:
        app = FeedbackApplicator()
        results = [
            _make_result(event_type="CPI", correct=True, actual_return=2.0),
            _make_result(event_type="CPI", correct=False, actual_return=-1.0),
            _make_result(event_type="CPI", correct=True, actual_return=1.5),
        ]
        krs = [_make_knowledge_record(event_type="CPI")]

        updated = app.apply(results, krs)

        assert len(updated) == 1
        assert updated[0].event_type == "CPI"

    def test_original_records_not_mutated(self) -> None:
        app = FeedbackApplicator()
        results = [_make_result()]
        kr = _make_knowledge_record()
        original_conf = kr.confidence

        app.apply(results, [kr])

        assert kr.confidence == original_conf

    def test_deterministic_output(self) -> None:
        app = FeedbackApplicator()
        results = [
            _make_result(event_type="CPI", correct=True, actual_return=2.0),
            _make_result(event_type="CPI", correct=False, actual_return=-1.0),
        ]
        krs = [_make_knowledge_record(event_type="CPI")]

        r1 = app.apply(results, krs)
        r2 = app.apply(results, krs)

        assert len(r1) == len(r2)
        assert r1[0].confidence == r2[0].confidence
        assert r1[0].explanation == r2[0].explanation

    def test_provenance_chain_on_calibrated_record(self) -> None:
        app = FeedbackApplicator()
        results = [_make_result()]
        kr = _make_knowledge_record()

        updated = app.apply(results, [kr])

        assert len(updated) == 1
        prov = updated[0].provenance
        assert prov is not None
        assert prov.created_by == "knowledge_calibrator"
        assert prov.previous_version_id == kr.knowledge_id

    def test_unscored_results_are_filtered(self) -> None:
        app = FeedbackApplicator()
        results = [
            _make_result(decision="POSITIVE", correct=True, actual_return=2.0),
            _make_result(decision=None, correct=None, actual_return=None),
            _make_result(decision="NEUTRAL", correct=True, actual_return=0.0),
        ]
        krs = [_make_knowledge_record()]

        updated = app.apply(results, krs)

        assert len(updated) == 1

    def test_versioned_store_persists(self, tmp_path: Path) -> None:
        app = FeedbackApplicator(versioned_store_dir=tmp_path)
        results = [_make_result()]
        kr = _make_knowledge_record()

        updated = app.apply(results, [kr])

        assert len(updated) == 1
        store_dir = tmp_path / kr.knowledge_id
        assert store_dir.exists()
        version_files = list(store_dir.glob("*.json"))
        assert len(version_files) == 1

    def test_versioned_store_increments_on_multiple_applies(self, tmp_path: Path) -> None:
        app = FeedbackApplicator(versioned_store_dir=tmp_path)
        results = [_make_result()]
        kr = _make_knowledge_record()

        app.apply(results, [kr])
        app.apply(results, [kr])

        store_dir = tmp_path / kr.knowledge_id
        version_files = list(store_dir.glob("*.json"))
        assert len(version_files) == 2
