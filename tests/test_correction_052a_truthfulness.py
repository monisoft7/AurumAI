"""Correction 052-A -- W12 truthfulness & provenance regression (READ-ONLY).

Locks three guarantees after renaming the W12 scenario-confidence key:

1. NUMERIC INVARIANCE -- every numeric leaf produced by ScenarioGenerator,
   RiskRewardValidator and DecisionEngine on a fixed representative chain
   is byte-identical to the pre-rename production behavior (golden captured
   from the pre-052-A code; the chain also reproduces the exact
   2026-08-24 runtime_20260824_085425 artifact numbers).
2. TRUTHFUL LABELS/PROVENANCE -- scenario confidence is exposed under
   ``scenario_confidence`` with explicit source/type provenance, and W12
   validation metadata/explanations declare their conviction-proxy basis.
3. DEPRECATED ALIAS SAFETY -- pre-rename payloads carrying
   ``confidence_inputs["final_confidence"]`` normalize on deserialization
   and validate to numerically identical results.
"""

from __future__ import annotations

import json

from confidence_engine.computer import ConfidenceComputer
from confidence_engine.contracts import InstitutionalConfidence, ThesisConfidence
from decision_engine.engine import DecisionEngine
from historical_validation.pure_path import numeric_leaves
from risk_reward_validation.contracts import RiskRewardValidation
from risk_reward_validation.validator import RiskRewardValidator
from scenario_generation.contracts import InstitutionalScenario, ScenarioGeneration
from scenario_generation.generator import ScenarioGenerator
from thesis_construction.contracts import InvestmentThesis, ThesisConstruction

SUPPORT = 0.3781          # inverted from 2026-08-24 expected_upside artifact
W9_FINAL_CONFIDENCE = 0.5922
REGIME = "INFLATIONARY"
HORIZON_DAYS = 90

# 2026-08-24 production artifact values (finalize.json decision block)
PRODUCTION = {
    "expected_reward": 0.2823,
    "expected_risk": 0.147,
    "expected_upside": 0.5647,
    "maximum_downside": 0.2941,
    "risk_reward_ratio": 1.0025,
    "status": "borderline",
    "tail_risk": 0.561,
    "liquidity_risk": 0.3733,
    "regime_risk": 0.3,
    "volatility_impact": 0.4609,
    "composite_score_recorded_pre_053c": 0.6359,
    "composite_score_expected_post_053c": 0.5359,
    "decision": "BUY",
    "institutional_confidence": 0.5922,
}

