"""Correction 032: multi-thesis candidate preservation through W10.

Proves the original W8 candidate set survives ThesisUpdate: only the
previous primary is replaced by its versioned successor (th_xxx.v2),
every other candidate is preserved, and W9/W12/W13 receive and evaluate
the full candidate set.
"""

from copy import deepcopy

from confidence_engine.contracts import InstitutionalConfidence
from counter_evidence.contracts import CounterEvidenceAssessment
from decision_engine.contracts import InstitutionalDecision
from evidence_reasoning.contracts import EvidenceReasoning, EvidenceSet
from knowledge.integrity.provenance import Provenance
from orchestration.stages import (
    _confidence_engine,
    _construction_from_update,
    _decision_engine,
    _risk_reward_validation,
    _scenario_generation,
    _thesis_update,
)
from scenario_generation.contracts import ScenarioGeneration
from thesis_construction.contracts import InvestmentThesis, ThesisConstruction
from thesis_construction.constructor import ThesisConstructor
from thesis_update.contracts import ThesisUpdate

TIMESTAMP = "2026-08-19T00:00:00Z"
UPDATE_TIMESTAMP = "2026-08-19T01:00:00Z"
REGIME = "NORMAL_GROWTH"
REASONING_ID = "rsn_032"
ASSESSMENT_ID = "cea_032"

_PROV_W8 = Provenance(
    created_at=TIMESTAMP, created_by="W8 ThesisBuilder", entity_version="1.0.0"
)
_PROV_W10 = Provenance(
    created_at=UPDATE_TIMESTAMP, created_by="W10 ThesisUpdater", entity_version="1.0.0"
)


# =========================================================================
# Helpers
# =========================================================================


def _make_thesis(
    thesis_id: str,
    direction: str,
    support: float,
    supporting_set_ids: tuple[str, ...] = (),
    remaining_unknowns: tuple[str, ...] = (),
    provenance: tuple[Provenance, ...] = (),
) -> InvestmentThesis:
    return InvestmentThesis(
        thesis_id=thesis_id,
        direction=direction,
        supporting_set_ids=supporting_set_ids,
        regime=REGIME,
        economic_mechanism="test mechanism",
        time_horizon_days=90,
        invalidating_conditions=("No specific invalidating conditions identified",),
        remaining_unknowns=remaining_unknowns,
        confidence_inputs={
            "avg_supporting_weight": support,
            "avg_supporting_consensus": round(min(support + 0.1, 1.0), 4),
            "conflict_severity": 0.0,
            "confidence_penalty": 0.0,
            "raw_support": round(support * support, 4),
        },
        institutional_support=support,
        explanation=f"test {direction} thesis",
        provenance_chain=provenance,
    )


def _make_construction(
    theses: list[InvestmentThesis],
    metadata: dict | None = None,
) -> ThesisConstruction:
    ranked = sorted(theses, key=lambda t: t.institutional_support, reverse=True)
    return ThesisConstruction(
        construction_id="tc_032",
        reasoning_id=REASONING_ID,
        assessment_id=ASSESSMENT_ID,
        timestamp=TIMESTAMP,
        regime=REGIME,
        theses=tuple(theses),
        ranked_thesis_ids=tuple(t.thesis_id for t in ranked),
        total_theses=len(theses),
        primary_thesis_id=ranked[0].thesis_id if ranked else "",
        metadata=metadata or {},
    )


def _versioned(thesis: InvestmentThesis, support_delta: float = 0.02) -> InvestmentThesis:
    return InvestmentThesis(
        thesis_id=f"{thesis.thesis_id}.v2",
        direction=thesis.direction,
        supporting_set_ids=thesis.supporting_set_ids,
        counter_evidence_ids=thesis.counter_evidence_ids,
        regime=thesis.regime,
        economic_mechanism=thesis.economic_mechanism,
        time_horizon_days=thesis.time_horizon_days,
        invalidating_conditions=thesis.invalidating_conditions,
        remaining_unknowns=thesis.remaining_unknowns,
        confidence_inputs=dict(thesis.confidence_inputs),
        institutional_support=round(thesis.institutional_support + support_delta, 4),
        explanation=thesis.explanation,
        provenance_chain=tuple(thesis.provenance_chain) + (_PROV_W10,),
        metadata={"thesis_version": 2, "previous_thesis_id": thesis.thesis_id},
    )


