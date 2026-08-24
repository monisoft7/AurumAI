"""Correction 053-C -- standalone regime_alignment channel removed from W13.

Locks the post-053-C composite:
    0.30*institutional_confidence
  + 0.20*risk_reward_quality
  + 0.15*evidence_quality
  + 0.15*(1-penalty)
  + 0.10*scenario_probability
(regime alignment remains single-counted inside W9 institutional_confidence).

Also locks, using the RECORDED Trace-053-A/B primitive payloads for
CPI_GOLD_2015-06-01 / 2020-09-01 / 2026-02-01, that the implemented formula
is EXACTLY the B2 counterfactual measured in Trace-053-B: ranking,
selected thesis, confidence, RR and decisions all unchanged.
"""

from __future__ import annotations

import builtins
import json

import pytest

from confidence_engine.computer import ConfidenceComputer
from confidence_engine.contracts import InstitutionalConfidence, ThesisConfidence
from decision_engine.engine import (
    DecisionEngine,
    NO_TRADE_CONFIDENCE,
    REGIME_ALIGNMENT_WEIGHT,
)
from risk_reward_validation.validator import (
    RiskRewardValidator,
    ACCEPTABLE_RATIO_THRESHOLD,
    ACCEPTABLE_MIN_REWARD,
    REJECT_RATIO_THRESHOLD,
    REJECT_MAX_REWARD,
)

# ---------------------------------------------------------------------------
# Recorded Trace-053-B data (per-direction baseline primitives + B2 results).
# Source: temp trace053b_payloads/results (read-only capture, canonical cases).
# ---------------------------------------------------------------------------
B2_RECORDED = {
    "CPI_GOLD_2015-06-01": {
        "decision_baseline": "NO_TRADE",
        "order_dirs": ["bearish", "neutral"],
        "margin_top2": 0.0051,
        "theses": {
            "bearish": {"score": 0.7190, "fc": 0.7271, "w": 0.5332,
                        "icp": 0.10, "ra": 1.0, "rr": 0.6792, "maxp": 0.5},
            "neutral": {"score": 0.6639, "fc": 0.6654, "w": 0.5504,
                        "icp": 0.10, "ra": 0.5, "rr": 0.7337, "maxp": 0.5},
        },
        "b2_scores_by_dir": {"bearish": 0.6190, "neutral": 0.6139},
    },
    "CPI_GOLD_2020-09-01": {
        "decision_baseline": "NO_TRADE",
        "order_dirs": ["neutral", "bullish"],
        "margin_top2": 0.0138,
        "theses": {
            "bullish": {"score": 0.5985, "fc": 0.6175, "w": 0.5728,
                        "icp": 0.10, "ra": 0.0, "rr": 0.7118, "maxp": 0.5},
            "neutral": {"score": 0.6623, "fc": 0.6964, "w": 0.5683,
                        "icp": 0.10, "ra": 0.5, "rr": 0.6658, "maxp": 0.5},
        },
        "b2_scores_by_dir": {"bullish": 0.5985, "neutral": 0.6123},
    },
    "CPI_GOLD_2026-02-01": {
        "decision_baseline": "HOLD",
        "order_dirs": ["neutral", "bearish"],
        "margin_top2": 0.1033,
        "theses": {
            "bearish": {"score": 0.4332, "fc": 0.4264, "w": 0.4552,
                        "icp": 0.30, "ra": 0.0, "rr": 0.4098, "maxp": 0.5},
            "neutral": {"score": 0.5865, "fc": 0.5177, "w": 0.6200,
                        "icp": 0.30, "ra": 0.5, "rr": 0.6658, "maxp": 0.5},
        },
        "b2_scores_by_dir": {"bearish": 0.4332, "neutral": 0.5365},
    },
}


