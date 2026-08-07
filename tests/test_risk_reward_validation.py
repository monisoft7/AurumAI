"""Unit + integration tests for W12 Institutional Risk / Reward Validation."""

import json

import pytest

from risk_reward_validation.contracts import (
    VALID_VALIDATION_STATUS,
    InstitutionalRiskValidation,
    RiskRewardValidation,
)
from risk_reward_validation.validator import RiskRewardValidator
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
    time_horizon_days: int = 90,
    economic_mechanism: str = "falling real yields support gold",
    remaining_unknowns: tuple[str, ...] = ("USD_FX",),
    invalidating_conditions: tuple[str, ...] = ("real yields reverse",),
    institutional_support: float = 0.7,
    confidence_inputs: dict | None = None,
) -> InvestmentThesis:
    if confidence_inputs is None:
        confidence_inputs = {
            "avg_supporting_weight": 0.8,
            "avg_supporting_consensus": 0.9,
            "conflict_severity": 0.0,
            "confidence_penalty": 0.0,
            "raw_support": 0.72,
        }
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
        confidence_inputs=confidence_inputs,
        institutional_support=institutional_support,
        explanation="test thesis",
    )


def _generate_scenarios(
    theses: tuple[InvestmentThesis, ...],
    regime: str = "NORMAL_GROWTH",
) -> ScenarioGeneration:
    construction = ThesisConstruction(
        construction_id="tc_w11_test",
        reasoning_id="er_w11_test",
        assessment_id="cea_w11_test",
        timestamp="2026-07-31T10:00:00",
        regime=regime,
        theses=theses,
        ranked_thesis_ids=tuple(t.thesis_id for t in theses),
        total_theses=len(theses),
        primary_thesis_id=theses[0].thesis_id if theses else "",
    )
    return ScenarioGenerator().generate(construction)


def _validate(
    theses: tuple[InvestmentThesis, ...],
    regime: str = "NORMAL_GROWTH",
) -> RiskRewardValidation:
    generation = _generate_scenarios(theses, regime=regime)
    return RiskRewardValidator().validate(generation)


def _strong_bullish_thesis() -> InvestmentThesis:
    return _make_thesis("th_strong", institutional_support=0.72, confidence_inputs={
        "avg_supporting_weight": 0.8,
        "avg_supporting_consensus": 0.9,
        "conflict_severity": 0.0,
        "confidence_penalty": 0.0,
        "raw_support": 0.72,
    })


def _weak_bullish_thesis() -> InvestmentThesis:
    return _make_thesis("th_weak", institutional_support=0.036, confidence_inputs={
        "avg_supporting_weight": 0.3,
        "avg_supporting_consensus": 0.4,
        "conflict_severity": 0.8,
        "confidence_penalty": 0.7,
        "raw_support": 0.12,
    })


# =========================================================================
# Contract tests
# =========================================================================