def _make_update(previous: InvestmentThesis, updated: InvestmentThesis) -> ThesisUpdate:
    return ThesisUpdate(
        update_id=f"update-{previous.thesis_id}-v2",
        previous_thesis_id=previous.thesis_id,
        previous_version="v1",
        new_thesis_version="v2",
        reasoning_id=REASONING_ID,
        assessment_id=ASSESSMENT_ID,
        timestamp=UPDATE_TIMESTAMP,
        updated_evidence=("ev_a",),
        confidence_delta=round(updated.institutional_support - previous.institutional_support, 4),
        changed_assumptions=(),
        change_summary="test",
        action="no_change",
        trigger_type="periodic",
        updated_thesis=updated,
    )


def _make_set(set_id: str, bias: str, weight: float, consensus: float) -> EvidenceSet:
    return EvidenceSet(
        set_id=set_id,
        event_type="GENERAL",
        bias=bias,
        supporting_evidence_ids=(f"ev_{set_id}",),
        net_institutional_weight=weight,
        consensus_score=consensus,
        conflict_score=0.0,
        confidence_contribution=weight * consensus,
        explanation=f"set {set_id}",
    )


def _make_reasoning(sets: list[EvidenceSet]) -> EvidenceReasoning:
    return EvidenceReasoning(
        reasoning_id=REASONING_ID,
        collection_id="col_032",
        timestamp=TIMESTAMP,
        regime=REGIME,
        evidence_sets=tuple(sets),
        total_evidence_sets=len(sets),
        total_evidence_items=len(sets),
    )


def _make_assessment() -> CounterEvidenceAssessment:
    return CounterEvidenceAssessment(
        assessment_id=ASSESSMENT_ID,
        reasoning_id=REASONING_ID,
        timestamp=TIMESTAMP,
        regime=REGIME,
        conflict_severity=0.0,
        confidence_penalty=0.0,
        regime_conflict=False,
        bias_flags=(),
    )


def _run_stages(results: dict) -> dict:
    """Run W12 -> W9 -> W12(validation) -> W13 in runtime order on a results dict."""
    generation = _scenario_generation({}, results)
    results["scenario_generation"] = generation
    confidence = _confidence_engine({}, results)
    results["confidence_engine"] = confidence
    validation = _risk_reward_validation({}, results)
    results["risk_reward_validation"] = validation
    decision = _decision_engine({}, results)
    results["decision_engine"] = decision
    return results


# =========================================================================
# Direct splice behavior
# =========================================================================


def test_two_candidates_survive_w10():
    bullish = _make_thesis("th_bull", "bullish", 0.6, ("es_bull",))
    neutral = _make_thesis("th_neutral", "neutral", 0.4, ("es_neutral",))
    construction = _make_construction([bullish, neutral])
    updated = _versioned(bullish)

    rebuilt = _construction_from_update(_make_update(bullish, updated), construction)

    assert rebuilt.total_theses == 2
    assert [t.thesis_id for t in rebuilt.theses] == ["th_bull.v2", "th_neutral"]


def test_three_candidates_survive_w10():
    bullish = _make_thesis("th_bull", "bullish", 0.5, ("es_bull",))
    bearish = _make_thesis("th_bear", "bearish", 0.6, ("es_bear",))
    neutral = _make_thesis("th_neutral", "neutral", 0.7, ("es_neutral",))
    construction = _make_construction([bullish, bearish, neutral])
    updated = _versioned(neutral)

    rebuilt = _construction_from_update(_make_update(neutral, updated), construction)

    assert rebuilt.total_theses == 3
    assert [t.thesis_id for t in rebuilt.theses] == [
        "th_bull",
        "th_bear",
        "th_neutral.v2",
    ]


