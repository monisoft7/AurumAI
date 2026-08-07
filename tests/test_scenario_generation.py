"""Unit + integration tests for W12 Institutional Scenario Generation."""

import json

import pytest

from scenario_generation.contracts import (
    PROBABILITY_EPSILON,
    SCENARIO_TYPE_LABELS,
    VALID_SCENARIO_TYPES,
    InstitutionalScenario,
    ScenarioGeneration,
)
from scenario_generation.generator import ScenarioGenerator
from thesis_construction.contracts import InvestmentThesis, ThesisConstruction


# =========================================================================
# Helpers
# =========================================================================


def _make_thesis(
    thesis_id: str = "th_1",
    direction: str = "bullish",
    regime: str = "NORMAL_GROWTH",
    economic_mechanism: str = "falling real yields support gold",
    time_horizon_days: int = 90,
    invalidating_conditions: tuple[str, ...] = ("real yields reverse",),
    remaining_unknowns: tuple[str, ...] = ("USD_FX",),
    institutional_support: float = 0.7,
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
            "avg_supporting_weight": 0.6,
            "avg_supporting_consensus": 0.8,
            "conflict_severity": 0.2,
            "confidence_penalty": 0.1,
            "raw_support": 0.48,
        },
        institutional_support=institutional_support,
        explanation="test thesis",
    )


def _make_construction(
    theses: tuple[InvestmentThesis, ...] | None = None,
    construction_id: str = "tc_w10_test",
    regime: str = "NORMAL_GROWTH",
) -> ThesisConstruction:
    if theses is None:
        theses = (_make_thesis(),)
    return ThesisConstruction(
        construction_id=construction_id,
        reasoning_id="er_w10_test",
        assessment_id="cea_w10_test",
        timestamp="2026-07-31T09:00:00",
        regime=regime,
        theses=theses,
        ranked_thesis_ids=tuple(t.thesis_id for t in theses),
        total_theses=len(theses),
        primary_thesis_id=theses[0].thesis_id if theses else "",
    )


def _generate(
    theses: tuple[InvestmentThesis, ...] | None = None,
) -> ScenarioGeneration:
    construction = _make_construction(theses)
    return ScenarioGenerator().generate(construction)


# =========================================================================
# Contract tests
# =========================================================================


