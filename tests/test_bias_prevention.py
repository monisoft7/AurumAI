"""Tests for the W13 bias prevention workflow (src/bias_prevention)."""

from confidence_engine.contracts import InstitutionalConfidence, ThesisConfidence
from counter_evidence.contracts import CounterEvidenceAssessment
from decision_engine.contracts import InstitutionalDecision
from thesis_construction.contracts import InvestmentThesis
from thesis_update.contracts import ThesisUpdate
from bias_prevention.contracts import BiasFinding, BiasReview, apply_bias_review
from bias_prevention.detector import BiasReviewer
from orchestration.stages import _bias_prevention, _decision_engine

TIMESTAMP = "2026-08-01T00:00:00Z"
THESIS_ID = "th_test.v2"


def _make_thesis(
    thesis_id: str = THESIS_ID,
    supporting_set_ids: tuple[str, ...] = ("set_a",),
    economic_mechanism: str = "",
    invalidating: tuple[str, ...] = ("No specific invalidating conditions identified",),
    weight: float = 0.6,
    support: float = 0.48,
    time_horizon_days: int = 90,
    explanation: str = "test thesis",
) -> InvestmentThesis:
    return InvestmentThesis(
        thesis_id=thesis_id,
        direction="bullish",
        supporting_set_ids=supporting_set_ids,
        regime="NORMAL_GROWTH",
        economic_mechanism=economic_mechanism,
        time_horizon_days=time_horizon_days,
        invalidating_conditions=invalidating,
        confidence_inputs={
            "avg_supporting_weight": weight,
            "avg_supporting_consensus": 0.8,
            "conflict_severity": 0.2,
            "confidence_penalty": 0.0,
            "raw_support": support,
        },
        institutional_support=support,
        explanation=explanation,
    )


def _make_update(
    action: str = "no_change",
    trigger_type: str = "periodic",
    thesis: InvestmentThesis | None = None,
    change_summary: str = "test",
    previous_thesis_id: str = "th_test",
) -> ThesisUpdate:
    return ThesisUpdate(
        update_id="update-th_test-v2",
        previous_thesis_id=previous_thesis_id,
        previous_version="v1",
        new_thesis_version="v2",
        reasoning_id="rsn-1",
        assessment_id="cae-1",
        timestamp=TIMESTAMP,
        updated_evidence=("ev_a",),
        confidence_delta=0.0,
        changed_assumptions=(),
        change_summary=change_summary,
        action=action,
        trigger_type=trigger_type,
        updated_thesis=thesis or _make_thesis(),
    )


def _make_assessment(
    contradicting_set_ids: tuple[str, ...] = (),
    bias_flags: tuple[str, ...] = (),
    conflict_severity: float = 0.2,
    regime_conflict: bool = False,
    supporting_set_ids: tuple[str, ...] = ("set_a",),
) -> CounterEvidenceAssessment:
    return CounterEvidenceAssessment(
        assessment_id="cae-1",
        reasoning_id="rsn-1",
        timestamp=TIMESTAMP,
        regime="NORMAL_GROWTH",
        supporting_set_ids=supporting_set_ids,
        contradicting_set_ids=contradicting_set_ids,
        conflict_severity=conflict_severity,
        confidence_penalty=0.0,
        regime_conflict=regime_conflict,
        bias_flags=bias_flags,
    )


def _make_confidence(
    final_confidence: float = 0.6,
    temporal_recency: float = 1.0,
    reliability: str = "moderate",
) -> InstitutionalConfidence:
    return InstitutionalConfidence(
        confidence_id="cf-1",
        construction_id="c1",
        timestamp=TIMESTAMP,
        regime="NORMAL_GROWTH",
        theses_confidence=(
            ThesisConfidence(
                thesis_id=THESIS_ID,
                final_confidence=final_confidence,
                confidence_breakdown={
                    "regime_alignment": 1.0,
                    "temporal_recency": temporal_recency,
                },
                reliability_category=reliability,
            ),
        ),
        ranked_thesis_ids=(THESIS_ID,),
        primary_thesis_id=THESIS_ID,
    )


def _review(**kwargs):
    update = kwargs.pop("update", _make_update())
    assessment = kwargs.pop("assessment", _make_assessment())
    confidence = kwargs.pop("confidence", _make_confidence())
    return BiasReviewer().review(update, assessment, confidence)