def test_only_previous_primary_replaced():
    bullish = _make_thesis("th_bull", "bullish", 0.5, ("es_bull",))
    bearish = _make_thesis("th_bear", "bearish", 0.6, ("es_bear",))
    neutral = _make_thesis("th_neutral", "neutral", 0.7, ("es_neutral",))
    construction = _make_construction([bullish, bearish, neutral])
    updated = _versioned(neutral)

    rebuilt = _construction_from_update(_make_update(neutral, updated), construction)

    assert rebuilt.theses[0] is bullish
    assert rebuilt.theses[1] is bearish
    assert rebuilt.theses[2] is updated


def test_non_primary_candidate_ids_unchanged():
    bullish = _make_thesis("th_bull", "bullish", 0.5, ("es_bull",))
    bearish = _make_thesis("th_bear", "bearish", 0.6, ("es_bear",))
    neutral = _make_thesis("th_neutral", "neutral", 0.7, ("es_neutral",))
    construction = _make_construction([bullish, bearish, neutral])

    rebuilt = _construction_from_update(
        _make_update(neutral, _versioned(neutral)), construction
    )

    non_primary = [t for t in rebuilt.theses if t.thesis_id != "th_neutral.v2"]
    assert {t.thesis_id for t in non_primary} == {"th_bull", "th_bear"}
    for t in non_primary:
        original = next(o for o in (bullish, bearish) if o.thesis_id == t.thesis_id)
        assert t.to_dict() == original.to_dict()


def test_primary_thesis_id_points_to_versioned():
    bullish = _make_thesis("th_bull", "bullish", 0.5, ("es_bull",))
    bearish = _make_thesis("th_bear", "bearish", 0.6, ("es_bear",))
    neutral = _make_thesis("th_neutral", "neutral", 0.7, ("es_neutral",))
    construction = _make_construction([bullish, bearish, neutral])
    updated = _versioned(neutral)

    rebuilt = _construction_from_update(_make_update(neutral, updated), construction)

    assert rebuilt.primary_thesis_id == "th_neutral.v2"
    assert rebuilt.primary_thesis.thesis_id == "th_neutral.v2"
    assert rebuilt.primary_thesis is updated


def test_ranked_thesis_ids_ordered_by_institutional_support():
    bullish = _make_thesis("th_bull", "bullish", 0.5, ("es_bull",))
    bearish = _make_thesis("th_bear", "bearish", 0.6, ("es_bear",))
    neutral = _make_thesis("th_neutral", "neutral", 0.7, ("es_neutral",))
    construction = _make_construction([bullish, bearish, neutral])
    updated = _versioned(neutral, support_delta=0.02)

    rebuilt = _construction_from_update(_make_update(neutral, updated), construction)

    assert rebuilt.ranked_thesis_ids == ("th_neutral.v2", "th_bear", "th_bull")
    by_id = {t.thesis_id: t.institutional_support for t in rebuilt.theses}
    supports = [by_id[rid] for rid in rebuilt.ranked_thesis_ids]
    assert supports == sorted(supports, reverse=True)


def test_total_theses_remains_n():
    theses = [
        _make_thesis("th_bull", "bullish", 0.5, ("es_bull",)),
        _make_thesis("th_bear", "bearish", 0.6, ("es_bear",)),
        _make_thesis("th_neutral", "neutral", 0.7, ("es_neutral",)),
    ]
    construction = _make_construction(theses)
    neutral = theses[2]

    rebuilt = _construction_from_update(
        _make_update(neutral, _versioned(neutral)), construction
    )

    assert rebuilt.total_theses == 3
    assert rebuilt.metadata.get("total_theses") != 1