class TestInstitutionalScenario:
    def test_minimal_scenario(self):
        s = InstitutionalScenario(
            scenario_id="sc_1",
            thesis_id="th_1",
            scenario_type="base",
            probability=0.5,
            expected_direction="bullish",
            time_horizon_days=90,
            regime_path=("NORMAL_GROWTH",),
        )
        assert s.scenario_id == "sc_1"
        assert s.expected_catalysts == ()

    def test_to_dict_from_dict_roundtrip(self):
        s = InstitutionalScenario(
            scenario_id="sc_rt",
            thesis_id="th_rt",
            scenario_type="bull",
            probability=0.3,
            expected_direction="bullish",
            time_horizon_days=90,
            expected_catalysts=("catalyst A",),
            assumptions=("assumption A",),
            confirmation_conditions=("confirm A",),
            invalidation_conditions=("invalidate A",),
            regime_path=("NORMAL_GROWTH", "NORMAL_GROWTH"),
            confidence_inputs={"final_confidence": 0.7},
        )
        d = s.to_dict()
        restored = InstitutionalScenario.from_dict(d)
        assert restored.scenario_id == s.scenario_id
        assert restored.scenario_type == "bull"
        assert restored.probability == 0.3
        assert restored.expected_catalysts == ("catalyst A",)
        assert restored.regime_path == ("NORMAL_GROWTH", "NORMAL_GROWTH")

    def test_validate_passes_for_valid(self):
        s = InstitutionalScenario(
            scenario_id="sc_valid",
            thesis_id="th_valid",
            scenario_type="bear",
            probability=0.2,
            expected_direction="bearish",
            time_horizon_days=30,
            regime_path=("NORMAL_GROWTH", "DEFLATIONARY_CRISIS"),
        )
        assert not s.validate()

    def test_validate_detects_bad_scenario_type(self):
        s = InstitutionalScenario(
            scenario_id="sc_bad",
            thesis_id="th_1",
            scenario_type="moon",
            probability=0.5,
            expected_direction="bullish",
            time_horizon_days=90,
            regime_path=("NORMAL_GROWTH",),
        )
        errors = s.validate()
        assert any("scenario_type" in e for e in errors)

    def test_validate_detects_bad_direction(self):
        s = InstitutionalScenario(
            scenario_id="sc_bad",
            thesis_id="th_1",
            scenario_type="base",
            probability=0.5,
            expected_direction="sideways",
            time_horizon_days=90,
            regime_path=("NORMAL_GROWTH",),
        )
        errors = s.validate()
        assert any("expected_direction" in e for e in errors)

    def test_validate_detects_out_of_range_probability(self):
        s = InstitutionalScenario(
            scenario_id="sc_bad",
            thesis_id="th_1",
            scenario_type="base",
            probability=1.5,
            expected_direction="bullish",
            time_horizon_days=90,
            regime_path=("NORMAL_GROWTH",),
        )
        errors = s.validate()
        assert any("probability" in e for e in errors)

    def test_validate_detects_empty_regime_path(self):
        s = InstitutionalScenario(
            scenario_id="sc_bad",
            thesis_id="th_1",
            scenario_type="base",
            probability=0.5,
            expected_direction="bullish",
            time_horizon_days=90,
            regime_path=(),
        )
        errors = s.validate()
        assert any("regime_path" in e for e in errors)

    def test_validate_detects_missing_ids(self):
        s = InstitutionalScenario(
            scenario_id="",
            thesis_id="",
            scenario_type="base",
            probability=0.5,
            expected_direction="bullish",
            time_horizon_days=90,
            regime_path=("NORMAL_GROWTH",),
        )
        errors = s.validate()
        assert any("scenario_id" in e for e in errors)
        assert any("thesis_id" in e for e in errors)

    def test_json_serializable(self):
        s = InstitutionalScenario(
            scenario_id="sc_json",
            thesis_id="th_json",
            scenario_type="base",
            probability=0.5,
            expected_direction="neutral",
            time_horizon_days=90,
            regime_path=("NORMAL_GROWTH",),
        )
        restored = InstitutionalScenario.from_dict(json.loads(json.dumps(s.to_dict())))
        assert restored.scenario_id == "sc_json"
        assert restored.expected_direction == "neutral"

    def test_valid_scenario_types(self):
        assert VALID_SCENARIO_TYPES == {"base", "bull", "bear"}
        assert SCENARIO_TYPE_LABELS["base"] == "Base Case"
        assert SCENARIO_TYPE_LABELS["bull"] == "Bull Case"
        assert SCENARIO_TYPE_LABELS["bear"] == "Bear Case"


class TestScenarioGeneration:
    def test_minimal_generation(self):
        g = ScenarioGeneration(
            scenario_generation_id="sg_1",
            construction_id="tc_1",
            confidence_id="cf_1",
            timestamp="2026-07-31T09:00:00",
            regime="NORMAL_GROWTH",
        )
        assert g.scenarios == ()
        assert g.total_scenarios == 0

    def test_to_dict_from_dict_roundtrip(self):
        s = InstitutionalScenario(
            scenario_id="sc_rt",
            thesis_id="th_1",
            scenario_type="base",
            probability=0.5,
            expected_direction="bullish",
            time_horizon_days=90,
            regime_path=("NORMAL_GROWTH",),
        )
        g = ScenarioGeneration(
            scenario_generation_id="sg_rt",
            construction_id="tc_rt",
            confidence_id="cf_rt",
            timestamp="2026-07-31T09:00:00",
            regime="NORMAL_GROWTH",
            scenarios=(s,),
            thesis_ids=("th_1",),
            total_scenarios=1,
            probability_consistency={"th_1": 1.0},
        )
        d = g.to_dict()
        restored = ScenarioGeneration.from_dict(d)
        assert restored.scenario_generation_id == g.scenario_generation_id
        assert len(restored.scenarios) == 1
        assert restored.scenarios[0].scenario_type == "base"
        assert restored.probability_consistency == {"th_1": 1.0}

    def test_validate_passes_for_generated(self):
        generation = _generate()
        assert not generation.validate()

    def test_validate_detects_probability_inconsistency(self):
        s = InstitutionalScenario(
            scenario_id="sc_x",
            thesis_id="th_1",
            scenario_type="base",
            probability=0.5,
            expected_direction="bullish",
            time_horizon_days=90,
            regime_path=("NORMAL_GROWTH",),
        )
        g = ScenarioGeneration(
            scenario_generation_id="sg_bad",
            construction_id="tc_1",
            confidence_id="cf_1",
            timestamp="2026-07-31T09:00:00",
            regime="NORMAL_GROWTH",
            scenarios=(s,),
            thesis_ids=("th_1",),
            total_scenarios=1,
            probability_consistency={"th_1": 0.5},
        )
        errors = g.validate()
        assert any("probability sum" in e for e in errors)

    def test_validate_detects_wrong_scenario_count(self):
        s = InstitutionalScenario(
            scenario_id="sc_x",
            thesis_id="th_1",
            scenario_type="base",
            probability=0.5,
            expected_direction="bullish",
            time_horizon_days=90,
            regime_path=("NORMAL_GROWTH",),
        )
        g = ScenarioGeneration(
            scenario_generation_id="sg_bad",
            construction_id="tc_1",
            confidence_id="cf_1",
            timestamp="2026-07-31T09:00:00",
            regime="NORMAL_GROWTH",
            scenarios=(s,),
            thesis_ids=("th_1", "th_2"),
            total_scenarios=1,
            probability_consistency={"th_1": 1.0, "th_2": 1.0},
        )
        errors = g.validate()
        assert any("3 scenarios" in e for e in errors)

    def test_scenarios_by_thesis(self):
        generation = _generate((_make_thesis("th_1"), _make_thesis("th_2", "bearish")))
        by_thesis = generation.scenarios_by_thesis
        assert set(by_thesis.keys()) == {"th_1", "th_2"}
        assert len(by_thesis["th_1"]) == 3
        assert len(by_thesis["th_2"]) == 3


