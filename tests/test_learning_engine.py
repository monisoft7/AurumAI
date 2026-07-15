import json
from pathlib import Path

import pytest

from knowledge.decision.context import DecisionContext
from knowledge.decision.decision import (
    Decision,
    DECISION_STRONG_POSITIVE,
    DECISION_POSITIVE,
    DECISION_NEUTRAL,
    DECISION_NEGATIVE,
    DECISION_STRONG_NEGATIVE,
)
from knowledge.learning.record import LearningRecord
from knowledge.learning.session import LearningSession
from knowledge.learning.feedback import KnowledgeFeedback
from knowledge.learning.engine import LearningEngine
from knowledge.learning.repository import LearningRepository


# ── Fixtures ────────────────────────────────────────────────────────────────

def make_decision(decision_type: str = DECISION_POSITIVE, confidence: float = 0.75,
                  event_type: str = "CPI") -> Decision:
    return Decision(
        decision_id=f"dec_reason_{event_type}",
        decision_type=decision_type,
        confidence=confidence,
        reasoning_chain_id=f"reason_{event_type}",
        evidence_count=3,
        explanation=f"Decision {decision_type} for {event_type}.",
        context=DecisionContext(event_type=event_type, query="outlook"),
    )


def make_records() -> list[LearningRecord]:
    return [
        LearningRecord(
            record_id="learn_dec_CPI_1",
            decision_id="dec_1",
            reasoning_chain_id="reason_CPI",
            event_type="CPI",
            decision_type=DECISION_POSITIVE,
            decision_confidence=0.75,
            expected_direction="positive",
            actual_return_pct=2.5,
            direction_correct=True,
            accuracy_score=1.0,
        ),
        LearningRecord(
            record_id="learn_dec_CPI_2",
            decision_id="dec_2",
            reasoning_chain_id="reason_CPI",
            event_type="CPI",
            decision_type=DECISION_POSITIVE,
            decision_confidence=0.70,
            expected_direction="positive",
            actual_return_pct=-1.0,
            direction_correct=False,
            accuracy_score=0.0,
        ),
        LearningRecord(
            record_id="learn_dec_CPI_3",
            decision_id="dec_3",
            reasoning_chain_id="reason_CPI",
            event_type="CPI",
            decision_type=DECISION_STRONG_POSITIVE,
            decision_confidence=0.85,
            expected_direction="positive",
            actual_return_pct=3.0,
            direction_correct=True,
            accuracy_score=1.0,
        ),
    ]


# ── LearningRecord ─────────────────────────────────────────────────────────

def test_learning_record_creation() -> None:
    record = LearningRecord(
        record_id="learn_1",
        decision_id="dec_1",
        reasoning_chain_id="reason_CPI",
        event_type="CPI",
        decision_type=DECISION_POSITIVE,
        decision_confidence=0.75,
        expected_direction="positive",
        actual_return_pct=2.5,
        direction_correct=True,
        accuracy_score=1.0,
    )
    assert record.record_id == "learn_1"
    assert record.event_type == "CPI"
    assert record.direction_correct is True


# ── LearningSession ────────────────────────────────────────────────────────

def test_learning_session_creation() -> None:
    records = make_records()
    session = LearningSession(
        session_id="session_test",
        records=tuple(records),
        total_records=3,
        correct_count=2,
        accuracy_rate=round(2 / 3, 6),
        avg_confidence=round((0.75 + 0.70 + 0.85) / 3, 6),
    )
    assert session.total_records == 3
    assert session.correct_count == 2
    assert session.accuracy_rate == round(2 / 3, 6)


# ── KnowledgeFeedback ─────────────────────────────────────────────────────

def test_knowledge_feedback_creation() -> None:
    feedback = KnowledgeFeedback(
        feedback_id="feedback_CPI_1",
        source_record_ids=("learn_1", "learn_2"),
        event_type="CPI",
        condition={"cpi_pressure": "up"},
        horizon_days=5,
        current_confidence=0.75,
        suggested_confidence=0.80,
        accuracy_rate=0.8,
        correct_count=2,
        sample_count=3,
        explanation="Good accuracy, confidence adjusted upward.",
    )
    assert feedback.feedback_id == "feedback_CPI_1"
    assert feedback.suggested_confidence == 0.80