class TestInstitutionalRiskValidation:
    def test_minimal_validation(self):
        v = InstitutionalRiskValidation(
            validation_id="rv_1",
            scenario_id="sc_1",
            thesis_id="th_1",
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
            validation_explanation="test",
        )
        assert v.validation_status == "acceptable"

    def test_to_dict_from_dict_roundtrip(self):
        v = InstitutionalRiskValidation(
            validation_id="rv_rt",
            scenario_id="sc_rt",
            thesis_id="th_rt",
            validation_status="borderline",
            expected_reward=0.15,
            expected_risk=0.2,
            risk_reward_ratio=1.5,
            maximum_downside=0.5,
            expected_upside=0.4,
            volatility_impact=0.5,
            regime_risk=0.6,
            liquidity_risk=0.4,
            tail_risk=0.5,
            validation_explanation="test explanation",
        )
        d = v.to_dict()
        restored = InstitutionalRiskValidation.from_dict(d)
        assert restored.validation_id == v.validation_id
        assert restored.validation_status == "borderline"
        assert restored.risk_reward_ratio == 1.5
        assert restored.maximum_downside == 0.5

    def test_validate_passes_for_valid(self):
        v = InstitutionalRiskValidation(
            validation_id="rv_valid",
            scenario_id="sc_valid",
            thesis_id="th_valid",
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
            validation_explanation="test",
        )
        assert not v.validate()

    def test_validate_detects_invalid_status(self):
        v = InstitutionalRiskValidation(
            validation_id="rv_bad",
            scenario_id="sc_1",
            thesis_id="th_1",
            validation_status="maybe",
            expected_reward=0.3,
            expected_risk=0.1,
            risk_reward_ratio=0.5,
            maximum_downside=0.2,
            expected_upside=0.8,
            volatility_impact=0.3,
            regime_risk=0.3,
            liquidity_risk=0.1,
            tail_risk=0.1,
            validation_explanation="test",
        )
        errors = v.validate()
        assert any("validation_status" in e for e in errors)

    def test_validate_detects_out_of_range_metrics(self):
        v = InstitutionalRiskValidation(
            validation_id="rv_bad",
            scenario_id="sc_1",
            thesis_id="th_1",
            validation_status="acceptable",
            expected_reward=1.5,
            expected_risk=-0.1,
            risk_reward_ratio=-1.0,
            maximum_downside=0.2,
            expected_upside=0.8,
            volatility_impact=0.3,
            regime_risk=0.3,
            liquidity_risk=0.1,
            tail_risk=0.1,
            validation_explanation="test",
        )
        errors = v.validate()
        assert any("expected_reward" in e for e in errors)
        assert any("expected_risk" in e for e in errors)
        assert any("risk_reward_ratio" in e for e in errors)

    def test_validate_detects_missing_explanation(self):
        v = InstitutionalRiskValidation(
            validation_id="rv_bad",
            scenario_id="sc_1",
            thesis_id="th_1",
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
        )
        errors = v.validate()
        assert any("validation_explanation" in e for e in errors)

    def test_json_serializable(self):
        v = InstitutionalRiskValidation(
            validation_id="rv_json",
            scenario_id="sc_json",
            thesis_id="th_json",
            validation_status="reject",
            expected_reward=0.02,
            expected_risk=0.3,
            risk_reward_ratio=8.0,
            maximum_downside=0.7,
            expected_upside=0.1,
            volatility_impact=0.6,
            regime_risk=0.8,
            liquidity_risk=0.6,
            tail_risk=0.8,
            validation_explanation="test",
        )
        restored = InstitutionalRiskValidation.from_dict(
            json.loads(json.dumps(v.to_dict()))
        )
        assert restored.validation_status == "reject"
        assert restored.tail_risk == 0.8

    def test_valid_statuses(self):
        assert VALID_VALIDATION_STATUS == {"acceptable", "borderline", "reject"}


