from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from knowledge._compat import FrozenDict, freeze_dict
from knowledge.regime.constants import (
    CANONICAL_REGIME_SET,
    VALID_TRANSITION_TYPES,
    REGIME_LABELS,
)


@dataclass(frozen=True)
class TriggerLevel:
    indicator: str = ""
    condition: str = ""
    target: str = ""
    threshold_value: float = 0.0
    direction: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "indicator": self.indicator,
            "condition": self.condition,
            "target": self.target,
            "threshold_value": self.threshold_value,
            "direction": self.direction,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TriggerLevel:
        return cls(
            indicator=str(data.get("indicator", "")),
            condition=str(data.get("condition", "")),
            target=str(data.get("target", "")),
            threshold_value=float(data.get("threshold_value", 0.0)),
            direction=str(data.get("direction", "")),
        )


@dataclass(frozen=True)
class RegimeIndicator:
    indicator: str = ""
    weight: float = 0.0
    description: str = ""
    tier: str = ""
    associated_kr_ids: tuple[str, ...] = ()
    data_source: str = ""
    frequency: str = ""
    unit: str = ""
    methodology_citation: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "associated_kr_ids", tuple(self.associated_kr_ids))

    def to_dict(self) -> dict[str, Any]:
        return {
            "indicator": self.indicator,
            "weight": self.weight,
            "description": self.description,
            "tier": self.tier,
            "associated_kr_ids": list(self.associated_kr_ids),
            "data_source": self.data_source,
            "frequency": self.frequency,
            "unit": self.unit,
            "methodology_citation": self.methodology_citation,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> RegimeIndicator:
        return cls(
            indicator=str(data.get("indicator", "")),
            weight=float(data.get("weight", 0.0)),
            description=str(data.get("description", "")),
            tier=str(data.get("tier", "")),
            associated_kr_ids=tuple(data.get("associated_kr_ids", ())),
            data_source=str(data.get("data_source", "")),
            frequency=str(data.get("frequency", "")),
            unit=str(data.get("unit", "")),
            methodology_citation=str(data.get("methodology_citation", "")),
        )


@dataclass(frozen=True)
class RegimeDiagnosis:
    regime: str = ""
    label: str = ""
    confidence: float = 0.0
    probabilities: dict[str, float] = field(default_factory=lambda: FrozenDict())
    in_transition: bool = False
    transition_type: str = "none"
    previous_regime: str = ""
    timestamp: str = ""
    transition_confidence: float = 0.0
    regime_duration_days: int = 0
    gram_residual: float = 0.0
    gram_trend: str = "stable"
    indicator_hierarchy: tuple[RegimeIndicator, ...] = ()
    trigger_levels: tuple[TriggerLevel, ...] = ()
    cross_asset_consistency: dict[str, Any] = field(default_factory=lambda: FrozenDict())

    def __post_init__(self) -> None:
        object.__setattr__(self, "probabilities", freeze_dict(self.probabilities))
        object.__setattr__(self, "cross_asset_consistency", freeze_dict(self.cross_asset_consistency))
        object.__setattr__(self, "indicator_hierarchy", tuple(self.indicator_hierarchy))
        object.__setattr__(self, "trigger_levels", tuple(self.trigger_levels))

    def to_dict(self) -> dict[str, Any]:
        return {
            "regime": self.regime,
            "label": self.label,
            "confidence": self.confidence,
            "probabilities": dict(self.probabilities),
            "in_transition": self.in_transition,
            "transition_type": self.transition_type,
            "previous_regime": self.previous_regime,
            "timestamp": self.timestamp,
            "transition_confidence": self.transition_confidence,
            "regime_duration_days": self.regime_duration_days,
            "gram_residual": self.gram_residual,
            "gram_trend": self.gram_trend,
            "indicator_hierarchy": [i.to_dict() for i in self.indicator_hierarchy],
            "trigger_levels": [t.to_dict() for t in self.trigger_levels],
            "cross_asset_consistency": dict(self.cross_asset_consistency),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> RegimeDiagnosis:
        return cls(
            regime=str(data.get("regime", "")),
            label=str(data.get("label", "")),
            confidence=float(data.get("confidence", 0.0)),
            probabilities=dict(data.get("probabilities", {})),
            in_transition=bool(data.get("in_transition", False)),
            transition_type=str(data.get("transition_type", "none")),
            previous_regime=str(data.get("previous_regime", "")),
            timestamp=str(data.get("timestamp", "")),
            transition_confidence=float(data.get("transition_confidence", 0.0)),
            regime_duration_days=int(data.get("regime_duration_days", 0)),
            gram_residual=float(data.get("gram_residual", 0.0)),
            gram_trend=str(data.get("gram_trend", "stable")),
            indicator_hierarchy=tuple(
                RegimeIndicator.from_dict(i) for i in data.get("indicator_hierarchy", [])
            ),
            trigger_levels=tuple(
                TriggerLevel.from_dict(t) for t in data.get("trigger_levels", [])
            ),
            cross_asset_consistency=dict(data.get("cross_asset_consistency", {})),
        )

    def validate(self) -> list[str]:
        errors: list[str] = []
        if self.regime not in CANONICAL_REGIME_SET:
            errors.append(f"unknown regime: {self.regime}")
        if not 0.0 <= self.confidence <= 1.0:
            errors.append("confidence out of range")
        if self.transition_type not in VALID_TRANSITION_TYPES:
            errors.append(f"unknown transition_type: {self.transition_type}")
        if self.in_transition and self.transition_type == "none":
            errors.append("in_transition=True but transition_type=none")
        if self.probabilities:
            total = sum(self.probabilities.values())
            if abs(total - 1.0) > 0.01:
                errors.append(f"probabilities sum to {total:.4f}, expected 1.0")
            actual_max = max(self.probabilities.values())
            if abs(actual_max - self.confidence) > 0.01:
                errors.append(f"confidence {self.confidence} != max probability {actual_max}")
        if self.gram_trend not in ("growing", "shrinking", "stable", ""):
            errors.append(f"unknown gram_trend: {self.gram_trend}")
        return errors
