"""W13 Institutional Trade Recommendation contracts."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from decision_engine.contracts import VALID_DECISIONS
from knowledge._compat import FrozenDict, freeze_dict
from knowledge.integrity.provenance import (
    Provenance,
    serialize_provenance,
    deserialize_provenance,
)


@dataclass(frozen=True)
class InstitutionalTradeRecommendation:
    """W13 output (final AurumAI v1.0 workflow): a complete, explainable
    trading recommendation that never violates the InstitutionalDecision."""

    recommendation_id: str
    decision_id: str
    recommendation_action: str
    instrument: str = ""
    entry_zone: tuple[str, ...] = ()
    stop_loss: str = ""
    take_profit_1: str = ""
    take_profit_2: str = ""
    position_size_recommendation: str = ""
    risk_pct: float = 0.0
    expected_holding_days: int = 0
    confidence: float = 0.0
    decision_summary: str = ""
    institutional_thesis_summary: str = ""
    major_supporting_evidence: tuple[str, ...] = ()
    major_counter_evidence: tuple[str, ...] = ()
    preconditions: tuple[str, ...] = ()
    invalidation_conditions: tuple[str, ...] = ()
    monitoring_conditions: tuple[str, ...] = ()
    provenance_chain: tuple[Provenance, ...] = ()
    metadata: dict[str, Any] = field(default_factory=lambda: FrozenDict())

    def __post_init__(self) -> None:
        object.__setattr__(self, "entry_zone", tuple(self.entry_zone))
        object.__setattr__(self, "major_supporting_evidence", tuple(self.major_supporting_evidence))
        object.__setattr__(self, "major_counter_evidence", tuple(self.major_counter_evidence))
        object.__setattr__(self, "preconditions", tuple(self.preconditions))
        object.__setattr__(
            self, "invalidation_conditions", tuple(self.invalidation_conditions)
        )
        object.__setattr__(self, "monitoring_conditions", tuple(self.monitoring_conditions))
        object.__setattr__(self, "provenance_chain", tuple(self.provenance_chain))
        object.__setattr__(self, "metadata", freeze_dict(self.metadata))

    def to_dict(self) -> dict[str, Any]:
        return {
            "recommendation_id": self.recommendation_id,
            "decision_id": self.decision_id,
            "recommendation_action": self.recommendation_action,
            "instrument": self.instrument,
            "entry_zone": list(self.entry_zone),
            "stop_loss": self.stop_loss,
            "take_profit_1": self.take_profit_1,
            "take_profit_2": self.take_profit_2,
            "position_size_recommendation": self.position_size_recommendation,
            "risk_pct": self.risk_pct,
            "expected_holding_days": self.expected_holding_days,
            "confidence": self.confidence,
            "decision_summary": self.decision_summary,
            "institutional_thesis_summary": self.institutional_thesis_summary,
            "major_supporting_evidence": list(self.major_supporting_evidence),
            "major_counter_evidence": list(self.major_counter_evidence),
            "preconditions": list(self.preconditions),
            "invalidation_conditions": list(self.invalidation_conditions),
            "monitoring_conditions": list(self.monitoring_conditions),
            "provenance_chain": [serialize_provenance(p) for p in self.provenance_chain],
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> InstitutionalTradeRecommendation:
        return cls(
            recommendation_id=str(data.get("recommendation_id", "")),
            decision_id=str(data.get("decision_id", "")),
            recommendation_action=str(data.get("recommendation_action", "")),
            instrument=str(data.get("instrument", "")),
            entry_zone=tuple(data.get("entry_zone", ())),
            stop_loss=str(data.get("stop_loss", "")),
            take_profit_1=str(data.get("take_profit_1", "")),
            take_profit_2=str(data.get("take_profit_2", "")),
            position_size_recommendation=str(
                data.get("position_size_recommendation", "")
            ),
            risk_pct=float(data.get("risk_pct", 0.0)),
            expected_holding_days=int(data.get("expected_holding_days", 0)),
            confidence=float(data.get("confidence", 0.0)),
            decision_summary=str(data.get("decision_summary", "")),
            institutional_thesis_summary=str(
                data.get("institutional_thesis_summary", "")
            ),
            major_supporting_evidence=tuple(data.get("major_supporting_evidence", ())),
            major_counter_evidence=tuple(data.get("major_counter_evidence", ())),
            preconditions=tuple(data.get("preconditions", ())),
            invalidation_conditions=tuple(data.get("invalidation_conditions", ())),
            monitoring_conditions=tuple(data.get("monitoring_conditions", ())),
            provenance_chain=tuple(
                deserialize_provenance(p)
                for p in data.get("provenance_chain", [])
                if p is not None
            ),
            metadata=dict(data.get("metadata", {})),
        )

    def validate(self) -> list[str]:
        errors: list[str] = []
        if not self.recommendation_id:
            errors.append("recommendation_id is required")
        if not self.decision_id:
            errors.append("decision_id is required")
        if self.recommendation_action not in VALID_DECISIONS:
            errors.append(f"invalid recommendation_action: {self.recommendation_action}")
        if not 0.0 <= self.confidence <= 1.0:
            errors.append(f"confidence out of range: {self.confidence}")
        if not 0.0 <= self.risk_pct <= 100.0:
            errors.append(f"risk_pct out of range: {self.risk_pct}")
        if self.recommendation_action in {"BUY", "SELL"}:
            if not self.instrument:
                errors.append("instrument is required for a directional recommendation")
            if not self.entry_zone:
                errors.append("entry_zone is required for a directional recommendation")
            if not self.stop_loss:
                errors.append("stop_loss is required for a directional recommendation")
            if not self.take_profit_1:
                errors.append("take_profit_1 is required for a directional recommendation")
            if not self.take_profit_2:
                errors.append("take_profit_2 is required for a directional recommendation")
            if not self.position_size_recommendation:
                errors.append(
                    "position_size_recommendation is required for a directional recommendation"
                )
            if self.risk_pct <= 0.0:
                errors.append("risk_pct must be positive for a directional recommendation")
            if self.expected_holding_days <= 0:
                errors.append(
                    "expected_holding_days must be positive for a directional recommendation"
                )
            if not self.major_supporting_evidence:
                errors.append(
                    "major_supporting_evidence is required for a directional recommendation"
                )
        if not self.decision_summary:
            errors.append("decision_summary is required")
        if not self.institutional_thesis_summary:
            errors.append("institutional_thesis_summary is required")
        if not self.provenance_chain:
            errors.append("provenance_chain is required")
        return errors
