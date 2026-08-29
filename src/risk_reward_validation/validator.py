"""W12 Institutional Risk / Reward Validation: validates every W12 scenario
and classifies it as acceptable, borderline, or reject.

Run-003 repair (Phase 6) -- market-based risk/reward.  The legacy validator
derived every metric from the scenario conviction proxy; the field names
pretended a support-derived quantity was market risk.  When an as-of
``MarketContext`` is supplied (see ``risk_reward_validation.market_context``),
the metrics are anchored on actual market quantities:

* scenario ranges are one expected-move over the scenario horizon:
  ``sigma_up_h  = semivol_up_daily   * sqrt(h)`` (favorable side) and
  ``sigma_down_h = semivol_down_daily * sqrt(h)`` (adverse side).  Both
  sides reuse the SAME zero-mean semi-deviation estimator, so treatment is
  direction-symmetric (bullish and bearish theses are mirrored formulas);
* favorable / adverse scenario mass aggregates the generator's own scenario
  probabilities by direction agreement with the thesis;
* ``risk_reward_ratio`` is the adverse mass times the adverse move over the
  favorable mass times the favorable move -- probability asymmetry under
  market-scaled magnitudes (higher = worse, legacy field semantics kept);
* ``maximum_downside`` / ``expected_upside`` are the market 1-sigma adverse /
  favorable moves over the horizon; ``tail_risk`` is the 2-sigma adverse
  excursion; ``volatility_impact`` is the realized-volatility expected move.

When no market context is available (explicit unavailable state), the
validator keeps the legacy conviction-derived computation and labels it
``conviction_fallback`` -- it never pretends a support-derived quantity is
market risk and never invents a volatility number.
"""

from __future__ import annotations

import math
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from knowledge.integrity.provenance import Provenance
from knowledge.regime.constants import INSTITUTIONAL_REGIMES
from risk_reward_validation.contracts import (
    InstitutionalRiskValidation,
    RiskRewardValidation,
)
from risk_reward_validation.market_context import MarketContext
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
# Legacy conviction-path reward thresholds (price-fraction space).  The
# market-based path classifies on the market ratio and favorable mass
# instead (see _classify_market); the legacy constants remain ONLY for the
# explicit conviction fallback.
ACCEPTABLE_MIN_REWARD = 0.15
REJECT_MAX_REWARD = 0.05

OPPOSITE_DIRECTION = {"bullish": "bearish", "bearish": "bullish"}


