"""Correction 053-C -- standalone regime_alignment channel removed from W13.

Locks the post-hardening composite (Final Hardening Group A):
    0.50*institutional_confidence
  + (1/3)*risk_reward_quality
  + (1/6)*scenario_probability
(regime alignment remains single-counted inside W9 institutional_confidence).

Also locks, using the RECORDED Trace-053-A/B primitive payloads for
CPI_GOLD_2015-06-01 / 2020-09-01 / 2026-02-01, that the implemented
composite reproduces the recorded hardening counterfactuals (independent
pinned values) and preserves the B2 Trace-053-B outcomes: ranking,
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
    def test_composite_matches_three_term_formula(self):
        # Final Hardening (Group A): the five-term composite collapsed to
        # three single-counted terms (confidence, rr_score, max_probability)
        # with renormalized weights 0.50 / 1/3 / 1/6.
        _, generation, validation, confidence, decision = _make_chain()
        tc = confidence.theses_confidence[0]
        ratios = [v.risk_reward_ratio for v in validation.validations]
        rr = round(sum(1 - min(r / 10, 1) for r in ratios) / len(ratios), 4)
        expected = round(
            0.50 * tc.final_confidence
            + (1.0 / 3.0) * rr
            + (1.0 / 6.0) * max(s.probability for s in generation.scenarios),
            4,
        )
        assert decision.metadata["composite_score"] == expected

    def test_no_regime_alignment_driver(self):
        _, _, _, _, decision = _make_chain()
        names = [d.name for d in decision.decision_drivers]
        assert "regime_alignment" not in names
        assert len(names) == 3
        assert abs(sum(d.weight for d in decision.decision_drivers) - 1.0) < 1e-9

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
        # Re-pinned for the Run-003 repair weights (regime channel removed;
        # 0.35/0.35/0.20/0.10; saturation-free diversity/provenance):
        # ps = 0.35*0.5402 + 0.35*1.0 + 0.20*(2/5) + 0.10*0 = 0.6191;
        # penalties = 0.25*(1/3) + 0.40*0.30 = 0.2033 -> 0.6191*0.7967.
        # Previous pins: 0.5856 (pre-Group A), 0.5673 (post-Group A).
        assert result["final_confidence"] == 0.4932
        assert result["confidence_breakdown"]["evidence_quality"] == 0.5402
        # Run-003 repair (Phase 7): the regime_alignment channel is removed.
        assert "regime_alignment" not in result["confidence_breakdown"]
        # Run-003 repair (Phase 5): saturation-free transforms:
        # diversity 2/(2+3) = 0.4, provenance 0/(0+2) = 0.0.
        assert result["confidence_breakdown"]["source_diversity"] == 0.4
        assert result["confidence_breakdown"]["knowledge_record_quality"] == 0.0
        assert "temporal_recency" not in result["confidence_breakdown"]
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
        from bias_prevention.contracts import (
            BiasFinding,
            BiasReview,
            SEVERITY_IMPACT,
            apply_bias_review,
        )
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
        # Run-003 repair (Phase 7): regime_blindness is neutralized, so the
        # D-04 gate below is exercised with a directly-constructed review
        # carrying a human-review-severity finding.
        review = BiasReview(
            review_id="bias-th_b",
            thesis_id="th_b",
            update_id="u",
            confidence_id="cf",
            assessment_id="c",
            timestamp="2026-08-23T00:00:00Z",
            regime="INFLATIONARY",
            findings=(
                BiasFinding(
                    bias_name="single_source_bias",
                    severity="high",
                    evidence="only a single supporting evidence source informs the thesis",
                    required_action="Diversify evidence sources before committing capital",
                    confidence_impact=SEVERITY_IMPACT["high"],
                ),
            ),
            overall_severity="high",
            total_confidence_impact=SEVERITY_IMPACT["high"],
            required_actions=("Diversify evidence sources before committing capital",),
            human_review_flag=True,
        )
        assert review.human_review_flag is True
        decision = InstitutionalDecision(
            decision_id="d", decision="BUY",
            # Final Hardening (Group A, D-04): the gate applies when the
            # reviewed thesis IS the selected thesis.
            selected_thesis_id=review.thesis_id,
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
            # Run-003 (Phase 4/11): the label carries the actual source
            # ("thesis_support" for penalty-adjusted institutional support).
            assert ci["scenario_confidence_source"] == "thesis_support"
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

# Recorded post-hardening counterfactuals (Final Hardening Group A): the
# three-term composite (0.50*fc + 1/3*rr + 1/6*maxp) applied to the SAME
# Trace-053-B primitives.  These are independent pinned expected values --
# NOT computed by the code under test -- so any change to the composite
# arithmetic, the candidate ranking, or the top-2 margin fails here instead
# of silently re-baselining.
HARDENING_RECORDED = {
    "CPI_GOLD_2015-06-01": {
        "scores": {"bearish": 0.6733, "neutral": 0.6606},
        "margin_top2": 0.0127,
    },
    "CPI_GOLD_2020-09-01": {
        "scores": {"bullish": 0.6294, "neutral": 0.6535},
        "margin_top2": 0.0241,
    },
    "CPI_GOLD_2026-02-01": {
        "scores": {"bearish": 0.4331, "neutral": 0.5641},
        "margin_top2": 0.1310,
    },
}

# Best-scenario risk_reward_ratio per (case, direction) for the decision-gate
# reconstruction: the NO_TRADE baselines must fail the W13 RR gate
# (ratio > NO_TRADE_RR_RATIO = 2.0), the HOLD baseline must clear it.  The
# remaining scenarios carry ratios whose mean reproduces the recorded rr
# score exactly (rr_score = mean(1 - ratio/10), rounded to 4dp).
BEST_SCENARIO_RR_RATIO = {
    # NO_TRADE baselines: every scenario shares the uniform recorded-mean
    # ratio 10*(1-rr), which already fails the W13 RR gate (> 2.0).
    ("CPI_GOLD_2015-06-01", "bearish"): 3.208,
    ("CPI_GOLD_2015-06-01", "neutral"): 2.663,
    ("CPI_GOLD_2020-09-01", "bullish"): 2.882,
    ("CPI_GOLD_2020-09-01", "neutral"): 3.342,
    ("CPI_GOLD_2026-02-01", "bearish"): 5.902,
    # HOLD baseline: the selected (base) scenario must clear the RR gate;
    # the two off-path scenarios carry the rest of the recorded mean.
    ("CPI_GOLD_2026-02-01", "neutral"): 1.5,
}


def _make_b2_case_chain(lid: str, case: dict):
    """Reconstruct one recorded Trace-053-B canonical case through REAL
    W11/W12/W13 objects.

    Each thesis carries its recorded primitives verbatim: final_confidence
    (fc), scenario probabilities at the recorded maxp, and validations whose
    mean rr component reproduces the recorded rr score
    (rr_score = round(mean(1 - ratio/10), 4)).  No recomputed shortcut is
    used -- DecisionEngine.decide() consumes fully constructed contracts, so
    the composite arithmetic, ranking and decision gates exercised are the
    production code paths.
    """
    from confidence_engine.computer import ConfidenceComputer
    from risk_reward_validation.contracts import (
        InstitutionalRiskValidation,
        RiskRewardValidation,
    )
    from scenario_generation.contracts import (
        InstitutionalScenario,
        ScenarioGeneration,
    )
    from thesis_construction.contracts import InvestmentThesis, ThesisConstruction

    theses, tcs, scenarios, validations = [], [], [], []
    for direction in case["order_dirs"]:
        prim = case["theses"][direction]
        thesis = InvestmentThesis(
            thesis_id=f"th_{lid}_{direction}",
            direction=direction,
            supporting_set_ids=("es_general",),
            counter_evidence_ids=(),
            regime="INFLATIONARY",
            economic_mechanism="mechanism",
            time_horizon_days=90,
            invalidating_conditions=("invalidation",),
            remaining_unknowns=("unknown",),
            confidence_inputs={
                "avg_supporting_weight": prim["w"],
                "avg_supporting_consensus": 1.0,
                "conflict_severity": 0.0,
                "confidence_penalty": prim["icp"],
                "raw_support": prim["w"],
            },
            institutional_support=0.3781,
            explanation="c053c-b2",
        )
        theses.append(thesis)
        tcs.append(ThesisConfidence(
            thesis_id=thesis.thesis_id,
            final_confidence=prim["fc"],
            confidence_breakdown={"regime_alignment": prim["ra"]},
            reliability_category=ConfidenceComputer.reliability_category(prim["fc"]),
        ))
        if (lid, direction) == ("CPI_GOLD_2026-02-01", "neutral"):
            # HOLD baseline: base scenario clears the RR gate, the two
            # off-path scenarios carry the rest of the recorded mean.
            ratios = {"base": 1.5, "bull": 4.263, "bear": 4.263}
        else:
            uniform = round(10.0 * (1.0 - prim["rr"]), 6)
            ratios = {"base": uniform, "bull": uniform, "bear": uniform}
        base_ratio = BEST_SCENARIO_RR_RATIO[(lid, direction)]
        for scenario_type in ("base", "bull", "bear"):
            sid = f"sc_{lid}_{direction}_{scenario_type}"
            scenarios.append(InstitutionalScenario(
                scenario_id=sid,
                thesis_id=thesis.thesis_id,
                scenario_type=scenario_type,
                probability=prim["maxp"],
                expected_direction=direction,
                time_horizon_days=90,
                regime_path=("INFLATIONARY",),
                confidence_inputs={
                    "scenario_confidence": 0.3781,
                    "scenario_confidence_source": "institutional_support",
                    "scenario_confidence_type": "conviction_proxy",
                },
            ))
            validations.append(InstitutionalRiskValidation(
                validation_id=f"vv_{sid}",
                scenario_id=sid,
                thesis_id=thesis.thesis_id,
                validation_status="borderline",
                expected_reward=0.2,
                expected_risk=0.1,
                risk_reward_ratio=base_ratio
                if scenario_type == "base" else ratios[scenario_type],
                maximum_downside=0.1,
                expected_upside=0.3,
                volatility_impact=0.1,
                regime_risk=0.1,
                liquidity_risk=0.1,
                tail_risk=0.1,
                validation_explanation="b2 counterfactual reconstruction",
            ))

    construction = ThesisConstruction(
        construction_id=f"tc_{lid}",
        reasoning_id="rsn_053c",
        assessment_id="cae_053c",
        timestamp="2026-08-24T06:56:54+00:00",
        regime="INFLATIONARY",
        theses=tuple(theses),
        ranked_thesis_ids=tuple(t.thesis_id for t in theses),
        total_theses=len(theses),
        primary_thesis_id=theses[0].thesis_id,
        metadata={},
    )
    confidence = InstitutionalConfidence(
        confidence_id=f"cf_{lid}",
        construction_id=construction.construction_id,
        timestamp="2026-08-24T06:56:54+00:00",
        regime="INFLATIONARY",
        theses_confidence=tuple(tcs),
        ranked_thesis_ids=tuple(t.thesis_id for t in theses),
        primary_thesis_id=theses[0].thesis_id,
    )
    generation = ScenarioGeneration(
        scenario_generation_id=f"sg_{lid}",
        construction_id=construction.construction_id,
        confidence_id=confidence.confidence_id,
        timestamp="2026-08-24T06:56:54+00:00",
        regime="INFLATIONARY",
        scenarios=tuple(scenarios),
        thesis_ids=tuple(t.thesis_id for t in theses),
        total_scenarios=len(scenarios),
    )
    validation = RiskRewardValidation(
        validation_id=f"rrv_{lid}",
        scenario_generation_id=generation.scenario_generation_id,
        timestamp="2026-08-24T06:56:54+00:00",
        regime="INFLATIONARY",
        validations=tuple(validations),
        scenario_ids=tuple(s.scenario_id for s in scenarios),
        total_validations=len(validations),
    )
    return DecisionEngine().decide(construction, confidence, generation, validation)


class TestCorrection053CB2Regression:
    # -- recorded B2 counterfactual integrity (Trace-053-B data) ----------

    def test_recorded_b2_counterfactual_identity_intact(self):
        # B2 removed exactly the +0.10*regime_alignment term from the
        # recorded six-term score: b2 == score - 0.10*ra for EVERY recorded
        # thesis.  Fails if any recorded B2 regression value is tampered with.
        for lid, case in B2_RECORDED.items():
            for direction, prim in case["theses"].items():
                b2 = round(prim["score"] - 0.10 * prim["ra"], 4)
                assert b2 == case["b2_scores_by_dir"][direction], (lid, direction)

    @pytest.mark.parametrize("lid", list(B2_RECORDED.keys()))
    def test_recorded_b2_ranking_and_margin_intact(self, lid):
        # The recorded B2 counterfactual itself must keep its recorded
        # ranking and exact top-2 margin.
        case = B2_RECORDED[lid]
        scores = case["b2_scores_by_dir"]
        order = sorted(scores, key=lambda k: -scores[k])
        assert order == case["order_dirs"], lid
        margin = round(scores[order[0]] - scores[order[1]], 4)
        assert margin == case["margin_top2"], lid

    # -- hardening composite regression through the real engine -----------

    @pytest.mark.parametrize("lid", list(B2_RECORDED.keys()))
    def test_hardening_composite_matches_recorded_counterfactual(self, lid):
        # The implemented three-term composite applied to the recorded
        # primitives must equal the independently pinned hardening
        # counterfactuals for BOTH theses (selected + rejected).
        case = B2_RECORDED[lid]
        expected = HARDENING_RECORDED[lid]
        decision = _make_b2_case_chain(lid, case)
        selected_dir = decision.metadata["selected_thesis_direction"]
        assert decision.metadata["composite_score"] == expected["scores"][selected_dir], lid
        rejected = decision.rejected_alternatives
        assert len(rejected) == 1, lid
        assert rejected[0].composite_score == expected["scores"][rejected[0].thesis_direction], lid

    @pytest.mark.parametrize("lid", list(B2_RECORDED.keys()))
    def test_hardening_ranking_margin_and_confidence_preserved(self, lid):
        case = B2_RECORDED[lid]
        expected = HARDENING_RECORDED[lid]
        decision = _make_b2_case_chain(lid, case)
        selected_dir = decision.metadata["selected_thesis_direction"]
        rejected = decision.rejected_alternatives
        # ranking: selected thesis and runner-up match the recorded order
        assert selected_dir == case["order_dirs"][0], lid
        assert rejected[0].thesis_direction == case["order_dirs"][1], lid
        # exact recorded top-2 margin under the hardening composite
        margin = round(
            decision.metadata["composite_score"] - rejected[0].composite_score, 4
        )
        assert margin == expected["margin_top2"], lid
        # confidence values are inputs, untouched by the hardening
        assert decision.institutional_confidence == case["theses"][selected_dir]["fc"], lid

    @pytest.mark.parametrize("lid", list(B2_RECORDED.keys()))
    def test_decision_baseline_rederived_from_recorded_primitives(self, lid):
        # The recorded decision must be re-derivable through the REAL
        # decision gates (confidence gate + RR gate + direction semantics)
        # from the recorded primitives -- not merely asserted to exist.
        case = B2_RECORDED[lid]
        decision = _make_b2_case_chain(lid, case)
        assert decision.decision == case["decision_baseline"], lid


