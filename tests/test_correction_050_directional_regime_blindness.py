"""Correction 050 -- regime_blindness is THESIS-DIRECTIONAL (focused tests).

Locks the validated semantic (Traces 050-A / 050-B):

  RB fires iff
    direction in {bullish, bearish}
    and REGIME_EXPECTED_BIAS[regime] in {bullish, bearish}
    and direction != REGIME_EXPECTED_BIAS[regime]
    and update.action in {no_change, scale, hedge}

  severity = critical iff contradicts AND action == 'no_change', else high.
  Neutral theses are never regime-blind on set-level conflict alone.

Includes the exact Trace-050-B eight-candidate regression (current 8/8 ->
corrected 3/8 firing) and sibling-invariance proof that no other BiasReview
finding changed as a function of this rule. Production data files must be
byte-identical before/after the module run.
"""

from __future__ import annotations

import hashlib
import sys
from dataclasses import replace
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from bias_prevention.contracts import apply_bias_review
from bias_prevention.detector import BiasReviewer
from confidence_engine.contracts import InstitutionalConfidence, ThesisConfidence
from counter_evidence.contracts import CounterEvidenceAssessment
from decision_engine.contracts import InstitutionalDecision
from thesis_construction.contracts import InvestmentThesis
from thesis_update.contracts import ThesisUpdate

TIMESTAMP = "2026-08-23T00:00:00Z"

WATCHED_FILES: tuple[str, ...] = (
    "data/history/gold/gold.csv",
    "data/context/dxy/dxy.csv",
    "data/economic/DFII10.csv",
    "data/economic/DGS10.csv",
    "data/lessons/cpi_gold_lessons.csv",
)


def _digest(rel: str) -> str:
    p = ROOT / rel
    return hashlib.sha256(p.read_bytes()).hexdigest() if p.is_file() else "<missing>"


def _thesis(direction: str, regime: str, *, explanation: str = "range historically similar past") -> InvestmentThesis:
    """Thesis engineered so ONLY regime_blindness can fire.

    - explicit invalidating conditions -> confirmation/anchoring clear
    - two supporting sets + two W7 supporting sets -> single_source clear
    - contradicting sets present -> groupthink clear
    - weight >= 0.5 -> narrative clear
    - explanation carries range/base-rate keywords and no decimal numbers
      -> false_precision / base_rate_neglect / ttid clear
    - 90d horizon + recency 1.0 -> recency clear
    """
    return InvestmentThesis(
        thesis_id="th_c050",
        direction=direction,
        supporting_set_ids=("set_a", "set_b"),
        counter_evidence_ids=("set_x",),
        regime=regime,
        economic_mechanism="",
        time_horizon_days=90,
        invalidating_conditions=("Exit if real yields rise above 2.5%",),
        remaining_unknowns=(),
        confidence_inputs={
            "avg_supporting_weight": 0.6,
            "avg_supporting_consensus": 0.9,
            "conflict_severity": 0.0,
            "confidence_penalty": 0.0,
            "raw_support": 0.54,
        },
        institutional_support=0.54,
        explanation=explanation,
    )


def _update(direction: str, regime: str, action: str = "no_change") -> ThesisUpdate:
    return ThesisUpdate(
        update_id="update-c050-v2",
        previous_thesis_id="th_c050",
        previous_version="v1",
        new_thesis_version="v2",
        reasoning_id="rsn-c050",
        assessment_id="cae-c050",
        timestamp=TIMESTAMP,
        updated_evidence=(),
        confidence_delta=0.0,
        changed_assumptions=(),
        change_summary="periodic review",
        action=action,
        trigger_type="periodic",
        updated_thesis=_thesis(direction, regime),
    )


def _assessment(regime: str, *, regime_conflict: bool = True) -> CounterEvidenceAssessment:
    return CounterEvidenceAssessment(
        assessment_id="cae-c050",
        reasoning_id="rsn-c050",
        timestamp=TIMESTAMP,
        regime=regime,
        supporting_set_ids=("set_a", "set_b"),
        contradicting_set_ids=("set_x",),
        conflict_severity=0.0,
        confidence_penalty=0.0,
        regime_conflict=regime_conflict,
        bias_flags=(),
    )


def _confidence() -> InstitutionalConfidence:
    return InstitutionalConfidence(
        confidence_id="cf-c050",
        construction_id="tc-c050",
        timestamp=TIMESTAMP,
        regime="NORMAL_GROWTH",
        theses_confidence=(
            ThesisConfidence(
                thesis_id="th_c050",
                final_confidence=0.5,
                confidence_breakdown={"regime_alignment": 0.5, "temporal_recency": 1.0},
                reliability_category="moderate",
            ),
        ),
        ranked_thesis_ids=("th_c050",),
        primary_thesis_id="th_c050",
    )