def test_metadata_preserved():
    theses = [
        _make_thesis("th_bull", "bullish", 0.5, ("es_bull",)),
        _make_thesis("th_neutral", "neutral", 0.7, ("es_neutral",)),
    ]
    metadata = {"directions_evaluated": 2, "total_evidence_sets": 4}
    construction = _make_construction(theses, metadata=metadata)
    neutral = theses[1]

    rebuilt = _construction_from_update(
        _make_update(neutral, _versioned(neutral)), construction
    )

    assert dict(rebuilt.metadata) == metadata


def test_regime_and_ids_preserved():
    theses = [
        _make_thesis("th_bull", "bullish", 0.5, ("es_bull",)),
        _make_thesis("th_neutral", "neutral", 0.7, ("es_neutral",)),
    ]
    construction = _make_construction(theses)
    neutral = theses[1]

    rebuilt = _construction_from_update(
        _make_update(neutral, _versioned(neutral)), construction
    )

    assert rebuilt.regime == REGIME
    assert rebuilt.reasoning_id == REASONING_ID
    assert rebuilt.assessment_id == ASSESSMENT_ID


def test_non_primary_provenance_unchanged():
    bull_prov = (_PROV_W8,)
    bear_prov = (_PROV_W8,)
    bullish = _make_thesis(
        "th_bull", "bullish", 0.5, ("es_bull",), provenance=bull_prov
    )
    bearish = _make_thesis(
        "th_bear", "bearish", 0.6, ("es_bear",), provenance=bear_prov
    )
    neutral = _make_thesis("th_neutral", "neutral", 0.7, ("es_neutral",))
    construction = _make_construction([bullish, bearish, neutral])

    rebuilt = _construction_from_update(
        _make_update(neutral, _versioned(neutral)), construction
    )

    rebuilt_bull = next(t for t in rebuilt.theses if t.thesis_id == "th_bull")
    rebuilt_bear = next(t for t in rebuilt.theses if t.thesis_id == "th_bear")
    assert rebuilt_bull.provenance_chain == bull_prov
    assert rebuilt_bear.provenance_chain == bear_prov
    versioned = next(t for t in rebuilt.theses if t.thesis_id == "th_neutral.v2")
    assert versioned.provenance_chain == (_PROV_W10,)


def test_single_thesis_backward_compat():
    neutral = _make_thesis("th_neutral", "neutral", 0.7, ("es_neutral",))
    construction = _make_construction([neutral])
    updated = _versioned(neutral)
    update = _make_update(neutral, updated)

    rebuilt = _construction_from_update(update, construction)

    assert rebuilt.total_theses == 1
    assert [t.thesis_id for t in rebuilt.theses] == ["th_neutral.v2"]
    assert rebuilt.ranked_thesis_ids == ("th_neutral.v2",)
    assert rebuilt.primary_thesis_id == "th_neutral.v2"
    assert rebuilt.construction_id == update.update_id
    assert rebuilt.regime == REGIME
    assert rebuilt.reasoning_id == REASONING_ID
    assert rebuilt.assessment_id == ASSESSMENT_ID
    assert dict(rebuilt.metadata) == dict(construction.metadata)


def test_deterministic_reconstruction():
    theses = [
        _make_thesis("th_bull", "bullish", 0.5, ("es_bull",)),
        _make_thesis("th_bear", "bearish", 0.6, ("es_bear",)),
        _make_thesis("th_neutral", "neutral", 0.7, ("es_neutral",)),
    ]
    construction = _make_construction(theses)
    update = _make_update(theses[2], _versioned(theses[2]))

    first = _construction_from_update(update, construction).to_dict()
    second = _construction_from_update(update, construction).to_dict()

    assert first == second


def test_json_round_trip_and_dict_input():
    theses = [
        _make_thesis("th_bull", "bullish", 0.5, ("es_bull",)),
        _make_thesis("th_bear", "bearish", 0.6, ("es_bear",)),
        _make_thesis("th_neutral", "neutral", 0.7, ("es_neutral",)),
    ]
    construction = _make_construction(theses)
    update = _make_update(theses[2], _versioned(theses[2]))

    rebuilt = _construction_from_update(update, construction)
    restored = ThesisConstruction.from_dict(rebuilt.to_dict())

    assert restored.to_dict() == rebuilt.to_dict()

    rebuilt_from_dict = _construction_from_update(update, construction.to_dict())
    assert rebuilt_from_dict.to_dict() == rebuilt.to_dict()


