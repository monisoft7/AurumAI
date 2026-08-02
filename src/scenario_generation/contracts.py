"""W12 Institutional Scenario Generation contracts."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from knowledge._compat import FrozenDict, freeze_dict
from knowledge.integrity.provenance import (
    Provenance,
    serialize_provenance,
    deserialize_provenance,
)
from thesis_construction.contracts import VALID_DIRECTIONS

VALID_SCENARIO_TYPES = {"base", "bull", "bear"}

SCENARIO_TYPE_LABELS = {
    "base": "Base Case",
    "bull": "Bull Case",
    "bear": "Bear Case",
}

PROBABILITY_EPSILON = 1e-4


@dataclass(frozen=True)
class InstitutionalScenario:
    """A single forward-looking market scenario for one investment thesis."""

    scenario_id: str
    thesis_id: str
    scenario_type: str
    probability: float
    expected_direction: str
    time_horizon_days: int
    expected_catalysts: tuple[str, ...] = ()
    assumptions: tuple[str, ...] = ()
    confirmation_conditions: tuple[str, ...] = ()
    invalidation_conditions: tuple[str, ...] = ()
    regime_path: tuple[str, ...] = ()
    confidence_inputs: dict[str, float] = field(default_factory=lambda: FrozenDict())
    provenance_chain: tuple[Provenance, ...] = ()
    metadata: dict[str, Any] = field(default_factory=lambda: FrozenDict())

    def __post_init__(self) -> None:
        object.__setattr__(self, "expected_catalysts", tuple(self.expected_catalysts))
        object.__setattr__(self, "assumptions", tuple(self.assumptions))
        object.__setattr__(
            self, "confirmation_conditions", tuple(self.confirmation_conditions)
        )
        object.__setattr__(
            self, "invalidation_conditions", tuple(self.invalidation_conditions)
        )
        object.__setattr__(self, "regime_path", tuple(self.regime_path))
        object.__setattr__(self, "confidence_inputs", freeze_dict(self.confidence_inputs))
        object.__setattr__(self, "provenance_chain", tuple(self.provenance_chain))
        object.__setattr__(self, "metadata", freeze_dict(self.metadata))

    def to_dict(self) -> dict[str, Any]:
        return {
            "scenario_id": self.scenario_id,
            "thesis_id": self.thesis_id,
            "scenario_type": self.scenario_type,
            "probability": self.probability,
            "expected_direction": self.expected_direction,
            "time_horizon_days": self.time_horizon_days,
            "expected_catalysts": list(self.expected_catalysts),
            "assumptions": list(self.assumptions),
            "confirmation_conditions": list(self.confirmation_conditions),
            "invalidation_conditions": list(self.invalidation_conditions),
            "regime_path": list(self.regime_path),
            "confidence_inputs": dict(self.confidence_inputs),
            "provenance_chain": [serialize_provenance(p) for p in self.provenance_chain],
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> InstitutionalScenario:
        return cls(
            scenario_id=str(data.get("scenario_id", "")),
            thesis_id=str(data.get("thesis_id", "")),
            scenario_type=str(data.get("scenario_type", "")),
            probability=float(data.get("probability", 0.0)),
            expected_direction=str(data.get("expected_direction", "")),
            time_horizon_days=int(data.get("time_horizon_days", 90)),
            expected_catalysts=tuple(data.get("expected_catalysts", ())),
            assumptions=tuple(data.get("assumptions", ())),
            confirmation_conditions=tuple(data.get("confirmation_conditions", ())),
            invalidation_conditions=tuple(data.get("invalidation_conditions", ())),
            regime_path=tuple(data.get("regime_path", ())),
            confidence_inputs=dict(data.get("confidence_inputs", {})),
            provenance_chain=tuple(
                deserialize_provenance(p)
                for p in data.get("provenance_chain", [])
                if p is not None
            ),
            metadata=dict(data.get("metadata", {})),
        )

    def validate(self) -> list[str]:
        errors: list[str] = []
        if not self.scenario_id:
            errors.append("scenario_id is required")
        if not self.thesis_id:
            errors.append("thesis_id is required")
        if self.scenario_type not in VALID_SCENARIO_TYPES:
            errors.append(f"invalid scenario_type: {self.scenario_type}")
        if not 0.0 <= self.probability <= 1.0:
            errors.append(f"probability out of range: {self.probability}")
        if self.expected_direction not in VALID_DIRECTIONS:
            errors.append(f"invalid expected_direction: {self.expected_direction}")
        if self.time_horizon_days <= 0:
            errors.append(f"time_horizon_days must be positive: {self.time_horizon_days}")
        if not self.regime_path:
            errors.append("regime_path is required")
        return errors


@dataclass(frozen=True)
class ScenarioGeneration:
    """W12 output: institutional forward-looking scenarios for every thesis."""

    scenario_generation_id: str
    construction_id: str
    confidence_id: str
    timestamp: str
    regime: str
    scenarios: tuple[InstitutionalScenario, ...] = ()
    thesis_ids: tuple[str, ...] = ()
    total_scenarios: int = 0
    probability_consistency: dict[str, float] = field(default_factory=lambda: FrozenDict())
    metadata: dict[str, Any] = field(default_factory=lambda: FrozenDict())

    def __post_init__(self) -> None:
        object.__setattr__(self, "scenarios", tuple(self.scenarios))
        object.__setattr__(self, "thesis_ids", tuple(self.thesis_ids))
        object.__setattr__(
            self, "probability_consistency", freeze_dict(self.probability_consistency)
        )
        object.__setattr__(self, "metadata", freeze_dict(self.metadata))

    def to_dict(self) -> dict[str, Any]:
        return {
            "scenario_generation_id": self.scenario_generation_id,
            "construction_id": self.construction_id,
            "confidence_id": self.confidence_id,
            "timestamp": self.timestamp,
            "regime": self.regime,
            "scenarios": [s.to_dict() for s in self.scenarios],
            "thesis_ids": list(self.thesis_ids),
            "total_scenarios": self.total_scenarios,
            "probability_consistency": dict(self.probability_consistency),
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ScenarioGeneration:
        return cls(
            scenario_generation_id=str(data.get("scenario_generation_id", "")),
            construction_id=str(data.get("construction_id", "")),
            confidence_id=str(data.get("confidence_id", "")),
            timestamp=str(data.get("timestamp", "")),
            regime=str(data.get("regime", "")),
            scenarios=tuple(
                InstitutionalScenario.from_dict(s) for s in data.get("scenarios", [])
            ),
            thesis_ids=tuple(data.get("thesis_ids", ())),
            total_scenarios=int(data.get("total_scenarios", 0)),
            probability_consistency=dict(data.get("probability_consistency", {})),
            metadata=dict(data.get("metadata", {})),
        )

    @property
    def scenarios_by_thesis(self) -> dict[str, tuple[InstitutionalScenario, ...]]:
        by_thesis: dict[str, list[InstitutionalScenario]] = {}
        for s in self.scenarios:
            by_thesis.setdefault(s.thesis_id, []).append(s)
        return {tid: tuple(items) for tid, items in by_thesis.items()}

    def validate(self) -> list[str]:
        errors: list[str] = []
        if not self.scenario_generation_id:
            errors.append("scenario_generation_id is required")
        if not self.construction_id:
            errors.append("construction_id is required")
        if not self.confidence_id:
            errors.append("confidence_id is required")
        for scenario in self.scenarios:
            errors.extend(f"{scenario.scenario_id}: {e}" for e in scenario.validate())
        if self.total_scenarios != len(self.scenarios):
            errors.append(
                f"total_scenarios mismatch: {self.total_scenarios} != {len(self.scenarios)}"
            )
        if self.total_scenarios != 3 * len(self.thesis_ids):
            errors.append(
                "expected exactly 3 scenarios (base/bull/bear) per thesis"
            )
        expected_sums = {tid: 1.0 for tid in self.thesis_ids}
        for tid, expected in expected_sums.items():
            actual = self.probability_consistency.get(tid, 0.0)
            if abs(actual - expected) > PROBABILITY_EPSILON:
                errors.append(
                    f"probability sum for thesis {tid} is {actual}, expected ~1.0"
                )
        return errors