def test_confirmation_bias_detected():
    review = _review()
    names = [f.bias_name for f in review.findings]
    assert "confirmation_bias" in names
    finding = next(f for f in review.findings if f.bias_name == "confirmation_bias")
    assert finding.severity == "medium"
    assert finding.required_action


def test_confirmation_bias_severity_boosted_by_flag():
    assessment = _make_assessment(bias_flags=("confirmation_bias",))
    review = _review(assessment=assessment)
    finding = next(f for f in review.findings if f.bias_name == "confirmation_bias")
    assert finding.severity == "high"


def test_confirmation_bias_cleared_by_disconfirming_evidence():
    thesis = _make_thesis(invalidating=("CPI MoM above 0.3% invalidates the view",))
    review = _review(update=_make_update(thesis=thesis))
    assert "confirmation_bias" not in [f.bias_name for f in review.findings]


def test_anchoring_detected_when_triggers_missing():
    review = _review()
    assert "anchoring" in [f.bias_name for f in review.findings]
    finding = next(f for f in review.findings if f.bias_name == "anchoring")
    assert finding.severity == "medium"
    assert "trigger" in finding.required_action.lower()


def test_anchoring_cleared_by_explicit_triggers():
    thesis = _make_thesis(invalidating=("Exit if real yield rises above 2.5%",))
    review = _review(update=_make_update(thesis=thesis))
    assert "anchoring" not in [f.bias_name for f in review.findings]


def test_recency_bias_detected_on_short_window_confidence():
    confidence = _make_confidence(temporal_recency=0.2)
    review = _review(confidence=confidence)
    assert "recency_bias" in [f.bias_name for f in review.findings]
    finding = next(f for f in review.findings if f.bias_name == "recency_bias")
    assert finding.severity == "low"


def test_recency_bias_cleared_by_multi_window():
    review = _review()
    assert "recency_bias" not in [f.bias_name for f in review.findings]


def test_narrative_bias_detected_when_story_outruns_evidence():
    thesis = _make_thesis(
        economic_mechanism="Real yield opportunity cost channel driving gold relative value",
        weight=0.4,
        support=0.32,
    )
    review = _review(update=_make_update(thesis=thesis))
    assert "narrative_bias" in [f.bias_name for f in review.findings]
    finding = next(f for f in review.findings if f.bias_name == "narrative_bias")
    assert finding.severity == "medium"


def test_overconfidence_detected():
    thesis = _make_thesis(weight=0.4, support=0.32)
    confidence = _make_confidence(final_confidence=0.8)
    review = _review(update=_make_update(thesis=thesis), confidence=confidence)
    assert "overconfidence" in [f.bias_name for f in review.findings]
    finding = next(f for f in review.findings if f.bias_name == "overconfidence")
    assert finding.severity == "high"


def test_overconfidence_cleared_when_evidence_supports_conviction():
    thesis = _make_thesis(weight=0.6, support=0.48)
    confidence = _make_confidence(final_confidence=0.8, reliability="high")
    review = _review(update=_make_update(thesis=thesis), confidence=confidence)
    assert "overconfidence" not in [f.bias_name for f in review.findings]


def test_single_source_bias_detected():
    thesis = _make_thesis(supporting_set_ids=("set_a",))
    review = _review(update=_make_update(thesis=thesis))
    assert "single_source_bias" in [f.bias_name for f in review.findings]


def test_single_source_cleared_by_diverse_sources():
    thesis = _make_thesis(supporting_set_ids=("set_a", "set_b", "set_c"))
    assessment = _make_assessment(supporting_set_ids=("set_a", "set_b", "set_c"))
    review = _review(update=_make_update(thesis=thesis), assessment=assessment)
    assert "single_source_bias" not in [f.bias_name for f in review.findings]


def test_regime_blindness_detected_when_regime_signal_ignored():
    assessment = _make_assessment(regime_conflict=True)
    review = _review(assessment=assessment)
    assert "regime_blindness" in [f.bias_name for f in review.findings]
    finding = next(f for f in review.findings if f.bias_name == "regime_blindness")
    assert finding.severity == "critical"


def test_regime_blindness_cleared_when_action_follows_signal():
    assessment = _make_assessment(regime_conflict=True)
    update = _make_update(action="exit", trigger_type="regime_break")
    review = _review(update=update, assessment=assessment)
    assert "regime_blindness" not in [f.bias_name for f in review.findings]


