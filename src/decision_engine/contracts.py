"""W12 Institutional Decision Engine contracts."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from knowledge._compat import FrozenDict, freeze_dict
from knowledge.integrity.provenance import (
    Provenance,
    serialize_provenance,
    deserialize_provenance,
)

VALID_DECISIONS = {"BUY", "SELL", "HOLD", "NO_TRADE"}

DECISION_LABELS = {
    "BUY": "Buy",
    "SELL": "Sell",
    "HOLD": "Hold",
    "NO_TRADE": "No Trade",
}


@dataclass(frozen=True)
class DecisionDriver:
    """A single decision driver with its weighted contribution."""

    name: str
    value: float
    weight: float
    score: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "value": self.value,
            "weight": self.weight,
            "score": self.score,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DecisionDriver:
        return cls(
            name=str(data.get("name", "")),
            value=float(data.get("value", 0.0)),
            weight=float(data.get("weight", 0.0)),
            score=float(data.get("score", 0.0)),
        )

    def validate(self) -> list[str]:
        errors: list[str] = []
        if not self.name:
            errors.append("name is required")
        if not 0.0 <= self.value <= 1.0:
            errors.append(f"value out of range: {self.value}")
        if not 0.0 <= self.weight <= 1.0:
            errors.append(f"weight out of range: {self.weight}")
        return errors


@dataclass(frozen=True)
class RejectedAlternative:
    """A thesis that was not selected, with the reason for rejection."""

    thesis_id: str
    thesis_direction: str
    composite_score: float
    rejection_reason: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "thesis_id": self.thesis_id,
            "thesis_direction": self.thesis_direction,
            "composite_score": self.composite_score,
            "rejection_reason": self.rejection_reason,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> RejectedAlternative:
        return cls(
            thesis_id=str(data.get("thesis_id", "")),
            thesis_direction=str(data.get("thesis_direction", "")),
            composite_score=float(data.get("composite_score", 0.0)),
            rejection_reason=str(data.get("rejection_reason", "")),
        )

    def validate(self) -> list[str]:
        errors: list[str] = []
        if not self.thesis_id:
            errors.append("thesis_id is required")
        if not self.rejection_reason:
            errors.append("rejection_reason is required")
        return errors


@dataclass(frozen=True)
class InstitutionalDecision:
    """W12 output: exactly one institutional decision (BUY / SELL / HOLD / NO TRADE)."""

    decision_id: str
    decision: str
    selected_thesis_id: str
    selected_scenario_id: str
    institutional_confidence: float
    risk_reward_summary: dict[str, Any] = field(default_factory=lambda: FrozenDict())
    decision_drivers: tuple[DecisionDriver, ...] = ()
    rejected_alternatives: tuple[RejectedAlternative, ...] = ()
    decision_explanation: str = ""
    preconditions: tuple[str, ...] = ()
    invalidation_conditions: tuple[str, ...] = ()
    provenance_chain: tuple[Provenance, ...] = ()
    metadata: dict[str, Any] = field(default_factory=lambda: FrozenDict())

    def __post_init__(self) -> None:
        object.__setattr__(self, "risk_reward_summary", freeze_dict(self.risk_reward_summary))
        object.__setattr__(self, "decision_drivers", tuple(self.decision_drivers))
        object.__setattr__(
            self, "rejected_alternatives", tuple(self.rejected_alternatives)
        )
        object.__setattr__(self, "preconditions", tuple(self.preconditions))
        object.__setattr__(
            self, "invalidation_conditions", tuple(self.invalidation_conditions)
        )
        object.__setattr__(self, "provenance_chain", tuple(self.provenance_chain))
        object.__setattr__(self, "metadata", freeze_dict(self.metadata))

    def to_dict(self) -> dict[str, Any]:
        return {
            "decision_id": self.decision_id,
            "decision": self.decision,
            "selected_thesis_id": self.selected_thesis_id,
            "selected_scenario_id": self.selected_scenario_id,
            "institutional_confidence": self.institutional_confidence,
            "risk_reward_summary": dict(self.risk_reward_summary),
            "decision_drivers": [d.to_dict() for d in self.decision_drivers],
            "rejected_alternatives": [r.to_dict() for r in self.rejected_alternatives],
            "decision_explanation": self.decision_explanation,
            "preconditions": list(self.preconditions),
            "invalidation_conditions": list(self.invalidation_conditions),
            "provenance_chain": [serialize_provenance(p) for p in self.provenance_chain],
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> InstitutionalDecision:
        return cls(
            decision_id=str(data.get("decision_id", "")),
            decision=str(data.get("decision", "")),
            selected_thesis_id=str(data.get("selected_thesis_id", "")),
            selected_scenario_id=str(data.get("selected_scenario_id", "")),
            institutional_confidence=float(data.get("institutional_confidence", 0.0)),
            risk_reward_summary=dict(data.get("risk_reward_summary", {})),
            decision_drivers=tuple(
                DecisionDriver.from_dict(d) for d in data.get("decision_drivers", [])
            ),
            rejected_alternatives=tuple(
                RejectedAlternative.from_dict(r)
                for r in data.get("rejected_alternatives", [])
            ),
            decision_explanation=str(data.get("decision_explanation", "")),
            preconditions=tuple(data.get("preconditions", ())),
            invalidation_conditions=tuple(data.get("invalidation_conditions", ())),
            provenance_chain=tuple(
                deserialize_provenance(p)
                for p in data.get("provenance_chain", [])
                if p is not None
            ),
            metadata=dict(data.get("metadata", {})),
        )

    def validate(self) -> list[str]:
        errors: list[str] = []
        if not self.decision_id:
            errors.append("decision_id is required")
        if self.decision not in VALID_DECISIONS:
            errors.append(f"invalid decision: {self.decision}")
        if not 0.0 <= self.institutional_confidence <= 1.0:
            errors.append(
                f"institutional_confidence out of range: {self.institutional_confidence}"
            )
        if self.decision != "NO_TRADE":
            if not self.selected_thesis_id:
                errors.append("selected_thesis_id is required for a directional decision")
            if not self.selected_scenario_id:
                errors.append("selected_scenario_id is required for a directional decision")
            if not self.preconditions:
                errors.append("preconditions are required for a directional decision")
            if not self.invalidation_conditions:
                errors.append(
                    "invalidation_conditions are required for a directional decision"
                )
        if not self.decision_explanation:
            errors.append("decision_explanation is required")
        for driver in self.decision_drivers:
            errors.extend(f"{driver.name}: {e}" for e in driver.validate())
        for alt in self.rejected_alternatives:
            errors.extend(f"{alt.thesis_id}: {e}" for e in alt.validate())
        return errors