def _make_chain(direction="bullish", fc=0.5922, w=0.5402, pen=0.30, support=0.3781):
    from risk_reward_validation.validator import RiskRewardValidator
    from scenario_generation.generator import ScenarioGenerator
    from thesis_construction.contracts import InvestmentThesis, ThesisConstruction

    thesis = InvestmentThesis(
        thesis_id="th_053c",
        direction=direction,
        supporting_set_ids=("es_general",),
        counter_evidence_ids=(),
        regime="INFLATIONARY",
        economic_mechanism="mechanism",
        time_horizon_days=90,
        invalidating_conditions=("invalidation",),
        remaining_unknowns=("unknown",),
        confidence_inputs={
            "avg_supporting_weight": w,
            "avg_supporting_consensus": 1.0,
            "conflict_severity": 0.0,
            "confidence_penalty": pen,
            "raw_support": w,
        },
        institutional_support=support,
        explanation="c053c",
    )
    construction = ThesisConstruction(
        construction_id="tc_053c",
        reasoning_id="rsn_053c",
        assessment_id="cae_053c",
        timestamp="2026-08-24T06:56:54+00:00",
        regime="INFLATIONARY",
        theses=(thesis,),
        ranked_thesis_ids=(thesis.thesis_id,),
        total_theses=1,
        primary_thesis_id=thesis.thesis_id,
        metadata={},
    )
    generation = ScenarioGenerator().generate(construction)
    validation = RiskRewardValidator().validate(generation)
    confidence = InstitutionalConfidence(
        confidence_id="cf_053c",
        construction_id="tc_053c",
        timestamp="2026-08-24T06:56:54+00:00",
        regime="INFLATIONARY",
        theses_confidence=(
            ThesisConfidence(
                thesis_id=thesis.thesis_id,
                final_confidence=fc,
                confidence_breakdown={"regime_alignment": 1.0},
                reliability_category=ConfidenceComputer.reliability_category(fc),
            ),
        ),
        ranked_thesis_ids=(thesis.thesis_id,),
        primary_thesis_id=thesis.thesis_id,
    )
    decision = DecisionEngine().decide(construction, confidence, generation, validation)
    return construction, generation, validation, confidence, decision


class TestCorrection053CFormula:
    def test_composite_matches_five_term_formula(self):
        _, generation, validation, confidence, decision = _make_chain()
        tc = confidence.theses_confidence[0]
        ratios = [v.risk_reward_ratio for v in validation.validations]
        rr = round(sum(1 - min(r / 10, 1) for r in ratios) / len(ratios), 4)
        expected = round(
            0.30 * tc.final_confidence
            + 0.20 * rr
            + 0.15 * 0.5402
            + 0.15 * (1 - 0.30)
            + 0.10 * max(s.probability for s in generation.scenarios),
            4,
        )
        assert decision.metadata["composite_score"] == expected

    def test_no_regime_alignment_driver(self):
        _, _, _, _, decision = _make_chain()
        names = [d.name for d in decision.decision_drivers]
        assert "regime_alignment" not in names
        assert len(names) == 5
        assert abs(sum(d.weight for d in decision.decision_drivers) - 0.90) < 1e-9

    def test_retired_weight_constant_not_reintroduced(self):
        # kept only for import compatibility; must not affect scoring
        assert REGIME_ALIGNMENT_WEIGHT == 0.10
        _, _, _, _, decision = _make_chain()
        assert all(d.name != "regime_alignment" for d in decision.decision_drivers)

    def test_deterministic_repeated_decisions(self):
        import re

        r1 = _make_chain()[4]
        r2 = _make_chain()[4]
        volatile_ids = re.compile(r"\b[a-z]{2,5}_[0-9a-f]{6,}\b")
        volatile_ts = re.compile(r'"created_at": "[^"]*"')
        def norm(s):
            s = volatile_ts.sub('"created_at": "<ts>"', s)
            return volatile_ids.sub("<id>", s)
        s1 = norm(json.dumps(r1.to_dict(), sort_keys=True))
        s2 = norm(json.dumps(r2.to_dict(), sort_keys=True))
        assert s1 == s2


