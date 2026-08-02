"""Tests for the W10 thesis update cycle (src/thesis_update)."""

from counter_evidence.contracts import CounterEvidenceAssessment
from evidence_reasoning.contracts import EvidenceReasoning, EvidenceSet
from thesis_construction.contracts import InvestmentThesis, ThesisConstruction
from thesis_update.contracts import ThesisUpdate
from thesis_update.updater import ThesisUpdater
from orchestration.stages import _thesis_update, _confidence_engine


def _make_set(
    set_id: str,
    weight: float,
    consensus: float,
    supporting_ids: tuple[str, ...] = ("ev_1", "ev_2"),
) -> EvidenceSet:
    return EvidenceSet(
        set_id=set_id,
        event_type="REAL_YIELD",
        bias="bullish",
        supporting_evidence_ids=supporting_ids,
        net_institutional_weight=weight,
        consensus_score=consensus,
        conflict_score=0.1,
        confidence_contribution=weight * consensus,
        explanation=f"set {set_id}",
    )


def _make_reasoning(
    sets: list[EvidenceSet],
    regime: str = "NORMAL_GROWTH",
    reasoning_id: str = "rsn-1",
) -> EvidenceReasoning:
    return EvidenceReasoning(
        reasoning_id=reasoning_id,
        collection_id="col-1",
        timestamp="2026-08-01T00:00:00Z",
        regime=regime,
        evidence_sets=tuple(sets),
        total_evidence_sets=len(sets),
        total_evidence_items=len(sets),
    )


def _make_assessment(
    contradicting_set_ids: tuple[str, ...] = (),
    penalty: float = 0.0,
    conflict_severity: float = 0.2,
    regime_conflict: bool = False,
    regime: str = "NORMAL_GROWTH",
) -> CounterEvidenceAssessment:
    return CounterEvidenceAssessment(
        assessment_id="cae-1",
        reasoning_id="rsn-1",
        timestamp="2026-08-01T00:00:00Z",
        regime=regime,
        supporting_set_ids=("set_a",),
        contradicting_set_ids=contradicting_set_ids,
        conflict_severity=conflict_severity,
        confidence_penalty=penalty,
        regime_conflict=regime_conflict,
        bias_flags=(),
    )


def _make_thesis(
    thesis_id: str = "th_test1",
    support: float = 0.72,
    supporting_set_ids: tuple[str, ...] = ("set_a",),
    counter_evidence_ids: tuple[str, ...] = (),
    regime: str = "NORMAL_GROWTH",
    conflict_severity: float = 0.2,
) -> InvestmentThesis:
    return InvestmentThesis(
        thesis_id=thesis_id,
        direction="bullish",
        supporting_set_ids=supporting_set_ids,
        counter_evidence_ids=counter_evidence_ids,
        regime=regime,
        economic_mechanism="Real yield channel",
        invalidating_conditions=("No specific invalidating conditions identified",),
        confidence_inputs={
            "avg_supporting_weight": 0.8,
            "avg_supporting_consensus": 0.9,
            "conflict_severity": conflict_severity,
            "confidence_penalty": 0.0,
            "raw_support": 0.72,
        },
        institutional_support=support,
        explanation="base thesis",
    )


def _make_construction(
    thesis: InvestmentThesis, reasoning_id: str = "rsn-1", assessment_id: str = "cae-1"
) -> ThesisConstruction:
    return ThesisConstruction(
        construction_id="construction-1",
        reasoning_id=reasoning_id,
        assessment_id=assessment_id,
        timestamp="2026-08-01T00:00:00Z",
        regime=thesis.regime,
        theses=(thesis,),
        ranked_thesis_ids=(thesis.thesis_id,),
        total_theses=1,
        primary_thesis_id=thesis.thesis_id,
    )


def test_update_versions_without_mutating_previous():
    set_a = _make_set("set_a", weight=0.8, consensus=0.9)
    reasoning = _make_reasoning([set_a])
    assessment = _make_assessment()
    thesis = _make_thesis()

    original = thesis.to_dict()
    update = ThesisUpdater().update(_make_construction(thesis), reasoning, assessment)

    assert thesis.to_dict() == original
    assert update.previous_thesis_id == "th_test1"
    assert update.previous_version == "v1"
    assert update.new_thesis_version == "v2"
    assert update.updated_thesis.thesis_id == "th_test1.v2"
    assert update.updated_thesis is not thesis


