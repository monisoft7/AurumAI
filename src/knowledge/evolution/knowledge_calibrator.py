from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from knowledge.integrity.knowledge_record import KnowledgeRecord
from knowledge.integrity.provenance import Provenance
from knowledge.learning.feedback import KnowledgeFeedback


class KnowledgeCalibrator:
    def calibrate(
        self,
        knowledge_record: KnowledgeRecord,
        feedback: KnowledgeFeedback,
    ) -> KnowledgeRecord:
        old_prov = knowledge_record.provenance
        new_version = self._bump_version(old_prov.entity_version if old_prov else "0.0.0")
        new_prov = Provenance(
            created_at=datetime.now(timezone.utc).isoformat(),
            created_by="knowledge_calibrator",
            entity_version=new_version,
            previous_version_id=knowledge_record.knowledge_id,
            metadata={"calibration_source": feedback.feedback_id},
        )

        new_explanation = (
            f"{knowledge_record.explanation} "
            f"[Calibrated via {feedback.feedback_id}: "
            f"confidence {knowledge_record.confidence} → {feedback.suggested_confidence}, "
            f"accuracy_rate={feedback.accuracy_rate}]"
        )

        return KnowledgeRecord(
            knowledge_id=knowledge_record.knowledge_id,
            event_type=knowledge_record.event_type,
            asset=knowledge_record.asset,
            condition=dict(knowledge_record.condition),
            horizon_days=knowledge_record.horizon_days,
            sample_count=knowledge_record.sample_count,
            positive_return_rate_pct=knowledge_record.positive_return_rate_pct,
            negative_return_rate_pct=knowledge_record.negative_return_rate_pct,
            up_direction_rate_pct=knowledge_record.up_direction_rate_pct,
            down_direction_rate_pct=knowledge_record.down_direction_rate_pct,
            flat_direction_rate_pct=knowledge_record.flat_direction_rate_pct,
            average_return_pct=knowledge_record.average_return_pct,
            median_return_pct=knowledge_record.median_return_pct,
            min_return_pct=knowledge_record.min_return_pct,
            max_return_pct=knowledge_record.max_return_pct,
            first_event_date=knowledge_record.first_event_date,
            last_event_date=knowledge_record.last_event_date,
            bias=knowledge_record.bias,
            confidence=feedback.suggested_confidence,
            explanation=new_explanation,
            source_lesson_ids=knowledge_record.source_lesson_ids,
            source_artifact_path=knowledge_record.source_artifact_path,
            source_artifact_sha256=knowledge_record.source_artifact_sha256,
            provenance=new_prov,
            metadata=dict(knowledge_record.metadata),
        )

    @staticmethod
    def _bump_version(current: str) -> str:
        parts = current.split(".")
        if len(parts) != 3:
            return "1.0.0"
        major, minor, patch = int(parts[0]), int(parts[1]), int(parts[2])
        patch += 1
        return f"{major}.{minor}.{patch}"