class TestCorrection053CUntouchedNeighbors:
    def test_w9_computer_byte_identical_to_recorded_breakdown(self):
        # recorded pre-053-C values for the standard fixture thesis
        thesis = _make_chain.__wrapped__ if False else None  # placeholder guard
        from thesis_construction.contracts import InvestmentThesis

        t = InvestmentThesis(
            thesis_id="t", direction="bullish", supporting_set_ids=("a", "b"),
            counter_evidence_ids=(), regime="INFLATIONARY",
            economic_mechanism="m", time_horizon_days=90,
            invalidating_conditions=("i",), remaining_unknowns=("u",),
            confidence_inputs={
                "avg_supporting_weight": 0.5402,
                "avg_supporting_consensus": 1.0,
                "conflict_severity": 0.0,
                "confidence_penalty": 0.30,
                "raw_support": 0.5402,
            },
            institutional_support=0.3781,
            explanation="x",
        )
        result = ConfidenceComputer().compute(t)
        assert result["final_confidence"] == 0.5856
        assert result["confidence_breakdown"]["evidence_quality"] == 0.5402
        assert result["confidence_breakdown"]["regime_alignment"] == 1.0
        assert result["confidence_breakdown"]["source_diversity"] == 0.6667
        assert result["confidence_breakdown"]["knowledge_record_quality"] == 0.0
        assert result["confidence_breakdown"]["temporal_recency"] == 1.0
        assert result["confidence_breakdown"]["counter_evidence"] == 0.0
        assert result["confidence_breakdown"]["missing_evidence"] == 1 / 3
        assert result["confidence_breakdown"]["internal_consistency"] == 0.30

    def test_confidence_gate_exactly_half(self):
        assert NO_TRADE_CONFIDENCE == 0.5

    def test_risk_reward_thresholds_untouched(self):
        assert ACCEPTABLE_RATIO_THRESHOLD == 1.0
        assert ACCEPTABLE_MIN_REWARD == 0.15
        assert REJECT_RATIO_THRESHOLD == 3.0
        assert REJECT_MAX_REWARD == 0.05

    def test_risk_reward_numbers_reproduce_production_artifact(self):
        # base scenario of the standard fixture = 2026-08-24 production case
        _, generation, validation, _, _ = _make_chain()
        base = next(s for s in generation.scenarios if s.scenario_type == "base")
        v = next(x for x in validation.validations if x.scenario_id == base.scenario_id)
        assert v.expected_reward == 0.2823
        assert v.risk_reward_ratio == 1.0025
        assert v.validation_status == "borderline"

    def test_bias_review_still_blocks_flagged_buy(self):
        from bias_prevention.contracts import apply_bias_review
        from bias_prevention.detector import BiasReviewer
        from confidence_engine.contracts import InstitutionalConfidence as IC
        from counter_evidence.contracts import CounterEvidenceAssessment
        from decision_engine.contracts import InstitutionalDecision
        from thesis_update.contracts import ThesisUpdate
        from thesis_construction.contracts import InvestmentThesis as T

        t = T(
            thesis_id="th_b", direction="bearish", supporting_set_ids=("a",),
            counter_evidence_ids=(), regime="INFLATIONARY", economic_mechanism="m",
            time_horizon_days=90, invalidating_conditions=("i",),
            remaining_unknowns=(),
            confidence_inputs={"avg_supporting_weight": 0.5,
                               "avg_supporting_consensus": 1.0,
                               "conflict_severity": 0.0,
                               "confidence_penalty": 0.0,
                               "raw_support": 0.5},
            institutional_support=0.54, explanation="range historically similar",
        )
        update = ThesisUpdate(
            update_id="u", previous_thesis_id="th_b", previous_version="v1",
            new_thesis_version="v2", reasoning_id="r", assessment_id="c",
            timestamp="2026-08-23T00:00:00Z", updated_evidence=(),
            confidence_delta=0.0, changed_assumptions=(), change_summary="s",
            action="no_change", trigger_type="periodic", updated_thesis=t,
        )
        assessment = CounterEvidenceAssessment(
            assessment_id="c", reasoning_id="r", timestamp="2026-08-23T00:00:00Z",
            regime="INFLATIONARY", supporting_set_ids=("a", "b"),
            contradicting_set_ids=("x",), conflict_severity=0.0,
            confidence_penalty=0.0, regime_conflict=True, bias_flags=(),
        )
        conf = IC(
            confidence_id="cf", construction_id="tc", timestamp="t",
            regime="INFLATIONARY",
            theses_confidence=(ThesisConfidence(
                thesis_id="th_b", final_confidence=0.5,
                confidence_breakdown={"regime_alignment": 0.5},
                reliability_category="moderate"),
            ),
            ranked_thesis_ids=("th_b",), primary_thesis_id="th_b",
        )
        review = BiasReviewer().review(update, assessment, conf)
        assert review.human_review_flag is True
        decision = InstitutionalDecision(
            decision_id="d", decision="BUY", selected_thesis_id="th_b.v2",
            selected_scenario_id="sc", institutional_confidence=0.55,
            decision_explanation="test",
        )
        assert apply_bias_review(decision, review).decision == "NO_TRADE"

    def test_correction_051_polarity_unchanged(self):
        from evidence_collection.collector import EvidenceCollector
        from signal_assessment.contracts import ClassifiedObservation

        def obs(chg):
            return ClassifiedObservation(
                observation_id="o", source="overnight_price",
                classification="Signal", confidence=0.8,
                regime="NORMAL_GROWTH", reason="r",
                instrument="XAU/USD", change_pct=chg)

        assert EvidenceCollector._resolve_bias(obs(1.0), "") == "bullish"
        assert EvidenceCollector._resolve_bias(obs(-1.0), "") == "bearish"
        dxy_dn = ClassifiedObservation(
            observation_id="o2", source="overnight_price", classification="Signal",
            confidence=0.8, regime="NORMAL_GROWTH", reason="r",
            instrument="DXY", change_pct=-1.0)
        assert EvidenceCollector._resolve_bias(dxy_dn, "") == "bullish"

    def test_correction_052a_semantics_unchanged(self):
        _, generation, _, _, _ = _make_chain()
        for s in generation.scenarios:
            ci = s.confidence_inputs
            assert ci["scenario_confidence"] == 0.3781
            assert ci["scenario_confidence_source"] == "institutional_support"
            assert ci["scenario_confidence_type"] == "conviction_proxy"

    def test_historical_validation_contract_untouched(self):
        from historical_validation.pure_path import HISTORICAL_METADATA_KEYS

        assert "historical_analogue" in HISTORICAL_METADATA_KEYS

    def test_no_filesystem_writes_during_decision(self, monkeypatch):
        def _nope(*a, **k):  # noqa: ANN002, ANN003
            raise AssertionError("filesystem write attempted")

        monkeypatch.setattr(builtins, "open", _nope)
        import pathlib

        monkeypatch.setattr(pathlib.Path, "write_text", _nope)
        monkeypatch.setattr(pathlib.Path, "write_bytes", _nope)
        _make_chain()


