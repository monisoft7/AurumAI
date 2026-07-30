from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from knowledge._compat import FrozenDict, freeze_dict
from knowledge.integrity.provenance import Provenance, serialize_provenance, deserialize_provenance

VALID_BIASES = {"bullish", "bearish", "neutral", "mixed"}


@dataclass(frozen=True)
class Evidence:
    """Canonical institutional Evidence matching INSTITUTIONAL_CONTRACTS.md Contract 4."""

    evidence_id: str
    source_kr_id: str
    source_kr_node_id: str
    event_type: str
    condition: dict[str, str]
    bias: str
    base_confidence: float
    regime_weight: float
    composite_weight: float
    explanation: str
    regime: str
    source_label: str
    supporting_observation_ids: tuple[str, ...] = ()
    contradicting_observation_ids: tuple[str, ...] = ()
    mechanism: str = ""
    failure_conditions: str = ""
    counter_examples: str = ""
    provenance: Provenance | None = None
    temporal_recency: float = 0.0
    metadata: dict[str, Any] = field(default_factory=lambda: FrozenDict())

    def __post_init__(self) -> None:
        object.__setattr__(self, "condition", freeze_dict(self.condition))
        object.__setattr__(self, "metadata", freeze_dict(self.metadata))
        object.__setattr__(self, "supporting_observation_ids", tuple(self.supporting_observation_ids))
        object.__setattr__(self, "contradicting_observation_ids", tuple(self.contradicting_observation_ids))

    def to_dict(self) -> dict[str, Any]:
        return {
            "evidence_id": self.evidence_id,
            "source_kr_id": self.source_kr_id,
            "source_kr_node_id": self.source_kr_node_id,
            "event_type": self.event_type,
            "condition": dict(self.condition),
            "bias": self.bias,
            "base_confidence": self.base_confidence,
            "regime_weight": self.regime_weight,
            "composite_weight": self.composite_weight,
            "explanation": self.explanation,
            "regime": self.regime,
            "source_label": self.source_label,
            "supporting_observation_ids": list(self.supporting_observation_ids),
            "contradicting_observation_ids": list(self.contradicting_observation_ids),
            "mechanism": self.mechanism,
            "failure_conditions": self.failure_conditions,
            "counter_examples": self.counter_examples,
            "provenance": serialize_provenance(self.provenance),
            "temporal_recency": self.temporal_recency,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Evidence:
        return cls(
            evidence_id=str(data.get("evidence_id", "")),
            source_kr_id=str(data.get("source_kr_id", "")),
            source_kr_node_id=str(data.get("source_kr_node_id", "")),
            event_type=str(data.get("event_type", "")),
            condition=dict(data.get("condition", {})),
            bias=str(data.get("bias", "")),
            base_confidence=float(data.get("base_confidence", 0.0)),
            regime_weight=float(data.get("regime_weight", 0.0)),
            composite_weight=float(data.get("composite_weight", 0.0)),
            explanation=str(data.get("explanation", "")),
            regime=str(data.get("regime", "")),
            source_label=str(data.get("source_label", "")),
            supporting_observation_ids=tuple(data.get("supporting_observation_ids", ())),
            contradicting_observation_ids=tuple(data.get("contradicting_observation_ids", ())),
            mechanism=str(data.get("mechanism", "")),
            failure_conditions=str(data.get("failure_conditions", "")),
            counter_examples=str(data.get("counter_examples", "")),
            provenance=deserialize_provenance(data.get("provenance")),
            temporal_recency=float(data.get("temporal_recency", 0.0)),
            metadata=dict(data.get("metadata", {})),
        )

    def validate(self) -> list[str]:
        errors: list[str] = []
        if self.bias not in VALID_BIASES:
            errors.append(f"invalid bias: {self.bias}")
        if not 0.0 <= self.base_confidence <= 1.0:
            errors.append(f"base_confidence out of range: {self.base_confidence}")
        if not 0.0 <= self.regime_weight <= 1.0:
            errors.append(f"regime_weight out of range: {self.regime_weight}")
        expected = round(self.base_confidence * self.regime_weight, 4)
        if abs(self.composite_weight - expected) > 0.0001:
            errors.append(f"composite_weight {self.composite_weight} != expected {expected}")
        if not 0.0 <= self.temporal_recency <= 1.0:
            errors.append(f"temporal_recency out of range: {self.temporal_recency}")
        return errors


@dataclass(frozen=True)
class EvidenceCollection:
    """W5 output: collection of Evidence items with aggregate metadata."""

    collection_id: str
    assessment_id: str
    timestamp: str
    regime: str
    items: tuple[Evidence, ...] = ()
    total_classified: int = 0
    signals_count: int = 0
    weak_signals_count: int = 0
    watch_count: int = 0
    filtered_noise_count: int = 0
    filtered_ignore_count: int = 0
    metadata: dict[str, Any] = field(default_factory=lambda: FrozenDict())

    def __post_init__(self) -> None:
        object.__setattr__(self, "items", tuple(self.items))
        object.__setattr__(self, "metadata", freeze_dict(self.metadata))

    def to_dict(self) -> dict[str, Any]:
        return {
            "collection_id": self.collection_id,
            "assessment_id": self.assessment_id,
            "timestamp": self.timestamp,
            "regime": self.regime,
            "items": [e.to_dict() for e in self.items],
            "total_classified": self.total_classified,
            "signals_count": self.signals_count,
            "weak_signals_count": self.weak_signals_count,
            "watch_count": self.watch_count,
            "filtered_noise_count": self.filtered_noise_count,
            "filtered_ignore_count": self.filtered_ignore_count,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> EvidenceCollection:
        return cls(
            collection_id=str(data.get("collection_id", "")),
            assessment_id=str(data.get("assessment_id", "")),
            timestamp=str(data.get("timestamp", "")),
            regime=str(data.get("regime", "")),
            items=tuple(Evidence.from_dict(e) for e in data.get("items", [])),
            total_classified=int(data.get("total_classified", 0)),
            signals_count=int(data.get("signals_count", 0)),
            weak_signals_count=int(data.get("weak_signals_count", 0)),
            watch_count=int(data.get("watch_count", 0)),
            filtered_noise_count=int(data.get("filtered_noise_count", 0)),
            filtered_ignore_count=int(data.get("filtered_ignore_count", 0)),
            metadata=dict(data.get("metadata", {})),
        )

    @property
    def evidence_count(self) -> int:
        return len(self.items)

    @property
    def avg_composite_weight(self) -> float:
        if not self.items:
            return 0.0
        return round(sum(e.composite_weight for e in self.items) / len(self.items), 4)