class TestRiskRewardValidation:
    def test_to_dict_from_dict_roundtrip(self):
        v = InstitutionalRiskValidation(
            validation_id="rv_1",
            scenario_id="sc_1",
            thesis_id="th_1",
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
            validation_explanation="test",
        )
        rv = RiskRewardValidation(
            validation_id="rvv_rt",
            scenario_generation_id="sg_rt",
            timestamp="2026-07-31T10:00:00",
            regime="NORMAL_GROWTH",
            validations=(v,),
            scenario_ids=("sc_1",),
            total_validations=1,
            summary={"acceptable": 1, "borderline": 0, "reject": 0},
        )
        d = rv.to_dict()
        restored = RiskRewardValidation.from_dict(d)
        assert restored.validation_id == rv.validation_id
        assert len(restored.validations) == 1
        assert restored.summary == {"acceptable": 1, "borderline": 0, "reject": 0}

    def test_validate_passes_for_generated(self):
        rv = _validate((_strong_bullish_thesis(),))
        assert not rv.validate()

    def test_validate_detects_summary_mismatch(self):
        v = InstitutionalRiskValidation(
            validation_id="rv_1",
            scenario_id="sc_1",
            thesis_id="th_1",
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
            validation_explanation="test",
        )
        rv = RiskRewardValidation(
            validation_id="rvv_bad",
            scenario_generation_id="sg_1",
            timestamp="2026-07-31T10:00:00",
            regime="NORMAL_GROWTH",
            validations=(v,),
            scenario_ids=("sc_1",),
            total_validations=1,
            summary={"acceptable": 0, "borderline": 1, "reject": 0},
        )
        errors = rv.validate()
        assert any("summary" in e for e in errors)

    def test_validate_detects_scenario_id_mismatch(self):
        v = InstitutionalRiskValidation(
            validation_id="rv_1",
            scenario_id="sc_x",
            thesis_id="th_1",
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
            validation_explanation="test",
        )
        rv = RiskRewardValidation(
            validation_id="rvv_bad",
            scenario_generation_id="sg_1",
            timestamp="2026-07-31T10:00:00",
            regime="NORMAL_GROWTH",
            validations=(v,),
            scenario_ids=("sc_other",),
            total_validations=1,
            summary={"acceptable": 1, "borderline": 0, "reject": 0},
        )
        errors = rv.validate()
        assert any("scenario_ids" in e for e in errors)

    def test_summary_properties(self):
        rv = _validate((_strong_bullish_thesis(),))
        assert rv.acceptable_count == rv.summary["acceptable"]
        assert rv.borderline_count == rv.summary["borderline"]
        assert rv.reject_count == rv.summary["reject"]


# =========================================================================
# RiskRewardValidator tests
# =========================================================================