def test_fallback_when_original_unavailable():
    neutral = _make_thesis("th_neutral", "neutral", 0.7, ("es_neutral",))
    update = _make_update(neutral, _versioned(neutral))

    rebuilt_none = _construction_from_update(update, None)
    rebuilt_error = _construction_from_update(update, {"error": "failed"})

    assert rebuilt_none.total_theses == 1
    assert rebuilt_none.theses[0].thesis_id == "th_neutral.v2"
    assert rebuilt_error.total_theses == 1
    assert rebuilt_error.theses[0].thesis_id == "th_neutral.v2"


# =========================================================================
# W9 / W12 / W13 propagation
# =========================================================================


def _three_candidate_inputs():
    sets = [
        _make_set("es_bull", "bullish", 0.7, 0.8),
        _make_set("es_bear", "bearish", 0.6, 0.7),
        _make_set("es_neutral", "neutral", 0.5, 0.6),
    ]
    reasoning = _make_reasoning(sets)
    assessment = _make_assessment()
    construction = ThesisConstructor().construct(reasoning, assessment)
    assert construction.total_theses == 3
    return reasoning, assessment, construction


def test_w9_w12_w13_receive_all_candidates():
    reasoning, assessment, construction = _three_candidate_inputs()
    results = {
        "evidence_reasoning": reasoning,
        "counter_evidence": assessment,
        "thesis_construction": construction,
    }
    update = _thesis_update({}, results)
    assert not isinstance(update, dict) or "error" not in update
    results["thesis_update"] = update
    outputs = _run_stages(results)

    generation: ScenarioGeneration = outputs["scenario_generation"]
    confidence: InstitutionalConfidence = outputs["confidence_engine"]
    decision: InstitutionalDecision = outputs["decision_engine"]

    primary_v2 = update.updated_thesis.thesis_id
    assert generation.total_scenarios == 9
    assert len(generation.thesis_ids) == 3
    assert primary_v2 in generation.thesis_ids
    assert all(s.thesis_id in set(generation.thesis_ids) for s in generation.scenarios)

    assert len(confidence.theses_confidence) == 3
    assert {tc.thesis_id for tc in confidence.theses_confidence} == set(
        generation.thesis_ids
    )

    assert decision.metadata["total_theses_evaluated"] == 3
    assert decision.selected_thesis_id == primary_v2
    assert decision.institutional_confidence > 0.0
    assert len(decision.rejected_alternatives) >= 2


def test_rejected_alternatives_populated_when_candidates_lose():
    reasoning, assessment, construction = _three_candidate_inputs()
    results = {
        "evidence_reasoning": reasoning,
        "counter_evidence": assessment,
        "thesis_construction": construction,
    }
    update = _thesis_update({}, results)
    results["thesis_update"] = update
    outputs = _run_stages(results)

    decision: InstitutionalDecision = outputs["decision_engine"]

    assert len(decision.rejected_alternatives) == 2
    reasons = [r.rejection_reason for r in decision.rejected_alternatives]
    assert any("lower composite score" in r for r in reasons)
    assert all(
        r.thesis_id != decision.selected_thesis_id
        for r in decision.rejected_alternatives
    )


