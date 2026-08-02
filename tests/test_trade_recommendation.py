"""Unit + integration tests for W14 Institutional Trade Recommendation."""

import json

import pytest

from decision_engine.contracts import DecisionDriver, InstitutionalDecision, RejectedAlternative
from trade_recommendation.contracts import InstitutionalTradeRecommendation
from trade_recommendation.recommender import RecommendationEngine


# =========================================================================
# Helpers
# =========================================================================


def _manual_decision(
    decision: str = "BUY",
    confidence: float = 0.8,
    rr: dict | None = None,
    drivers: tuple = (),
    preconditions: tuple = ("mechanism continues",),
    invalidation: tuple = ("real yields reverse",),
    selected_thesis_id: str = "th_1",
    selected_scenario_id: str = "sc_1",
    explanation: str = "decision=BUY; reason=test rationale",
) -> InstitutionalDecision:
    if rr is None:
        rr = {
            "status": "acceptable",
            "expected_reward": 0.3053,
            "expected_risk": 0.0625,
            "risk_reward_ratio": 0.5,
            "maximum_downside": 0.4,
            "expected_upside": 0.6,
            "tail_risk": 0.1,
            "liquidity_risk": 0.2,
            "regime_risk": 0.4,
            "volatility_impact": 0.3,
        }
    if not drivers:
        drivers = (
            DecisionDriver("institutional_confidence", confidence, 0.3, round(confidence * 0.3, 4)),
            DecisionDriver("risk_reward_quality", 0.9, 0.2, 0.18),
            DecisionDriver("evidence_quality", 0.8, 0.15, 0.12),
            DecisionDriver("counter_evidence_quality", 1.0, 0.15, 0.15),
            DecisionDriver("scenario_probability", 0.5, 0.1, 0.05),
            DecisionDriver("regime_alignment", 1.0, 0.1, 0.1),
        )
    return InstitutionalDecision(
        decision_id="dec_test",
        decision=decision,
        selected_thesis_id=selected_thesis_id,
        selected_scenario_id=selected_scenario_id,
        institutional_confidence=confidence,
        risk_reward_summary=rr,
        decision_drivers=drivers,
        rejected_alternatives=(
            RejectedAlternative(
                thesis_id="th_2",
                thesis_direction="bearish",
                composite_score=0.4,
                rejection_reason="lower composite score",
            ),
        ),
        decision_explanation=explanation,
        preconditions=preconditions,
        invalidation_conditions=invalidation,
    )


def _recommend(
    decision: InstitutionalDecision,
    instrument: str = "XAU/USD",
    reference_price: float | None = None,
) -> InstitutionalTradeRecommendation:
    return RecommendationEngine().recommend(
        decision, instrument=instrument, reference_price=reference_price
    )


def _decide_via_chain(
    theses: tuple,
    regime: str = "NORMAL_GROWTH",
) -> InstitutionalDecision:
    from confidence_engine.contracts import InstitutionalConfidence, ThesisConfidence
    from confidence_engine.engine import ConfidenceEngine
    from decision_engine.engine import DecisionEngine
    from risk_reward_validation.validator import RiskRewardValidator
    from scenario_generation.generator import ScenarioGenerator
    from thesis_construction.contracts import ThesisConstruction

    construction = ThesisConstruction(
        construction_id="tc_w13_test",
        reasoning_id="er_w13_test",
        assessment_id="cea_w13_test",
        timestamp="2026-07-31T12:00:00",
        regime=regime,
        theses=theses,
        ranked_thesis_ids=tuple(t.thesis_id for t in theses),
        total_theses=len(theses),
        primary_thesis_id=theses[0].thesis_id if theses else "",
    )
    tcs = tuple(
        ThesisConfidence(
            thesis_id=t.thesis_id,
            final_confidence=float(t.confidence_inputs.get("avg_supporting_weight", 0.0)),
            confidence_breakdown={
                "regime_alignment": (
                    1.0
                    if t.direction == "bullish" and regime == "NORMAL_GROWTH"
                    else 0.0 if t.direction != "neutral" else 0.5
                )
            },
            remaining_uncertainty=round(
                1.0 - float(t.confidence_inputs.get("avg_supporting_weight", 0.0)), 4
            ),
            reliability_category="high",
        )
        for t in theses
    )
    confidence = InstitutionalConfidence(
        confidence_id="cf_w13_test",
        construction_id=construction.construction_id,
        timestamp="2026-07-31T12:00:00",
        regime=regime,
        theses_confidence=tcs,
        ranked_thesis_ids=construction.ranked_thesis_ids,
        primary_thesis_id=construction.primary_thesis_id,
    )
    generation = ScenarioGenerator().generate(construction, confidence)
    validation = RiskRewardValidator().validate(generation)
    return DecisionEngine().decide(construction, confidence, generation, validation)


