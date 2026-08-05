"""Unit + integration tests for W13 Institutional Decision Engine."""

import json

import pytest

from confidence_engine.contracts import InstitutionalConfidence, ThesisConfidence
from decision_engine.contracts import (
    VALID_DECISIONS,
    DecisionDriver,
    InstitutionalDecision,
    RejectedAlternative,
)
from decision_engine.engine import DecisionEngine
from risk_reward_validation.contracts import (
    InstitutionalRiskValidation,
    RiskRewardValidation,
)
from scenario_generation.contracts import InstitutionalScenario, ScenarioGeneration
from scenario_generation.generator import ScenarioGenerator
from thesis_construction.contracts import InvestmentThesis, ThesisConstruction


# =========================================================================
# Helpers
# =========================================================================


def _make_thesis(
    thesis_id: str = "th_1",
    direction: str = "bullish",
    regime: str = "NORMAL_GROWTH",
    confidence: float = 0.8,
    time_horizon_days: int = 90,
    economic_mechanism: str = "falling real yields support gold",
    remaining_unknowns: tuple[str, ...] = ("USD_FX",),
    invalidating_conditions: tuple[str, ...] = ("real yields reverse",),
) -> InvestmentThesis:
    return InvestmentThesis(
        thesis_id=thesis_id,
        direction=direction,
        supporting_set_ids=("es_real_yield",),
        counter_evidence_ids=(),
        regime=regime,
        economic_mechanism=economic_mechanism,
        time_horizon_days=time_horizon_days,
        invalidating_conditions=invalidating_conditions,
        remaining_unknowns=remaining_unknowns,
        confidence_inputs={
            "avg_supporting_weight": confidence,
            "avg_supporting_consensus": round(min(confidence + 0.1, 1.0), 4),
            "conflict_severity": 0.0,
            "confidence_penalty": 0.0,
            "raw_support": round(confidence * confidence, 4),
        },
        institutional_support=confidence,
        explanation="test thesis",
    )


def _build_inputs(
    theses: tuple[InvestmentThesis, ...],
    regime: str = "NORMAL_GROWTH",
    confidences: dict[str, float] | None = None,
) -> tuple[
    ThesisConstruction,
    InstitutionalConfidence,
    ScenarioGeneration,
    RiskRewardValidation,
]:
    if confidences is None:
        confidences = {
            t.thesis_id: float(t.confidence_inputs.get("avg_supporting_weight", 0.0))
            for t in theses
        }
    construction = ThesisConstruction(
        construction_id="tc_w12_test",
        reasoning_id="er_w12_test",
        assessment_id="cea_w12_test",
        timestamp="2026-07-31T11:00:00",
        regime=regime,
        theses=theses,
        ranked_thesis_ids=tuple(t.thesis_id for t in theses),
        total_theses=len(theses),
        primary_thesis_id=theses[0].thesis_id if theses else "",
    )
    tcs = tuple(
        ThesisConfidence(
            thesis_id=t.thesis_id,
            final_confidence=confidences.get(t.thesis_id, 0.0),
            confidence_breakdown={
                "regime_alignment": (
                    1.0
                    if t.direction == "bullish"
                    and regime == "NORMAL_GROWTH"
                    else 0.0 if t.direction != "neutral" else 0.5
                )
            },
            remaining_uncertainty=round(
                1.0 - confidences.get(t.thesis_id, 0.0), 4
            ),
            reliability_category=(
                "high" if confidences.get(t.thesis_id, 0.0) >= 0.7 else "very_low"
            ),
        )
        for t in theses
    )
    confidence = InstitutionalConfidence(
        confidence_id="cf_w12_test",
        construction_id=construction.construction_id,
        timestamp="2026-07-31T11:00:00",
        regime=regime,
        theses_confidence=tcs,
        ranked_thesis_ids=construction.ranked_thesis_ids,
        primary_thesis_id=construction.primary_thesis_id,
    )
    generation = ScenarioGenerator().generate(construction, confidence)
    validation = RiskRewardValidatorForTest().validate(generation)
    return construction, confidence, generation, validation