class TestRiskRewardValidator:
    def test_one_validation_per_scenario(self):
        rv = _validate((_strong_bullish_thesis(),))
        assert rv.total_validations == 3
        assert len(rv.validations) == 3
        assert set(rv.scenario_ids) == {v.scenario_id for v in rv.validations}

    def test_scenario_id_mapping(self):
        generation = _generate_scenarios((_strong_bullish_thesis(),))
        scenario_ids = {s.scenario_id for s in generation.scenarios}
        rv = RiskRewardValidator().validate(generation)
        assert set(rv.scenario_ids) == scenario_ids

    def test_metrics_in_range(self):
        rv = _validate((_strong_bullish_thesis(), _weak_bullish_thesis()))
        for v in rv.validations:
            for metric in (
                v.expected_reward,
                v.expected_risk,
                v.risk_reward_ratio,
                v.maximum_downside,
                v.expected_upside,
                v.volatility_impact,
                v.regime_risk,
                v.liquidity_risk,
                v.tail_risk,
            ):
                assert 0.0 <= metric <= 10.0
            assert 0.0 <= v.maximum_downside <= 1.0
            assert 0.0 <= v.expected_upside <= 1.0

    def test_strong_bullish_thesis_classification(self):
        generation = _generate_scenarios((_strong_bullish_thesis(),))
        rv = RiskRewardValidator().validate(generation)
        by_scenario = {}
        for v in rv.validations:
            scenario = next(
                s for s in generation.scenarios if s.scenario_id == v.scenario_id
            )
            by_scenario[scenario.scenario_type] = v
        assert by_scenario["bull"].validation_status == "acceptable"
        assert by_scenario["base"].validation_status == "acceptable"
        assert by_scenario["bear"].validation_status == "reject"

    def test_strong_bullish_thesis_exact_metrics(self):
        rv = _validate((_strong_bullish_thesis(),))
        generation = _generate_scenarios((_strong_bullish_thesis(),))
        bull = next(v for v in rv.validations if v.metadata["scenario_type"] == "bull")
        assert bull.expected_upside == 0.804
        assert bull.maximum_downside == 0.1984
        assert bull.expected_reward == 0.279
        assert bull.expected_risk == 0.0688
        assert bull.tail_risk == 0.14
        assert bull.regime_risk == 0.4
        assert bull.volatility_impact == 0.34
        assert bull.liquidity_risk == 0.1233

    def test_weak_bullish_thesis_classification(self):
        generation = _generate_scenarios((_weak_bullish_thesis(),))
        rv = RiskRewardValidator().validate(generation)
        by_scenario = {}
        for v in rv.validations:
            scenario = next(s for s in generation.scenarios if s.scenario_id == v.scenario_id)
            by_scenario[scenario.scenario_type] = v
        assert by_scenario["bull"].validation_status == "reject"
        assert by_scenario["base"].validation_status == "borderline"

    def test_risk_reward_ratio_formula(self):
        from risk_reward_validation.validator import MAX_RISK_REWARD_RATIO

        rv = _validate((_strong_bullish_thesis(), _weak_bullish_thesis()))
        for v in rv.validations:
            if v.expected_reward > 0.0:
                risk_score = round(
                    0.5 * v.expected_risk
                    + 0.2 * v.tail_risk
                    + 0.2 * v.regime_risk
                    + 0.1 * v.liquidity_risk,
                    4,
                )
                expected = min(round(risk_score / v.expected_reward, 4), MAX_RISK_REWARD_RATIO)
                assert v.risk_reward_ratio == expected

    def test_bear_scenario_more_downside_than_upside(self):
        generation = _generate_scenarios((_strong_bullish_thesis(),))
        rv = RiskRewardValidator().validate(generation)
        for v in rv.validations:
            scenario = next(s for s in generation.scenarios if s.scenario_id == v.scenario_id)
            if scenario.scenario_type == "bear":
                assert v.maximum_downside > v.expected_upside

    def test_regime_risk_unknown_regime(self):
        rv = _validate((_strong_bullish_thesis(),), regime="MYSTERY_REGIME")
        for v in rv.validations:
            assert v.regime_risk == 1.0

    def test_regime_risk_transition_vs_continuation(self):
        assert RiskRewardValidator._regime_risk(()) == 1.0
        assert RiskRewardValidator._regime_risk(("NORMAL_GROWTH",)) == 0.3
        assert RiskRewardValidator._regime_risk(
            ("NORMAL_GROWTH", "NORMAL_GROWTH")
        ) == 0.4
        assert RiskRewardValidator._regime_risk(
            ("NORMAL_GROWTH", "DEFLATIONARY_CRISIS")
        ) == 0.75
        assert RiskRewardValidator._regime_risk(("UNKNOWN", "X")) == 1.0

    def test_classify_thresholds(self):
        classify = RiskRewardValidator._classify
        assert classify(0.3, 0.5) == "acceptable"
        assert classify(0.3, 1.0) == "acceptable"
        assert classify(0.2, 1.1) == "borderline"
        assert classify(0.1, 2.0) == "borderline"
        assert classify(0.2, 3.0) == "reject"
        assert classify(0.01, 0.5) == "reject"
        assert classify(0.04, 0.5) == "reject"
        assert classify(0.05, 0.5) == "borderline"

    def test_alignment(self):
        assert RiskRewardValidator._alignment("bullish") == 1.0
        assert RiskRewardValidator._alignment("bearish") == 0.0
        assert RiskRewardValidator._alignment("neutral") == 0.5

    def test_explanation_is_detailed(self):
        rv = _validate((_strong_bullish_thesis(),))
        for v in rv.validations:
            assert v.validation_explanation
            assert v.validation_status in v.validation_explanation
            assert "expected_reward" in v.validation_explanation
            assert "risk_reward_ratio" in v.validation_explanation
            assert "tail_risk" in v.validation_explanation
            assert "reason=" in v.validation_explanation

    def test_provenance_chain_ends_with_w12(self):
        rv = _validate((_strong_bullish_thesis(),))
        for v in rv.validations:
            assert v.provenance_chain[-1].created_by == "W12 RiskRewardValidator"
            assert any(
                p.created_by == "W12 ScenarioGenerator" for p in v.provenance_chain
            )

    def test_summary_counts(self):
        rv = _validate((_strong_bullish_thesis(),))
        counts = {"acceptable": 0, "borderline": 0, "reject": 0}
        for v in rv.validations:
            counts[v.validation_status] += 1
        assert rv.summary == counts

    def test_empty_generation(self):
        generation = _generate_scenarios(())
        rv = RiskRewardValidator().validate(generation)
        assert rv.total_validations == 0
        assert rv.validations == ()
        assert rv.scenario_ids == ()
        assert rv.summary == {"acceptable": 0, "borderline": 0, "reject": 0}

    def test_generation_roundtrip(self):
        rv = _validate((_strong_bullish_thesis(), _weak_bullish_thesis()))
        restored = RiskRewardValidation.from_dict(rv.to_dict())
        assert restored.validation_id == rv.validation_id
        assert restored.total_validations == 6
        assert restored.summary == rv.summary
        assert not restored.validate()

    def test_json_serializable(self):
        rv = _validate((_strong_bullish_thesis(), _weak_bullish_thesis()))
        restored = RiskRewardValidation.from_dict(json.loads(json.dumps(rv.to_dict())))
        assert restored.total_validations == 6
        assert not restored.validate()