def test_clean_review():
    thesis = _make_thesis(
        supporting_set_ids=("set_a", "set_b"),
        economic_mechanism="",
        invalidating=("Exit if real yields rise above 2.5%",),
        weight=0.6,
    )
    assessment = _make_assessment(
        contradicting_set_ids=("set_x",),
        supporting_set_ids=("set_a", "set_b"),
    )
    review = _review(
        update=_make_update(thesis=thesis),
        assessment=assessment,
    )
    assert review.findings == ()
    assert review.overall_severity == "clean"
    assert review.total_confidence_impact == 0.0
    assert not review.human_review_flag
    assert not review.validate()


def test_human_review_flag_on_high_severity():
    thesis = _make_thesis(weight=0.4, support=0.32)
    confidence = _make_confidence(final_confidence=0.8)
    review = _review(update=_make_update(thesis=thesis), confidence=confidence)
    assert review.human_review_flag is True
    assert review.overall_severity == "high"


def test_severity_and_impact_aggregation():
    thesis = _make_thesis(
        economic_mechanism="Inflation premium channel",
        weight=0.4,
        support=0.32,
    )
    confidence = _make_confidence(final_confidence=0.8)
    assessment = _make_assessment(regime_conflict=True)
    review = _review(
        update=_make_update(thesis=thesis),
        assessment=assessment,
        confidence=confidence,
    )
    assert review.overall_severity == "critical"
    assert review.total_confidence_impact > 0.25
    assert len(review.required_actions) == len(review.findings)


def test_apply_bias_review_gates_directional_decision():
    decision = InstitutionalDecision(
        decision_id="dec-1",
        decision="BUY",
        selected_thesis_id=THESIS_ID,
        selected_scenario_id="sc-1",
        institutional_confidence=0.6,
        decision_explanation="test decision",
        preconditions=("p",),
        invalidation_conditions=("i",),
    )
    thesis = _make_thesis(weight=0.4, support=0.32)
    confidence = _make_confidence(final_confidence=0.8)
    review = _review(update=_make_update(thesis=thesis), confidence=confidence)

    gated = apply_bias_review(decision, review)
    assert gated.decision == "NO_TRADE"
    assert "BLOCKED BY BIAS PREVENTION" in gated.decision_explanation
    assert gated.metadata["bias_review"]["review_id"] == review.review_id
    assert gated.metadata["bias_review"]["human_review_flag"] is True


def test_apply_bias_review_does_not_gate_clean_review():
    decision = InstitutionalDecision(
        decision_id="dec-1",
        decision="BUY",
        selected_thesis_id=THESIS_ID,
        selected_scenario_id="sc-1",
        institutional_confidence=0.6,
        decision_explanation="test decision",
        preconditions=("p",),
        invalidation_conditions=("i",),
    )
    thesis = _make_thesis(
        supporting_set_ids=("set_a", "set_b"),
        invalidating=("Exit if real yields rise above 2.5%",),
    )
    assessment = _make_assessment(
        contradicting_set_ids=("set_x",),
        supporting_set_ids=("set_a", "set_b"),
    )
    review = _review(
        update=_make_update(thesis=thesis),
        assessment=assessment,
    )
    assert review.overall_severity == "clean"
    result = apply_bias_review(decision, review)
    assert result.decision == "BUY"
    assert "bias_review" in result.metadata
    assert result.metadata["bias_review"]["human_review_flag"] is False


def test_apply_bias_review_annotates_existing_no_trade():
    decision = InstitutionalDecision(
        decision_id="dec-1",
        decision="NO_TRADE",
        selected_thesis_id="",
        selected_scenario_id="",
        institutional_confidence=0.0,
        decision_explanation="no eligible thesis",
    )
    thesis = _make_thesis(weight=0.4, support=0.32)
    confidence = _make_confidence(final_confidence=0.8)
    review = _review(update=_make_update(thesis=thesis), confidence=confidence)
    result = apply_bias_review(decision, review)
    assert result.decision == "NO_TRADE"
    assert "BIAS REVIEW" in result.decision_explanation


def test_determinism():
    first = _review().to_dict()
    second = _review().to_dict()
    assert first == second


def test_roundtrip():
    review = _review()
    restored = BiasReview.from_dict(review.to_dict())
    assert restored == review


def test_validate_flags_invalid_severity():
    review = BiasReview(
        review_id="b",
        thesis_id="t",
        update_id="u",
        confidence_id="c",
        assessment_id="a",
        timestamp="now",
        regime="R",
        findings=(
            BiasFinding(
                bias_name="x",
                severity="extreme",
                evidence="e",
                required_action="a",
                confidence_impact=0.1,
            ),
        ),
        overall_severity="extreme",
        total_confidence_impact=0.1,
        required_actions=("a",),
    )
    errors = review.validate()
    assert any("invalid severity" in e for e in errors)
    assert any("invalid overall_severity" in e for e in errors)


