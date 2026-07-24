from __future__ import annotations

from pathlib import Path

from knowledge.decision.context import DecisionContext
from knowledge.decision.decision import Decision
from knowledge.integrity.knowledge_record import KnowledgeRecord
from knowledge.integrity.versioning import VersionedStore
from knowledge.learning.engine import LearningEngine
from knowledge.learning.feedback import KnowledgeFeedback
from simulation.models import EventRunResult

from knowledge.evolution.knowledge_calibrator import KnowledgeCalibrator


class FeedbackApplicator:
    def __init__(self, versioned_store_dir: Path | None = None):
        self._engine = LearningEngine()
        self._calibrator = KnowledgeCalibrator()
        self._versioned_store: VersionedStore[dict] | None = (
            VersionedStore[dict](versioned_store_dir) if versioned_store_dir else None
        )

    def apply(
        self,
        results: list[EventRunResult],
        knowledge_records: list[KnowledgeRecord],
    ) -> list[KnowledgeRecord]:
        scored = [
            r
            for r in results
            if r.decision is not None
            and r.decision_correct is not None
            and r.decision_actual_return_pct is not None
        ]
        if not scored:
            return []

        grouped: dict[str, list[EventRunResult]] = {}
        for r in scored:
            grouped.setdefault(r.event_type, []).append(r)

        updated: list[KnowledgeRecord] = []
        for event_type, group in grouped.items():
            feedback = self._build_feedback(event_type, group)
            matching = [kr for kr in knowledge_records if kr.event_type == event_type]
            for kr in matching:
                calibrated = self._calibrator.calibrate(kr, feedback)
                updated.append(calibrated)
                if self._versioned_store:
                    self._persist_version(kr.knowledge_id, kr, calibrated)

        return updated

    def _build_feedback(
        self,
        event_type: str,
        results: list[EventRunResult],
    ) -> KnowledgeFeedback:
        records = []
        for idx, rr in enumerate(results):
            decision = Decision(
                decision_id=f"eval_{event_type}_{idx}",
                decision_type=rr.decision or "NEUTRAL",
                confidence=rr.forecast_confidence or 0.0,
                reasoning_chain_id=f"chain_{event_type}_{idx}",
                evidence_count=0,
                explanation=f"Evaluated {event_type} result {idx}.",
                context=DecisionContext(event_type=event_type, query=""),
            )
            record = self._engine.evaluate(decision, rr.decision_actual_return_pct or 0.0)
            records.append(record)

        return self._engine.generate_feedback(
            records,
            condition={},
            horizon_days=0,
        )

    def _persist_version(
        self,
        entity_id: str,
        old_record: KnowledgeRecord,
        new_record: KnowledgeRecord,
    ) -> None:
        if self._versioned_store is None:
            return
        existing = self._versioned_store.latest_version(entity_id)
        prev_file = f"v{existing.version_number:04d}.json" if existing else None
        self._versioned_store.save(
            entity_id,
            new_record.to_dict(),
            previous_version_file=prev_file,
        )