# ── LearningEngine — evaluate ─────────────────────────────────────────────

def test_evaluate_positive_correct() -> None:
    decision = make_decision(DECISION_POSITIVE, 0.75)
    record = LearningEngine().evaluate(decision, actual_return_pct=2.0)
    assert record.expected_direction == "positive"
    assert record.direction_correct is True
    assert record.accuracy_score == 1.0
    assert record.decision_id == decision.decision_id


def test_evaluate_positive_wrong() -> None:
    decision = make_decision(DECISION_POSITIVE, 0.75)
    record = LearningEngine().evaluate(decision, actual_return_pct=-1.0)
    assert record.expected_direction == "positive"
    assert record.direction_correct is False
    assert record.accuracy_score == 0.0


def test_evaluate_strong_positive_correct() -> None:
    decision = make_decision(DECISION_STRONG_POSITIVE, 0.85)
    record = LearningEngine().evaluate(decision, actual_return_pct=3.0)
    assert record.expected_direction == "positive"
    assert record.direction_correct is True


def test_evaluate_negative_correct() -> None:
    decision = make_decision(DECISION_NEGATIVE, 0.70)
    record = LearningEngine().evaluate(decision, actual_return_pct=-2.0)
    assert record.expected_direction == "negative"
    assert record.direction_correct is True


def test_evaluate_negative_wrong() -> None:
    decision = make_decision(DECISION_NEGATIVE, 0.70)
    record = LearningEngine().evaluate(decision, actual_return_pct=1.5)
    assert record.expected_direction == "negative"
    assert record.direction_correct is False


def test_evaluate_strong_negative_correct() -> None:
    decision = make_decision(DECISION_STRONG_NEGATIVE, 0.80)
    record = LearningEngine().evaluate(decision, actual_return_pct=-3.0)
    assert record.expected_direction == "negative"
    assert record.direction_correct is True


def test_evaluate_neutral_always_correct() -> None:
    decision = make_decision(DECISION_NEUTRAL, 0.50)
    record = LearningEngine().evaluate(decision, actual_return_pct=5.0)
    assert record.expected_direction == "neutral"
    assert record.direction_correct is True
    assert record.accuracy_score == 1.0

    record = LearningEngine().evaluate(decision, actual_return_pct=-5.0)
    assert record.direction_correct is True


def test_evaluate_zero_positive() -> None:
    decision = make_decision(DECISION_POSITIVE, 0.75)
    record = LearningEngine().evaluate(decision, actual_return_pct=0.0)
    assert record.expected_direction == "positive"
    assert record.direction_correct is False
    assert record.accuracy_score == 0.0


def test_evaluate_zero_negative() -> None:
    decision = make_decision(DECISION_NEGATIVE, 0.70)
    record = LearningEngine().evaluate(decision, actual_return_pct=0.0)
    assert record.direction_correct is False


def test_evaluate_record_id_format() -> None:
    decision = make_decision(DECISION_POSITIVE)
    record = LearningEngine().evaluate(decision, 1.0)
    assert record.record_id == f"learn_{decision.decision_id}"
    assert record.reasoning_chain_id == decision.reasoning_chain_id


def test_evaluate_preserves_confidence() -> None:
    decision = make_decision(DECISION_POSITIVE, confidence=0.65)
    record = LearningEngine().evaluate(decision, 1.0)
    assert record.decision_confidence == 0.65


# ── LearningEngine — create_session ───────────────────────────────────────

def test_create_session_empty() -> None:
    session = LearningEngine().create_session([])
    assert session.total_records == 0
    assert session.accuracy_rate == 0.0
    assert session.avg_confidence == 0.0