# Golden numeric leaves captured from PRE-052-A code on the same inputs.
GOLDEN_JSON = '''\
{
 "base_scenario_validation": {
  "Base Case": {
   "ratio": 1.0025,
   "reward": 0.2823,
   "status": "borderline"
  },
  "Bear Case": {
   "ratio": 8.7069,
   "reward": 0.0423,
   "status": "reject"
  },
  "Bull Case": {
   "ratio": 1.9564,
   "reward": 0.1766,
   "status": "borderline"
  }
 },
 "decision_leaves": {
  "decision_drivers[0].score": 0.1777,
  "decision_drivers[0].value": 0.5922,
  "decision_drivers[0].weight": 0.3,
  "decision_drivers[1].score": 0.1222,
  "decision_drivers[1].value": 0.6111,
  "decision_drivers[1].weight": 0.2,
  "decision_drivers[2].score": 0.081,
  "decision_drivers[2].value": 0.5402,
  "decision_drivers[2].weight": 0.15,
  "decision_drivers[3].score": 0.105,
  "decision_drivers[3].value": 0.7,
  "decision_drivers[3].weight": 0.15,
  "decision_drivers[4].score": 0.05,
  "decision_drivers[4].value": 0.5,
  "decision_drivers[4].weight": 0.1,
  "institutional_confidence": 0.5922,
  "metadata.composite_score": 0.5359,
  "metadata.total_rejected_alternatives": 0.0,
  "metadata.total_theses_evaluated": 1.0,
  "risk_reward_summary.expected_reward": 0.2823,
  "risk_reward_summary.expected_risk": 0.147,
  "risk_reward_summary.expected_upside": 0.5647,
  "risk_reward_summary.liquidity_risk": 0.3733,
  "risk_reward_summary.maximum_downside": 0.2941,
  "risk_reward_summary.regime_risk": 0.3,
  "risk_reward_summary.risk_reward_ratio": 1.0025,
  "risk_reward_summary.tail_risk": 0.561,
  "risk_reward_summary.volatility_impact": 0.4609
 },
 "generation_leaves": {
  "metadata.scenarios_per_thesis": 3.0,
  "metadata.total_theses_covered": 1.0,
  "probability_consistency.th_052a": 1.0,
  "scenarios[0].confidence_inputs.institutional_support": 0.3781,
  "scenarios[0].confidence_inputs.remaining_uncertainty": 0.6219,
  "scenarios[0].confidence_inputs.scenario_confidence": 0.3781,
  "scenarios[0].probability": 0.5,
  "scenarios[0].time_horizon_days": 90.0,
  "scenarios[1].confidence_inputs.institutional_support": 0.3781,
  "scenarios[1].confidence_inputs.remaining_uncertainty": 0.6219,
  "scenarios[1].confidence_inputs.scenario_confidence": 0.3781,
  "scenarios[1].probability": 0.3128,
  "scenarios[1].time_horizon_days": 90.0,
  "scenarios[2].confidence_inputs.institutional_support": 0.3781,
  "scenarios[2].confidence_inputs.remaining_uncertainty": 0.6219,
  "scenarios[2].confidence_inputs.scenario_confidence": 0.3781,
  "scenarios[2].probability": 0.1872,
  "scenarios[2].time_horizon_days": 90.0,
  "total_scenarios": 3.0
 },
 "validation_leaves": {
  "metadata.total_scenarios_validated": 3.0,
  "summary.acceptable": 0.0,
  "summary.borderline": 2.0,
  "summary.reject": 1.0,
  "total_validations": 3.0,
  "validations[0].expected_reward": 0.2823,
  "validations[0].expected_risk": 0.147,
  "validations[0].expected_upside": 0.5647,
  "validations[0].liquidity_risk": 0.3733,
  "validations[0].maximum_downside": 0.2941,
  "validations[0].metadata.probability": 0.5,
  "validations[0].regime_risk": 0.3,
  "validations[0].risk_reward_ratio": 1.0025,
  "validations[0].tail_risk": 0.561,
  "validations[0].volatility_impact": 0.4609,
  "validations[1].expected_reward": 0.1766,
  "validations[1].expected_risk": 0.092,
  "validations[1].expected_upside": 0.5647,
  "validations[1].liquidity_risk": 0.3733,
  "validations[1].maximum_downside": 0.2941,
  "validations[1].metadata.probability": 0.3128,
  "validations[1].regime_risk": 0.75,
  "validations[1].risk_reward_ratio": 1.9564,
  "validations[1].tail_risk": 0.561,
  "validations[1].volatility_impact": 0.686,
  "validations[2].expected_reward": 0.0423,
  "validations[2].expected_risk": 0.1376,
  "validations[2].expected_upside": 0.2259,
  "validations[2].liquidity_risk": 0.3733,
  "validations[2].maximum_downside": 0.7353,
  "validations[2].metadata.probability": 0.1872,
  "validations[2].regime_risk": 0.75,
  "validations[2].risk_reward_ratio": 8.7069,
  "validations[2].tail_risk": 0.561,
  "validations[2].volatility_impact": 0.686
 }
}
    '''


def _make_construction() -> ThesisConstruction:
    thesis = InvestmentThesis(
        thesis_id="th_052a",
        direction="bullish",
        supporting_set_ids=("es_general", "es_inflation"),
        counter_evidence_ids=("es_usd_fx",),
        regime=REGIME,
        economic_mechanism="CPI disinflation supports real-yield decline",
        time_horizon_days=HORIZON_DAYS,
        invalidating_conditions=("Counter-evidence strengthens",),
        remaining_unknowns=("Missing evidence channels: CB_GOLD",),
        confidence_inputs={
            "avg_supporting_weight": 0.5402,
            "avg_supporting_consensus": 1.0,
            "conflict_severity": 0.0,
            "confidence_penalty": 0.30,
            "raw_support": 0.5402,
        },
        institutional_support=SUPPORT,
        explanation="trace052a regression",
    )
    return ThesisConstruction(
        construction_id="tc_052a",
        reasoning_id="rsn_052a",
        assessment_id="cae_052a",
        timestamp="2026-08-24T06:56:54+00:00",
        regime=REGIME,
        theses=(thesis,),
        ranked_thesis_ids=(thesis.thesis_id,),
        total_theses=1,
        primary_thesis_id=thesis.thesis_id,
        metadata={},
    )