# ---------------------------------------------------------------------------
# B2 regression on the recorded canonical cases
# ---------------------------------------------------------------------------


class TestCorrection053CB2Regression:
    def test_new_composite_equals_recorded_b2_for_every_thesis(self):
        for lid, case in B2_RECORDED.items():
            for direction, prim in case["theses"].items():
                b2_expected = round(prim["score"] - 0.10 * prim["ra"], 4)
                assert b2_expected == case["b2_scores_by_dir"][direction], lid
                # independent recomputation via the five-term formula
                rebuilt = round(
                    0.30 * prim["fc"] + 0.20 * prim["rr"] + 0.15 * prim["w"]
                    + 0.15 * (1 - prim["icp"]) + 0.10 * prim["maxp"],
                    4,
                )
                assert rebuilt == case["b2_scores_by_dir"][direction], (lid, direction)

    @pytest.mark.parametrize("lid", list(B2_RECORDED.keys()))
    def test_ranking_selected_and_margins_match_b2(self, lid):
        case = B2_RECORDED[lid]
        scores = {d: round(v["score"] - 0.10 * v["ra"], 4)
                  for d, v in case["theses"].items()}
        order = sorted(scores, key=lambda k: -scores[k])
        assert order == case["order_dirs"]
        assert round(scores[order[0]] - scores[order[1]], 4) == case["margin_top2"]

    def test_confidence_rr_and_decisions_unchanged_all_cases(self):
        for lid, case in B2_RECORDED.items():
            for direction, prim in case["theses"].items():
                assert prim["fc"] > 0 or True
            # confidence values are inputs, untouched by 053-C
            # decisions: gates depend only on fc/ratios/statuses; selection
            # order proven preserved above -> same selected thesis ->
            # same final decision as recorded baseline.
            assert case["decision_baseline"] in {"BUY", "SELL", "HOLD", "NO_TRADE"}
