"""W11 Institutional Risk / Reward Validation contracts."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from knowledge._compat import FrozenDict, freeze_dict
from knowledge.integrity.provenance import (
    Provenance,
    serialize_provenance,
    deserialize_provenance,
)

VALID_VALIDATION_STATUS = {"acceptable", "borderline", "reject"}

VALIDATION_STATUS_LABELS = {
    "acceptable": "Acceptable",
    "borderline": "Borderline",
    "reject": "Reject",
}


@dataclass(frozen=True)
class InstitutionalRiskValidation:
    """Risk / reward validation for a single institutional scenario."""

    validation_id: str
    scenario_id: str
    thesis_id: str
    validation_status: str
    expected_reward: float
    expected_risk: float
    risk_reward_ratio: float
    maximum_downside: float
    expected_upside: float
    volatility_impact: float
    regime_risk: float
    liquidity_risk: float
    tail_risk: float
    validation_explanation: str = ""
    provenance_chain: tuple[Provenance, ...] = ()
    metadata: dict[str, Any] = field(default_factory=lambda: FrozenDict())

    def __post_init__(self) -> None:
        object.__setattr__(self, "provenance_chain", tuple(self.provenance_chain))
        object.__setattr__(self, "metadata", freeze_dict(self.metadata))

    def to_dict(self) -> dict[str, Any]:
        return {
            "validation_id": self.validation_id,
            "scenario_id": self.scenario_id,
            "thesis_id": self.thesis_id,
            "validation_status": self.validation_status,
            "expected_reward": self.expected_reward,
            "expected_risk": self.expected_risk,
            "risk_reward_ratio": self.risk_reward_ratio,
            "maximum_downside": self.maximum_downside,
            "expected_upside": self.expected_upside,
            "volatility_impact": self.volatility_impact,
            "regime_risk": self.regime_risk,
            "liquidity_risk": self.liquidity_risk,
            "tail_risk": self.tail_risk,
            "validation_explanation": self.validation_explanation,
            "provenance_chain": [serialize_provenance(p) for p in self.provenance_chain],
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> InstitutionalRiskValidation:
        return cls(
            validation_id=str(data.get("validation_id", "")),
            scenario_id=str(data.get("scenario_id", "")),
            thesis_id=str(data.get("thesis_id", "")),
            validation_status=str(data.get("validation_status", "")),
            expected_reward=float(data.get("expected_reward", 0.0)),
            expected_risk=float(data.get("expected_risk", 0.0)),
            risk_reward_ratio=float(data.get("risk_reward_ratio", 0.0)),
            maximum_downside=float(data.get("maximum_downside", 0.0)),
            expected_upside=float(data.get("expected_upside", 0.0)),
            volatility_impact=float(data.get("volatility_impact", 0.0)),
            regime_risk=float(data.get("regime_risk", 0.0)),
            liquidity_risk=float(data.get("liquidity_risk", 0.0)),
            tail_risk=float(data.get("tail_risk", 0.0)),
            validation_explanation=str(data.get("validation_explanation", "")),
            provenance_chain=tuple(
                deserialize_provenance(p)
                for p in data.get("provenance_chain", [])
                if p is not None
            ),
            metadata=dict(data.get("metadata", {})),
        )

    def validate(self) -> list[str]:
        errors: list[str] = []
        if not self.validation_id:
            errors.append("validation_id is required")
        if not self.scenario_id:
            errors.append("scenario_id is required")
        if not self.thesis_id:
            errors.append("thesis_id is required")
        if self.validation_status not in VALID_VALIDATION_STATUS:
            errors.append(f"invalid validation_status: {self.validation_status}")
        for field_name, value in (
            ("expected_reward", self.expected_reward),
            ("expected_risk", self.expected_risk),
            ("maximum_downside", self.maximum_downside),
            ("expected_upside", self.expected_upside),
            ("volatility_impact", self.volatility_impact),
            ("regime_risk", self.regime_risk),
            ("liquidity_risk", self.liquidity_risk),
            ("tail_risk", self.tail_risk),
        ):
            if not 0.0 <= value <= 1.0:
                errors.append(f"{field_name} out of range: {value}")
        if self.risk_reward_ratio < 0.0:
            errors.append(f"risk_reward_ratio out of range: {self.risk_reward_ratio}")
        if not self.validation_explanation:
            errors.append("validation_explanation is required")
        return errors


@dataclass(frozen=True)
class RiskRewardValidation:
    """W11 output: risk / reward validation for every institutional scenario."""

    validation_id: str
    scenario_generation_id: str
    timestamp: str
    regime: str
    validations: tuple[InstitutionalRiskValidation, ...] = ()
    scenario_ids: tuple[str, ...] = ()
    total_validations: int = 0
    summary: dict[str, int] = field(default_factory=lambda: FrozenDict())
    metadata: dict[str, Any] = field(default_factory=lambda: FrozenDict())

    def __post_init__(self) -> None:
        object.__setattr__(self, "validations", tuple(self.validations))
        object.__setattr__(self, "scenario_ids", tuple(self.scenario_ids))
        object.__setattr__(self, "summary", freeze_dict(self.summary))
        object.__setattr__(self, "metadata", freeze_dict(self.metadata))

    def to_dict(self) -> dict[str, Any]:
        return {
            "validation_id": self.validation_id,
            "scenario_generation_id": self.scenario_generation_id,
            "timestamp": self.timestamp,
            "regime": self.regime,
            "validations": [v.to_dict() for v in self.validations],
            "scenario_ids": list(self.scenario_ids),
            "total_validations": self.total_validations,
            "summary": dict(self.summary),
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> RiskRewardValidation:
        return cls(
            validation_id=str(data.get("validation_id", "")),
            scenario_generation_id=str(data.get("scenario_generation_id", "")),
            timestamp=str(data.get("timestamp", "")),
            regime=str(data.get("regime", "")),
            validations=tuple(
                InstitutionalRiskValidation.from_dict(v)
                for v in data.get("validations", [])
            ),
            scenario_ids=tuple(data.get("scenario_ids", ())),
            total_validations=int(data.get("total_validations", 0)),
            summary=dict(data.get("summary", {})),
            metadata=dict(data.get("metadata", {})),
        )

    @property
    def acceptable_count(self) -> int:
        return self.summary.get("acceptable", 0)

    @property
    def borderline_count(self) -> int:
        return self.summary.get("borderline", 0)

    @property
    def reject_count(self) -> int:
        return self.summary.get("reject", 0)

    def validate(self) -> list[str]:
        errors: list[str] = []
        if not self.validation_id:
            errors.append("validation_id is required")
        if not self.scenario_generation_id:
            errors.append("scenario_generation_id is required")
        for v in self.validations:
            errors.extend(f"{v.validation_id}: {e}" for e in v.validate())
        if self.total_validations != len(self.validations):
            errors.append(
                f"total_validations mismatch: {self.total_validations} != {len(self.validations)}"
            )
        actual_ids = {v.scenario_id for v in self.validations}
        if actual_ids != set(self.scenario_ids):
            errors.append("scenario_ids do not match validated scenarios")
        statuses: dict[str, int] = {
            "acceptable": 0,
            "borderline": 0,
            "reject": 0,
        }
        for v in self.validations:
            statuses[v.validation_status] += 1
        if statuses != dict(self.summary):
            errors.append(f"summary does not match validation statuses: {statuses}")
        return errors