def test_create_session_with_records() -> None:
    records = make_records()
    session = LearningEngine().create_session(records)
    assert session.total_records == 3
    assert session.correct_count == 2
    assert session.accuracy_rate == round(2 / 3, 6)
    expected_avg = round((0.75 + 0.70 + 0.85) / 3, 6)
    assert session.avg_confidence == expected_avg


def test_create_session_summary() -> None:
    records = make_records()
    session = LearningEngine().create_session(records)
    assert session.summary["total_records"] == 3
    assert session.summary["correct_count"] == 2
    assert session.summary["incorrect_count"] == 1
    assert session.summary["accuracy_rate"] == round(2 / 3, 6)


def test_create_session_all_correct() -> None:
    records = [
        LearningRecord(
            record_id=f"r{i}", decision_id=f"d{i}", reasoning_chain_id="rc",
            event_type="CPI", decision_type=DECISION_POSITIVE,
            decision_confidence=0.8, expected_direction="positive",
            actual_return_pct=1.0, direction_correct=True, accuracy_score=1.0,
        )
        for i in range(5)
    ]
    session = LearningEngine().create_session(records)
    assert session.accuracy_rate == 1.0
    assert session.correct_count == 5


def test_create_session_all_wrong() -> None:
    records = [
        LearningRecord(
            record_id=f"r{i}", decision_id=f"d{i}", reasoning_chain_id="rc",
            event_type="CPI", decision_type=DECISION_POSITIVE,
            decision_confidence=0.8, expected_direction="positive",
            actual_return_pct=-1.0, direction_correct=False, accuracy_score=0.0,
        )
        for i in range(3)
    ]
    session = LearningEngine().create_session(records)
    assert session.accuracy_rate == 0.0
    assert session.correct_count == 0


# ── LearningEngine — generate_feedback ───────────────────────────────────

def test_generate_feedback_empty() -> None:
    feedback = LearningEngine().generate_feedback([], condition={}, horizon_days=5)
    assert feedback.sample_count == 0
    assert feedback.accuracy_rate == 0.0
    assert "No learning records" in feedback.explanation


def test_generate_feedback_improving() -> None:
    records = make_records()  # 2/3 correct = 0.667 accuracy
    feedback = LearningEngine().generate_feedback(records, condition={"p": "up"})
    assert feedback.event_type == "CPI"
    assert feedback.sample_count == 3
    assert feedback.correct_count == 2
    assert feedback.accuracy_rate == round(2 / 3, 6)
    assert feedback.condition == {"p": "up"}
    assert "stable" in feedback.explanation


def test_generate_feedback_high_accuracy() -> None:
    records = [
        LearningRecord(
            record_id=f"r{i}", decision_id=f"d{i}", reasoning_chain_id="rc",
            event_type="CPI", decision_type=DECISION_POSITIVE,
            decision_confidence=0.8, expected_direction="positive",
            actual_return_pct=1.0, direction_correct=True, accuracy_score=1.0,
        )
        for i in range(10)
    ]
    feedback = LearningEngine().generate_feedback(records)
    assert feedback.accuracy_rate == 1.0
    assert feedback.correct_count == 10
    assert "improving" in feedback.explanation


def test_generate_feedback_low_accuracy() -> None:
    records = [
        LearningRecord(
            record_id=f"r{i}", decision_id=f"d{i}", reasoning_chain_id="rc",
            event_type="CPI", decision_type=DECISION_POSITIVE,
            decision_confidence=0.8, expected_direction="positive",
            actual_return_pct=-1.0, direction_correct=False, accuracy_score=0.0,
        )
        for i in range(10)
    ]
    feedback = LearningEngine().generate_feedback(records)
    assert feedback.accuracy_rate == 0.0
    assert "declining" in feedback.explanation