from risk_reward_validation.validator import RiskRewardValidator as _RV


class RiskRewardValidatorForTest(_RV):
    pass


def _decide(
    theses: tuple[InvestmentThesis, ...],
    regime: str = "NORMAL_GROWTH",
    confidences: dict[str, float] | None = None,
) -> tuple[InstitutionalDecision, dict]:
    construction, confidence, generation, validation = _build_inputs(
        theses, regime=regime, confidences=confidences
    )
    decision = DecisionEngine().decide(construction, confidence, generation, validation)
    return decision, {
        "construction": construction,
        "confidence": confidence,
        "generation": generation,
        "validation": validation,
    }


def _strong_bullish() -> InvestmentThesis:
    return _make_thesis("th_strong", "bullish", confidence=0.8)


def _weak_bullish() -> InvestmentThesis:
    return _make_thesis("th_weak", "bullish", confidence=0.3)


def _medium_bullish() -> InvestmentThesis:
    return _make_thesis("th_medium", "bullish", confidence=0.6)


# =========================================================================
# Contract tests
# =========================================================================


class TestDecisionDriver:
    def test_roundtrip(self):
        d = DecisionDriver(name="evidence_quality", value=0.8, weight=0.15, score=0.12)
        restored = DecisionDriver.from_dict(d.to_dict())
        assert restored.name == "evidence_quality"
        assert restored.score == 0.12

    def test_validate(self):
        d = DecisionDriver(name="", value=2.0, weight=-1.0, score=0.0)
        errors = d.validate()
        assert any("name" in e for e in errors)
        assert any("value" in e for e in errors)
        assert any("weight" in e for e in errors)


class TestRejectedAlternative:
    def test_roundtrip(self):
        r = RejectedAlternative(
            thesis_id="th_1",
            thesis_direction="bullish",
            composite_score=0.4,
            rejection_reason="lower score",
        )
        restored = RejectedAlternative.from_dict(r.to_dict())
        assert restored.thesis_id == "th_1"
        assert restored.rejection_reason == "lower score"

    def test_validate(self):
        r = RejectedAlternative(
            thesis_id="", thesis_direction="", composite_score=0.4, rejection_reason=""
        )
        errors = r.validate()
        assert any("thesis_id" in e for e in errors)
        assert any("rejection_reason" in e for e in errors)


