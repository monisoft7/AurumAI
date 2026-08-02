"""W12 Institutional Risk / Reward Validation: validates every W12 scenario
and classifies it as acceptable, borderline, or reject."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from knowledge.integrity.provenance import Provenance
from knowledge.regime.constants import INSTITUTIONAL_REGIMES
from risk_reward_validation.contracts import (
    InstitutionalRiskValidation,
    RiskRewardValidation,
)
from scenario_generation.contracts import InstitutionalScenario, ScenarioGeneration

RELIABILITY_PENALTY: dict[str, float] = {
    "high": 0.0,
    "moderate": 0.25,
    "low": 0.5,
    "very_low": 0.75,
}

MAX_RISK_REWARD_RATIO = 10.0
ACCEPTABLE_RATIO_THRESHOLD = 1.0
REJECT_RATIO_THRESHOLD = 3.0
ACCEPTABLE_MIN_REWARD = 0.15
REJECT_MAX_REWARD = 0.05


class RiskRewardValidator:
    """Computes risk / reward metrics for every scenario and classifies it."""

    def validate(self, generation: ScenarioGeneration) -> RiskRewardValidation:
        prov = Provenance(
            created_at=datetime.now(timezone.utc).isoformat(),
            created_by="W12 RiskRewardValidator",
            entity_version="1.0.0",
        )

        validations: list[InstitutionalRiskValidation] = []
        for scenario in generation.scenarios:
            validations.append(self._validate_scenario(scenario, prov))

        summary: dict[str, int] = {"acceptable": 0, "borderline": 0, "reject": 0}
        for v in validations:
            summary[v.validation_status] += 1

        return RiskRewardValidation(
            validation_id=f"rv_{uuid4().hex[:12]}",
            scenario_generation_id=generation.scenario_generation_id,
            timestamp=datetime.now(timezone.utc).isoformat(),
            regime=generation.regime,
            validations=tuple(validations),
            scenario_ids=tuple(v.scenario_id for v in validations),
            total_validations=len(validations),
            summary=summary,
            metadata={
                "total_scenarios_validated": len(validations),
            },
        )

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _validate_scenario(
        self,
        scenario: InstitutionalScenario,
        provenance: Provenance,
    ) -> InstitutionalRiskValidation:
        conf = float(scenario.confidence_inputs.get("final_confidence", 0.0))
        unc = float(scenario.confidence_inputs.get("remaining_uncertainty", 1.0))
        reliability = str(
            scenario.confidence_inputs.get("reliability_category", "very_low")
        )
        penalty = RELIABILITY_PENALTY.get(reliability, 0.75)

        alignment = self._alignment(scenario.expected_direction)
        upside_potential = round(
            (0.3 + 0.7 * conf) * (0.4 + 0.6 * alignment), 4
        )
        downside_potential = round(
            (0.3 + 0.7 * unc) * (0.4 + 0.6 * (1.0 - alignment)), 4
        )

        expected_upside = upside_potential
        maximum_downside = downside_potential
        expected_reward = round(scenario.probability * upside_potential, 4)
        expected_risk = round(scenario.probability * downside_potential, 4)

        tail_risk = round(0.5 * unc + 0.5 * penalty, 4)
        liquidity_risk = round(
            min(scenario.time_horizon_days / 365.0, 1.0) * 0.5
            + penalty * 0.5,
            4,
        )
        regime_risk = self._regime_risk(scenario.regime_path)
        volatility_impact = round(0.5 * unc + 0.5 * regime_risk, 4)

        risk_score = round(
            0.5 * expected_risk
            + 0.2 * tail_risk
            + 0.2 * regime_risk
            + 0.1 * liquidity_risk,
            4,
        )
        if expected_reward > 0.0:
            risk_reward_ratio = min(
                round(risk_score / expected_reward, 4),
                MAX_RISK_REWARD_RATIO,
            )
        else:
            risk_reward_ratio = MAX_RISK_REWARD_RATIO

        status = self._classify(
            expected_reward=expected_reward,
            risk_reward_ratio=risk_reward_ratio,
        )
        explanation = self._explanation(
            scenario=scenario,
            status=status,
            expected_reward=expected_reward,
            expected_risk=expected_risk,
            risk_reward_ratio=risk_reward_ratio,
            maximum_downside=maximum_downside,
            expected_upside=expected_upside,
            tail_risk=tail_risk,
            liquidity_risk=liquidity_risk,
            regime_risk=regime_risk,
            volatility_impact=volatility_impact,
        )

        return InstitutionalRiskValidation(
            validation_id=f"rv_{uuid4().hex[:12]}",
            scenario_id=scenario.scenario_id,
            thesis_id=scenario.thesis_id,
            validation_status=status,
            expected_reward=expected_reward,
            expected_risk=expected_risk,
            risk_reward_ratio=risk_reward_ratio,
            maximum_downside=maximum_downside,
            expected_upside=expected_upside,
            volatility_impact=volatility_impact,
            regime_risk=regime_risk,
            liquidity_risk=liquidity_risk,
            tail_risk=tail_risk,
            validation_explanation=explanation,
            provenance_chain=tuple(list(scenario.provenance_chain) + [provenance]),
            metadata={
                "scenario_type": scenario.scenario_type,
                "scenario_label": scenario.metadata.get(
                    "scenario_label", scenario.scenario_type
                ),
                "probability": scenario.probability,
            },
        )

    @staticmethod
    def _alignment(expected_direction: str) -> float:
        if expected_direction == "bullish":
            return 1.0
        if expected_direction == "bearish":
            return 0.0
        return 0.5

    @staticmethod
    def _regime_risk(regime_path: tuple[str, ...]) -> float:
        if not regime_path:
            return 1.0
        if regime_path[0] not in INSTITUTIONAL_REGIMES:
            return 1.0
        if len(regime_path) == 1:
            return 0.3
        if regime_path[0] == regime_path[1]:
            return 0.4
        return 0.75

    @staticmethod
    def _classify(
        expected_reward: float,
        risk_reward_ratio: float,
    ) -> str:
        if risk_reward_ratio >= REJECT_RATIO_THRESHOLD or expected_reward < REJECT_MAX_REWARD:
            return "reject"
        if risk_reward_ratio <= ACCEPTABLE_RATIO_THRESHOLD and expected_reward >= ACCEPTABLE_MIN_REWARD:
            return "acceptable"
        return "borderline"

    @staticmethod
    def _explanation(
        scenario: InstitutionalScenario,
        status: str,
        expected_reward: float,
        expected_risk: float,
        risk_reward_ratio: float,
        maximum_downside: float,
        expected_upside: float,
        tail_risk: float,
        liquidity_risk: float,
        regime_risk: float,
        volatility_impact: float,
    ) -> str:
        parts = [
            f"status={status}",
            f"scenario={scenario.scenario_type}",
            f"direction={scenario.expected_direction}",
            f"expected_reward={expected_reward}",
            f"expected_risk={expected_risk}",
            f"risk_reward_ratio={risk_reward_ratio}",
            f"maximum_downside={maximum_downside}",
            f"expected_upside={expected_upside}",
            f"tail_risk={tail_risk}",
            f"liquidity_risk={liquidity_risk}",
            f"regime_risk={regime_risk}",
            f"volatility_impact={volatility_impact}",
        ]
        if status == "acceptable":
            reason = "expected reward exceeds expected risk with sufficient margin"
        elif status == "borderline":
            reason = "expected reward only modestly exceeds expected risk; margin insufficient"
        else:
            reason = "risk exceeds expected reward or expected reward is negligible"
        parts.append(f"reason={reason}")
        return "; ".join(parts)