def test_issue001_versioned_primary_remains_correct():
    sets = [_make_set("es_bull", "bullish", 0.95, 0.95)]
    reasoning = _make_reasoning(sets)
    assessment = _make_assessment()
    construction = ThesisConstructor().construct(reasoning, assessment)
    assert construction.total_theses == 2  # bullish + neutral

    results = {
        "evidence_reasoning": reasoning,
        "counter_evidence": assessment,
        "thesis_construction": construction,
    }
    update = _thesis_update({}, results)
    assert not isinstance(update, dict) or "error" not in update
    results["thesis_update"] = update
    outputs = _run_stages(results)

    decision: InstitutionalDecision = outputs["decision_engine"]
    generation: ScenarioGeneration = outputs["scenario_generation"]

    primary_v2 = update.updated_thesis.thesis_id
    assert primary_v2.endswith(".v2")
    assert decision.selected_thesis_id == primary_v2
    assert decision.institutional_confidence > 0.0
    assert decision.decision != "NO_TRADE"
    assert len(generation.thesis_ids) == 2
    assert primary_v2 in generation.thesis_ids


def test_n1_numeric_invariance():
    sets = [_make_set("es_bull", "bullish", 0.95, 0.95)]
    reasoning = _make_reasoning(sets)
    assessment = _make_assessment()

    # Path A: original single-thesis construction + W10 update (spliced).
    bullish = _make_thesis("th_bull", "bullish", 0.95, ("es_bull",))
    construction = _make_construction([bullish])
    assert construction.total_theses == 1
    results_a = {
        "evidence_reasoning": reasoning,
        "counter_evidence": assessment,
        "thesis_construction": construction,
    }
    update = _thesis_update({}, results_a)
    assert not isinstance(update, dict) or "error" not in update
    results_a["thesis_update"] = update
    outputs_a = _run_stages(results_a)

    # Path B: the equivalent collapsed single-thesis construction directly.
    versioned = update.updated_thesis
    collapsed = ThesisConstruction(
        construction_id="tc_collapsed",
        reasoning_id=REASONING_ID,
        assessment_id=ASSESSMENT_ID,
        timestamp=TIMESTAMP,
        regime=versioned.regime,
        theses=(versioned,),
        ranked_thesis_ids=(versioned.thesis_id,),
        total_theses=1,
        primary_thesis_id=versioned.thesis_id,
    )
    results_b = {
        "evidence_reasoning": reasoning,
        "counter_evidence": assessment,
        "thesis_construction": collapsed,
    }
    outputs_b = _run_stages(results_b)

    decision_a: InstitutionalDecision = outputs_a["decision_engine"]
    decision_b: InstitutionalDecision = outputs_b["decision_engine"]
    confidence_a: InstitutionalConfidence = outputs_a["confidence_engine"]
    confidence_b: InstitutionalConfidence = outputs_b["confidence_engine"]

    assert decision_a.decision == decision_b.decision
    assert decision_a.selected_thesis_id == decision_b.selected_thesis_id
    assert decision_a.institutional_confidence == decision_b.institutional_confidence
    assert decision_a.metadata["composite_score"] == decision_b.metadata["composite_score"]
    assert [d.score for d in decision_a.decision_drivers] == [
        d.score for d in decision_b.decision_drivers
    ]
    assert (
        confidence_a.theses_confidence[0].final_confidence
        == confidence_b.theses_confidence[0].final_confidence
    )
    assert outputs_a["scenario_generation"].total_scenarios == outputs_b["scenario_generation"].total_scenarios


# =========================================================================
# No candidate-generation changes
# =========================================================================


def test_no_candidate_generation_changes():
    neutral_only = _make_reasoning(
        [
            _make_set("es_a", "neutral", 0.5, 0.6),
            _make_set("es_b", "neutral", 0.4, 0.5),
        ]
    )
    assert ThesisConstructor().construct(neutral_only, _make_assessment()).total_theses == 1

    bullish_only = _make_reasoning([_make_set("es_a", "bullish", 0.5, 0.6)])
    assert ThesisConstructor().construct(bullish_only, _make_assessment()).total_theses == 2

    mixed = _make_reasoning(
        [
            _make_set("es_a", "bullish", 0.5, 0.6),
            _make_set("es_b", "bearish", 0.4, 0.5),
        ]
    )
    assert ThesisConstructor().construct(mixed, _make_assessment()).total_theses == 3