class TestInstitutionalDecision:
    def test_roundtrip(self):
        d = InstitutionalDecision(
            decision_id="dec_rt",
            decision="BUY",
            selected_thesis_id="th_1",
            selected_scenario_id="sc_1",
            institutional_confidence=0.8,
            risk_reward_summary={"status": "acceptable", "risk_reward_ratio": 0.5},
            decision_drivers=(
                DecisionDriver("institutional_confidence", 0.8, 0.3, 0.24),
            ),
            rejected_alternatives=(
                RejectedAlternative("th_2", "bearish", 0.3, "lower score"),
            ),
            decision_explanation="decision=BUY; reason=test",
            preconditions=("mechanism continues",),
            invalidation_conditions=("real yields reverse",),
        )
        restored = InstitutionalDecision.from_dict(d.to_dict())
        assert restored.decision == "BUY"
        assert restored.selected_thesis_id == "th_1"
        assert len(restored.decision_drivers) == 1
        assert len(restored.rejected_alternatives) == 1

    def test_validate_passes_for_generated(self):
        decision, _ = _decide((_strong_bullish(),))
        assert not decision.validate()

    def test_validate_detects_invalid_decision(self):
        d = InstitutionalDecision(
            decision_id="dec_bad",
            decision="MAYBE",
            selected_thesis_id="",
            selected_scenario_id="",
            institutional_confidence=0.0,
            decision_explanation="test",
        )
        errors = d.validate()
        assert any("decision" in e for e in errors)

    def test_validate_detects_missing_ids_for_directional(self):
        d = InstitutionalDecision(
            decision_id="dec_bad",
            decision="BUY",
            selected_thesis_id="",
            selected_scenario_id="",
            institutional_confidence=0.8,
            decision_explanation="test",
        )
        errors = d.validate()
        assert any("selected_thesis_id" in e for e in errors)
        assert any("selected_scenario_id" in e for e in errors)
        assert any("preconditions" in e for e in errors)
        assert any("invalidation_conditions" in e for e in errors)

    def test_validate_allows_empty_for_no_trade(self):
        d = InstitutionalDecision(
            decision_id="dec_nt",
            decision="NO_TRADE",
            selected_thesis_id="",
            selected_scenario_id="",
            institutional_confidence=0.0,
            decision_explanation="test",
        )
        assert not d.validate()

    def test_validate_detects_missing_explanation(self):
        d = InstitutionalDecision(
            decision_id="dec_bad",
            decision="HOLD",
            selected_thesis_id="th_1",
            selected_scenario_id="sc_1",
            institutional_confidence=0.5,
            preconditions=("x",),
            invalidation_conditions=("y",),
        )
        errors = d.validate()
        assert any("decision_explanation" in e for e in errors)

    def test_validate_detects_out_of_range_confidence(self):
        d = InstitutionalDecision(
            decision_id="dec_bad",
            decision="NO_TRADE",
            selected_thesis_id="",
            selected_scenario_id="",
            institutional_confidence=2.0,
            decision_explanation="test",
        )
        errors = d.validate()
        assert any("institutional_confidence" in e for e in errors)

    def test_json_serializable(self):
        decision, _ = _decide((_strong_bullish(), _medium_bullish()))
        restored = InstitutionalDecision.from_dict(json.loads(json.dumps(decision.to_dict())))
        assert restored.decision == decision.decision
        assert not restored.validate()

    def test_valid_decisions(self):
        assert VALID_DECISIONS == {"BUY", "SELL", "HOLD", "NO_TRADE"}


# =========================================================================
# DecisionEngine tests
# =========================================================================