# =========================================================================
# ScenarioGenerator tests
# =========================================================================


class TestScenarioGenerator:
    def test_three_scenarios_per_thesis(self):
        generation = _generate()
        assert generation.total_scenarios == 3
        types = {s.scenario_type for s in generation.scenarios}
        assert types == {"base", "bull", "bear"}
        assert generation.thesis_ids == ("th_1",)

    def test_probabilities_sum_to_one(self):
        generation = _generate()
        for tid, total in generation.probability_consistency.items():
            assert abs(total - 1.0) <= PROBABILITY_EPSILON
        assert abs(
            sum(s.probability for s in generation.scenarios) - 1.0
        ) <= PROBABILITY_EPSILON

    def test_base_probability_is_half(self):
        generation = _generate()
        for s in generation.scenarios:
            if s.scenario_type == "base":
                assert s.probability == 0.5

    def test_bullish_thesis_skews_bull(self):
        generation = _generate()
        probs = {s.scenario_type: s.probability for s in generation.scenarios}
        assert probs["bull"] > probs["bear"]
        assert probs["bear"] == 0.165
        assert probs["bull"] == 0.335

    def test_bearish_thesis_skews_bear(self):
        generation = _generate((_make_thesis("th_1", "bearish"),))
        probs = {s.scenario_type: s.probability for s in generation.scenarios}
        assert probs["bear"] > probs["bull"]
        assert probs["bear"] == 0.335
        assert probs["bull"] == 0.165

    def test_neutral_thesis_splits_tails(self):
        generation = _generate((_make_thesis("th_1", "neutral"),))
        probs = {s.scenario_type: s.probability for s in generation.scenarios}
        assert probs["bull"] == 0.25
        assert probs["bear"] == 0.25

    def test_expected_directions(self):
        thesis = _make_thesis("th_1", "bullish")
        generation = _generate((thesis,))
        by_type = {s.scenario_type: s for s in generation.scenarios}
        assert by_type["base"].expected_direction == "bullish"
        assert by_type["bull"].expected_direction == "bullish"
        assert by_type["bear"].expected_direction == "bearish"

    def test_time_horizon_inherited(self):
        generation = _generate((_make_thesis("th_1", time_horizon_days=45),))
        for s in generation.scenarios:
            assert s.time_horizon_days == 45

    def test_regime_path_base_persists(self):
        generation = _generate()
        for s in generation.scenarios:
            if s.scenario_type == "base":
                assert s.regime_path == ("NORMAL_GROWTH",)

    def test_regime_path_bull_and_bear(self):
        construction = _make_construction(regime="NORMAL_GROWTH")
        generation = ScenarioGenerator().generate(construction)
        by_type = {s.scenario_type: s for s in generation.scenarios}
        assert by_type["bull"].regime_path == ("NORMAL_GROWTH", "NORMAL_GROWTH")
        assert by_type["bear"].regime_path == ("NORMAL_GROWTH", "DEFLATIONARY_CRISIS")

    def test_regime_path_inflationary(self):
        construction = _make_construction(regime="INFLATIONARY")
        generation = ScenarioGenerator().generate(construction)
        by_type = {s.scenario_type: s for s in generation.scenarios}
        assert by_type["bull"].regime_path == ("INFLATIONARY", "NORMAL_GROWTH")
        assert by_type["bear"].regime_path == ("INFLATIONARY", "STAGFLATIONARY")

    def test_unknown_regime_falls_back(self):
        construction = _make_construction(regime="UNKNOWN_REGIME")
        generation = ScenarioGenerator().generate(construction)
        by_type = {s.scenario_type: s for s in generation.scenarios}
        assert by_type["base"].regime_path == ("UNKNOWN_REGIME",)
        assert by_type["bull"].regime_path == ("UNKNOWN_REGIME", "UNKNOWN_REGIME")
        assert by_type["bear"].regime_path == ("UNKNOWN_REGIME", "UNKNOWN_REGIME")

    def test_catalysts_are_populated_and_deterministic(self):
        thesis = _make_thesis(
            "th_1",
            economic_mechanism="falling real yields support gold",
            remaining_unknowns=("USD_FX",),
        )
        generation = _generate((thesis,))
        by_type = {s.scenario_type: s for s in generation.scenarios}
        assert len(by_type["base"].expected_catalysts) >= 1
        assert any("falling real yields" in c for c in by_type["bull"].expected_catalysts)
        assert any("USD_FX" in c for c in by_type["bear"].expected_catalysts)

        generation2 = _generate((thesis,))
        by_type2 = {s.scenario_type: s for s in generation2.scenarios}
        assert by_type2["base"].expected_catalysts == by_type["base"].expected_catalysts

    def test_assumptions_and_conditions_populated(self):
        thesis = _make_thesis("th_1", invalidating_conditions=("real yields reverse",))
        generation = _generate((thesis,))
        by_type = {s.scenario_type: s for s in generation.scenarios}
        for s in generation.scenarios:
            assert len(s.assumptions) >= 1
            assert len(s.confirmation_conditions) >= 1
            assert len(s.invalidation_conditions) >= 1
        assert "real yields reverse" in by_type["base"].invalidation_conditions
        assert "real yields reverse" in by_type["bull"].invalidation_conditions
        assert all(
            "real yields reverse" not in c
            for c in by_type["bear"].invalidation_conditions
        )

    def test_confidence_inputs_from_thesis_fallback(self):
        generation = _generate()
        for s in generation.scenarios:
            assert s.confidence_inputs["final_confidence"] == 0.6
            assert s.confidence_inputs["remaining_uncertainty"] == 0.4
            assert s.confidence_inputs["institutional_support"] == 0.7
            assert s.confidence_inputs["reliability_category"] == "moderate"

    def test_provenance_chain_ends_with_w12(self):
        generation = _generate()
        for s in generation.scenarios:
            assert len(s.provenance_chain) >= 1
            assert s.provenance_chain[-1].created_by == "W12 ScenarioGenerator"

    def test_metadata_label(self):
        generation = _generate()
        by_type = {s.scenario_type: s for s in generation.scenarios}
        assert by_type["base"].metadata["scenario_label"] == "Base Case"
        assert by_type["bull"].metadata["scenario_label"] == "Bull Case"
        assert by_type["bear"].metadata["scenario_label"] == "Bear Case"

    def test_empty_construction(self):
        construction = _make_construction(())
        generation = ScenarioGenerator().generate(construction)
        assert generation.total_scenarios == 0
        assert generation.thesis_ids == ()
        assert generation.probability_consistency == {}

    def test_missing_confidence_uses_thesis_fallback(self):
        thesis = _make_thesis("th_1")
        construction = _make_construction((thesis,))
        generation = ScenarioGenerator().generate(construction)
        assert generation.total_scenarios == 3
        assert generation.confidence_id == f"cf_fallback_{construction.construction_id}"
        for s in generation.scenarios:
            assert s.confidence_inputs["final_confidence"] == 0.6
            assert s.confidence_inputs["reliability_category"] == "moderate"

    def test_generation_roundtrip(self):
        generation = _generate(
            (_make_thesis("th_1"), _make_thesis("th_2", "bearish"))
        )
        restored = ScenarioGeneration.from_dict(generation.to_dict())
        assert restored.scenario_generation_id == generation.scenario_generation_id
        assert restored.total_scenarios == 6
        assert restored.probability_consistency == generation.probability_consistency
        assert restored.validate() == []

    def test_json_serializable(self):
        generation = _generate((_make_thesis("th_1"), _make_thesis("th_2", "neutral")))
        restored = ScenarioGeneration.from_dict(
            json.loads(json.dumps(generation.to_dict()))
        )
        assert restored.total_scenarios == 6
        assert not restored.validate()