def test_second_update_chains_v3():
    set_a = _make_set("set_a", weight=0.8, consensus=0.9)
    reasoning = _make_reasoning([set_a])
    assessment = _make_assessment()
    thesis = _make_thesis()

    updater = ThesisUpdater()
    first = updater.update(_make_construction(thesis), reasoning, assessment)
    second = updater.update(
        _make_construction(first.updated_thesis), reasoning, assessment
    )

    assert second.previous_thesis_id == "th_test1.v2"
    assert second.previous_version == "v2"
    assert second.new_thesis_version == "v3"
    assert second.updated_thesis.thesis_id == "th_test1.v3"
    assert first.updated_thesis.thesis_id == "th_test1.v2"
    assert first.updated_thesis.to_dict() != second.updated_thesis.to_dict()


def test_no_change_when_delta_within_bands():
    set_a = _make_set("set_a", weight=0.8, consensus=0.9)
    reasoning = _make_reasoning([set_a])
    assessment = _make_assessment()
    thesis = _make_thesis(support=0.72)

    update = ThesisUpdater().update(_make_construction(thesis), reasoning, assessment)

    assert update.confidence_delta == 0.0
    assert update.action == "no_change"
    assert update.trigger_type == "periodic"
    assert update.changed_assumptions == ()


def test_scale_on_strong_support_improvement():
    thesis = _make_thesis(support=0.3, conflict_severity=0.2)

    better = _make_set("set_a", weight=0.8, consensus=0.9)
    reasoning = _make_reasoning([better])
    assessment = _make_assessment()

    update = ThesisUpdater().update(_make_construction(thesis), reasoning, assessment)

    assert update.confidence_delta > 0.25
    assert update.action == "scale"
    assert update.trigger_type == "threshold_crossing"
    assert "institutional support improvement" in update.changed_assumptions


def test_hedge_on_significant_confidence_drop():
    set_a = _make_set("set_a", weight=1.0, consensus=0.9)
    thesis = _make_thesis(support=0.9, conflict_severity=0.1)

    reasoning = _make_reasoning([set_a])
    assessment = _make_assessment(penalty=0.5, conflict_severity=0.5)

    update = ThesisUpdater().update(_make_construction(thesis), reasoning, assessment)

    assert update.confidence_delta == -0.45
    assert update.action == "hedge"
    assert "institutional support erosion" in update.changed_assumptions
    assert "evidence conflict escalation" in update.changed_assumptions


def test_exit_on_regime_break_with_large_drop():
    set_a = _make_set("set_a", weight=1.0, consensus=0.8)
    thesis = _make_thesis(support=0.8, regime="NORMAL_GROWTH")

    reasoning = _make_reasoning([set_a], regime="CRISIS")
    assessment = _make_assessment(penalty=0.6, regime="CRISIS")

    update = ThesisUpdater().update(_make_construction(thesis), reasoning, assessment)

    assert update.action == "exit"
    assert update.trigger_type == "regime_break"
    assert "macro regime shift" in update.changed_assumptions
    assert update.updated_thesis.regime == "CRISIS"


def test_pause_on_regime_break_with_small_drop():
    set_a = _make_set("set_a", weight=1.0, consensus=0.8)
    thesis = _make_thesis(support=0.8, regime="NORMAL_GROWTH")

    reasoning = _make_reasoning([set_a], regime="CRISIS")
    assessment = _make_assessment(penalty=0.15, regime="CRISIS")

    update = ThesisUpdater().update(_make_construction(thesis), reasoning, assessment)

    assert update.confidence_delta == -0.12
    assert update.action == "pause"
    assert update.trigger_type == "regime_break"


def test_exit_on_support_collapse():
    set_a = _make_set("set_a", weight=1.0, consensus=0.8)
    thesis = _make_thesis(support=0.8)

    reasoning = _make_reasoning([])
    assessment = _make_assessment()

    update = ThesisUpdater().update(_make_construction(thesis), reasoning, assessment)

    assert update.confidence_delta == -0.8
    assert update.action == "exit"
    assert "support below viability threshold" in update.changed_assumptions
    assert update.updated_thesis.institutional_support == 0.0


def test_counter_evidence_pressure_detected():
    set_a = _make_set("set_a", weight=0.8, consensus=0.9)
    thesis = _make_thesis(support=0.72, counter_evidence_ids=("set_x",))

    reasoning = _make_reasoning([set_a])
    assessment = _make_assessment(contradicting_set_ids=("set_x", "set_y"))

    update = ThesisUpdater().update(_make_construction(thesis), reasoning, assessment)

    assert "counter-evidence pressure" in update.changed_assumptions
    assert update.updated_thesis.counter_evidence_ids == ("set_x", "set_y")