class TestDecisionEngine:
    def test_strong_bullish_yields_buy(self):
        decision, _ = _decide((_strong_bullish(),))
        assert decision.decision == "BUY"
        assert decision.selected_thesis_id == "th_strong"
        assert decision.institutional_confidence == 0.8

    def test_strong_bearish_yields_sell(self):
        thesis = _make_thesis("th_bear", "bearish", confidence=0.8)
        decision, _ = _decide((thesis,))
        assert decision.decision == "SELL"
        assert decision.selected_thesis_id == "th_bear"

    def test_neutral_yields_hold(self):
        thesis = _make_thesis("th_neutral", "neutral", confidence=0.6)
        decision, _ = _decide((thesis,))
        assert decision.decision == "HOLD"
        assert decision.selected_thesis_id == "th_neutral"

    def test_weak_thesis_yields_no_trade(self):
        decision, _ = _decide((_weak_bullish(),))
        assert decision.decision == "NO_TRADE"
        assert decision.selected_thesis_id == "th_weak"
        assert decision.institutional_confidence == 0.3

    def test_neutral_low_confidence_no_trade(self):
        thesis = _make_thesis("th_n", "neutral", confidence=0.2)
        decision, _ = _decide((thesis,))
        assert decision.decision == "NO_TRADE"

    def test_empty_construction_no_trade(self):
        decision, _ = _decide(())
        assert decision.decision == "NO_TRADE"
        assert decision.rejected_alternatives == ()

    def test_selected_scenario_is_base(self):
        decision, _ = _decide((_strong_bullish(),))
        assert decision.metadata["selected_scenario_type"] == "base"

    def test_selection_prefers_highest_score(self):
        decision, _ = _decide((_strong_bullish(), _medium_bullish()))
        assert decision.selected_thesis_id == "th_strong"
        ids = [r.thesis_id for r in decision.rejected_alternatives]
        assert "th_medium" in ids
        medium = next(r for r in decision.rejected_alternatives if r.thesis_id == "th_medium")
        assert "lower composite score" in medium.rejection_reason

    def test_ineligible_thesis_rejected_by_w11(self):
        thesis = _make_thesis("th_1", "bullish", confidence=0.8)
        construction, confidence, generation, validation = _build_inputs((thesis,))
        scenarios = []
        validations = []
        for stype, direction, prob in (
            ("base", "bullish", 0.5),
            ("bull", "bullish", 0.35),
            ("bear", "bearish", 0.15),
        ):
            sc = InstitutionalScenario(
                scenario_id=f"sc_{stype}",
                thesis_id="th_1",
                scenario_type=stype,
                probability=prob,
                expected_direction=direction,
                time_horizon_days=90,
                regime_path=("NORMAL_GROWTH",),
                confidence_inputs={
                    "final_confidence": 0.8,
                    "remaining_uncertainty": 0.2,
                    "institutional_support": 0.8,
                    "reliability_category": "high",
                },
            )
            scenarios.append(sc)
            validations.append(
                InstitutionalRiskValidation(
                    validation_id=f"rv_{stype}",
                    scenario_id=sc.scenario_id,
                    thesis_id="th_1",
                    validation_status="reject",
                    expected_reward=0.01,
                    expected_risk=0.5,
                    risk_reward_ratio=9.0,
                    maximum_downside=0.9,
                    expected_upside=0.1,
                    volatility_impact=0.8,
                    regime_risk=0.8,
                    liquidity_risk=0.6,
                    tail_risk=0.9,
                    validation_explanation="rejected",
                )
            )
        generation = ScenarioGeneration(
            scenario_generation_id="sg_manual",
            construction_id=construction.construction_id,
            confidence_id=confidence.confidence_id,
            timestamp="2026-07-31T11:00:00",
            regime="NORMAL_GROWTH",
            scenarios=tuple(scenarios),
            thesis_ids=("th_1",),
            total_scenarios=3,
            probability_consistency={"th_1": 1.0},
        )
        validation = RiskRewardValidation(
            validation_id="rvv_manual",
            scenario_generation_id="sg_manual",
            timestamp="2026-07-31T11:00:00",
            regime="NORMAL_GROWTH",
            validations=tuple(validations),
            scenario_ids=tuple(v.scenario_id for v in validations),
            total_validations=3,
            summary={"acceptable": 0, "borderline": 0, "reject": 3},
        )
        decision = DecisionEngine().decide(
            construction, confidence, generation, validation
        )
        assert decision.decision == "NO_TRADE"
        assert len(decision.rejected_alternatives) == 1
        assert "rejected by W12" in decision.rejected_alternatives[0].rejection_reason

    def test_no_trade_when_rr_ratio_exceeds_threshold(self):
        thesis = _make_thesis("th_1", "bullish", confidence=0.8)
        construction, confidence, generation, validation = _build_inputs((thesis,))
        scenario = generation.scenarios[0]
        validation = RiskRewardValidation(
            validation_id="rvv_manual",
            scenario_generation_id=generation.scenario_generation_id,
            timestamp="2026-07-31T11:00:00",
            regime="NORMAL_GROWTH",
            validations=(
                InstitutionalRiskValidation(
                    validation_id="rv_1",
                    scenario_id=scenario.scenario_id,
                    thesis_id=thesis.thesis_id,
                    validation_status="acceptable",
                    expected_reward=0.3,
                    expected_risk=0.6,
                    risk_reward_ratio=2.5,
                    maximum_downside=0.7,
                    expected_upside=0.9,
                    volatility_impact=0.6,
                    regime_risk=0.5,
                    liquidity_risk=0.4,
                    tail_risk=0.6,
                    validation_explanation="acceptable but risky",
                ),
            ),
            scenario_ids=(scenario.scenario_id,),
            total_validations=1,
            summary={"acceptable": 1, "borderline": 0, "reject": 0},
        )
        decision = DecisionEngine().decide(construction, confidence, generation, validation)
        assert decision.decision == "NO_TRADE"

    def test_drivers_include_all_six(self):
        decision, _ = _decide((_strong_bullish(),))
        names = [d.name for d in decision.decision_drivers]
        assert names == [
            "institutional_confidence",
            "risk_reward_quality",
            "evidence_quality",
            "counter_evidence_quality",
            "scenario_probability",
            "regime_alignment",
        ]
        assert abs(sum(d.weight for d in decision.decision_drivers) - 1.0) < 1e-6
        for d in decision.decision_drivers:
            assert d.score == round(d.value * d.weight, 4)

    def test_risk_reward_summary_present(self):
        decision, _ = _decide((_strong_bullish(),))
        summary = decision.risk_reward_summary
        assert summary["status"] in {"acceptable", "borderline", "reject"}
        assert "expected_reward" in summary
        assert "risk_reward_ratio" in summary
        assert "maximum_downside" in summary

    def test_preconditions_and_invalidation(self):
        decision, _ = _decide((_strong_bullish(),))
        assert decision.preconditions
        assert decision.invalidation_conditions
        assert any("real yields reverse" in c for c in decision.invalidation_conditions)

    def test_explanation_complete(self):
        decision, _ = _decide((_strong_bullish(),))
        assert decision.decision in decision.decision_explanation
        assert "selected_thesis=th_strong" in decision.decision_explanation
        assert "composite_score=" in decision.decision_explanation
        assert "reason=" in decision.decision_explanation

    def test_provenance_chain_ends_with_w13(self):
        decision, _ = _decide((_strong_bullish(),))
        assert decision.provenance_chain[-1].created_by == "W13 DecisionEngine"
        assert any(p.created_by == "W12 RiskRewardValidator" for p in decision.provenance_chain)

    def test_composite_score_matches_drivers(self):
        decision, _ = _decide((_strong_bullish(),))
        driver_sum = sum(d.score for d in decision.decision_drivers)
        assert abs(driver_sum - decision.metadata["composite_score"]) < 0.005

    def test_metadata_totals(self):
        decision, _ = _decide((_strong_bullish(), _medium_bullish()))
        assert decision.metadata["total_theses_evaluated"] == 2
        assert decision.metadata["total_rejected_alternatives"] == 1

    def test_rejected_alternatives_sorted_desc(self):
        decision, _ = _decide((_strong_bullish(), _medium_bullish()))
        scores = [r.composite_score for r in decision.rejected_alternatives]
        assert scores == sorted(scores, reverse=True)

    def test_roundtrip_roundtrip(self):
        decision, _ = _decide((_strong_bullish(), _weak_bullish()))
        restored = InstitutionalDecision.from_dict(decision.to_dict())
        assert restored.decision_id == decision.decision_id
        assert restored.decision == decision.decision
        assert len(restored.decision_drivers) == 6
        assert len(restored.rejected_alternatives) == 1
        assert not restored.validate()

    def test_determine_decision_direct(self):
        determine = DecisionEngine()._determine_decision
        tc_high = ThesisConfidence("a", final_confidence=0.8)
        tc_med = ThesisConfidence("a", final_confidence=0.6)
        tc_low = ThesisConfidence("a", final_confidence=0.2)
        tc_sub = ThesisConfidence("a", final_confidence=0.4)
        assert determine(_make_thesis("a", "bullish", confidence=0.8), tc_high, _rv_acceptable()) == "BUY"
        assert determine(_make_thesis("a", "bearish", confidence=0.8), tc_high, _rv_acceptable()) == "SELL"
        assert determine(_make_thesis("a", "neutral", confidence=0.6), tc_med, _rv_acceptable()) == "HOLD"
        assert determine(_make_thesis("a", "neutral", confidence=0.2), tc_low, _rv_acceptable()) == "NO_TRADE"
        assert determine(_make_thesis("a", "bullish", confidence=0.4), tc_sub, _rv_acceptable()) == "NO_TRADE"
        assert determine(_make_thesis("a", "bullish", confidence=0.8), tc_high, _rv_risky()) == "NO_TRADE"