# =========================================================================
# W8 -> W9 -> W12 integration test
# =========================================================================


def test_w8_to_w10_integration():
    from evidence_collection.contracts import Evidence, EvidenceCollection
    from evidence_reasoning.reasoner import EvidenceReasoner
    from counter_evidence.assessor import CounterEvidenceAssessor
    from thesis_construction.constructor import ThesisConstructor

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
        collection_id="ec_w8_w10", assessment_id="sa_w8_w10",
        timestamp="2026-07-31T09:00:00", regime="NORMAL_GROWTH",
        items=(ev1, ev2), total_classified=2, signals_count=2,
    )

    reasoning = EvidenceReasoner().reason(collection)
    assessment = CounterEvidenceAssessor().assess(reasoning)
    construction = ThesisConstructor().construct(reasoning, assessment)
    generation = ScenarioGenerator().generate(construction)

    assert generation.construction_id == construction.construction_id
    assert generation.confidence_id == f"cf_fallback_{construction.construction_id}"
    assert generation.regime == "NORMAL_GROWTH"
    assert generation.total_scenarios == 3 * construction.total_theses

    covered_ids = {s.thesis_id for s in generation.scenarios}
    assert covered_ids == {t.thesis_id for t in construction.theses}

    for s in generation.scenarios:
        errors = s.validate()
        assert not errors, f"Scenario validation failed: {errors}"
        assert s.expected_direction in {"bullish", "bearish", "neutral"}
        assert 0.0 <= s.probability <= 1.0
        assert len(s.regime_path) >= 1

    assert not generation.validate()
    for tid, total in generation.probability_consistency.items():
        assert abs(total - 1.0) <= PROBABILITY_EPSILON

    provenance_ok = all(
        s.provenance_chain[-1].created_by == "W12 ScenarioGenerator"
        and not any(p.created_by == "W9 ConfidenceEngine" for p in s.provenance_chain)
        for s in generation.scenarios
    )
    assert provenance_ok