def test_stage_integration():
    result = _bias_prevention(
        {},
        {
            "thesis_update": _make_update().to_dict(),
            "counter_evidence": _make_assessment().to_dict(),
            "confidence_engine": _make_confidence().to_dict(),
        },
    )
    assert isinstance(result, BiasReview)
    assert result.review_id == "bias-th_test.v2"


def test_stage_missing_inputs_returns_error():
    result = _bias_prevention({}, {})
    assert isinstance(result, dict)
    assert "error" in result


def _decision_stage_results(bias_review: bool) -> dict:
    from scenario_generation.contracts import InstitutionalScenario, ScenarioGeneration
    from risk_reward_validation.contracts import (
        InstitutionalRiskValidation,
        RiskRewardValidation,
    )
    from thesis_construction.contracts import ThesisConstruction

    thesis = _make_thesis()
    construction = ThesisConstruction(
        construction_id="c1",
        reasoning_id="rsn-1",
        assessment_id="cae-1",
        timestamp=TIMESTAMP,
        regime="NORMAL_GROWTH",
        theses=(thesis,),
        ranked_thesis_ids=(thesis.thesis_id,),
        total_theses=1,
        primary_thesis_id=thesis.thesis_id,
    )
    scenario = InstitutionalScenario(
        scenario_id="sc-1",
        thesis_id=thesis.thesis_id,
        scenario_type="base",
        probability=0.6,
        expected_direction="bullish",
        time_horizon_days=90,
        confirmation_conditions=("p",),
        invalidation_conditions=("i",),
    )
    generation = ScenarioGeneration(
        scenario_generation_id="sg-1",
        construction_id="c1",
        confidence_id="cf-1",
        timestamp=TIMESTAMP,
        regime="NORMAL_GROWTH",
        scenarios=(scenario,),
        thesis_ids=(thesis.thesis_id,),
        total_scenarios=1,
    )
    validation_item = InstitutionalRiskValidation(
        validation_id="v-1",
        scenario_id="sc-1",
        thesis_id=thesis.thesis_id,
        validation_status="acceptable",
        expected_reward=2.0,
        expected_risk=1.0,
        risk_reward_ratio=2.0,
        maximum_downside=1.0,
        expected_upside=2.0,
        volatility_impact=0.3,
        regime_risk=0.2,
        liquidity_risk=0.1,
        tail_risk=0.2,
    )
    validation = RiskRewardValidation(
        validation_id="v-1",
        scenario_generation_id="sg-1",
        timestamp=TIMESTAMP,
        regime="NORMAL_GROWTH",
        validations=(validation_item,),
        scenario_ids=("sc-1",),
        total_validations=1,
    )
    results = {
        "thesis_construction": construction.to_dict(),
        "confidence_engine": _make_confidence().to_dict(),
        "scenario_generation": generation.to_dict(),
        "risk_reward_validation": validation.to_dict(),
    }
    if bias_review:
        results["bias_prevention"] = _review().to_dict()
    return results


def test_decision_stage_consumes_clean_bias_review():
    thesis = _make_thesis(
        supporting_set_ids=("set_a", "set_b"),
        invalidating=("Exit if real yields rise above 2.5%",),
    )
    assessment = _make_assessment(
        contradicting_set_ids=("set_x",),
        supporting_set_ids=("set_a", "set_b"),
    )
    results = _decision_stage_results(bias_review=True)
    results["bias_prevention"] = _bias_prevention(
        {},
        {
            "thesis_update": _make_update(thesis=thesis).to_dict(),
            "counter_evidence": assessment.to_dict(),
            "confidence_engine": _make_confidence().to_dict(),
        },
    ).to_dict()
    result = _decision_engine({}, results)
    assert isinstance(result, InstitutionalDecision)
    assert result.decision == "BUY"
    assert "bias_review" in result.metadata
    assert result.metadata["bias_review"]["overall_severity"] == "clean"
    assert result.metadata["bias_review"]["human_review_flag"] is False


def test_decision_stage_backward_compatible_without_bias_review():
    result = _decision_engine({}, _decision_stage_results(bias_review=False))
    assert isinstance(result, InstitutionalDecision)
    assert result.decision == "BUY"
    assert "bias_review" not in result.metadata