def _rv_acceptable() -> InstitutionalRiskValidation:
    return InstitutionalRiskValidation(
        validation_id="rv_ok",
        scenario_id="sc_ok",
        thesis_id="a",
        validation_status="acceptable",
        expected_reward=0.3,
        expected_risk=0.1,
        risk_reward_ratio=0.5,
        maximum_downside=0.2,
        expected_upside=0.8,
        volatility_impact=0.3,
        regime_risk=0.3,
        liquidity_risk=0.1,
        tail_risk=0.1,
        validation_explanation="ok",
    )


def _rv_risky() -> InstitutionalRiskValidation:
    return InstitutionalRiskValidation(
        validation_id="rv_risky",
        scenario_id="sc_risky",
        thesis_id="a",
        validation_status="acceptable",
        expected_reward=0.3,
        expected_risk=0.6,
        risk_reward_ratio=2.5,
        maximum_downside=0.7,
        expected_upside=0.8,
        volatility_impact=0.6,
        regime_risk=0.5,
        liquidity_risk=0.4,
        tail_risk=0.6,
        validation_explanation="risky",
    )


# =========================================================================
# W8 -> W9 -> W12 -> W13 integration test
# =========================================================================


def test_w8_to_w9_to_w12_to_w13_integration():
    from evidence_collection.contracts import Evidence, EvidenceCollection
    from evidence_reasoning.reasoner import EvidenceReasoner
    from counter_evidence.assessor import CounterEvidenceAssessor
    from thesis_construction.constructor import ThesisConstructor
    from confidence_engine.engine import ConfidenceEngine
    from scenario_generation.generator import ScenarioGenerator
    from risk_reward_validation.validator import RiskRewardValidator

    ev1 = Evidence(
        evidence_id="ev_gold_1", source_kr_id="KR-001", source_kr_node_id="KR-001",
        event_type="REAL_YIELD", condition={"instrument": "XAU/USD"}, bias="bullish",
        base_confidence=0.85, regime_weight=0.8, composite_weight=0.68,
        explanation="Real yields falling", regime="NORMAL_GROWTH",
        source_label="overnight_price",
        temporal_recency=0.9,
        metadata={"instrument": "XAU/USD", "classification": "Signal"},
    )
    ev2 = Evidence(
        evidence_id="ev_dxy_1", source_kr_id="KR-002", source_kr_node_id="KR-002",
        event_type="USD_FX", condition={"instrument": "DXY"}, bias="bearish",
        base_confidence=0.72, regime_weight=0.8, composite_weight=0.576,
        explanation="DXY weakening", regime="NORMAL_GROWTH",
        source_label="overnight_price",
        temporal_recency=0.85,
        metadata={"instrument": "DXY", "classification": "Signal"},
    )

    collection = EvidenceCollection(
        collection_id="ec_w12", assessment_id="sa_w12",
        timestamp="2026-07-31T11:00:00", regime="NORMAL_GROWTH",
        items=(ev1, ev2), total_classified=2, signals_count=2,
    )

    reasoning = EvidenceReasoner().reason(collection)
    assessment = CounterEvidenceAssessor().assess(reasoning)
    construction = ThesisConstructor().construct(reasoning, assessment)
    confidence = ConfidenceEngine().evaluate(construction)
    generation = ScenarioGenerator().generate(construction, confidence)
    validation = RiskRewardValidator().validate(generation)
    decision = DecisionEngine().decide(
        construction, confidence, generation, validation
    )

    assert decision.decision in VALID_DECISIONS
    assert decision.selected_thesis_id in {
        t.thesis_id for t in construction.theses
    } or decision.decision == "NO_TRADE"
    if decision.decision != "NO_TRADE":
        assert decision.selected_scenario_id in {
            s.scenario_id for s in generation.scenarios
        }
        assert decision.selected_thesis_id == construction.primary_thesis_id or (
            decision.metadata["composite_score"] >= 0
        )
        assert decision.preconditions
        assert decision.invalidation_conditions
        assert len(decision.decision_drivers) == 6

    assert not decision.validate()
    assert decision.decision_explanation
    assert decision.provenance_chain[-1].created_by == "W13 DecisionEngine"
    assert any(p.created_by == "W9 ConfidenceEngine" for p in decision.provenance_chain)

    for alt in decision.rejected_alternatives:
        assert alt.thesis_id != decision.selected_thesis_id
        assert alt.rejection_reason


