from __future__ import annotations

from typing import Any

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


class LearningEngine:
    def evaluate(self, decision: Decision, actual_return_pct: float) -> LearningRecord:
        expected = self._expected_direction(decision.decision_type)
        direction_correct = self._direction_correct(expected, actual_return_pct)
        accuracy_score = self._compute_accuracy(expected, actual_return_pct)
        record_id = f"learn_{decision.decision_id}"

        return LearningRecord(
            record_id=record_id,
            decision_id=decision.decision_id,
            reasoning_chain_id=decision.reasoning_chain_id,
            event_type=decision.context.event_type,
            decision_type=decision.decision_type,
            decision_confidence=decision.confidence,
            expected_direction=expected,
            actual_return_pct=actual_return_pct,
            direction_correct=direction_correct,
            accuracy_score=accuracy_score,
            details={
                "decision_type": decision.decision_type,
                "decision_confidence": decision.confidence,
                "expected_direction": expected,
                "actual_return_pct": actual_return_pct,
            },
        )

    def create_session(self, records: list[LearningRecord]) -> LearningSession:
        if not records:
            return LearningSession(
                session_id="session_empty",
                records=(),
                total_records=0,
                correct_count=0,
                accuracy_rate=0.0,
                avg_confidence=0.0,
            )
        total = len(records)
        correct = sum(1 for r in records if r.direction_correct)
        accuracy_rate = round(correct / total, 6)
        avg_conf = round(
            sum(r.decision_confidence for r in records) / total, 6
        )
        first_id = records[0].record_id
        last_id = records[-1].record_id
        session_id = f"session_{first_id}_{last_id}"

        return LearningSession(
            session_id=session_id,
            records=tuple(records),
            total_records=total,
            correct_count=correct,
            accuracy_rate=accuracy_rate,
            avg_confidence=avg_conf,
            summary={
                "total_records": total,
                "correct_count": correct,
                "incorrect_count": total - correct,
                "accuracy_rate": accuracy_rate,
                "avg_confidence": avg_conf,
            },
        )

    def generate_feedback(
        self,
        records: list[LearningRecord],
        condition: dict[str, str] | None = None,
        horizon_days: int = 0,
    ) -> KnowledgeFeedback:
        if not records:
            return KnowledgeFeedback(
                feedback_id="feedback_empty",
                source_record_ids=(),
                event_type="",
                condition=condition or {},
                horizon_days=horizon_days,
                current_confidence=0.0,
                suggested_confidence=0.0,
                accuracy_rate=0.0,
                correct_count=0,
                sample_count=0,
                explanation="No learning records to generate feedback from.",
            )

        total = len(records)
        correct = sum(1 for r in records if r.direction_correct)
        accuracy_rate = round(correct / total, 6)
        avg_conf = round(
            sum(r.decision_confidence for r in records) / total, 6
        )
        event_type = records[0].event_type
        suggested = self._suggest_confidence(avg_conf, accuracy_rate)
        record_ids = tuple(r.record_id for r in records)
        feedback_id = f"feedback_{event_type}_{records[0].record_id}"

        if accuracy_rate >= 0.7:
            trend = "improving"
        elif accuracy_rate <= 0.4:
            trend = "declining"
        else:
            trend = "stable"

        explanation = (
            f"Feedback for {event_type}: {correct}/{total} records correct "
            f"(accuracy: {accuracy_rate:.1%}, trend: {trend}). "
            f"Confidence adjusted from {avg_conf:.3f} to {suggested:.3f}."
        )

        return KnowledgeFeedback(
            feedback_id=feedback_id,
            source_record_ids=record_ids,
            event_type=event_type,
            condition=condition or {},
            horizon_days=horizon_days,
            current_confidence=avg_conf,
            suggested_confidence=suggested,
            accuracy_rate=accuracy_rate,
            correct_count=correct,
            sample_count=total,
            explanation=explanation,
        )

    def _expected_direction(self, decision_type: str) -> str:
        if decision_type in (DECISION_STRONG_POSITIVE, DECISION_POSITIVE):
            return "positive"
        if decision_type in (DECISION_STRONG_NEGATIVE, DECISION_NEGATIVE):
            return "negative"
        return "neutral"

    def _direction_correct(self, expected: str, actual_return: float) -> bool:
        if expected == "positive":
            return actual_return > 0
        if expected == "negative":
            return actual_return < 0
        return True

    def _compute_accuracy(self, expected: str, actual_return: float) -> float:
        if expected == "neutral":
            return 1.0
        if (expected == "positive" and actual_return > 0) or (
            expected == "negative" and actual_return < 0
        ):
            return 1.0
        return 0.0

    def _suggest_confidence(self, current: float, accuracy_rate: float) -> float:
        return round(0.6 * current + 0.4 * accuracy_rate, 6)
