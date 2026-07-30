from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from knowledge._compat import FrozenDict, freeze_dict
from knowledge.integrity.provenance import Provenance, serialize_provenance, deserialize_provenance

VALID_BIAS_FLAGS = {
    "confirmation_bias",
    "source_concentration",
    "regime_conflict",
    "temporal_conflict",
    "missing_evidence",
    "cross_set_conflict",
    "no_dissent",
}


@dataclass(frozen=True)
class CounterEvidenceAssessment:
    """W7 output: identifies everything that weakens, contradicts, or biases
    the current institutional evidence set."""

    assessment_id: str
    reasoning_id: str
    timestamp: str
    regime: str
    related_set_ids: tuple[str, ...] = ()
    supporting_set_ids: tuple[str, ...] = ()
    contradicting_set_ids: tuple[str, ...] = ()
    missing_evidence: tuple[str, ...] = ()
    bias_flags: tuple[str, ...] = ()
    conflict_severity: float = 0.0
    confidence_penalty: float = 0.0
    regime_conflict: bool = False
    explanation: str = ""
    provenance_chain: tuple[Provenance, ...] = ()
    metadata: dict[str, Any] = field(default_factory=lambda: FrozenDict())

    def __post_init__(self) -> None:
        object.__setattr__(self, "related_set_ids", tuple(self.related_set_ids))
        object.__setattr__(self, "supporting_set_ids", tuple(self.supporting_set_ids))
        object.__setattr__(self, "contradicting_set_ids", tuple(self.contradicting_set_ids))
        object.__setattr__(self, "missing_evidence", tuple(self.missing_evidence))
        object.__setattr__(self, "bias_flags", tuple(self.bias_flags))
        object.__setattr__(self, "provenance_chain", tuple(self.provenance_chain))
        object.__setattr__(self, "metadata", freeze_dict(self.metadata))

    def to_dict(self) -> dict[str, Any]:
        return {
            "assessment_id": self.assessment_id,
            "reasoning_id": self.reasoning_id,
            "timestamp": self.timestamp,
            "regime": self.regime,
            "related_set_ids": list(self.related_set_ids),
            "supporting_set_ids": list(self.supporting_set_ids),
            "contradicting_set_ids": list(self.contradicting_set_ids),
            "missing_evidence": list(self.missing_evidence),
            "bias_flags": list(self.bias_flags),
            "conflict_severity": self.conflict_severity,
            "confidence_penalty": self.confidence_penalty,
            "regime_conflict": self.regime_conflict,
            "explanation": self.explanation,
            "provenance_chain": [serialize_provenance(p) for p in self.provenance_chain],
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CounterEvidenceAssessment:
        return cls(
            assessment_id=str(data.get("assessment_id", "")),
            reasoning_id=str(data.get("reasoning_id", "")),
            timestamp=str(data.get("timestamp", "")),
            regime=str(data.get("regime", "")),
            related_set_ids=tuple(data.get("related_set_ids", ())),
            supporting_set_ids=tuple(data.get("supporting_set_ids", ())),
            contradicting_set_ids=tuple(data.get("contradicting_set_ids", ())),
            missing_evidence=tuple(data.get("missing_evidence", ())),
            bias_flags=tuple(data.get("bias_flags", ())),
            conflict_severity=float(data.get("conflict_severity", 0.0)),
            confidence_penalty=float(data.get("confidence_penalty", 0.0)),
            regime_conflict=bool(data.get("regime_conflict", False)),
            explanation=str(data.get("explanation", "")),
            provenance_chain=tuple(
                deserialize_provenance(p) for p in data.get("provenance_chain", []) if p is not None
            ),
            metadata=dict(data.get("metadata", {})),
        )

    def validate(self) -> list[str]:
        errors: list[str] = []
        for flag in self.bias_flags:
            if flag not in VALID_BIAS_FLAGS:
                errors.append(f"unknown bias flag: {flag}")
        if not 0.0 <= self.conflict_severity <= 1.0:
            errors.append(f"conflict_severity out of range: {self.conflict_severity}")
        if not 0.0 <= self.confidence_penalty <= 1.0:
            errors.append(f"confidence_penalty out of range: {self.confidence_penalty}")
        if not self.regime:
            errors.append("regime is required")
        return errors
