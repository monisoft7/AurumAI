from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from knowledge.integrity.provenance import Provenance, deserialize_provenance, serialize_provenance


@dataclass(frozen=True)
class KnowledgeRecord:
    knowledge_id: str
    event_type: str
    asset: str
    condition: dict[str, str]
    horizon_days: int
    sample_count: int
    positive_return_rate_pct: float
    negative_return_rate_pct: float
    up_direction_rate_pct: float
    down_direction_rate_pct: float
    flat_direction_rate_pct: float
    average_return_pct: float
    median_return_pct: float
    min_return_pct: float
    max_return_pct: float
    first_event_date: str
    last_event_date: str
    bias: str
    confidence: float
    explanation: str
    source_lesson_ids: tuple[str, ...] = ()
    source_artifact_path: str = ""
    source_artifact_sha256: str = ""
    provenance: Provenance | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> KnowledgeRecord:
        return cls(
            knowledge_id=data["knowledge_id"],
            event_type=data["event_type"],
            asset=data["asset"],
            source_lesson_ids=tuple(str(v) for v in data.get("source_lesson_ids", ())),
            source_artifact_path=str(data.get("source_artifact_path", "")),
            source_artifact_sha256=str(data.get("source_artifact_sha256", "")),
            condition=dict(data.get("condition", {})),
            horizon_days=int(data.get("horizon_days", 0)),
            sample_count=int(data.get("sample_count", 0)),
            positive_return_rate_pct=float(data.get("positive_return_rate_pct", 0.0)),
            negative_return_rate_pct=float(data.get("negative_return_rate_pct", 0.0)),
            up_direction_rate_pct=float(data.get("up_direction_rate_pct", 0.0)),
            down_direction_rate_pct=float(data.get("down_direction_rate_pct", 0.0)),
            flat_direction_rate_pct=float(data.get("flat_direction_rate_pct", 0.0)),
            average_return_pct=float(data.get("average_return_pct", 0.0)),
            median_return_pct=float(data.get("median_return_pct", 0.0)),
            min_return_pct=float(data.get("min_return_pct", 0.0)),
            max_return_pct=float(data.get("max_return_pct", 0.0)),
            first_event_date=str(data.get("first_event_date", "")),
            last_event_date=str(data.get("last_event_date", "")),
            bias=data.get("bias", ""),
            confidence=float(data.get("confidence", 0.0)),
            explanation=data.get("explanation", ""),
            provenance=deserialize_provenance(data.get("provenance")),
            metadata=dict(data.get("metadata", {})),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "knowledge_id": self.knowledge_id,
            "event_type": self.event_type,
            "asset": self.asset,
            "source_lesson_ids": list(self.source_lesson_ids),
            "source_artifact_path": self.source_artifact_path,
            "source_artifact_sha256": self.source_artifact_sha256,
            "condition": dict(self.condition),
            "horizon_days": self.horizon_days,
            "sample_count": self.sample_count,
            "positive_return_rate_pct": self.positive_return_rate_pct,
            "negative_return_rate_pct": self.negative_return_rate_pct,
            "up_direction_rate_pct": self.up_direction_rate_pct,
            "down_direction_rate_pct": self.down_direction_rate_pct,
            "flat_direction_rate_pct": self.flat_direction_rate_pct,
            "average_return_pct": self.average_return_pct,
            "median_return_pct": self.median_return_pct,
            "min_return_pct": self.min_return_pct,
            "max_return_pct": self.max_return_pct,
            "first_event_date": self.first_event_date,
            "last_event_date": self.last_event_date,
            "bias": self.bias,
            "confidence": self.confidence,
            "explanation": self.explanation,
            "provenance": serialize_provenance(self.provenance),
            "metadata": dict(self.metadata),
        }
