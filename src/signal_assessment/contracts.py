from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from knowledge._compat import FrozenDict, freeze_dict


class ClassificationLabel(str, Enum):
    SIGNAL = "Signal"
    WEAK_SIGNAL = "Weak Signal"
    WATCH = "Watch"
    NOISE = "Noise"
    IGNORE = "Ignore"


VALID_LABELS = {e.value for e in ClassificationLabel}


@dataclass(frozen=True)
class CriterionScore:
    """Score for one of the 5 Meth. §7 noise/signal criteria."""

    criterion: str
    score: float
    threshold: float
    passed: bool
    detail: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "criterion": self.criterion,
            "score": self.score,
            "threshold": self.threshold,
            "passed": self.passed,
            "detail": self.detail,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CriterionScore:
        return cls(
            criterion=str(data.get("criterion", "")),
            score=float(data.get("score", 0.0)),
            threshold=float(data.get("threshold", 0.0)),
            passed=bool(data.get("passed", False)),
            detail=str(data.get("detail", "")),
        )


@dataclass(frozen=True)
class ClassifiedObservation:
    """A single observation from PreMarketBriefing with signal/noise classification."""

    observation_id: str
    source: str
    classification: str
    confidence: float
    regime: str
    reason: str
    evidence: tuple[CriterionScore, ...] = ()
    related_kr_ids: tuple[str, ...] = ()
    instrument: str = ""
    value: float = 0.0
    change_pct: float = 0.0
    change_sigma: float = 0.0

    def __post_init__(self) -> None:
        object.__setattr__(self, "evidence", tuple(self.evidence))
        object.__setattr__(self, "related_kr_ids", tuple(self.related_kr_ids))

    def to_dict(self) -> dict[str, Any]:
        return {
            "observation_id": self.observation_id,
            "source": self.source,
            "classification": self.classification,
            "confidence": self.confidence,
            "regime": self.regime,
            "reason": self.reason,
            "evidence": [e.to_dict() for e in self.evidence],
            "related_kr_ids": list(self.related_kr_ids),
            "instrument": self.instrument,
            "value": self.value,
            "change_pct": self.change_pct,
            "change_sigma": self.change_sigma,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ClassifiedObservation:
        return cls(
            observation_id=str(data.get("observation_id", "")),
            source=str(data.get("source", "")),
            classification=str(data.get("classification", "")),
            confidence=float(data.get("confidence", 0.0)),
            regime=str(data.get("regime", "")),
            reason=str(data.get("reason", "")),
            evidence=tuple(CriterionScore.from_dict(e) for e in data.get("evidence", [])),
            related_kr_ids=tuple(data.get("related_kr_ids", ())),
            instrument=str(data.get("instrument", "")),
            value=float(data.get("value", 0.0)),
            change_pct=float(data.get("change_pct", 0.0)),
            change_sigma=float(data.get("change_sigma", 0.0)),
        )


@dataclass(frozen=True)
class SignalAssessment:
    """W5 output contract: transforms PreMarketBriefing into classified observations."""

    assessment_id: str
    briefing_id: str
    timestamp: str
    regime: str
    regime_confidence: float
    observations: tuple[ClassifiedObservation, ...] = ()
    metadata: dict[str, Any] = field(default_factory=lambda: FrozenDict())

    def __post_init__(self) -> None:
        object.__setattr__(self, "observations", tuple(self.observations))
        object.__setattr__(self, "metadata", freeze_dict(self.metadata))

    def to_dict(self) -> dict[str, Any]:
        return {
            "assessment_id": self.assessment_id,
            "briefing_id": self.briefing_id,
            "timestamp": self.timestamp,
            "regime": self.regime,
            "regime_confidence": self.regime_confidence,
            "observations": [o.to_dict() for o in self.observations],
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SignalAssessment:
        return cls(
            assessment_id=str(data.get("assessment_id", "")),
            briefing_id=str(data.get("briefing_id", "")),
            timestamp=str(data.get("timestamp", "")),
            regime=str(data.get("regime", "")),
            regime_confidence=float(data.get("regime_confidence", 0.0)),
            observations=tuple(
                ClassifiedObservation.from_dict(o) for o in data.get("observations", [])
            ),
            metadata=dict(data.get("metadata", {})),
        )

    @property
    def signal_count(self) -> int:
        return sum(1 for o in self.observations if o.classification == ClassificationLabel.SIGNAL.value)

    @property
    def noise_count(self) -> int:
        return sum(1 for o in self.observations if o.classification == ClassificationLabel.NOISE.value)

    @property
    def weak_signal_count(self) -> int:
        return sum(1 for o in self.observations if o.classification == ClassificationLabel.WEAK_SIGNAL.value)