# =========================================================================
# W13 orchestration stage tests
# =========================================================================


def test_w13_orchestration_stage():
    from orchestration.stages import _decision_engine

    construction, confidence, generation, validation = _build_inputs(
        (_strong_bullish(), _medium_bullish())
    )
    result = _decision_engine(
        {},
        {
            "thesis_construction": construction.to_dict(),
            "confidence_engine": confidence.to_dict(),
            "scenario_generation": generation.to_dict(),
            "risk_reward_validation": validation.to_dict(),
        },
    )
    assert isinstance(result, InstitutionalDecision)
    assert result.decision in VALID_DECISIONS
    assert result.decision == "BUY"


def test_w12_orchestration_stage_missing_data():
    from orchestration.stages import _decision_engine

    result = _decision_engine({}, {})
    assert isinstance(result, dict)
    assert "error" in result

    result = _decision_engine(
        {},
        {
            "thesis_construction": {},
            "confidence_engine": {},
            "scenario_generation": {},
        },
    )
    assert isinstance(result, dict)
    assert "error" in result


def test_w12_orchestration_stage_propagates_upstream_errors():
    from orchestration.stages import _decision_engine

    result = _decision_engine(
        {},
        {
            "thesis_construction": {"error": "failed"},
            "confidence_engine": {},
            "scenario_generation": {},
            "risk_reward_validation": {},
        },
    )
    assert isinstance(result, dict)
    assert "error" in result