def _thesis(
    thesis_id: str = "th_1",
    direction: str = "bullish",
    confidence: float = 0.8,
) -> "InvestmentThesis":
    from thesis_construction.contracts import InvestmentThesis

    return InvestmentThesis(
        thesis_id=thesis_id,
        direction=direction,
        supporting_set_ids=("es_real_yield",),
        counter_evidence_ids=(),
        regime="NORMAL_GROWTH",
        economic_mechanism="falling real yields support gold",
        time_horizon_days=90,
        invalidating_conditions=("real yields reverse",),
        remaining_unknowns=("USD_FX",),
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


# =========================================================================
# Contract tests
# =========================================================================


class TestInstitutionalTradeRecommendation:
    def test_roundtrip(self):
        rec = _recommend(_manual_decision())
        restored = InstitutionalTradeRecommendation.from_dict(rec.to_dict())
        assert restored.recommendation_id == rec.recommendation_id
        assert restored.recommendation_action == "BUY"
        assert restored.entry_zone == rec.entry_zone
        assert restored.stop_loss == rec.stop_loss

    def test_validate_passes_for_generated(self):
        rec = _recommend(_manual_decision())
        assert not rec.validate()

    def test_validate_detects_invalid_action(self):
        rec = InstitutionalTradeRecommendation(
            recommendation_id="rec_bad",
            decision_id="dec_bad",
            recommendation_action="MAYBE",
            confidence=0.5,
            decision_summary="x",
            institutional_thesis_summary="y",
        )
        errors = rec.validate()
        assert any("recommendation_action" in e for e in errors)

    def test_validate_detects_missing_trading_fields_for_buy(self):
        rec = InstitutionalTradeRecommendation(
            recommendation_id="rec_bad",
            decision_id="dec_bad",
            recommendation_action="BUY",
            instrument="XAU/USD",
            confidence=0.8,
            risk_pct=0.0,
            expected_holding_days=0,
            decision_summary="x",
            institutional_thesis_summary="y",
            major_supporting_evidence=(),
        )
        errors = rec.validate()
        assert any("entry_zone" in e for e in errors)
        assert any("stop_loss" in e for e in errors)
        assert any("take_profit_1" in e for e in errors)
        assert any("take_profit_2" in e for e in errors)
        assert any("position_size_recommendation" in e for e in errors)
        assert any("risk_pct" in e for e in errors)
        assert any("expected_holding_days" in e for e in errors)
        assert any("major_supporting_evidence" in e for e in errors)

    def test_validate_allows_empty_trading_fields_for_no_trade(self):
        from knowledge.integrity.provenance import Provenance

        rec = InstitutionalTradeRecommendation(
            recommendation_id="rec_nt",
            decision_id="dec_nt",
            recommendation_action="NO_TRADE",
            confidence=0.0,
            decision_summary="x",
            institutional_thesis_summary="y",
            provenance_chain=(
                Provenance("2026-07-31T12:00:00", "W13 DecisionEngine", "1.0.0"),
            ),
        )
        assert not rec.validate()

    def test_validate_detects_missing_summaries(self):
        rec = InstitutionalTradeRecommendation(
            recommendation_id="rec_bad",
            decision_id="dec_bad",
            recommendation_action="HOLD",
            confidence=0.5,
        )
        errors = rec.validate()
        assert any("decision_summary" in e for e in errors)
        assert any("institutional_thesis_summary" in e for e in errors)

    def test_validate_detects_out_of_range_confidence(self):
        rec = InstitutionalTradeRecommendation(
            recommendation_id="rec_bad",
            decision_id="dec_bad",
            recommendation_action="HOLD",
            confidence=2.0,
            decision_summary="x",
            institutional_thesis_summary="y",
        )
        errors = rec.validate()
        assert any("confidence" in e for e in errors)

    def test_json_serializable(self):
        rec = _recommend(_manual_decision())
        restored = InstitutionalTradeRecommendation.from_dict(
            json.loads(json.dumps(rec.to_dict()))
        )
        assert restored.recommendation_action == "BUY"
        assert not restored.validate()


# =========================================================================
# RecommendationEngine tests
# =========================================================================


class TestRecommendationEngine:
    def test_buy_recommendation_complete(self):
        rec = _recommend(_manual_decision())
        assert rec.recommendation_action == "BUY"
        assert rec.instrument == "XAU/USD"
        assert len(rec.entry_zone) == 2
        assert rec.stop_loss
        assert rec.take_profit_1
        assert rec.take_profit_2
        assert "risk" in rec.position_size_recommendation
        assert rec.risk_pct == 1.05
        assert rec.expected_holding_days == 102
        assert rec.confidence == 0.8

    def test_buy_levels_percentage_form(self):
        rec = _recommend(_manual_decision())
        assert rec.entry_zone == ("anchor +0.0%", "anchor +0.25%")
        assert rec.stop_loss == "anchor -1.1%"
        assert rec.take_profit_1 == "anchor +1.05%"
        assert rec.take_profit_2 == "anchor +2.1%"

    def test_buy_levels_absolute_with_reference_price(self):
        rec = _recommend(_manual_decision(), reference_price=2000.0)
        assert rec.entry_zone == ("2000.00", "2005.00")
        assert rec.stop_loss == "1978.00"
        assert rec.take_profit_1 == "2021.00"
        assert rec.take_profit_2 == "2042.00"

    def test_sell_levels_mirrored(self):
        rec = _recommend(_manual_decision(decision="SELL"), reference_price=2000.0)
        assert rec.recommendation_action == "SELL"
        assert rec.entry_zone == ("1995.00", "2000.00")
        assert rec.stop_loss == "2022.00"
        assert rec.take_profit_1 == "1979.00"
        assert rec.take_profit_2 == "1958.00"

    def test_sell_uses_negative_percentage_form(self):
        rec = _recommend(_manual_decision(decision="SELL"))
        assert rec.entry_zone == ("anchor -0.25%", "anchor +0.0%")
        assert rec.stop_loss == "anchor +1.1%"
        assert rec.take_profit_1 == "anchor -1.05%"
        assert rec.take_profit_2 == "anchor -2.1%"

    def test_hold_recommendation_has_no_trading_levels(self):
        rec = _recommend(_manual_decision(decision="HOLD", confidence=0.6))
        assert rec.recommendation_action == "HOLD"
        assert rec.entry_zone == ()
        assert rec.stop_loss == ""
        assert rec.take_profit_1 == ""
        assert rec.take_profit_2 == ""
        assert rec.position_size_recommendation == ""
        assert rec.risk_pct == 0.0
        assert rec.expected_holding_days == 0

    def test_no_trade_recommendation_has_no_trading_levels(self):
        decision = _manual_decision(
            decision="NO_TRADE",
            confidence=0.0,
            selected_thesis_id="",
            selected_scenario_id="",
            preconditions=(),
            invalidation=(),
            explanation="decision=NO_TRADE; reason=no thesis clears thresholds",
        )
        rec = _recommend(decision)
        assert rec.recommendation_action == "NO_TRADE"
        assert rec.entry_zone == ()
        assert rec.stop_loss == ""
        assert rec.risk_pct == 0.0
        assert rec.expected_holding_days == 0

    def test_action_never_violates_decision(self):
        for action in ("BUY", "SELL", "HOLD", "NO_TRADE"):
            decision = _manual_decision(decision=action, confidence=0.6)
            rec = _recommend(decision)
            assert rec.recommendation_action == decision.decision

    def test_custom_instrument(self):
        rec = _recommend(_manual_decision(), instrument="XAG/USD")
        assert rec.instrument == "XAG/USD"

    def test_risk_pct_capped(self):
        decision = _manual_decision(confidence=1.0)
        rec = _recommend(decision)
        assert rec.risk_pct <= 2.0

    def test_holding_days_minimum(self):
        decision = InstitutionalDecision.from_dict(
            {
                **_manual_decision().to_dict(),
                "risk_reward_summary": {
                    **_manual_decision().risk_reward_summary,
                    "liquidity_risk": 1.0,
                },
            }
        )
        rec = _recommend(decision)
        assert rec.expected_holding_days == 30

    def test_decision_summary_populated(self):
        rec = _recommend(_manual_decision())
        assert "decision=BUY" in rec.decision_summary
        assert "confidence=0.8" in rec.decision_summary
        assert "risk_reward_status=acceptable" in rec.decision_summary

    def test_institutional_thesis_summary_preserved(self):
        decision = _manual_decision(explanation="decision=BUY; reason=test rationale")
        rec = _recommend(decision)
        assert rec.institutional_thesis_summary == decision.decision_explanation

    def test_major_supporting_evidence_from_drivers(self):
        rec = _recommend(_manual_decision())
        assert any("institutional_confidence=0.8" in e for e in rec.major_supporting_evidence)
        assert any("regime_alignment=1.0" in e for e in rec.major_supporting_evidence)

    def test_major_counter_evidence_includes_rejected(self):
        rec = _recommend(_manual_decision())
        assert any("rejected thesis th_2" in e for e in rec.major_counter_evidence)
        assert not any("counter-evidence penalty" in e for e in rec.major_counter_evidence)

    def test_major_counter_evidence_includes_penalty_when_present(self):
        drivers = (
            DecisionDriver("institutional_confidence", 0.8, 0.3, 0.24),
            DecisionDriver("risk_reward_quality", 0.9, 0.2, 0.18),
            DecisionDriver("evidence_quality", 0.8, 0.15, 0.12),
            DecisionDriver("counter_evidence_quality", 0.6, 0.15, 0.09),
            DecisionDriver("scenario_probability", 0.5, 0.1, 0.05),
            DecisionDriver("regime_alignment", 1.0, 0.1, 0.1),
        )
        rec = _recommend(_manual_decision(drivers=drivers))
        assert any("counter-evidence penalty=0.4" in e for e in rec.major_counter_evidence)

    def test_preconditions_and_invalidation_carried(self):
        rec = _recommend(_manual_decision())
        assert rec.preconditions == ("mechanism continues",)
        assert rec.invalidation_conditions == ("real yields reverse",)

    def test_monitoring_conditions_include_invalidation(self):
        rec = _recommend(_manual_decision())
        assert any("monitor: real yields reverse" in c for c in rec.monitoring_conditions)
        assert any("re-evaluate" in c for c in rec.monitoring_conditions)

    def test_provenance_chain_ends_with_w14(self):
        rec = _recommend(_manual_decision())
        assert rec.provenance_chain[-1].created_by == "W14 RecommendationEngine"
        assert len(rec.provenance_chain) >= 1

    def test_buy_via_full_chain(self):
        decision = _decide_via_chain((_thesis("th_1", "bullish"),))
        assert decision.decision == "BUY"
        rec = _recommend(decision)
        assert rec.recommendation_action == "BUY"
        assert not rec.validate()
        assert rec.metadata["selected_thesis_id"] == decision.selected_thesis_id

    def test_no_trade_via_full_chain(self):
        decision = _decide_via_chain((_thesis("th_1", "bullish", confidence=0.3),))
        assert decision.decision == "NO_TRADE"
        rec = _recommend(decision)
        assert rec.recommendation_action == "NO_TRADE"
        assert not rec.validate()

    def test_roundtrip_via_full_chain(self):
        decision = _decide_via_chain(
            (_thesis("th_1", "bullish"), _thesis("th_2", "bullish", confidence=0.6))
        )
        rec = _recommend(decision, reference_price=2400.0)
        restored = InstitutionalTradeRecommendation.from_dict(rec.to_dict())
        assert restored.recommendation_action == rec.recommendation_action
        assert restored.entry_zone == rec.entry_zone
        assert restored.instrument == "XAU/USD"
        assert not restored.validate()


# =========================================================================
# W8 -> W9 -> W12 -> W13 -> W14 integration test
# =========================================================================


def test_w8_to_w14_full_integration():
    from evidence_collection.contracts import Evidence, EvidenceCollection
    from evidence_reasoning.reasoner import EvidenceReasoner
    from counter_evidence.assessor import CounterEvidenceAssessor
    from thesis_construction.constructor import ThesisConstructor
    from confidence_engine.engine import ConfidenceEngine
    from scenario_generation.generator import ScenarioGenerator
    from risk_reward_validation.validator import RiskRewardValidator
    from decision_engine.engine import DecisionEngine

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
        collection_id="ec_w13", assessment_id="sa_w13",
        timestamp="2026-07-31T12:00:00", regime="NORMAL_GROWTH",
        items=(ev1, ev2), total_classified=2, signals_count=2,
    )

    reasoning = EvidenceReasoner().reason(collection)
    assessment = CounterEvidenceAssessor().assess(reasoning)
    construction = ThesisConstructor().construct(reasoning, assessment)
    confidence = ConfidenceEngine().evaluate(construction)
    generation = ScenarioGenerator().generate(construction, confidence)
    validation = RiskRewardValidator().validate(generation)
    decision = DecisionEngine().decide(construction, confidence, generation, validation)
    rec = RecommendationEngine().recommend(decision, instrument="XAU/USD")

    assert rec.decision_id == decision.decision_id
    assert rec.recommendation_action == decision.decision
    assert rec.confidence == decision.institutional_confidence
    assert rec.instrument == "XAU/USD"
    assert not rec.validate()

    if decision.decision in {"BUY", "SELL"}:
        assert len(rec.entry_zone) == 2
        assert rec.stop_loss
        assert rec.take_profit_1
        assert rec.take_profit_2
        assert rec.position_size_recommendation
        assert rec.risk_pct > 0.0
        assert rec.expected_holding_days > 0
        assert rec.major_supporting_evidence
        assert rec.preconditions
        assert rec.invalidation_conditions
    else:
        assert rec.entry_zone == ()
        assert rec.risk_pct == 0.0

    assert rec.decision_summary
    assert rec.institutional_thesis_summary
    assert rec.monitoring_conditions
    assert rec.provenance_chain[-1].created_by == "W14 RecommendationEngine"
    assert any(p.created_by == "W9 ConfidenceEngine" for p in rec.provenance_chain)
    assert any(p.created_by == "W13 DecisionEngine" for p in rec.provenance_chain)


# =========================================================================
# W14 orchestration stage tests
# =========================================================================


def test_w13_orchestration_stage():
    from orchestration.stages import _trade_recommendation

    decision = _manual_decision()
    result = _trade_recommendation({}, {"decision_engine": decision.to_dict()})
    assert isinstance(result, InstitutionalTradeRecommendation)
    assert result.recommendation_action == "BUY"
    assert result.instrument == "XAU/USD"


def test_w13_orchestration_stage_asset_param():
    from orchestration.stages import _trade_recommendation

    decision = _manual_decision()
    result = _trade_recommendation(
        {"asset": "XAG/USD", "reference_price": 28.5},
        {"decision_engine": decision.to_dict()},
    )
    assert result.instrument == "XAG/USD"
    assert result.stop_loss


def test_w13_orchestration_stage_missing_data():
    from orchestration.stages import _trade_recommendation

    result = _trade_recommendation({}, {})
    assert isinstance(result, dict)
    assert "error" in result


def test_w13_orchestration_stage_propagates_upstream_errors():
    from orchestration.stages import _trade_recommendation

    result = _trade_recommendation({}, {"decision_engine": {"error": "failed"}})
    assert isinstance(result, dict)
    assert "error" in result