# =========================================================================
# W8 -> W10 -> W12 integration test
# =========================================================================


def test_w8_to_w10_to_w11_integration():
    from evidence_collection.contracts import Evidence, EvidenceCollection
    from evidence_reasoning.reasoner import EvidenceReasoner
    from counter_evidence.assessor import CounterEvidenceAssessor
    from thesis_construction.constructor import ThesisConstructor
    from scenario_generation.generator import ScenarioGenerator

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
        collection_id="ec_w11", assessment_id="sa_w11",
        timestamp="2026-07-31T10:00:00", regime="NORMAL_GROWTH",
        items=(ev1, ev2), total_classified=2, signals_count=2,
    )

    reasoning = EvidenceReasoner().reason(collection)
    assessment = CounterEvidenceAssessor().assess(reasoning)
    construction = ThesisConstructor().construct(reasoning, assessment)
    generation = ScenarioGenerator().generate(construction)
    validation = RiskRewardValidator().validate(generation)

    assert validation.scenario_generation_id == generation.scenario_generation_id
    assert validation.regime == "NORMAL_GROWTH"
    assert validation.total_validations == generation.total_scenarios

    generation_scenario_ids = {s.scenario_id for s in generation.scenarios}
    assert set(validation.scenario_ids) == generation_scenario_ids
    assert set(validation.summary.values()) and not validation.validate()

    for v in validation.validations:
        errors = v.validate()
        assert not errors, f"Validation failed: {errors}"
        assert v.validation_status in VALID_VALIDATION_STATUS
        assert 0.0 <= v.risk_reward_ratio <= 10.0
        assert v.provenance_chain[-1].created_by == "W12 RiskRewardValidator"
        assert any(p.created_by == "W12 ScenarioGenerator" for p in v.provenance_chain)

    total = sum(validation.summary.values())
    assert total == validation.total_validations


# =========================================================================
# W12 orchestration stage tests
# =========================================================================


def test_w11_orchestration_stage():
    from orchestration.stages import _risk_reward_validation

    generation = _generate_scenarios((_strong_bullish_thesis(), _weak_bullish_thesis()))
    result = _risk_reward_validation({}, {"scenario_generation": generation.to_dict()})
    assert isinstance(result, RiskRewardValidation)
    assert result.scenario_generation_id == generation.scenario_generation_id
    assert result.total_validations == 6


def test_w11_orchestration_stage_missing_data():
    from orchestration.stages import _risk_reward_validation

    result = _risk_reward_validation({}, {})
    assert isinstance(result, dict)
    assert "error" in result


def test_w11_orchestration_stage_propagates_upstream_errors():
    from orchestration.stages import _risk_reward_validation

    result = _risk_reward_validation(
        {}, {"scenario_generation": {"error": "failed"}}
    )
    assert isinstance(result, dict)
    assert "error" in result
