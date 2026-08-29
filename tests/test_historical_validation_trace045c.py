"""Focused tests for Trace 045-C -- historical signal -> W4/W5 -> W6-W13.

For the FIRST cohort case the Trace-045-B reconstructed SignalAssessment is
injected through the EXISTING pure collector into the existing W6-W13 chain,
FULL vs NO_HISTORY sharing an IDENTICAL signal/evidence input.
"""

from __future__ import annotations

import hashlib
import socket
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from historical_validation.cases import build_validation_cases
from historical_validation.compare import (
    compare_variants,
    numeric_leaf_comparison,
)
from historical_validation.signal_replay import run_replay_variant
from historical_validation.snapshot import build_snapshot


@pytest.fixture(scope="module")
def case():
    cases = build_validation_cases(path=ROOT / "data" / "lessons" / "cpi_gold_lessons.csv")
    return cases[0]


@pytest.fixture(scope="module")
def case_snapshot(case):
    return build_snapshot(case)


@pytest.fixture(scope="module")
def guarded_bundle(case, case_snapshot):
    watched = [
        "data/history/gold/gold.csv",
        "data/context/dxy/dxy.csv",
        "data/economic/DFII10.csv",
        "data/economic/DGS10.csv",
        "data/economic/T5YIE.csv",
        "data/calendar/cpi_releases.csv",
        "data/economic/output/knowledge.json",
        "data/economic/gold_oi_state.json",
        "data/lessons/cpi_gold_lessons.csv",
        "runtime/run_registry.jsonl",
    ]

    def digest(rel: str):
        p = ROOT / rel
        return hashlib.sha256(p.read_bytes()).hexdigest() if p.is_file() else "<missing>"

    before = {rel: digest(rel) for rel in watched}
    full_a = run_replay_variant(case, history_enabled=True, run_label="c1", snapshot=case_snapshot)
    no_history = run_replay_variant(case, history_enabled=False, run_label="c1", snapshot=case_snapshot)
    full_b = run_replay_variant(case, history_enabled=True, run_label="c2", snapshot=case_snapshot)
    after = {rel: digest(rel) for rel in watched}
    return {
        "full_a": full_a,
        "no_history": no_history,
        "full_b": full_b,
        "comparison": compare_variants(full_a, no_history),
        "before": before,
        "after": after,
    }


# ---------------------------------------------------------------------------
# 1. Historical SignalAssessment reaches W4/W5
# ---------------------------------------------------------------------------


def test_historical_signal_assessment_reaches_w4_w5(guarded_bundle) -> None:
    r = guarded_bundle["full_a"]
    assert r["trace_sub_id"] == "045-C"
    sa = r["signal_assessment_summary"]
    assert sa["observation_count"] >= 5
    ev = r["evidence_summary"]
    assert ev["item_count"] >= 1
    assert ev["knowledge_record_nodes"] >= 1
    # The reasoning stage consumed exactly these evidence items PLUS the
    # single bounded HISTORICAL_MEMORY item (Run-003 Phase 8, FULL only).
    reasoning = r["serialized_outputs"]["evidence_reasoning"]
    assert reasoning["metadata"]["collection_items"] == ev["item_count"] + 1
    mem_sets = [
        s
        for s in reasoning["evidence_sets"]
        if s["event_type"] == "HISTORICAL_MEMORY"
    ]
    assert len(mem_sets) == 1
    # CORE instruments propagated into the collection.
    instruments = {i["instrument"] for i in ev["items"]}
    assert {"XAU/USD", "DXY"} <= instruments


# ---------------------------------------------------------------------------
# 2. FULL and NO_HISTORY receive identical SignalAssessment
# ---------------------------------------------------------------------------


def test_identical_signal_assessment_between_variants(guarded_bundle) -> None:
    a, n = guarded_bundle["full_a"], guarded_bundle["no_history"]
    assert a["signal_assessment_summary"] == n["signal_assessment_summary"]
    assert a["evidence_summary"] == n["evidence_summary"]
    assert a["snapshot_summary"] == n["snapshot_summary"]
    assert a["evaluated_thesis_directions"] == n["evaluated_thesis_directions"]


# ---------------------------------------------------------------------------
# 3. Current/today context is never called
# ---------------------------------------------------------------------------


def test_today_context_never_called(case, case_snapshot, monkeypatch) -> None:
    def _blocked(*args, **kwargs):
        raise AssertionError("network/socket was opened")

    monkeypatch.setattr(socket, "socket", _blocked)
    monkeypatch.setattr(socket, "create_connection", _blocked)
    from decision_engine.contracts import VALID_DECISIONS

    result = run_replay_variant(
        case, history_enabled=True, run_label="cx", snapshot=case_snapshot
    )
    assert result["decision"] in VALID_DECISIONS


# ---------------------------------------------------------------------------
# 4. No production filesystem mutation
# ---------------------------------------------------------------------------


def test_no_production_filesystem_mutation(guarded_bundle) -> None:
    b = guarded_bundle
    assert b["before"] == b["after"]


# ---------------------------------------------------------------------------
# 5. Candidate directions are driven by actual reconstructed evidence
# ---------------------------------------------------------------------------


