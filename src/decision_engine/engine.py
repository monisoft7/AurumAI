"""W13 Institutional Decision Engine: produces exactly one institutional
decision (BUY / SELL / HOLD / NO TRADE) from W8, W9, and W12 outputs."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from confidence_engine.contracts import InstitutionalConfidence, ThesisConfidence
from decision_engine.contracts import (
    DecisionDriver,
    InstitutionalDecision,
    RejectedAlternative,
)
from knowledge.integrity.provenance import Provenance
from risk_reward_validation.contracts import (
    InstitutionalRiskValidation,
    RiskRewardValidation,
)
from scenario_generation.contracts import InstitutionalScenario, ScenarioGeneration
from thesis_construction.contracts import InvestmentThesis, ThesisConstruction

MAX_RISK_REWARD_RATIO = 10.0

CONFIDENCE_WEIGHT = 0.30
RR_WEIGHT = 0.20
EVIDENCE_WEIGHT = 0.15
COUNTER_EVIDENCE_WEIGHT = 0.15
SCENARIO_PROBABILITY_WEIGHT = 0.10
REGIME_ALIGNMENT_WEIGHT = 0.10

NO_TRADE_CONFIDENCE = 0.5
HOLD_CONFIDENCE = 0.35
NO_TRADE_RR_RATIO = 2.0

STATUS_RANK = {"acceptable": 0, "borderline": 1, "reject": 2}
TYPE_RANK = {"base": 0, "bull": 1, "bear": 2}

ELIGIBLE_STATUSES = {"acceptable", "borderline"}

# Correction 053-C: the standalone regime-alignment channel
# (+ REGIME_ALIGNMENT_WEIGHT * regime_alignment) was removed from the
# composite -- regime alignment is already represented inside W9
# institutional_confidence (positive_score weight 0.15).  Trace 053-B B2
# verified this removal preserves candidate ranking and decisions on the
# canonical smoke cases.  The constant is kept only for import
# compatibility and MUST NOT be reintroduced into _score_thesis.
REGIME_ALIGNMENT_WEIGHT = 0.10


class DecisionEngine:
    """Scores every thesis, selects the optimal one, and derives the
    single institutional decision."""

    def decide(
        self,
        construction: ThesisConstruction,
        confidence: InstitutionalConfidence,
        generation: ScenarioGeneration,
        validation: RiskRewardValidation,
    ) -> InstitutionalDecision:
        prov = Provenance(
            created_at=datetime.now(timezone.utc).isoformat(),
            created_by="W13 DecisionEngine",
            entity_version="1.0.0",
        )

        v_by_sid = {v.scenario_id: v for v in validation.validations}
        scenario_by_sid = {s.scenario_id: s for s in generation.scenarios}

        scored: list[dict[str, Any]] = []
        for thesis in construction.theses:
            tc = self._find_confidence(confidence, thesis.thesis_id)
            thesis_scenarios = [
                s for s in generation.scenarios if s.thesis_id == thesis.thesis_id
            ]
            thesis_validations = [
                v_by_sid[s.scenario_id]
                for s in thesis_scenarios
                if s.scenario_id in v_by_sid
            ]
            stats = self._score_thesis(
                thesis=thesis,
                tc=tc,
                scenarios=thesis_scenarios,
                validations=thesis_validations,
            )
            scored.append(
                {
                    "thesis": thesis,
                    "tc": tc,
                    "scenarios": thesis_scenarios,
                    "validations": thesis_validations,
                    **stats,
                }
            )

        if not scored:
            return self._no_trade(
                construction=construction,
                confidence=confidence,
                provenance=prov,
                rejected=[],
            )

        eligible = [s for s in scored if s["best_status"] in ELIGIBLE_STATUSES]
        if not eligible:
            rejected = self._rejected_alternatives(
                scored, construction, confidence, generation, validation, selected=None
            )
            return self._no_trade(
                construction=construction,
                confidence=confidence,
                provenance=prov,
                rejected=rejected,
            )

        selected = max(eligible, key=lambda s: s["score"])
        best_scenario, best_validation = self._select_best_scenario(
            selected["scenarios"], selected["validations"]
        )
        decision = self._determine_decision(
            thesis=selected["thesis"],
            tc=selected["tc"],
            validation=best_validation,
        )

        rejected = self._rejected_alternatives(
            scored,
            construction,
            confidence,
            generation,
            validation,
            selected=selected,
        )

        drivers = self._decision_drivers(selected, best_scenario)
        rr_summary = self._risk_reward_summary(best_validation)
        confidence_value = selected["tc"].final_confidence if selected["tc"] else 0.0
        explanation = self._explanation(
            decision=decision,
            thesis=selected["thesis"],
            scenario=best_scenario,
            score=selected["score"],
            confidence_value=confidence_value,
            rr_summary=rr_summary,
        )
        preconditions = self._preconditions(best_scenario)
        invalidation = self._invalidation_conditions(
            best_scenario, selected["thesis"]
        )
        chain = self._provenance_chain(best_validation, prov)

        return InstitutionalDecision(
            decision_id=f"dec_{uuid4().hex[:12]}",
            decision=decision,
            selected_thesis_id=selected["thesis"].thesis_id,
            selected_scenario_id=best_scenario.scenario_id,
            institutional_confidence=round(confidence_value, 4),
            risk_reward_summary=rr_summary,
            decision_drivers=tuple(drivers),
            rejected_alternatives=tuple(rejected),
            decision_explanation=explanation,
            preconditions=preconditions,
            invalidation_conditions=invalidation,
            provenance_chain=tuple(chain),
            metadata={
                "selected_thesis_direction": selected["thesis"].direction,
                "selected_scenario_type": best_scenario.scenario_type,
                "composite_score": round(selected["score"], 4),
                "total_theses_evaluated": len(scored),
                "total_rejected_alternatives": len(rejected),
            },
        )

    # ------------------------------------------------------------------
    # Scoring
    # ------------------------------------------------------------------

    def _score_thesis(
        self,
        thesis: InvestmentThesis,
        tc: ThesisConfidence | None,
        scenarios: list[InstitutionalScenario],
        validations: list[InstitutionalRiskValidation],
    ) -> dict[str, float]:
        confidence = tc.final_confidence if tc else 0.0
        evidence_quality = float(
            thesis.confidence_inputs.get("avg_supporting_weight", 0.0)
        )
        counter_penalty = float(
            thesis.confidence_inputs.get("confidence_penalty", 0.0)
        )
        max_probability = max(
            (s.probability for s in scenarios), default=0.0
        )

        rr_components: list[float] = []
        best_status = "reject"
        for v in validations:
            rr_components.append(
                1.0 - min(v.risk_reward_ratio / MAX_RISK_REWARD_RATIO, 1.0)
            )
            if STATUS_RANK[v.validation_status] < STATUS_RANK[best_status]:
                best_status = v.validation_status
        rr_score = round(sum(rr_components) / len(rr_components), 4) if rr_components else 0.0

        # Correction 053-C: REGIME_ALIGNMENT_WEIGHT channel removed.
        # regime_alignment remains inside W9 institutional_confidence
        # (positive_score, weight 0.15) -- single-count only now.
        score = round(
            CONFIDENCE_WEIGHT * confidence
            + RR_WEIGHT * rr_score
            + EVIDENCE_WEIGHT * evidence_quality
            + COUNTER_EVIDENCE_WEIGHT * (1.0 - counter_penalty)
            + SCENARIO_PROBABILITY_WEIGHT * max_probability,
            4,
        )
        return {
            "score": score,
            "confidence": confidence,
            "rr_score": rr_score,
            "evidence_quality": evidence_quality,
            "counter_penalty": counter_penalty,
            "max_probability": max_probability,
            "best_status": best_status,
        }

    def _select_best_scenario(
        self,
        scenarios: list[InstitutionalScenario],
        validations: list[InstitutionalRiskValidation],
    ) -> tuple[InstitutionalScenario, InstitutionalRiskValidation]:
        v_by_sid = {v.scenario_id: v for v in validations}
        ranked = []
        for s in scenarios:
            v = v_by_sid.get(s.scenario_id)
            if v is None:
                continue
            ranked.append((s, v))
        ranked = [
            (s, v)
            for s, v in ranked
            if v.validation_status in ELIGIBLE_STATUSES
        ]
        if not ranked and scenarios and validations:
            ranked = [(scenarios[0], validations[0])]
        ranked.sort(
            key=lambda item: (
                STATUS_RANK[item[1].validation_status],
                -item[0].probability,
                TYPE_RANK.get(item[0].scenario_type, 9),
            )
        )
        return ranked[0]

    def _determine_decision(
        self,
        thesis: InvestmentThesis,
        tc: ThesisConfidence | None,
        validation: InstitutionalRiskValidation,
    ) -> str:
        confidence = tc.final_confidence if tc else 0.0
        if confidence < NO_TRADE_CONFIDENCE:
            return "NO_TRADE"
        if validation.risk_reward_ratio > NO_TRADE_RR_RATIO:
            return "NO_TRADE"
        if thesis.direction == "bullish":
            return "BUY"
        if thesis.direction == "bearish":
            return "SELL"
        if confidence >= HOLD_CONFIDENCE:
            return "HOLD"
        return "NO_TRADE"

    # ------------------------------------------------------------------
    # Output builders
    # ------------------------------------------------------------------

    def _decision_drivers(
        self, selected: dict[str, Any], scenario: InstitutionalScenario
    ) -> list[DecisionDriver]:
        specs = (
            ("institutional_confidence", selected["confidence"], CONFIDENCE_WEIGHT),
            ("risk_reward_quality", selected["rr_score"], RR_WEIGHT),
            ("evidence_quality", selected["evidence_quality"], EVIDENCE_WEIGHT),
            (
                "counter_evidence_quality",
                1.0 - selected["counter_penalty"],
                COUNTER_EVIDENCE_WEIGHT,
            ),
            ("scenario_probability", selected["max_probability"], SCENARIO_PROBABILITY_WEIGHT),
            # Correction 053-C: standalone regime_alignment driver removed;
            # regime alignment is single-counted inside institutional_confidence.
        )
        return [
            DecisionDriver(
                name=name,
                value=round(value, 4),
                weight=weight,
                score=round(value * weight, 4),
            )
            for name, value, weight in specs
        ]

    @staticmethod
    def _risk_reward_summary(
        validation: InstitutionalRiskValidation,
    ) -> dict[str, Any]:
        return {
            "status": validation.validation_status,
            "expected_reward": validation.expected_reward,
            "expected_risk": validation.expected_risk,
            "risk_reward_ratio": validation.risk_reward_ratio,
            "maximum_downside": validation.maximum_downside,
            "expected_upside": validation.expected_upside,
            "tail_risk": validation.tail_risk,
            "liquidity_risk": validation.liquidity_risk,
            "regime_risk": validation.regime_risk,
            "volatility_impact": validation.volatility_impact,
        }

    def _rejected_alternatives(
        self,
        scored: list[dict[str, Any]],
        construction: ThesisConstruction,
        confidence: InstitutionalConfidence,
        generation: ScenarioGeneration,
        validation: RiskRewardValidation,
        selected: dict[str, Any] | None,
    ) -> list[RejectedAlternative]:
        rejected: list[RejectedAlternative] = []
        for entry in scored:
            if selected is not None and entry["thesis"].thesis_id == selected["thesis"].thesis_id:
                continue
            if entry["best_status"] not in ELIGIBLE_STATUSES:
                reason = (
                    f"no acceptable or borderline scenario: all scenarios rejected "
                    f"by W12 risk/reward validation (best status={entry['best_status']})"
                )
            elif selected is None:
                reason = (
                    "not selected: no other thesis cleared selection"
                )
            else:
                reason = (
                    f"lower composite score ({entry['score']}) than selected thesis "
                    f"({selected['score']})"
                )
            rejected.append(
                RejectedAlternative(
                    thesis_id=entry["thesis"].thesis_id,
                    thesis_direction=entry["thesis"].direction,
                    composite_score=round(entry["score"], 4),
                    rejection_reason=reason,
                )
            )
        rejected.sort(key=lambda r: -r.composite_score)
        return rejected

    @staticmethod
    def _preconditions(scenario: InstitutionalScenario) -> tuple[str, ...]:
        return tuple(scenario.confirmation_conditions)

    @staticmethod
    def _invalidation_conditions(
        scenario: InstitutionalScenario,
        thesis: InvestmentThesis,
    ) -> tuple[str, ...]:
        combined: list[str] = []
        for condition in list(scenario.invalidation_conditions) + list(
            thesis.invalidating_conditions
        ):
            if condition not in combined:
                combined.append(condition)
        return tuple(combined)

    @staticmethod
    def _provenance_chain(
        validation: InstitutionalRiskValidation,
        prov: Provenance,
    ) -> list[Provenance]:
        return list(validation.provenance_chain) + [prov]

    @staticmethod
    def _explanation(
        decision: str,
        thesis: InvestmentThesis,
        scenario: InstitutionalScenario,
        score: float,
        confidence_value: float,
        rr_summary: dict[str, Any],
    ) -> str:
        rationale = {
            "BUY": "selected bullish thesis clears institutional confidence and risk/reward thresholds",
            "SELL": "selected bearish thesis clears institutional confidence and risk/reward thresholds",
            "HOLD": "selected thesis is neutral; no directional bias",
            "NO_TRADE": "no thesis clears institutional confidence and risk/reward thresholds",
        }[decision]
        return (
            f"decision={decision}; selected_thesis={thesis.thesis_id} "
            f"({thesis.direction}); selected_scenario={scenario.scenario_id} "
            f"({scenario.scenario_type}, p={scenario.probability}); "
            f"composite_score={score}; institutional_confidence={confidence_value}; "
            f"risk_reward_status={rr_summary.get('status')}; "
            f"risk_reward_ratio={rr_summary.get('risk_reward_ratio')}; "
            f"reason={rationale}"
        )

    @staticmethod
    def _no_trade(
        construction: ThesisConstruction,
        confidence: InstitutionalConfidence,
        provenance: Provenance,
        rejected: list[RejectedAlternative],
    ) -> InstitutionalDecision:
        explanation = (
            "decision=NO_TRADE; no eligible thesis selected; "
            "reason=no thesis clears institutional confidence and risk/reward thresholds"
        )
        chain = list(
            confidence.theses_confidence[0].provenance_chain
            if confidence.theses_confidence
            else []
        ) + [provenance]
        return InstitutionalDecision(
            decision_id=f"dec_{uuid4().hex[:12]}",
            decision="NO_TRADE",
            selected_thesis_id="",
            selected_scenario_id="",
            institutional_confidence=0.0,
            risk_reward_summary={},
            decision_drivers=(),
            rejected_alternatives=tuple(rejected),
            decision_explanation=explanation,
            preconditions=(),
            invalidation_conditions=(),
            provenance_chain=tuple(chain),
            metadata={
                "selected_thesis_direction": "",
                "selected_scenario_type": "",
                "composite_score": 0.0,
                "total_theses_evaluated": len(construction.theses),
                "total_rejected_alternatives": len(rejected),
            },
        )

    @staticmethod
    def _find_confidence(
        confidence: InstitutionalConfidence,
        thesis_id: str,
    ) -> ThesisConfidence | None:
        for tc in confidence.theses_confidence:
            if tc.thesis_id == thesis_id:
                return tc
        return None