def test_decision_stage_gates_on_human_review():
    thesis = _make_thesis(weight=0.4, support=0.32)
    confidence = _make_confidence(final_confidence=0.8)
    results = _decision_stage_results(bias_review=True)
    results["thesis_construction"] = None
    results["bias_prevention"] = _bias_prevention(
        {},
        {
            "thesis_update": _make_update(thesis=thesis).to_dict(),
            "counter_evidence": _make_assessment().to_dict(),
            "confidence_engine": confidence.to_dict(),
        },
    ).to_dict()
    from thesis_construction.contracts import ThesisConstruction

    results["thesis_construction"] = ThesisConstruction(
        construction_id="c1",
        reasoning_id="rsn-1",
        assessment_id="cae-1",
        timestamp=TIMESTAMP,
        regime="NORMAL_GROWTH",
        theses=(thesis,),
        ranked_thesis_ids=(thesis.thesis_id,),
        total_theses=1,
        primary_thesis_id=thesis.thesis_id,
    ).to_dict()
    result = _decision_engine({}, results)
    assert result.decision == "NO_TRADE"
    assert "BLOCKED BY BIAS PREVENTION" in result.decision_explanation


def test_base_rate_neglect_detected():
    thesis = _make_thesis(explanation="gold will rise as real yields fall")
    review = _review(update=_make_update(thesis=thesis))
    names = [f.bias_name for f in review.findings]
    assert "base_rate_neglect" in names
    finding = next(f for f in review.findings if f.bias_name == "base_rate_neglect")
    assert finding.severity == "medium"


def test_base_rate_neglect_cleared_by_historical_reference():
    thesis = _make_thesis(
        explanation="gold will rise as it did historically after real yield peaks"
    )
    review = _review(update=_make_update(thesis=thesis))
    assert "base_rate_neglect" not in [f.bias_name for f in review.findings]


def test_attribution_error_detected():
    update = _make_update(change_summary="prior view returned strong profits")
    review = _review(update=update)
    assert "attribution_error" in [f.bias_name for f in review.findings]
    finding = next(f for f in review.findings if f.bias_name == "attribution_error")
    assert finding.severity == "low"


def test_attribution_error_cleared_by_journal_reference():
    update = _make_update(
        change_summary="prior thesis reviewed in the decision journal; return was strong"
    )
    review = _review(update=update)
    assert "attribution_error" not in [f.bias_name for f in review.findings]


def test_attribution_error_cleared_without_history():
    update = _make_update(
        change_summary="prior view returned strong profits",
        previous_thesis_id="",
    )
    review = _review(update=update)
    assert "attribution_error" not in [f.bias_name for f in review.findings]


def test_groupthink_detected_when_no_variant_view():
    review = _review()
    assert "groupthink" in [f.bias_name for f in review.findings]
    finding = next(f for f in review.findings if f.bias_name == "groupthink")
    assert finding.severity == "medium"


def test_groupthink_cleared_by_variant_view():
    assessment = _make_assessment(contradicting_set_ids=("set_x",))
    review = _review(assessment=assessment)
    assert "groupthink" not in [f.bias_name for f in review.findings]


def test_false_precision_detected_on_point_estimate():
    thesis = _make_thesis(explanation="gold target 2,450.50 with upside 5.2")
    review = _review(update=_make_update(thesis=thesis))
    assert "false_precision" in [f.bias_name for f in review.findings]
    finding = next(f for f in review.findings if f.bias_name == "false_precision")
    assert finding.severity == "low"


def test_false_precision_cleared_by_range():
    thesis = _make_thesis(explanation="gold target 2,450.50 range 2,400-2,500")
    review = _review(update=_make_update(thesis=thesis))
    assert "false_precision" not in [f.bias_name for f in review.findings]


def test_this_time_is_different_detected():
    update = _make_update(
        change_summary="this time is different: unprecedented Fed policy",
        thesis=_make_thesis(explanation="structural break in the gold market"),
    )
    review = _review(update=update)
    assert "this_time_is_different" in [f.bias_name for f in review.findings]
    finding = next(
        f for f in review.findings if f.bias_name == "this_time_is_different"
    )
    assert finding.severity == "medium"


def test_this_time_is_different_cleared_by_analogues():
    update = _make_update(
        change_summary="this time is different but analogous to 2022",
    )
    review = _review(update=update)
    assert "this_time_is_different" not in [f.bias_name for f in review.findings]