def test_w13_stage_uses_versioned_thesis_from_update():
    """Issue #001 regression: when thesis_update is present, _decision_engine
    must evaluate the versioned thesis so that confidence keyed by the
    versioned thesis_id is found instead of defaulting to 0.0."""
    from thesis_update.contracts import ThesisUpdate
    from orchestration.stages import _decision_engine

    original = _make_thesis("th_issue001", "bullish", confidence=0.8)
    versioned = InvestmentThesis(
        thesis_id="th_issue001.v2",
        direction=original.direction,
        supporting_set_ids=original.supporting_set_ids,
        counter_evidence_ids=original.counter_evidence_ids,
        regime=original.regime,
        economic_mechanism=original.economic_mechanism,
        time_horizon_days=original.time_horizon_days,
        invalidating_conditions=original.invalidating_conditions,
        remaining_unknowns=original.remaining_unknowns,
        confidence_inputs=dict(original.confidence_inputs),
        institutional_support=original.institutional_support,
        explanation=original.explanation,
    )

    # Confidence, scenarios and validations are keyed to the versioned thesis,
    # mirroring the runtime where confidence/scenario stages consume the update.
    _, confidence, generation, validation = _build_inputs(
        (versioned,), confidences={"th_issue001.v2": 0.8}
    )
    construction, _, _, _ = _build_inputs((original,))

    update = ThesisUpdate(
        update_id="update-th_issue001-v2",
        previous_thesis_id="th_issue001",
        previous_version="v1",
        new_thesis_version="v2",
        reasoning_id="er_w12_test",
        assessment_id="cea_w12_test",
        timestamp="2026-07-31T11:00:00",
        updated_evidence=(),
        confidence_delta=0.0,
        changed_assumptions=(),
        change_summary="test",
        action="no_change",
        trigger_type="periodic",
        updated_thesis=versioned,
    )

    result = _decision_engine(
        {},
        {
            "thesis_construction": construction.to_dict(),
            "thesis_update": update.to_dict(),
            "confidence_engine": confidence.to_dict(),
            "scenario_generation": generation.to_dict(),
            "risk_reward_validation": validation.to_dict(),
        },
    )

    assert isinstance(result, InstitutionalDecision)
    assert result.selected_thesis_id == "th_issue001.v2"
    assert result.institutional_confidence > 0.0
    assert result.decision != "NO_TRADE"
