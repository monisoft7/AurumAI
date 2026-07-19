import json
from pathlib import Path

from knowledge._compat import atomic_write_json

from knowledge.learning.record import LearningRecord
from knowledge.learning.session import LearningSession
from knowledge.learning.feedback import KnowledgeFeedback


class LearningRepository:
    def save_record(self, record: LearningRecord, path: Path) -> None:
        payload = {
            "record_id": record.record_id,
            "decision_id": record.decision_id,
            "reasoning_chain_id": record.reasoning_chain_id,
            "event_type": record.event_type,
            "decision_type": record.decision_type,
            "decision_confidence": record.decision_confidence,
            "expected_direction": record.expected_direction,
            "actual_return_pct": record.actual_return_pct,
            "direction_correct": record.direction_correct,
            "accuracy_score": record.accuracy_score,
            "details": record.details,
        }
        atomic_write_json(path, payload)

    def load_record(self, path: Path) -> LearningRecord:
        payload = json.loads(path.read_text())
        return LearningRecord(
            record_id=payload["record_id"],
            decision_id=payload["decision_id"],
            reasoning_chain_id=payload["reasoning_chain_id"],
            event_type=payload["event_type"],
            decision_type=payload["decision_type"],
            decision_confidence=payload.get("decision_confidence", 0.0),
            expected_direction=payload.get("expected_direction", ""),
            actual_return_pct=payload.get("actual_return_pct", 0.0),
            direction_correct=payload.get("direction_correct", False),
            accuracy_score=payload.get("accuracy_score", 0.0),
            details=payload.get("details", {}),
        )

    def save_session(self, session: LearningSession, path: Path) -> None:
        payload = {
            "session_id": session.session_id,
            "total_records": session.total_records,
            "correct_count": session.correct_count,
            "accuracy_rate": session.accuracy_rate,
            "avg_confidence": session.avg_confidence,
            "summary": session.summary,
            "records": [
                {
                    "record_id": r.record_id,
                    "decision_id": r.decision_id,
                    "reasoning_chain_id": r.reasoning_chain_id,
                    "event_type": r.event_type,
                    "decision_type": r.decision_type,
                    "decision_confidence": r.decision_confidence,
                    "expected_direction": r.expected_direction,
                    "actual_return_pct": r.actual_return_pct,
                    "direction_correct": r.direction_correct,
                    "accuracy_score": r.accuracy_score,
                    "details": r.details,
                }
                for r in session.records
            ],
        }
        atomic_write_json(path, payload)

    def load_session(self, path: Path) -> LearningSession:
        payload = json.loads(path.read_text())
        records = []
        for r_data in payload.get("records", []):
            records.append(LearningRecord(
                record_id=r_data["record_id"],
                decision_id=r_data["decision_id"],
                reasoning_chain_id=r_data["reasoning_chain_id"],
                event_type=r_data["event_type"],
                decision_type=r_data["decision_type"],
                decision_confidence=r_data.get("decision_confidence", 0.0),
                expected_direction=r_data.get("expected_direction", ""),
                actual_return_pct=r_data.get("actual_return_pct", 0.0),
                direction_correct=r_data.get("direction_correct", False),
                accuracy_score=r_data.get("accuracy_score", 0.0),
                details=r_data.get("details", {}),
            ))
        return LearningSession(
            session_id=payload["session_id"],
            records=tuple(records),
            total_records=payload.get("total_records", 0),
            correct_count=payload.get("correct_count", 0),
            accuracy_rate=payload.get("accuracy_rate", 0.0),
            avg_confidence=payload.get("avg_confidence", 0.0),
            summary=payload.get("summary", {}),
        )

    def save_feedback(self, feedback: KnowledgeFeedback, path: Path) -> None:
        payload = {
            "feedback_id": feedback.feedback_id,
            "source_record_ids": list(feedback.source_record_ids),
            "event_type": feedback.event_type,
            "condition": feedback.condition,
            "horizon_days": feedback.horizon_days,
            "current_confidence": feedback.current_confidence,
            "suggested_confidence": feedback.suggested_confidence,
            "accuracy_rate": feedback.accuracy_rate,
            "correct_count": feedback.correct_count,
            "sample_count": feedback.sample_count,
            "explanation": feedback.explanation,
            "metadata": feedback.metadata,
        }
        atomic_write_json(path, payload)

    def load_feedback(self, path: Path) -> KnowledgeFeedback:
        payload = json.loads(path.read_text())
        return KnowledgeFeedback(
            feedback_id=payload["feedback_id"],
            source_record_ids=tuple(payload.get("source_record_ids", [])),
            event_type=payload.get("event_type", ""),
            condition=payload.get("condition", {}),
            horizon_days=payload.get("horizon_days", 0),
            current_confidence=payload.get("current_confidence", 0.0),
            suggested_confidence=payload.get("suggested_confidence", 0.0),
            accuracy_rate=payload.get("accuracy_rate", 0.0),
            correct_count=payload.get("correct_count", 0),
            sample_count=payload.get("sample_count", 0),
            explanation=payload.get("explanation", ""),
            metadata=payload.get("metadata", {}),
        )