def test_generate_feedback_suggested_confidence() -> None:
    records = [
        LearningRecord(
            record_id=f"r{i}", decision_id=f"d{i}", reasoning_chain_id="rc",
            event_type="CPI", decision_type=DECISION_POSITIVE,
            decision_confidence=0.80, expected_direction="positive",
            actual_return_pct=1.0, direction_correct=True, accuracy_score=1.0,
        )
        for i in range(5)
    ]
    feedback = LearningEngine().generate_feedback(records)
    # avg_conf = 0.8, accuracy_rate = 1.0
    # suggested = 0.6 * 0.8 + 0.4 * 1.0 = 0.48 + 0.4 = 0.88
    expected = round(0.6 * 0.80 + 0.4 * 1.0, 6)
    assert feedback.suggested_confidence == expected
    assert feedback.current_confidence == 0.80


def test_generate_feedback_confidence_decrease() -> None:
    records = [
        LearningRecord(
            record_id=f"r{i}", decision_id=f"d{i}", reasoning_chain_id="rc",
            event_type="CPI", decision_type=DECISION_POSITIVE,
            decision_confidence=0.80, expected_direction="positive",
            actual_return_pct=-1.0, direction_correct=False, accuracy_score=0.0,
        )
        for i in range(5)
    ]
    feedback = LearningEngine().generate_feedback(records)
    # avg_conf = 0.8, accuracy_rate = 0.0
    # suggested = 0.6 * 0.8 + 0.4 * 0.0 = 0.48
    assert feedback.suggested_confidence < feedback.current_confidence


# ── LearningRepository ────────────────────────────────────────────────────

def test_repository_save_and_load_record(tmp_path: Path) -> None:
    decision = make_decision(DECISION_POSITIVE)
    record = LearningEngine().evaluate(decision, actual_return_pct=2.0)
    path = tmp_path / "record.json"
    LearningRepository().save_record(record, path)
    assert path.exists()

    loaded = LearningRepository().load_record(path)
    assert loaded.record_id == record.record_id
    assert loaded.decision_id == record.decision_id
    assert loaded.event_type == "CPI"
    assert loaded.direction_correct is True
    assert loaded.accuracy_score == 1.0


def test_repository_save_and_load_session(tmp_path: Path) -> None:
    records = make_records()
    session = LearningEngine().create_session(records)
    path = tmp_path / "session.json"
    LearningRepository().save_session(session, path)
    assert path.exists()

    loaded = LearningRepository().load_session(path)
    assert loaded.session_id == session.session_id
    assert loaded.total_records == 3
    assert loaded.correct_count == 2
    assert len(loaded.records) == 3


def test_repository_save_and_load_feedback(tmp_path: Path) -> None:
    records = make_records()
    feedback = LearningEngine().generate_feedback(records)
    path = tmp_path / "feedback.json"
    LearningRepository().save_feedback(feedback, path)
    assert path.exists()

    loaded = LearningRepository().load_feedback(path)
    assert loaded.feedback_id == feedback.feedback_id
    assert loaded.sample_count == 3
    assert loaded.correct_count == 2


def test_repository_session_preserves_record_details(tmp_path: Path) -> None:
    records = make_records()
    session = LearningEngine().create_session(records)
    path = tmp_path / "session_details.json"
    LearningRepository().save_session(session, path)
    loaded = LearningRepository().load_session(path)
    assert loaded.records[0].decision_id == "dec_1"
    assert loaded.records[0].actual_return_pct == 2.5


def test_repository_record_file_format(tmp_path: Path) -> None:
    decision = make_decision(DECISION_POSITIVE)
    record = LearningEngine().evaluate(decision, 1.5)
    path = tmp_path / "format.json"
    LearningRepository().save_record(record, path)

    raw = json.loads(path.read_text())
    assert raw["record_id"] == record.record_id
    assert raw["decision_type"] == DECISION_POSITIVE
    assert raw["direction_correct"] is True

    path2 = tmp_path / "session_fmt.json"
    session = LearningEngine().create_session([record])
    LearningRepository().save_session(session, path2)
    raw2 = json.loads(path2.read_text())
    assert raw2["total_records"] == 1
    assert "records" in raw2