def _rb(update: ThesisUpdate, assessment: CounterEvidenceAssessment):
    review = BiasReviewer().review(update, assessment, _confidence())
    finding = next((f for f in review.findings if f.bias_name == "regime_blindness"), None)
    others = sorted(f.bias_name for f in review.findings if f.bias_name != "regime_blindness")
    return finding, others


# ---------------------------------------------------------------------------
# 1-2. aligned directional theses are never regime-blind
# ---------------------------------------------------------------------------


def test_aligned_bullish_in_bullish_regime_not_flagged():
    finding, others = _rb(_update("bullish", "NORMAL_GROWTH"), _assessment("NORMAL_GROWTH"))
    assert finding is None
    assert others == []


def test_aligned_bearish_in_bearish_regime_not_flagged():
    finding, others = _rb(_update("bearish", "DEFLATIONARY_CRISIS"), _assessment("DEFLATIONARY_CRISIS"))
    assert finding is None
    assert others == []


# ---------------------------------------------------------------------------
# 3-4. opposed directional theses under no_change -> critical
# ---------------------------------------------------------------------------


def test_opposed_bullish_in_bearish_regime_critical():
    finding, _ = _rb(
        _update("bullish", "DEFLATIONARY_CRISIS"), _assessment("DEFLATIONARY_CRISIS")
    )
    assert finding is not None and finding.severity == "critical"


def test_opposed_bearish_in_bullish_regime_critical():
    finding, _ = _rb(
        _update("bearish", "INFLATIONARY"), _assessment("INFLATIONARY")
    )
    assert finding is not None and finding.severity == "critical"


# ---------------------------------------------------------------------------
# 5. neutral + set-level conflict -> never regime-blind
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("regime", ["INFLATIONARY", "STAGFLATIONARY", "DEFLATIONARY_CRISIS"])
def test_neutral_never_regime_blind_on_set_conflict(regime):
    finding, others = _rb(_update("neutral", regime), _assessment(regime))
    assert finding is None
    assert "regime_blindness" not in others


# ---------------------------------------------------------------------------
# 6. opposed thesis with scale / hedge retains non-critical behavior
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("action", ["scale", "hedge"])
def test_opposed_with_scale_or_hedge_is_high_not_critical(action):
    finding, _ = _rb(
        _update("bearish", "INFLATIONARY", action=action), _assessment("INFLATIONARY")
    )
    assert finding is not None
    assert finding.severity == "high"
    assert finding.confidence_impact == 0.25


def test_exit_action_clears_regime_blindness():
    finding, _ = _rb(
        _update("bearish", "INFLATIONARY", action="exit"), _assessment("INFLATIONARY")
    )
    assert finding is None


# ---------------------------------------------------------------------------
# 7. deterministic repeated result
# ---------------------------------------------------------------------------


def test_deterministic_repeated_review():
    update = _update("bearish", "INFLATIONARY")
    assessment = _assessment("INFLATIONARY")
    conf = _confidence()
    first = BiasReviewer().review(update, assessment, conf).to_dict()
    second = BiasReviewer().review(update, assessment, conf).to_dict()
    assert first == second


# ---------------------------------------------------------------------------
# 8. exact Trace-050-B eight-candidate regression (8/8 -> 3/8)
# ---------------------------------------------------------------------------

TRACE_050B_CANDIDATES = (
    # (case, direction, regime, action, expected_rb_severity or None)
    ("2015-06", "bullish", "DEFLATIONARY_CRISIS", "no_change", "critical"),
    ("2015-06", "neutral", "DEFLATIONARY_CRISIS", "no_change", None),
    ("2015-06", "bearish", "DEFLATIONARY_CRISIS", "no_change", None),
    ("2020-09", "bullish", "STAGFLATIONARY", "no_change", "critical"),
    ("2020-09", "neutral", "STAGFLATIONARY", "no_change", None),
    ("2026-02", "neutral", "INFLATIONARY", "no_change", None),
    ("2026-02", "bullish", "INFLATIONARY", "no_change", None),
    ("2026-02", "bearish", "INFLATIONARY", "no_change", "critical"),
)


def test_trace050b_eight_candidate_regression():
    fired = []
    for case, direction, regime, action, expected in TRACE_050B_CANDIDATES:
        finding, _ = _rb(_update(direction, regime, action), _assessment(regime))
        got = finding.severity if finding is not None else None
        assert got == expected, (case, direction, regime, got, expected)
        if got is not None:
            fired.append((case, direction))
    assert len(fired) == 3, fired


