from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from knowledge._compat import FrozenDict, freeze_dict
from knowledge.integrity.provenance import Provenance, serialize_provenance, deserialize_provenance

VALID_DIRECTIONS = {"bullish", "bearish", "neutral"}


@dataclass(frozen=True)
class InvestmentThesis:
    """A single institutional investment thesis built from weighted evidence."""

    thesis_id: str
    direction: str
    supporting_set_ids: tuple[str, ...] = ()
    counter_evidence_ids: tuple[str, ...] = ()
    regime: str = ""
    economic_mechanism: str = ""
    time_horizon_days: int = 90
    invalidating_conditions: tuple[str, ...] = ()
    remaining_unknowns: tuple[str, ...] = ()
    confidence_inputs: dict[str, float] = field(default_factory=lambda: FrozenDict())
    institutional_support: float = 0.0
    explanation: str = ""
    provenance_chain: tuple[Provenance, ...] = ()
    metadata: dict[str, Any] = field(default_factory=lambda: FrozenDict())

    def __post_init__(self) -> None:
        object.__setattr__(self, "supporting_set_ids", tuple(self.supporting_set_ids))
        object.__setattr__(self, "counter_evidence_ids", tuple(self.counter_evidence_ids))
        object.__setattr__(self, "invalidating_conditions", tuple(self.invalidating_conditions))
        object.__setattr__(self, "remaining_unknowns", tuple(self.remaining_unknowns))
        object.__setattr__(self, "confidence_inputs", freeze_dict(self.confidence_inputs))
        object.__setattr__(self, "provenance_chain", tuple(self.provenance_chain))
        object.__setattr__(self, "metadata", freeze_dict(self.metadata))

    def to_dict(self) -> dict[str, Any]:
        return {
            "thesis_id": self.thesis_id,
            "direction": self.direction,
            "supporting_set_ids": list(self.supporting_set_ids),
            "counter_evidence_ids": list(self.counter_evidence_ids),
            "regime": self.regime,
            "economic_mechanism": self.economic_mechanism,
            "time_horizon_days": self.time_horizon_days,
            "invalidating_conditions": list(self.invalidating_conditions),
            "remaining_unknowns": list(self.remaining_unknowns),
            "confidence_inputs": dict(self.confidence_inputs),
            "institutional_support": self.institutional_support,
            "explanation": self.explanation,
            "provenance_chain": [serialize_provenance(p) for p in self.provenance_chain],
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> InvestmentThesis:
        return cls(
            thesis_id=str(data.get("thesis_id", "")),
            direction=str(data.get("direction", "")),
            supporting_set_ids=tuple(data.get("supporting_set_ids", ())),
            counter_evidence_ids=tuple(data.get("counter_evidence_ids", ())),
            regime=str(data.get("regime", "")),
            economic_mechanism=str(data.get("economic_mechanism", "")),
            time_horizon_days=int(data.get("time_horizon_days", 90)),
            invalidating_conditions=tuple(data.get("invalidating_conditions", ())),
            remaining_unknowns=tuple(data.get("remaining_unknowns", ())),
            confidence_inputs=dict(data.get("confidence_inputs", {})),
            institutional_support=float(data.get("institutional_support", 0.0)),
            explanation=str(data.get("explanation", "")),
            provenance_chain=tuple(
                deserialize_provenance(p) for p in data.get("provenance_chain", []) if p is not None
            ),
            metadata=dict(data.get("metadata", {})),
        )

    def validate(self) -> list[str]:
        errors: list[str] = []
        if self.direction not in VALID_DIRECTIONS:
            errors.append(f"invalid direction: {self.direction}")
        if not 0.0 <= self.institutional_support <= 1.0:
            errors.append(f"institutional_support out of range: {self.institutional_support}")
        if self.time_horizon_days <= 0:
            errors.append(f"time_horizon_days must be positive: {self.time_horizon_days}")
        return errors


@dataclass(frozen=True)
class ThesisConstruction:
    """W8 output: collection of competing investment theses ranked by support."""

    construction_id: str
    reasoning_id: str
    assessment_id: str
    timestamp: str
    regime: str
    theses: tuple[InvestmentThesis, ...] = ()
    ranked_thesis_ids: tuple[str, ...] = ()
    total_theses: int = 0
    primary_thesis_id: str = ""
    metadata: dict[str, Any] = field(default_factory=lambda: FrozenDict())

    def __post_init__(self) -> None:
        object.__setattr__(self, "theses", tuple(self.theses))
        object.__setattr__(self, "ranked_thesis_ids", tuple(self.ranked_thesis_ids))
        object.__setattr__(self, "metadata", freeze_dict(self.metadata))

    def to_dict(self) -> dict[str, Any]:
        return {
            "construction_id": self.construction_id,
            "reasoning_id": self.reasoning_id,
            "assessment_id": self.assessment_id,
            "timestamp": self.timestamp,
            "regime": self.regime,
            "theses": [t.to_dict() for t in self.theses],
            "ranked_thesis_ids": list(self.ranked_thesis_ids),
            "total_theses": self.total_theses,
            "primary_thesis_id": self.primary_thesis_id,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ThesisConstruction:
        return cls(
            construction_id=str(data.get("construction_id", "")),
            reasoning_id=str(data.get("reasoning_id", "")),
            assessment_id=str(data.get("assessment_id", "")),
            timestamp=str(data.get("timestamp", "")),
            regime=str(data.get("regime", "")),
            theses=tuple(InvestmentThesis.from_dict(t) for t in data.get("theses", [])),
            ranked_thesis_ids=tuple(data.get("ranked_thesis_ids", ())),
            total_theses=int(data.get("total_theses", 0)),
            primary_thesis_id=str(data.get("primary_thesis_id", "")),
            metadata=dict(data.get("metadata", {})),
        )

    @property
    def primary_thesis(self) -> InvestmentThesis | None:
        for t in self.theses:
            if t.thesis_id == self.primary_thesis_id:
                return t
        return None
