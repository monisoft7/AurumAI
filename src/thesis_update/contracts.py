"""Update-cycle contracts for the thesis update stage: the versioned update
note produced when an existing thesis is updated with new evidence.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from knowledge._compat import FrozenDict, freeze_dict
from knowledge.integrity.provenance import Provenance, serialize_provenance, deserialize_provenance
from thesis_construction.contracts import InvestmentThesis

VALID_ACTIONS = {"no_change", "scale", "hedge", "pause", "exit"}
VALID_TRIGGER_TYPES = {"periodic", "cumulative_evidence", "threshold_crossing", "regime_break"}


@dataclass(frozen=True)
class ThesisUpdate:
    """W10 output: immutable, versioned update of an existing thesis.

    The previous thesis is left untouched; `updated_thesis` is a new thesis
    version whose thesis_id carries the version suffix. The full history is
    preserved through the provenance chain.
    """

    update_id: str
    previous_thesis_id: str
    previous_version: str
    new_thesis_version: str
    reasoning_id: str
    assessment_id: str
    timestamp: str
    updated_evidence: tuple[str, ...]
    confidence_delta: float
    changed_assumptions: tuple[str, ...]
    change_summary: str
    action: str
    trigger_type: str
    updated_thesis: InvestmentThesis
    provenance_chain: tuple[Provenance, ...] = ()
    metadata: dict[str, Any] = field(default_factory=lambda: FrozenDict())

    def __post_init__(self) -> None:
        object.__setattr__(self, "updated_evidence", tuple(self.updated_evidence))
        object.__setattr__(self, "changed_assumptions", tuple(self.changed_assumptions))
        object.__setattr__(self, "provenance_chain", tuple(self.provenance_chain))
        object.__setattr__(self, "metadata", freeze_dict(self.metadata))

    def to_dict(self) -> dict[str, Any]:
        return {
            "update_id": self.update_id,
            "previous_thesis_id": self.previous_thesis_id,
            "previous_version": self.previous_version,
            "new_thesis_version": self.new_thesis_version,
            "reasoning_id": self.reasoning_id,
            "assessment_id": self.assessment_id,
            "timestamp": self.timestamp,
            "updated_evidence": list(self.updated_evidence),
            "confidence_delta": self.confidence_delta,
            "changed_assumptions": list(self.changed_assumptions),
            "change_summary": self.change_summary,
            "action": self.action,
            "trigger_type": self.trigger_type,
            "updated_thesis": self.updated_thesis.to_dict(),
            "provenance_chain": [serialize_provenance(p) for p in self.provenance_chain],
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ThesisUpdate:
        return cls(
            update_id=str(data.get("update_id", "")),
            previous_thesis_id=str(data.get("previous_thesis_id", "")),
            previous_version=str(data.get("previous_version", "")),
            new_thesis_version=str(data.get("new_thesis_version", "")),
            reasoning_id=str(data.get("reasoning_id", "")),
            assessment_id=str(data.get("assessment_id", "")),
            timestamp=str(data.get("timestamp", "")),
            updated_evidence=tuple(data.get("updated_evidence", ())),
            confidence_delta=float(data.get("confidence_delta", 0.0)),
            changed_assumptions=tuple(data.get("changed_assumptions", ())),
            change_summary=str(data.get("change_summary", "")),
            action=str(data.get("action", "")),
            trigger_type=str(data.get("trigger_type", "")),
            updated_thesis=InvestmentThesis.from_dict(data.get("updated_thesis", {})),
            provenance_chain=tuple(
                deserialize_provenance(p) for p in data.get("provenance_chain", []) if p is not None
            ),
            metadata=dict(data.get("metadata", {})),
        )

    def validate(self) -> list[str]:
        errors: list[str] = []
        if self.action not in VALID_ACTIONS:
            errors.append(f"invalid action: {self.action}")
        if self.trigger_type not in VALID_TRIGGER_TYPES:
            errors.append(f"invalid trigger_type: {self.trigger_type}")
        if not self.previous_thesis_id:
            errors.append("previous_thesis_id is required")
        if not self.new_thesis_version:
            errors.append("new_thesis_version is required")
        if not -1.0 <= self.confidence_delta <= 1.0:
            errors.append(f"confidence_delta out of range: {self.confidence_delta}")
        if self.updated_thesis.thesis_id == self.previous_thesis_id:
            errors.append("updated_thesis must be a new version, not the previous thesis")
        errors.extend(self.updated_thesis.validate())
        return errors