class RiskRewardValidator:
    """Computes risk / reward metrics for every scenario and classifies it."""

    def validate(
        self,
        generation: ScenarioGeneration,
        market_context: MarketContext | None = None,
    ) -> RiskRewardValidation:
        prov = Provenance(
            created_at=datetime.now(timezone.utc).isoformat(),
            created_by="W12 RiskRewardValidator",
            entity_version="1.0.0",
        )

        use_market = bool(market_context is not None and market_context.available)
        thesis_favorable_mass, thesis_adverse_mass = (
            self._direction_masses(generation) if use_market else ({}, {})
        )

        validations: list[InstitutionalRiskValidation] = []
        for scenario in generation.scenarios:
            if use_market:
                validations.append(
                    self._validate_scenario_market(
                        scenario,
                        market_context,
                        thesis_favorable_mass.get(scenario.thesis_id, 0.0),
                        thesis_adverse_mass.get(scenario.thesis_id, 0.0),
                        prov,
                    )
                )
            else:
                validations.append(
                    self._validate_scenario_conviction(scenario, prov)
                )

        summary: dict[str, int] = {"acceptable": 0, "borderline": 0, "reject": 0}
        for v in validations:
            summary[v.validation_status] += 1

        metadata: dict[str, Any] = {
            "total_scenarios_validated": len(validations),
            "risk_basis": (
                "market_asof" if use_market else "conviction_fallback"
            ),
            "market_context": (
                market_context.describe() if market_context is not None else None
            ),
            "market_context_provenance": (
                dict(market_context.provenance)
                if market_context is not None
                else None
            ),
        }

        return RiskRewardValidation(
            validation_id=f"rv_{uuid4().hex[:12]}",
            scenario_generation_id=generation.scenario_generation_id,
            timestamp=datetime.now(timezone.utc).isoformat(),
            regime=generation.regime,
            validations=tuple(validations),
            scenario_ids=tuple(v.scenario_id for v in validations),
            total_validations=len(validations),
            summary=summary,
            metadata=metadata,
        )

    # ------------------------------------------------------------------
    # Market-based path (Run-003 repair, Phase 6)
    # ------------------------------------------------------------------

    @staticmethod
    def _direction_masses(
        generation: ScenarioGeneration,
    ) -> tuple[dict[str, float], dict[str, float]]:
        """Favorable / adverse scenario probability mass per thesis.

        The base scenario of a directional thesis expects the thesis
        direction (generator contract), so it contributes to the favorable
        mass; the extreme scenario of the opposite direction contributes to
        the adverse mass.  Masses reuse the generator's own probabilities --
        nothing is re-allocated here.
        """
        thesis_direction: dict[str, str] = {}
        for scenario in generation.scenarios:
            if scenario.scenario_type == "base":
                thesis_direction.setdefault(
                    scenario.thesis_id, scenario.expected_direction
                )
        favorable: dict[str, float] = {}
        adverse: dict[str, float] = {}
        for scenario in generation.scenarios:
            direction = thesis_direction.get(scenario.thesis_id, "")
            opposite = OPPOSITE_DIRECTION.get(direction, "")
            if not direction or not opposite:
                continue
            favorable[scenario.thesis_id] = favorable.get(scenario.thesis_id, 0.0)
            adverse[scenario.thesis_id] = adverse.get(scenario.thesis_id, 0.0)
            if scenario.expected_direction == direction:
                favorable[scenario.thesis_id] += scenario.probability
            elif scenario.expected_direction == opposite:
                adverse[scenario.thesis_id] += scenario.probability
        return favorable, adverse

    def _validate_scenario_market(
        self,
        scenario: InstitutionalScenario,
        market_context: MarketContext,
        favorable_mass: float,
        adverse_mass: float,
        provenance: Provenance,
    ) -> InstitutionalRiskValidation:
        horizon = max(1, int(scenario.time_horizon_days))
        sqrt_h = math.sqrt(float(horizon))
        sigma_up = float(market_context.semivol_up_daily) * sqrt_h
        sigma_down = float(market_context.semivol_down_daily) * sqrt_h
        realized_vol = float(market_context.realized_vol_daily)

        probability = float(scenario.probability)
        direction = scenario.expected_direction
        thesis_direction = self._thesis_direction_for(scenario)
        opposite = OPPOSITE_DIRECTION.get(thesis_direction, "")
        favorable_scenario = direction == thesis_direction and direction in (
            "bullish",
            "bearish",
        )
        adverse_scenario = direction == opposite and opposite in ("bullish", "bearish")

        expected_reward = round(probability * sigma_up, 6) if favorable_scenario else 0.0
        expected_risk = round(probability * sigma_down, 6) if adverse_scenario else 0.0

        # Thesis-level market ratio, uniform across the thesis's scenarios
        # (mirrors the legacy per-thesis uniformity so W13 eligibility keeps
        # its semantics).  Favorable mass of zero means no favorable scenario
        # exists for the trade -- ratio saturates at MAX.
        if favorable_mass > 0.0 and sigma_up > 0.0:
            raw_ratio = (adverse_mass * sigma_down) / (favorable_mass * sigma_up)
            risk_reward_ratio = min(round(raw_ratio, 4), MAX_RISK_REWARD_RATIO)
        else:
            risk_reward_ratio = MAX_RISK_REWARD_RATIO

        tail_raw = 2.0 * sigma_down
        tail_clamped = tail_raw > 1.0
        tail_risk = round(min(tail_raw, 1.0), 6)
        volatility_impact = round(min(realized_vol * sqrt_h, 1.0), 6)
        liquidity_risk = round(
            min(scenario.time_horizon_days / 365.0, 1.0) * 0.5,
            4,
        )
        regime_risk = self._regime_risk(scenario.regime_path)

        status = self._classify_market(
            risk_reward_ratio=risk_reward_ratio,
            favorable_mass=favorable_mass,
        )
        explanation = self._explanation_market(
            scenario=scenario,
            status=status,
            expected_reward=expected_reward,
            expected_risk=expected_risk,
            risk_reward_ratio=risk_reward_ratio,
            sigma_up=sigma_up,
            sigma_down=sigma_down,
            favorable_mass=favorable_mass,
            adverse_mass=adverse_mass,
            tail_risk=tail_risk,
            tail_clamped=tail_clamped,
            volatility_impact=volatility_impact,
            liquidity_risk=liquidity_risk,
            regime_risk=regime_risk,
            as_of=market_context.as_of,
        )

        return InstitutionalRiskValidation(
            validation_id=f"rv_{uuid4().hex[:12]}",
            scenario_id=scenario.scenario_id,
            thesis_id=scenario.thesis_id,
            validation_status=status,
            expected_reward=expected_reward,
            expected_risk=expected_risk,
            risk_reward_ratio=risk_reward_ratio,
            maximum_downside=round(sigma_down, 6),
            expected_upside=round(sigma_up, 6),
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
                "metrics_basis": "market_asof",
                "derivation": (
                    "scenario ranges = zero-mean semi-deviation expected moves "
                    "(semivol_up/semivol_down * sqrt(horizon)) from as-of gold "
                    "history; ratio = (adverse mass * adverse move) / "
                    "(favorable mass * favorable move); masses reuse the "
                    "generator's scenario probabilities"
                ),
                "market_as_of": market_context.as_of,
                "expected_move_up_h": round(sigma_up, 6),
                "expected_move_down_h": round(sigma_down, 6),
                "favorable_mass": round(favorable_mass, 6),
                "adverse_mass": round(adverse_mass, 6),
                "tail_clamped": tail_clamped,
                "liquidity_risk_basis": "horizon_heuristic (unchanged legacy)",
                "regime_risk_basis": "regime_path (unchanged legacy)",
            },
        )

    @staticmethod
    def _thesis_direction_for(scenario: InstitutionalScenario) -> str:
        """The traded direction a scenario is validated against.

        The base scenario's expected_direction IS the thesis direction by
        generator contract, so it identifies the thesis direction for every
        scenario of the same thesis.
        """
        if scenario.scenario_type == "base":
            return scenario.expected_direction
        if scenario.expected_direction == "bullish":
            return "bullish"
        if scenario.expected_direction == "bearish":
            return "bearish"
        return scenario.expected_direction

    @staticmethod
    def _classify_market(
        risk_reward_ratio: float,
        favorable_mass: float,
    ) -> str:
        if favorable_mass <= 0.0 or risk_reward_ratio >= REJECT_RATIO_THRESHOLD:
            return "reject"
        if risk_reward_ratio <= ACCEPTABLE_RATIO_THRESHOLD:
            return "acceptable"
        return "borderline"

    @staticmethod
    def _explanation_market(
        scenario: InstitutionalScenario,
        status: str,
        expected_reward: float,
        expected_risk: float,
        risk_reward_ratio: float,
        sigma_up: float,
        sigma_down: float,
        favorable_mass: float,
        adverse_mass: float,
        tail_risk: float,
        tail_clamped: bool,
        volatility_impact: float,
        liquidity_risk: float,
        regime_risk: float,
        as_of: str,
    ) -> str:
        parts = [
            f"status={status}",
            f"scenario={scenario.scenario_type}",
            f"direction={scenario.expected_direction}",
            f"basis=market_asof (as-of {as_of})",
            f"expected_reward={expected_reward}",
            f"expected_risk={expected_risk}",
            f"risk_reward_ratio={risk_reward_ratio}",
            f"expected_move_up_h={round(sigma_up, 6)}",
            f"expected_move_down_h={round(sigma_down, 6)}",
            f"favorable_mass={round(favorable_mass, 6)}",
            f"adverse_mass={round(adverse_mass, 6)}",
            f"maximum_downside={round(sigma_down, 6)}",
            f"expected_upside={round(sigma_up, 6)}",
            f"tail_risk={tail_risk}" + (" (clamped)" if tail_clamped else ""),
            f"liquidity_risk={liquidity_risk}",
            f"regime_risk={regime_risk}",
            f"volatility_impact={volatility_impact}",
        ]
        if status == "acceptable":
            reason = "market-anchored favorable mass/value exceeds adverse mass/value"
        elif status == "borderline":
            reason = (
                "market-anchored adverse mass/value exceeds favorable side but "
                "below reject threshold"
            )
        else:
            reason = (
                "no favorable scenario mass or adverse market value dominates "
                "by more than the reject threshold"
            )
        parts.append(f"reason={reason}")
        return "; ".join(parts)

    # ------------------------------------------------------------------
    # Legacy conviction path (explicit fallback basis)
    # ------------------------------------------------------------------

    def _validate_scenario_conviction(
        self,
        scenario: InstitutionalScenario,
        provenance: Provenance,
    ) -> InstitutionalRiskValidation:
        # Correction 052-A: read the truthful scenario-confidence key.  The
        # deprecated "final_confidence" fallback exists ONLY for scenarios
        # constructed from pre-052-A serialized payloads; it can never alter
        # numerics for ScenarioGenerator output, which always writes the new
        # key.  All quantities below are deterministic conviction-derived
        # functions of that proxy plus direction/regime/horizon -- no
        # market-risk observation enters this fallback, and the basis is
        # labeled explicitly (Run-003 repair, Phase 6).
        conf = float(
            scenario.confidence_inputs.get(
                "scenario_confidence",
                scenario.confidence_inputs.get("final_confidence", 0.0),
            )
        )
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

        status = self._classify_conviction(
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
                # Run-003 repair (Phase 6): this fallback is reached ONLY
                # when no as-of market context is available.  The metrics are
                # deterministic functions of the W12 conviction proxy
                # (institutional_support), direction alignment, regime path
                # and horizon -- they are NOT market-risk measurements and
                # are labeled as such.
                "metrics_basis": "conviction_fallback",
                "derivation": (
                    "deterministic function of scenario_confidence "
                    "(institutional_support), direction, regime_path, "
                    "time_horizon_days; no market-risk inputs available"
                ),
            },
        )

    # ------------------------------------------------------------------
    # Shared helpers
    # ------------------------------------------------------------------

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
    def _classify_conviction(
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
            "basis=conviction_fallback (no as-of market context)",
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