def test_updated_thesis_carries_new_state_and_history():
    set_a = _make_set("set_a", weight=0.8, consensus=0.9, supporting_ids=("ev_a", "ev_b"))
    thesis = _make_thesis()
    base_chain_len = len(thesis.provenance_chain)

    reasoning = _make_reasoning([set_a])
    assessment = _make_assessment()

    update = ThesisUpdater().update(_make_construction(thesis), reasoning, assessment)
    updated = update.updated_thesis

    assert update.updated_evidence == ("ev_a", "ev_b")
    assert updated.institutional_support == 0.72
    assert updated.supporting_set_ids == ("set_a",)
    assert updated.regime == "NORMAL_GROWTH"
    assert "UPDATED v2" in updated.explanation
    assert updated.metadata["thesis_version"] == 2
    assert updated.metadata["previous_thesis_id"] == "th_test1"
    assert len(updated.provenance_chain) == base_chain_len + 1
    assert updated.provenance_chain[-1].created_by == "W10 ThesisUpdater"
    assert not update.validate()


def test_determinism():
    set_a = _make_set("set_a", weight=0.8, consensus=0.9)
    reasoning = _make_reasoning([set_a])
    assessment = _make_assessment()
    construction = _make_construction(_make_thesis())

    updater = ThesisUpdater()
    first = updater.update(construction, reasoning, assessment).to_dict()
    second = updater.update(construction, reasoning, assessment).to_dict()
    assert first == second


def test_roundtrip():
    set_a = _make_set("set_a", weight=0.8, consensus=0.9)
    update = ThesisUpdater().update(
        _make_construction(_make_thesis()),
        _make_reasoning([set_a]),
        _make_assessment(),
    )
    restored = ThesisUpdate.from_dict(update.to_dict())
    assert restored == update


def test_validate_flags_bad_action_and_same_thesis_id():
    update = ThesisUpdate(
        update_id="u",
        previous_thesis_id="th_a",
        previous_version="v1",
        new_thesis_version="v2",
        reasoning_id="r",
        assessment_id="a",
        timestamp="now",
        updated_evidence=(),
        confidence_delta=0.0,
        changed_assumptions=(),
        change_summary="",
        action="frobnicate",
        trigger_type="periodic",
        updated_thesis=_make_thesis(thesis_id="th_a"),
    )
    errors = update.validate()
    assert any("invalid action" in e for e in errors)
    assert any("must be a new version" in e for e in errors)


def test_stage_integration():
    set_a = _make_set("set_a", weight=0.8, consensus=0.9)
    construction = _make_construction(_make_thesis())
    reasoning = _make_reasoning([set_a])
    assessment = _make_assessment()

    result = _thesis_update(
        {},
        {
            "thesis_construction": construction.to_dict(),
            "evidence_reasoning": reasoning.to_dict(),
            "counter_evidence": assessment.to_dict(),
        },
    )
    assert isinstance(result, ThesisUpdate)
    assert result.updated_thesis.thesis_id == "th_test1.v2"


def test_stage_missing_inputs_returns_error():
    result = _thesis_update({}, {})
    assert isinstance(result, dict)
    assert "error" in result


def test_stage_no_theses_returns_error():
    construction = ThesisConstruction(
        construction_id="c",
        reasoning_id="r",
        assessment_id="a",
        timestamp="now",
        regime="NORMAL_GROWTH",
        theses=(),
        total_theses=0,
    )
    set_a = _make_set("set_a", weight=0.8, consensus=0.9)
    result = _thesis_update(
        {},
        {
            "thesis_construction": construction.to_dict(),
            "evidence_reasoning": _make_reasoning([set_a]).to_dict(),
            "counter_evidence": _make_assessment().to_dict(),
        },
    )
    assert isinstance(result, dict)
    assert "error" in result


def test_confidence_engine_prefers_updated_thesis():
    from confidence_engine.contracts import InstitutionalConfidence

    set_a = _make_set("set_a", weight=0.8, consensus=0.9)
    construction = _make_construction(_make_thesis())
    reasoning = _make_reasoning([set_a])
    assessment = _make_assessment()
    update = ThesisUpdater().update(construction, reasoning, assessment)

    result = _confidence_engine(
        {},
        {
            "thesis_construction": construction.to_dict(),
            "thesis_update": update.to_dict(),
        },
    )
    assert isinstance(result, InstitutionalConfidence)
    assert result.primary_thesis_id == "th_test1.v2"
    assert [t.thesis_id for t in result.theses_confidence] == ["th_test1.v2"]


def test_confidence_engine_falls_back_to_construction():
    from confidence_engine.contracts import InstitutionalConfidence

    construction = _make_construction(_make_thesis())
    result = _confidence_engine({}, {"thesis_construction": construction.to_dict()})
    assert isinstance(result, InstitutionalConfidence)
    assert result.primary_thesis_id == "th_test1"
