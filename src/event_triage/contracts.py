"""Tiering contracts for the institutional signal tiering stage: tier levels,
per-observation assignments, and the aggregate tiering result contract.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from knowledge._compat import FrozenDict, freeze_dict


class TierLevel(str, Enum):
    """Institutional priority tiers, ordered from most to least urgent."""

    TIER_1 = "Tier 1"
    TIER_2 = "Tier 2"
    TIER_3 = "Tier 3"
    TIER_4 = "Tier 4"


VALID_TIERS = {t.value for t in TierLevel}

TIER_RANK = {t.value: i + 1 for i, t in enumerate(TierLevel)}


@dataclass(frozen=True)
class TierAssignment:
    """Tiering result for a single classified observation.

    portfolio_impact, regime_relevance and price_impact are the W4 triplet
    scores (0 to 1) used to derive the tier, so every assignment is
    auditable and explainable.
    """

    observation_id: str
    tier: str
    classification: str
    confidence: float
    instrument: str
    portfolio_impact: float
    regime_relevance: float
    price_impact: float
    reason: str
    trigger_level: str = ""
    monitoring_frequency: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "tier", str(self.tier))
        object.__setattr__(self, "monitoring_frequency", str(self.monitoring_frequency))

    def to_dict(self) -> dict[str, Any]:
        return {
            "observation_id": self.observation_id,
            "tier": self.tier,
            "classification": self.classification,
            "confidence": self.confidence,
            "instrument": self.instrument,
            "portfolio_impact": self.portfolio_impact,
            "regime_relevance": self.regime_relevance,
            "price_impact": self.price_impact,
            "reason": self.reason,
            "trigger_level": self.trigger_level,
            "monitoring_frequency": self.monitoring_frequency,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TierAssignment:
        return cls(
            observation_id=str(data.get("observation_id", "")),
            tier=str(data.get("tier", "")),
            classification=str(data.get("classification", "")),
            confidence=float(data.get("confidence", 0.0)),
            instrument=str(data.get("instrument", "")),
            portfolio_impact=float(data.get("portfolio_impact", 0.0)),
            regime_relevance=float(data.get("regime_relevance", 0.0)),
            price_impact=float(data.get("price_impact", 0.0)),
            reason=str(data.get("reason", "")),
            trigger_level=str(data.get("trigger_level", "")),
            monitoring_frequency=str(data.get("monitoring_frequency", "")),
        )


@dataclass(frozen=True)
class SignalTiering:
    """W4 output: institutional tier assignment for every observation.

    The prioritized watchlist (Tier 1 first, then Tier 2, Tier 3, Tier 4)
    carries explicit trigger levels for Tier 1 and Tier 2 entries.
    """

    tiering_id: str
    assessment_id: str
    timestamp: str
    regime: str
    assignments: tuple[TierAssignment, ...] = ()
    metadata: dict[str, Any] = field(default_factory=lambda: FrozenDict())

    def __post_init__(self) -> None:
        object.__setattr__(self, "assignments", tuple(self.assignments))
        object.__setattr__(self, "metadata", freeze_dict(self.metadata))

    def to_dict(self) -> dict[str, Any]:
        return {
            "tiering_id": self.tiering_id,
            "assessment_id": self.assessment_id,
            "timestamp": self.timestamp,
            "regime": self.regime,
            "assignments": [a.to_dict() for a in self.assignments],
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SignalTiering:
        return cls(
            tiering_id=str(data.get("tiering_id", "")),
            assessment_id=str(data.get("assessment_id", "")),
            timestamp=str(data.get("timestamp", "")),
            regime=str(data.get("regime", "")),
            assignments=tuple(TierAssignment.from_dict(a) for a in data.get("assignments", [])),
            metadata=dict(data.get("metadata", {})),
        )

    def validate(self) -> list[str]:
        errors: list[str] = []
        for assignment in self.assignments:
            if assignment.tier not in VALID_TIERS:
                errors.append(f"invalid tier: {assignment.tier}")
            for label, score in (
                ("portfolio_impact", assignment.portfolio_impact),
                ("regime_relevance", assignment.regime_relevance),
                ("price_impact", assignment.price_impact),
            ):
                if not 0.0 <= score <= 1.0:
                    errors.append(f"{assignment.observation_id}: {label} out of range: {score}")
            if assignment.tier in ("Tier 1", "Tier 2") and not assignment.trigger_level:
                errors.append(f"{assignment.observation_id}: Tier 1/2 requires a trigger level")
        return errors

    @property
    def tier1_count(self) -> int:
        return sum(1 for a in self.assignments if a.tier == "Tier 1")

    @property
    def tier2_count(self) -> int:
        return sum(1 for a in self.assignments if a.tier == "Tier 2")

    @property
    def tier3_count(self) -> int:
        return sum(1 for a in self.assignments if a.tier == "Tier 3")

    @property
    def tier4_count(self) -> int:
        return sum(1 for a in self.assignments if a.tier == "Tier 4")

    @property
    def tier_counts(self) -> dict[str, int]:
        return {
            "tier1": self.tier1_count,
            "tier2": self.tier2_count,
            "tier3": self.tier3_count,
            "tier4": self.tier4_count,
        }

    @property
    def prioritized_watchlist(self) -> list[dict[str, Any]]:
        """Ordered watchlist: Tier 1 first, then Tier 2, Tier 3, Tier 4."""
        ordered = sorted(
            self.assignments,
            key=lambda a: TIER_RANK.get(a.tier, 4),
        )
        return [a.to_dict() for a in ordered]