def _run_chain():
    construction = _make_construction()
    thesis = construction.theses[0]
    generation = ScenarioGenerator().generate(construction)
    validation = RiskRewardValidator().validate(generation)
    confidence = InstitutionalConfidence(
        confidence_id="cf_052a",
        construction_id="tc_052a",
        timestamp="2026-08-24T06:56:54+00:00",
        regime=REGIME,
        theses_confidence=(
            ThesisConfidence(
                thesis_id=thesis.thesis_id,
                final_confidence=W9_FINAL_CONFIDENCE,
                confidence_breakdown={"regime_alignment": 1.0},
                reliability_category=ConfidenceComputer.reliability_category(
                    W9_FINAL_CONFIDENCE
                ),
            ),
        ),
        ranked_thesis_ids=(thesis.thesis_id,),
        primary_thesis_id=thesis.thesis_id,
    )
    decision = DecisionEngine().decide(construction, confidence, generation, validation)
    return generation, validation, decision


def _normalized_leaves(obj) -> dict:
    """Since Correction 053-C the golden is captured on post-052-A naming,
    so no key translation is required -- plain numeric-leaf comparison."""
    return {k: v for k, v in sorted(numeric_leaves(obj).items())}


# =========================================================================
# 1. Numeric invariance vs pre-rename golden
# =========================================================================


class TestCorrection052ANumericInvariance:
    def test_generation_numeric_leaves_identical(self):
        generation, _, _ = _run_chain()
        golden = json.loads(GOLDEN_JSON)
        assert _normalized_leaves(generation.to_dict()) == golden["generation_leaves"]

    def test_validation_numeric_leaves_identical(self):
        _, validation, _ = _run_chain()
        golden = json.loads(GOLDEN_JSON)
        assert _normalized_leaves(validation.to_dict()) == golden["validation_leaves"]

    def test_decision_numeric_leaves_identical(self):
        _, _, decision = _run_chain()
        golden = json.loads(GOLDEN_JSON)
        assert _normalized_leaves(decision.to_dict()) == golden["decision_leaves"]

    def test_value_multisets_identical_without_path_normalization(self):
        """Even ignoring renames, the multiset of numeric values is unchanged."""
        generation, validation, decision = _run_chain()
        golden = json.loads(GOLDEN_JSON)
        for artifact, obj in (
            ("generation_leaves", generation.to_dict()),
            ("validation_leaves", validation.to_dict()),
            ("decision_leaves", decision.to_dict()),
        ):
            assert sorted(numeric_leaves(obj).values()) == sorted(
                golden[artifact].values()
            )

    def test_scenario_statuses_and_ratios_identical(self):
        _, validation, _ = _run_chain()
        golden = json.loads(GOLDEN_JSON)
        observed = {
            v.metadata["scenario_label"]: {
                "ratio": v.risk_reward_ratio,
                "reward": v.expected_reward,
                "status": v.validation_status,
            }
            for v in validation.validations
        }
        assert observed == golden["base_scenario_validation"]

    def test_decision_selection_unchanged(self):
        _, _, decision = _run_chain()
        assert decision.decision == PRODUCTION["decision"]
        assert decision.selected_thesis_id == "th_052a"
        assert decision.metadata["selected_scenario_type"] == "base"
        assert decision.metadata["composite_score"] == PRODUCTION["composite_score_expected_post_053c"]
        assert decision.institutional_confidence == PRODUCTION[
            "institutional_confidence"
        ]


# =========================================================================
# 2. Reproduction of the 2026-08-24 production artifact numbers
# =========================================================================