# =========================================================================
# W12 orchestration stage tests
# =========================================================================


def test_w10_orchestration_stage():
    from orchestration.stages import _scenario_generation

    construction = _make_construction(
        (_make_thesis("th_1"), _make_thesis("th_2", "bearish"))
    )
    result = _scenario_generation(
        {},
        {
            "thesis_construction": construction.to_dict(),
        },
    )
    assert isinstance(result, ScenarioGeneration)
    assert result.construction_id == construction.construction_id
    assert result.confidence_id == f"cf_fallback_{construction.construction_id}"
    assert result.total_scenarios == 6


def test_scenario_generation_no_longer_consumes_confidence_engine():
    """Regression: the W12 scenario generation stage must not depend on, or
    consume, the W9 ConfidenceEngine output.  A confidence_engine result
    present in the pipeline results must be ignored entirely (the frozen DAG
    runs W12 before W9, so the read is dead code)."""
    import inspect

    from orchestration.stages import _scenario_generation

    sig = inspect.signature(ScenarioGenerator.generate)
    assert "confidence" not in sig.parameters

    construction = _make_construction(
        (_make_thesis("th_1"), _make_thesis("th_2", "bearish"))
    )
    confidence_data = _make_confidence(construction)
    result = _scenario_generation(
        {},
        {
            "thesis_construction": construction.to_dict(),
            "confidence_engine": confidence_data,
        },
    )
    assert isinstance(result, ScenarioGeneration)
    assert result.construction_id == construction.construction_id
    assert result.confidence_id == f"cf_fallback_{construction.construction_id}"
    assert result.metadata["confidence_source"] == "thesis_fallback"
    assert result.total_scenarios == 6

    for s in result.scenarios:
        thesis = next(
            t for t in construction.theses if t.thesis_id == s.thesis_id
        )
        fallback = ScenarioGenerator._fallback_confidence(thesis)
        assert s.confidence_inputs["final_confidence"] == fallback