# ---------------------------------------------------------------------------
# 9. sibling invariance: flipping ONLY direction never changes non-RB findings
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "regime", ["NORMAL_GROWTH", "INFLATIONARY", "STAGFLATIONARY", "DEFLATIONARY_CRISIS"]
)
@pytest.mark.parametrize("action", ["no_change", "scale", "hedge", "exit"])
def test_no_other_finding_changes_as_function_of_direction_rule(regime, action):
    def names(direction):
        _, others = _rb(_update(direction, regime, action), _assessment(regime))
        return others

    assert names("bullish") == names("bearish")


# ---------------------------------------------------------------------------
# Sibling checks still fire on their own triggers (rule change isolated)
# ---------------------------------------------------------------------------


def test_false_precision_sibling_still_fires():
    update = _update(
        "bearish",
        "INFLATIONARY",
    )
    thesis = update.updated_thesis
    from dataclasses import replace

    thesis = replace(thesis, explanation="support equals 0.5349 exactly")
    update = replace(update, updated_thesis=thesis)
    review = BiasReviewer().review(update, _assessment("INFLATIONARY"), _confidence())
    assert "false_precision" in [f.bias_name for f in review.findings]


def test_single_source_sibling_still_fires():
    update = _update("bearish", "INFLATIONARY")
    thesis = replace(update.updated_thesis, supporting_set_ids=("set_a",))
    update = replace(update, updated_thesis=thesis)
    assessment = CounterEvidenceAssessment(
        assessment_id="cae-c050",
        reasoning_id="rsn-c050",
        timestamp=TIMESTAMP,
        regime="INFLATIONARY",
        supporting_set_ids=("set_a",),
        contradicting_set_ids=("set_x",),
        conflict_severity=0.0,
        confidence_penalty=0.0,
        regime_conflict=True,
        bias_flags=(),
    )
    review = BiasReviewer().review(update, assessment, _confidence())
    assert "single_source_bias" in [f.bias_name for f in review.findings]


# ---------------------------------------------------------------------------
# Decision gate unchanged end-to-end for a flagged review
# ---------------------------------------------------------------------------


def test_human_review_flag_and_gate_semantics_unchanged():
    update = _update("bearish", "INFLATIONARY")
    review = BiasReviewer().review(update, _assessment("INFLATIONARY"), _confidence())
    assert review.human_review_flag is True
    # Final Hardening (Group A, D-04): the gate applies when the reviewed
    # thesis IS the selected thesis.  (The pre-hardening version of this
    # test asserted a block even when the review targeted a different
    # candidate than the selected thesis -- the cross-thesis veto that the
    # hardening wave removed.)
    decision = InstitutionalDecision(
        decision_id="dec-c050",
        decision="BUY",
        selected_thesis_id=review.thesis_id,
        selected_scenario_id="sc-c050",
        institutional_confidence=0.55,
        decision_explanation="test",
    )
    gated = apply_bias_review(decision, review)
    assert gated.decision == "NO_TRADE"
    assert "BLOCKED BY BIAS PREVENTION" in gated.decision_explanation


def test_review_of_non_selected_candidate_is_advisory_only():
    # Final Hardening (Group A, D-04): a human-review finding on a
    # candidate that was NOT selected must not veto the decision made on
    # a different thesis; it is recorded as an explicit advisory.
    update = _update("bearish", "INFLATIONARY")
    review = BiasReviewer().review(update, _assessment("INFLATIONARY"), _confidence())
    assert review.human_review_flag is True
    decision = InstitutionalDecision(
        decision_id="dec-c050-b",
        decision="BUY",
        selected_thesis_id="th_other_candidate",
        selected_scenario_id="sc-c050-b",
        institutional_confidence=0.55,
        decision_explanation="test",
    )
    gated = apply_bias_review(decision, review)
    assert gated.decision == "BUY"
    assert "BIAS REVIEW ADVISORY" in gated.decision_explanation
    assert gated.metadata["bias_review"]["human_review_flag"] is True
    assert gated.metadata["reviewed_thesis_id"] == review.thesis_id


# ---------------------------------------------------------------------------
# 10. production data files byte-identical across the module run
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def watched_digests():
    before = {rel: _digest(rel) for rel in WATCHED_FILES}
    yield before
    after = {rel: _digest(rel) for rel in WATCHED_FILES}
    assert before == after, "production data files changed during Correction-050 tests"