def test_candidate_directions_driven_by_reconstructed_evidence(guarded_bundle) -> None:
    r = guarded_bundle["full_a"]
    # Run-003 repair: candidate directions are driven by SET biases (which
    # now include the memory desk's set), not raw item biases.
    reasoning = r["serialized_outputs"]["evidence_reasoning"]
    set_biases = {s["bias"] for s in reasoning["evidence_sets"] if s["bias"]}
    assert set_biases <= {"bullish", "bearish", "neutral", "mixed"}
    assert {"bullish", "bearish"} & set_biases, "expected directional evidence"
    expected = ["bearish", "bullish", "neutral"]
    if "bearish" not in set_biases:
        expected.remove("bearish")
    if "bullish" not in set_biases:
        expected.remove("bullish")
    assert r["evaluated_thesis_directions"] == expected
    supports = r["institutional_support_by_direction"]
    assert len(supports) == len(r["evaluated_thesis_directions"])
    for direction, value in supports.items():
        if direction == "neutral":
            # Run-003 Phase 4: a neutral thesis is an absence claim with
            # ZERO institutional support -- it can no longer win on
            # uninformative-set weight.
            assert value == 0.0
        else:
            assert value > 0.0
    # Selected direction must be directional whenever one exists.
    if set(expected) - {"neutral"}:
        assert r["selected_thesis_direction"] != "neutral"


# ---------------------------------------------------------------------------
# 6. Deterministic repeated execution
# ---------------------------------------------------------------------------


def test_deterministic_repeated_execution(guarded_bundle) -> None:
    a, b = guarded_bundle["full_a"], guarded_bundle["full_b"]
    assert numeric_leaf_comparison(a["serialized_outputs"]) == numeric_leaf_comparison(
        b["serialized_outputs"]
    )
    assert a["signal_assessment_summary"] == b["signal_assessment_summary"]
    assert a["selected_thesis_direction"] == b["selected_thesis_direction"]
    assert a["decision"] == b["decision"]
    assert list(a["analogue_match_ids"]) == list(b["analogue_match_ids"])


# ---------------------------------------------------------------------------
# 7. No lookahead remains green
# ---------------------------------------------------------------------------


def test_no_lookahead_green(guarded_bundle, case) -> None:
    cutoff = case.evaluation_date.isoformat()
    dates_by_id = {}
    import csv

    with (ROOT / "data" / "lessons" / "cpi_gold_lessons.csv").open(
        "r", encoding="utf-8", newline=""
    ) as fh:
        for row in csv.DictReader(fh):
            dates_by_id[row["lesson_id"]] = row["event_date"]
    for name in ("full_a", "no_history", "full_b"):
        r = guarded_bundle[name]
        assert all(r["no_lookahead_checks"].values()), name
        assert all(r["payload_lookahead_checks"].values()), name
    for lesson_id in guarded_bundle["full_a"]["analogue_match_ids"]:
        assert lesson_id != case.lesson_id
        assert dates_by_id[lesson_id] < cutoff


# ---------------------------------------------------------------------------
# 8. Numeric FULL vs NO_HISTORY comparison
# ---------------------------------------------------------------------------


def test_numeric_full_vs_no_history_comparison(guarded_bundle) -> None:
    # Run-003 repair (Phase 8): memory feeds ONE bounded HISTORICAL_MEMORY
    # evidence set in FULL, so numeric identity between variants no longer
    # holds by design.  The pinned contract is now structural: exactly one
    # memory set in FULL, none in NO_HISTORY, identical shared evidence,
    # and the recorded comparison booleans reflecting the measured payloads.
    a, n = guarded_bundle["full_a"], guarded_bundle["no_history"]
    cmp = guarded_bundle["comparison"]
    full_sets = a["serialized_outputs"]["evidence_reasoning"]["evidence_sets"]
    nohist_sets = n["serialized_outputs"]["evidence_reasoning"]["evidence_sets"]
    mem = [s for s in full_sets if s["event_type"] == "HISTORICAL_MEMORY"]
    assert len(mem) == 1
    assert all(s["event_type"] != "HISTORICAL_MEMORY" for s in nohist_sets)
    nonmem_full = {
        s["set_id"]: s for s in full_sets if s["event_type"] != "HISTORICAL_MEMORY"
    }
    nonmem_nohist = {s["set_id"]: s for s in nohist_sets}
    assert set(nonmem_full) == set(nonmem_nohist)
    for sid, s in nonmem_full.items():
        assert s["net_institutional_weight"] == nonmem_nohist[sid]["net_institutional_weight"]
        assert s["consensus_score"] == nonmem_nohist[sid]["consensus_score"]
        assert s["bias"] == nonmem_nohist[sid]["bias"]
    assert cmp["history_changed_thesis"] is (
        a["selected_thesis_direction"] != n["selected_thesis_direction"]
        or a["evaluated_thesis_directions"] != n["evaluated_thesis_directions"]
        or a["institutional_support_by_direction"]
        != n["institutional_support_by_direction"]
        or a["confidence_payload_summary"] != n["confidence_payload_summary"]
    )
    assert cmp["history_changed_decision"] is (
        a["decision"] != n["decision"]
        or a["decision_risk_reward_summary"] != n["decision_risk_reward_summary"]
    )
    # Historical payloads exist ONLY in FULL.
    assert a["historical_metadata_present"]["historical_analogue"] is True
    assert n["historical_metadata_present"]["historical_analogue"] is False
    full_assessments = a["candidate_historical_assessments"]
    assert full_assessments and any(
        e.get("historical_assessment") for e in full_assessments
    )