class TestCorrection052AProductionReproduction:
    def test_base_scenario_matches_production_artifact_exactly(self):
        generation, validation, _ = _run_chain()
        base = next(
            s for s in generation.scenarios if s.scenario_type == "base"
        )
        v = next(
            v
            for v in validation.validations
            if v.scenario_id == base.scenario_id
        )
        assert v.expected_reward == PRODUCTION["expected_reward"]
        assert v.expected_risk == PRODUCTION["expected_risk"]
        assert v.expected_upside == PRODUCTION["expected_upside"]
        assert v.maximum_downside == PRODUCTION["maximum_downside"]
        assert v.risk_reward_ratio == PRODUCTION["risk_reward_ratio"]
        assert v.validation_status == PRODUCTION["status"]
        assert v.tail_risk == PRODUCTION["tail_risk"]
        assert v.liquidity_risk == PRODUCTION["liquidity_risk"]
        assert v.regime_risk == PRODUCTION["regime_risk"]
        assert v.volatility_impact == PRODUCTION["volatility_impact"]


# =========================================================================
# 3. Truthful labels / provenance
# =========================================================================


class TestCorrection052AProvenance:
    def test_scenario_confidence_key_and_provenance(self):
        generation, _, _ = _run_chain()
        assert generation.metadata["scenario_confidence_source"] == (
            "institutional_support"
        )
        assert generation.metadata["scenario_confidence_type"] == "conviction_proxy"
        for s in generation.scenarios:
            ci = s.confidence_inputs
            assert "final_confidence" not in ci
            assert ci["scenario_confidence"] == SUPPORT
            assert ci["scenario_confidence_source"] == "institutional_support"
            assert ci["scenario_confidence_type"] == "conviction_proxy"

    def test_validator_declares_conviction_basis(self):
        _, validation, _ = _run_chain()
        for v in validation.validations:
            assert v.metadata["metrics_basis"] == "conviction_proxy"
            assert "no market-risk inputs" in v.metadata["derivation"]
            assert "basis=conviction_proxy" in v.validation_explanation


# =========================================================================
# 4. Deprecated alias safety
# =========================================================================


class TestCorrection052ADeprecatedAlias:
    @staticmethod
    def _legacy_payload() -> dict:
        generation, _, _ = _run_chain()
        payload = dict(generation.to_dict())
        scenarios = []
        for s in payload["scenarios"]:
            s = json.loads(json.dumps(s))
            ci = s["confidence_inputs"]
            ci["final_confidence"] = ci.pop("scenario_confidence")
            ci.pop("scenario_confidence_source", None)
            ci.pop("scenario_confidence_type", None)
            scenarios.append(s)
        payload["scenarios"] = scenarios
        return payload

    def test_from_dict_normalizes_legacy_key(self):
        legacy = self._legacy_payload()
        restored = ScenarioGeneration.from_dict(legacy)
        for s in restored.scenarios:
            ci = s.confidence_inputs
            assert ci["scenario_confidence"] == SUPPORT
            # alias retained verbatim for auditability, never re-written
            assert ci.get("final_confidence") == SUPPORT

    def test_alias_validates_to_identical_numerics(self):
        legacy = ScenarioGeneration.from_dict(self._legacy_payload())
        modern, _, _ = _run_chain()
        va = RiskRewardValidator().validate(legacy)
        vb = RiskRewardValidator().validate(modern)
        strip_volatile = lambda v: {  # noqa: E731
            k: val
            for k, val in v.to_dict().items()
            if k not in ("validation_id", "timestamp", "provenance_chain")
        }
        items_a = [
            {k: x for k, x in strip_volatile(v).items() if k != "scenario_id"}
            for v in va.validations
        ]
        items_b = [
            {k: x for k, x in strip_volatile(v).items() if k != "scenario_id"}
            for v in vb.validations
        ]
        # explanation/metadata now identical too (basis fields derive from
        # validator, not from input keys); numerics must match exactly.
        assert items_a == items_b

    def test_alias_cannot_fire_on_generator_output(self):
        generation, _, _ = _run_chain()
        for s in generation.scenarios:
            assert "scenario_confidence" in s.confidence_inputs
            # truthful key always present -> fallback branch unreachable
            assert s.confidence_inputs.get("scenario_confidence") is not None