def _make_confidence(construction) -> dict:
    from confidence_engine.contracts import (
        InstitutionalConfidence,
        ThesisConfidence,
    )

    tcs = tuple(
        ThesisConfidence(
            thesis_id=t.thesis_id,
            final_confidence=0.9,
            remaining_uncertainty=0.1,
            reliability_category="high",
        )
        for t in construction.theses
    )
    return InstitutionalConfidence(
        confidence_id="cf_should_be_ignored",
        construction_id=construction.construction_id,
        timestamp="2026-07-31T09:00:00",
        regime=construction.regime,
        theses_confidence=tcs,
        ranked_thesis_ids=construction.ranked_thesis_ids,
        primary_thesis_id=construction.primary_thesis_id,
    ).to_dict()


def test_w10_orchestration_stage_missing_data():
    from orchestration.stages import _scenario_generation

    result = _scenario_generation({}, {})
    assert isinstance(result, dict)
    assert "error" in result

    # W12 runs before W9 in the frozen v1.x DAG; missing W9 confidence must
    # degrade gracefully (PROJECT_SCOPE_V1 sec. 6.6), not error.
    construction = _make_construction()
    result = _scenario_generation(
        {}, {"thesis_construction": construction.to_dict()}
    )
    assert isinstance(result, ScenarioGeneration)
    assert result.construction_id == construction.construction_id
    assert result.total_scenarios == 3
    assert result.metadata["confidence_source"] == "thesis_fallback"
    assert result.confidence_id == f"cf_fallback_{construction.construction_id}"


def test_generate_without_confidence_uses_thesis_fallback():
    construction = _make_construction((_make_thesis("th_1"),))
    generation = ScenarioGenerator().generate(construction)

    assert generation.metadata["confidence_source"] == "thesis_fallback"
    assert generation.confidence_id == f"cf_fallback_{construction.construction_id}"
    for tid, total in generation.probability_consistency.items():
        assert abs(total - 1.0) <= PROBABILITY_EPSILON
    for s in generation.scenarios:
        assert 0.0 <= s.probability <= 1.0
        assert s.confidence_inputs["final_confidence"] == 0.6
        assert s.confidence_inputs["remaining_uncertainty"] == 0.4
        assert s.confidence_inputs["reliability_category"] == "moderate"
    assert not generation.validate()


def test_generate_without_confidence_deterministic():
    construction = _make_construction((_make_thesis("th_1"),))
    first = ScenarioGenerator().generate(construction)
    second = ScenarioGenerator().generate(construction)
    by_type_a = {s.scenario_type: s.probability for s in first.scenarios}
    by_type_b = {s.scenario_type: s.probability for s in second.scenarios}
    assert by_type_a == by_type_b


def test_w10_orchestration_stage_propagates_upstream_errors():
    from orchestration.stages import _scenario_generation

    result = _scenario_generation(
        {},
        {
            "thesis_construction": {"error": "failed"},
        },
    )
    assert isinstance(result, dict)
    assert "error" in result


def test_w10_stage_uses_versioned_thesis_from_update():
    """Issue #001 regression: when thesis_update is present, _scenario_generation
    must generate scenarios keyed to the versioned thesis_id so the decision
    stage can resolve them for the versioned thesis."""
    from thesis_update.contracts import ThesisUpdate
    from orchestration.stages import _scenario_generation

    original = _make_thesis("th_issue001", "bullish")
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

    construction = _make_construction((original,))

    update = ThesisUpdate(
        update_id="update-th_issue001-v2",
        previous_thesis_id="th_issue001",
        previous_version="v1",
        new_thesis_version="v2",
        reasoning_id="er_w10_test",
        assessment_id="cea_w10_test",
        timestamp="2026-07-31T09:00:00",
        updated_evidence=(),
        confidence_delta=0.0,
        changed_assumptions=(),
        change_summary="test",
        action="no_change",
        trigger_type="periodic",
        updated_thesis=versioned,
    )

    result = _scenario_generation(
        {},
        {
            "thesis_construction": construction.to_dict(),
            "thesis_update": update.to_dict(),
        },
    )

    assert isinstance(result, ScenarioGeneration)
    assert result.scenarios
    assert all(s.thesis_id == "th_issue001.v2" for s in result.scenarios)
    assert result.metadata["confidence_source"] == "thesis_fallback"
    assert result.confidence_id == f"cf_fallback_{result.construction_id}"
