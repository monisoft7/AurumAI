from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from knowledge._compat import FrozenDict, freeze_dict
from knowledge.integrity.provenance import Provenance, serialize_provenance, deserialize_provenance

VALID_BIASES = {"bullish", "bearish", "neutral", "mixed"}


OPPOSITE_BIAS: dict[str, str] = {
    "bullish": "bearish",
    "bearish": "bullish",
    "neutral": "",
    "mixed": "",
}


@dataclass(frozen=True)
class EvidenceSet:
    """A grouped set of related Evidence items with consensus/conflict analysis."""

    set_id: str
    event_type: str
    bias: str
    evidence_ids: tuple[str, ...] = ()
    supporting_evidence_ids: tuple[str, ...] = ()
    contradicting_evidence_ids: tuple[str, ...] = ()
    duplicate_evidence_ids: tuple[str, ...] = ()
    net_institutional_weight: float = 0.0
    consensus_score: float = 0.0
    conflict_score: float = 0.0
    regime_dependency: str = ""
    confidence_contribution: float = 0.0
    explanation: str = ""
    provenance_chain: tuple[Provenance, ...] = ()
    metadata: dict[str, Any] = field(default_factory=lambda: FrozenDict())

    def __post_init__(self) -> None:
        object.__setattr__(self, "evidence_ids", tuple(self.evidence_ids))
        object.__setattr__(self, "supporting_evidence_ids", tuple(self.supporting_evidence_ids))
        object.__setattr__(self, "contradicting_evidence_ids", tuple(self.contradicting_evidence_ids))
        object.__setattr__(self, "duplicate_evidence_ids", tuple(self.duplicate_evidence_ids))
        object.__setattr__(self, "provenance_chain", tuple(self.provenance_chain))
        object.__setattr__(self, "metadata", freeze_dict(self.metadata))

    def to_dict(self) -> dict[str, Any]:
        return {
            "set_id": self.set_id,
            "event_type": self.event_type,
            "bias": self.bias,
            "evidence_ids": list(self.evidence_ids),
            "supporting_evidence_ids": list(self.supporting_evidence_ids),
            "contradicting_evidence_ids": list(self.contradicting_evidence_ids),
            "duplicate_evidence_ids": list(self.duplicate_evidence_ids),
            "net_institutional_weight": self.net_institutional_weight,
            "consensus_score": self.consensus_score,
            "conflict_score": self.conflict_score,
            "regime_dependency": self.regime_dependency,
            "confidence_contribution": self.confidence_contribution,
            "explanation": self.explanation,
            "provenance_chain": [serialize_provenance(p) for p in self.provenance_chain],
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> EvidenceSet:
        return cls(
            set_id=str(data.get("set_id", "")),
            event_type=str(data.get("event_type", "")),
            bias=str(data.get("bias", "")),
            evidence_ids=tuple(data.get("evidence_ids", ())),
            supporting_evidence_ids=tuple(data.get("supporting_evidence_ids", ())),
            contradicting_evidence_ids=tuple(data.get("contradicting_evidence_ids", ())),
            duplicate_evidence_ids=tuple(data.get("duplicate_evidence_ids", ())),
            net_institutional_weight=float(data.get("net_institutional_weight", 0.0)),
            consensus_score=float(data.get("consensus_score", 0.0)),
            conflict_score=float(data.get("conflict_score", 0.0)),
            regime_dependency=str(data.get("regime_dependency", "")),
            confidence_contribution=float(data.get("confidence_contribution", 0.0)),
            explanation=str(data.get("explanation", "")),
            provenance_chain=tuple(
                deserialize_provenance(p) for p in data.get("provenance_chain", []) if p is not None
            ),
            metadata=dict(data.get("metadata", {})),
        )

    def validate(self) -> list[str]:
        errors: list[str] = []
        if self.bias not in VALID_BIASES and self.bias:
            errors.append(f"invalid bias: {self.bias}")
        if not 0.0 <= self.net_institutional_weight <= 1.0:
            errors.append(f"net_institutional_weight out of range: {self.net_institutional_weight}")
        if not 0.0 <= self.consensus_score <= 1.0:
            errors.append(f"consensus_score out of range: {self.consensus_score}")
        if not 0.0 <= self.conflict_score <= 1.0:
            errors.append(f"conflict_score out of range: {self.conflict_score}")
        if not 0.0 <= self.confidence_contribution <= 1.0:
            errors.append(f"confidence_contribution out of range: {self.confidence_contribution}")
        if not self.event_type:
            errors.append("event_type is required")
        return errors


@dataclass(frozen=True)
class EvidenceReasoning:
    """W6 output: grouped, weighted, deduplicated evidence sets for thesis construction."""

    reasoning_id: str
    collection_id: str
    timestamp: str
    regime: str
    evidence_sets: tuple[EvidenceSet, ...] = ()
    total_evidence_sets: int = 0
    total_evidence_items: int = 0
    duplicates_removed: int = 0
    metadata: dict[str, Any] = field(default_factory=lambda: FrozenDict())

    def __post_init__(self) -> None:
        object.__setattr__(self, "evidence_sets", tuple(self.evidence_sets))
        object.__setattr__(self, "metadata", freeze_dict(self.metadata))

    def to_dict(self) -> dict[str, Any]:
        return {
            "reasoning_id": self.reasoning_id,
            "collection_id": self.collection_id,
            "timestamp": self.timestamp,
            "regime": self.regime,
            "evidence_sets": [s.to_dict() for s in self.evidence_sets],
            "total_evidence_sets": self.total_evidence_sets,
            "total_evidence_items": self.total_evidence_items,
            "duplicates_removed": self.duplicates_removed,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> EvidenceReasoning:
        return cls(
            reasoning_id=str(data.get("reasoning_id", "")),
            collection_id=str(data.get("collection_id", "")),
            timestamp=str(data.get("timestamp", "")),
            regime=str(data.get("regime", "")),
            evidence_sets=tuple(EvidenceSet.from_dict(s) for s in data.get("evidence_sets", [])),
            total_evidence_sets=int(data.get("total_evidence_sets", 0)),
            total_evidence_items=int(data.get("total_evidence_items", 0)),
            duplicates_removed=int(data.get("duplicates_removed", 0)),
            metadata=dict(data.get("metadata", {})),
        )

    @property
    def avg_consensus_score(self) -> float:
        if not self.evidence_sets:
            return 0.0
        return round(sum(s.consensus_score for s in self.evidence_sets) / len(self.evidence_sets), 4)

    @property
    def avg_conflict_score(self) -> float:
        if not self.evidence_sets:
            return 0.0
        return round(sum(s.conflict_score for s in self.evidence_sets) / len(self.evidence_sets), 4)
