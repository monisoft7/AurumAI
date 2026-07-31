from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from knowledge._compat import FrozenDict, freeze_dict
from knowledge.integrity.provenance import Provenance, serialize_provenance, deserialize_provenance

VALID_RELIABILITY = {"high", "moderate", "low", "very_low"}


@dataclass(frozen=True)
class ThesisConfidence:
    """Confidence assessment for a single Investment Thesis."""

    thesis_id: str
    final_confidence: float = 0.0
    confidence_breakdown: dict[str, float] = field(default_factory=lambda: FrozenDict())
    positive_contributors: tuple[dict[str, float], ...] = ()
    negative_contributors: tuple[dict[str, float], ...] = ()
    confidence_penalties: tuple[dict[str, float], ...] = ()
    remaining_uncertainty: float = 0.0
    reliability_category: str = "very_low"
    provenance_chain: tuple[Provenance, ...] = ()
    metadata: dict[str, Any] = field(default_factory=lambda: FrozenDict())

    def __post_init__(self) -> None:
        object.__setattr__(self, "confidence_breakdown", freeze_dict(self.confidence_breakdown))
        object.__setattr__(self, "positive_contributors", tuple(self.positive_contributors))
        object.__setattr__(self, "negative_contributors", tuple(self.negative_contributors))
        object.__setattr__(self, "confidence_penalties", tuple(self.confidence_penalties))
        object.__setattr__(self, "provenance_chain", tuple(self.provenance_chain))
        object.__setattr__(self, "metadata", freeze_dict(self.metadata))

    def to_dict(self) -> dict[str, Any]:
        return {
            "thesis_id": self.thesis_id,
            "final_confidence": self.final_confidence,
            "confidence_breakdown": dict(self.confidence_breakdown),
            "positive_contributors": [dict(c) for c in self.positive_contributors],
            "negative_contributors": [dict(c) for c in self.negative_contributors],
            "confidence_penalties": [dict(c) for c in self.confidence_penalties],
            "remaining_uncertainty": self.remaining_uncertainty,
            "reliability_category": self.reliability_category,
            "provenance_chain": [serialize_provenance(p) for p in self.provenance_chain],
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ThesisConfidence:
        return cls(
            thesis_id=str(data.get("thesis_id", "")),
            final_confidence=float(data.get("final_confidence", 0.0)),
            confidence_breakdown=dict(data.get("confidence_breakdown", {})),
            positive_contributors=tuple(
                dict(c) for c in data.get("positive_contributors", [])
            ),
            negative_contributors=tuple(
                dict(c) for c in data.get("negative_contributors", [])
            ),
            confidence_penalties=tuple(
                dict(c) for c in data.get("confidence_penalties", [])
            ),
            remaining_uncertainty=float(data.get("remaining_uncertainty", 0.0)),
            reliability_category=str(data.get("reliability_category", "very_low")),
            provenance_chain=tuple(
                deserialize_provenance(p)
                for p in data.get("provenance_chain", [])
                if p is not None
            ),
            metadata=dict(data.get("metadata", {})),
        )

    def validate(self) -> list[str]:
        errors: list[str] = []
        if not 0.0 <= self.final_confidence <= 1.0:
            errors.append(f"final_confidence out of range: {self.final_confidence}")
        if not 0.0 <= self.remaining_uncertainty <= 1.0:
            errors.append(f"remaining_uncertainty out of range: {self.remaining_uncertainty}")
        if self.reliability_category not in VALID_RELIABILITY:
            errors.append(f"invalid reliability_category: {self.reliability_category}")
        if not self.thesis_id:
            errors.append("thesis_id is required")
        return errors


@dataclass(frozen=True)
class InstitutionalConfidence:
    """W9 output: confidence assessment for every thesis in ThesisConstruction."""

    confidence_id: str
    construction_id: str
    timestamp: str
    regime: str
    theses_confidence: tuple[ThesisConfidence, ...] = ()
    ranked_thesis_ids: tuple[str, ...] = ()
    low_confidence_thesis_ids: tuple[str, ...] = ()
    conflicting_high_confidence_pairs: tuple[tuple[str, str], ...] = ()
    primary_thesis_id: str = ""
    metadata: dict[str, Any] = field(default_factory=lambda: FrozenDict())

    def __post_init__(self) -> None:
        object.__setattr__(self, "theses_confidence", tuple(self.theses_confidence))
        object.__setattr__(self, "ranked_thesis_ids", tuple(self.ranked_thesis_ids))
        object.__setattr__(self, "low_confidence_thesis_ids", tuple(self.low_confidence_thesis_ids))
        object.__setattr__(
            self,
            "conflicting_high_confidence_pairs",
            tuple(tuple(p) for p in self.conflicting_high_confidence_pairs),
        )
        object.__setattr__(self, "metadata", freeze_dict(self.metadata))

    def to_dict(self) -> dict[str, Any]:
        return {
            "confidence_id": self.confidence_id,
            "construction_id": self.construction_id,
            "timestamp": self.timestamp,
            "regime": self.regime,
            "theses_confidence": [tc.to_dict() for tc in self.theses_confidence],
            "ranked_thesis_ids": list(self.ranked_thesis_ids),
            "low_confidence_thesis_ids": list(self.low_confidence_thesis_ids),
            "conflicting_high_confidence_pairs": [
                list(p) for p in self.conflicting_high_confidence_pairs
            ],
            "primary_thesis_id": self.primary_thesis_id,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> InstitutionalConfidence:
        return cls(
            confidence_id=str(data.get("confidence_id", "")),
            construction_id=str(data.get("construction_id", "")),
            timestamp=str(data.get("timestamp", "")),
            regime=str(data.get("regime", "")),
            theses_confidence=tuple(
                ThesisConfidence.from_dict(tc) for tc in data.get("theses_confidence", [])
            ),
            ranked_thesis_ids=tuple(data.get("ranked_thesis_ids", ())),
            low_confidence_thesis_ids=tuple(data.get("low_confidence_thesis_ids", ())),
            conflicting_high_confidence_pairs=tuple(
                tuple(p) for p in data.get("conflicting_high_confidence_pairs", [])
            ),
            primary_thesis_id=str(data.get("primary_thesis_id", "")),
            metadata=dict(data.get("metadata", {})),
        )

    @property
    def primary_confidence(self) -> ThesisConfidence | None:
        for tc in self.theses_confidence:
            if tc.thesis_id == self.primary_thesis_id:
                return tc
        return None

    @property
    def avg_confidence(self) -> float:
        if not self.theses_confidence:
            return 0.0
        return round(
            sum(tc.final_confidence for tc in self.theses_confidence)
            / len(self.theses_confidence),
            4,
        )
