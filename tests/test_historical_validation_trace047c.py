"""Focused tests for Correction 047-C -- enriched corpus + signal full chain."""

from __future__ import annotations

import hashlib
import socket
import subprocess
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
from historical_validation.enriched_path import (
    build_enriched_analogue_payload,
    verify_episode_trends_asof,
)
from historical_validation.enriched_replay import run_enriched_replay_variant
from historical_validation.signal_replay import run_replay_variant
from historical_validation.snapshot import SnapshotConfig, build_snapshot

LESSONS = ROOT / "data" / "lessons" / "cpi_gold_lessons.csv"

SMOKE_IDS = (
    "CPI_GOLD_2015-06-01",
    "CPI_GOLD_2020-09-01",
    "CPI_GOLD_2026-02-01",
)

WATCHED_FILES: tuple[str, ...] = (
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
)


def _digest(rel: str):
    p = ROOT / rel
    return hashlib.sha256(p.read_bytes()).hexdigest() if p.is_file() else "<missing>"


@pytest.fixture(scope="module")
def bundle():
    cases = {c.lesson_id: c for c in build_validation_cases(path=LESSONS)}
    missing = [lid for lid in SMOKE_IDS if lid not in cases]
    assert not missing, f"smoke cases missing from cohort: {missing}"

    before_files = {rel: _digest(rel) for rel in WATCHED_FILES}
    before_state = sorted(p.name for p in (ROOT / "data" / "state").glob("*"))

    pre, full_a, no_history, full_b = {}, {}, {}, {}
    trends_safe, infos = {}, {}
    for lid in SMOKE_IDS:
        case = cases[lid]
        snap = build_snapshot(case)
        trends_safe[lid] = verify_episode_trends_asof(snap.evaluation_date)
        infos[lid] = build_enriched_analogue_payload(snap)[1]
        pre[lid] = run_replay_variant(
            case, history_enabled=True, run_label="pre", snapshot=snap
        )
        full_a[lid] = run_enriched_replay_variant(
            case, history_enabled=True, run_label="a", snapshot=snap
        )
        no_history[lid] = run_enriched_replay_variant(
            case, history_enabled=False, run_label="a", snapshot=snap
        )
        full_b[lid] = run_enriched_replay_variant(
            case, history_enabled=True, run_label="b", snapshot=snap
        )

    after_files = {rel: _digest(rel) for rel in WATCHED_FILES}
    after_state = sorted(p.name for p in (ROOT / "data" / "state").glob("*"))
    return {
        "cases": cases,
        "pre": pre,
        "full_a": full_a,
        "no_history": no_history,
        "full_b": full_b,
        "comparisons": {
            lid: compare_variants(full_a[lid], no_history[lid]) for lid in SMOKE_IDS
        },
        "trends_safe": trends_safe,
        "infos": infos,
        "before_files": before_files,
        "after_files": after_files,
        "before_state": before_state,
        "after_state": after_state,
    }


# ---------------------------------------------------------------------------
# 1. The 047-A enriched corpus reaches the full pure chain
# ---------------------------------------------------------------------------


def test_enriched_corpus_reaches_full_chain(bundle) -> None:
    for lid in SMOKE_IDS:
        full = bundle["full_a"][lid]
        info = bundle["infos"][lid]
        assert list(full["analogue_match_ids"]) == list(info["match_ids"]), lid
        assert full["condition_exact_match_count"] >= 1, lid
        assert set(full["retrieval_methods"].values()) <= {"exact", "contextual"}, lid
        assert full["eligible_episode_count"] == info["eligible_episode_count"] > 0, lid
    set_changed = sum(
        1 for lid in SMOKE_IDS
        if set(bundle["full_a"][lid]["analogue_match_ids"])
        != set(bundle["pre"][lid]["analogue_match_ids"])
    )
    order_changed = sum(
        1 for lid in SMOKE_IDS
        if list(bundle["full_a"][lid]["analogue_match_ids"])
        != list(bundle["pre"][lid]["analogue_match_ids"])
    )
    assert set_changed >= 2 and order_changed == 3


# ---------------------------------------------------------------------------
# 2. Historical SignalAssessment identical FULL vs NO_HISTORY
# ---------------------------------------------------------------------------


def test_signal_assessment_identical_full_vs_no_history(bundle) -> None:
    for lid in SMOKE_IDS:
        a, n = bundle["full_a"][lid], bundle["no_history"][lid]
        assert a["signal_assessment_summary"] == n["signal_assessment_summary"], lid
        assert a["snapshot_summary"] == n["snapshot_summary"], lid
        assert a["evaluation_date"] == n["evaluation_date"], lid
        assert a["lesson_id"] == n["lesson_id"], lid
        assert a["briefing_asof_checks"] == n["briefing_asof_checks"], lid


# ---------------------------------------------------------------------------
# 3. W4/W5 evidence is non-degenerate (STOP CONDITION check)
# ---------------------------------------------------------------------------


def test_w4_w5_evidence_non_degenerate(bundle) -> None:
    for lid in SMOKE_IDS:
        for name in ("full_a", "no_history", "full_b"):
            ev = bundle[name][lid]["evidence_summary"]
            sa = bundle[name][lid]["signal_assessment_summary"]
            assert sa["observation_count"] >= 5, (lid, name)
            assert ev["item_count"] >= 1, (lid, name)
            assert ev["knowledge_record_nodes"] >= 1, (lid, name)
            instruments = set(ev["instruments"])
            assert {"XAU/USD"} <= instruments, (lid, name)
            biases = set(ev["biases"])
            assert biases <= {"bullish", "bearish", "neutral"}, (lid, name)
            assert {"bullish", "bearish"} & biases, (lid, name)


# ---------------------------------------------------------------------------
# 4. Candidate directions produced from the reconstructed signal path
# ---------------------------------------------------------------------------


def test_candidate_directions_from_reconstructed_signal_path(bundle) -> None:
    for lid in SMOKE_IDS:
        r = bundle["full_a"][lid]
        sets_biases = {
            es.get("bias")
            for es in r["serialized_outputs"]["evidence_reasoning"]["evidence_sets"]
            if es.get("bias")
        }
        assert sets_biases <= {"bullish", "bearish", "neutral", "mixed"}, lid
        if {"bullish", "bearish"} <= sets_biases:
            expected = ["bullish", "bearish", "neutral"]
        elif "bullish" in sets_biases:
            expected = ["bullish", "neutral"]
        elif "bearish" in sets_biases:
            expected = ["bearish", "neutral"]
        else:
            expected = ["neutral"]
        assert sorted(r["evaluated_thesis_directions"]) == sorted(expected), lid
        supports = r["institutional_support_by_direction"]
        assert set(supports) == set(expected), lid
        for direction, value in supports.items():
            if direction == "neutral":
                # Run-003 Phase 4: neutral thesis = absence claim, zero support.
                assert value == 0.0, lid
            else:
                assert value > 0.0, lid
        if set(expected) - {"neutral"}:
            assert r["selected_thesis_direction"] != "neutral", lid

    from decision_engine.contracts import VALID_DECISIONS

    assert r["decision"] in VALID_DECISIONS, lid
    noh = bundle["no_history"][lid]
    # Run-003 Phase 8: NO_HISTORY may carry a strict subset of the FULL
    # candidate directions (the memory vote can add one).
    assert set(noh["evaluated_thesis_directions"]) <= set(
        r["evaluated_thesis_directions"]
    ), lid
    shapes = {
        tuple(bundle["full_a"][lid]["evaluated_thesis_directions"])
        for lid in SMOKE_IDS
    }
    assert len(shapes) >= 2, "candidate shapes identical across cases"


# ---------------------------------------------------------------------------
# 6. Numeric comparison: memory is the only channel difference
# ---------------------------------------------------------------------------


def test_full_no_history_numeric_invariance(bundle) -> None:
    for lid in SMOKE_IDS:
        full = bundle["full_a"][lid]
        noh = bundle["no_history"][lid]
        cmp_ = bundle["comparisons"][lid]
        # Run-003 repair (Phase 8): the ONLY structural difference is the
        # single bounded HISTORICAL_MEMORY evidence set in FULL.
        full_sets = full["serialized_outputs"]["evidence_reasoning"]["evidence_sets"]
        noh_sets = noh["serialized_outputs"]["evidence_reasoning"]["evidence_sets"]
        mem = [s for s in full_sets if s["event_type"] == "HISTORICAL_MEMORY"]
        assert len(mem) == 1, lid
        assert all(s["event_type"] != "HISTORICAL_MEMORY" for s in noh_sets), lid
        nonmem_full = {
            s["set_id"]: s for s in full_sets if s["event_type"] != "HISTORICAL_MEMORY"
        }
        nonmem_nohist = {s["set_id"]: s for s in noh_sets}
        assert set(nonmem_full) == set(nonmem_nohist), lid
        for sid, s in nonmem_full.items():
            assert s["net_institutional_weight"] == nonmem_nohist[sid]["net_institutional_weight"], lid
            assert s["bias"] == nonmem_nohist[sid]["bias"], lid
        assert cmp_["history_changed_thesis"] is (
            full["selected_thesis_direction"] != noh["selected_thesis_direction"]
            or full["evaluated_thesis_directions"] != noh["evaluated_thesis_directions"]
            or full["institutional_support_by_direction"]
            != noh["institutional_support_by_direction"]
        ), lid
        assert cmp_["history_changed_decision"] is (
            full["decision"] != noh["decision"]
            or full["decision_risk_reward_summary"] != noh["decision_risk_reward_summary"]
        ), lid

        from decision_engine.contracts import VALID_DECISIONS

        assert full["decision"] in VALID_DECISIONS, lid
        assert noh["decision"] in VALID_DECISIONS, lid
        assert full["candidate_historical_assessments"], lid
        assert noh["analogue_match_ids"] == (), lid


def test_enriched_matches_consumed_by_w6(bundle) -> None:
    for lid in SMOKE_IDS:
        r = bundle["full_a"][lid]
        assert r["historical_retrieval_payload_present"] is True, lid
        reasoning = r["serialized_outputs"]["evidence_reasoning"]
        analogue = reasoning["metadata"].get("historical_analogue")
        assert analogue is not None, lid
        payload_ids = [m["lesson_id"] for m in analogue["matches"]]
        assert payload_ids == list(r["analogue_match_ids"]), lid
        assert analogue["match_count"] == len(payload_ids), lid
        methods = {
            m["lesson_id"]: m["similarity"]["retrieval_method"]
            for m in analogue["matches"]
        }
        assert methods == dict(r["retrieval_methods"]), lid
        breakdown = r["analogue_similarity_breakdown"]
        assert set(breakdown) == set(payload_ids), lid
        top = payload_ids[0]
        assert breakdown[top]["condition_similarity"] == 1.0, lid
        n = bundle["no_history"][lid]
        assert n["historical_retrieval_payload_present"] is False, lid
        n_reasoning = n["serialized_outputs"]["evidence_reasoning"]
        assert n_reasoning["metadata"].get("historical_analogue") is None, lid


# ---------------------------------------------------------------------------
# 6. Adjudication propagates
# ---------------------------------------------------------------------------


def test_adjudication_propagates(bundle) -> None:
    for lid in SMOKE_IDS:
        r = bundle["full_a"][lid]
        assert r["historical_metadata_present"]["historical_adjudication"] is True, lid
        assert r["historical_adjudication_present"] is True, lid
        assessments = r["candidate_historical_assessments"]
        assert assessments, lid
        by_dir = {a["thesis_direction"]: a for a in assessments}
        assert set(by_dir) == set(r["evaluated_thesis_directions"]), lid
        for direction, a in by_dir.items():
            ha = a["historical_assessment"]
            assert ha is not None, (lid, direction)
            horizons = ha["horizon_results"]
            assert {"1d", "5d", "20d"} <= set(horizons), (lid, direction)
            assert ha["evidence_ids"] == list(r["analogue_match_ids"]), (
                lid, direction
            )


# ---------------------------------------------------------------------------
# 7. (superseded numeric invariance pinned structurally above)
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# 8. Deterministic repeated run
# ---------------------------------------------------------------------------


def test_deterministic_repeat(bundle, monkeypatch) -> None:
    def _blocked(*args, **kwargs):
        raise AssertionError("network/socket was opened")

    monkeypatch.setattr(socket, "socket", _blocked)
    monkeypatch.setattr(socket, "create_connection", _blocked)

    for lid in SMOKE_IDS:
        snap = build_snapshot(bundle["cases"][lid])
        rerun = run_enriched_replay_variant(
            bundle["cases"][lid], history_enabled=True, run_label="c", snapshot=snap
        )
        base = bundle["full_a"][lid]
        assert numeric_leaf_comparison(rerun["serialized_outputs"]) == (
            numeric_leaf_comparison(base["serialized_outputs"])
        ), lid
        assert rerun["decision"] == base["decision"], lid
        assert rerun["selected_thesis_direction"] == base["selected_thesis_direction"], lid
        assert rerun["institutional_confidence"] == base["institutional_confidence"], lid
        assert list(rerun["analogue_match_ids"]) == list(base["analogue_match_ids"]), lid
        assert rerun["signal_assessment_summary"] == base["signal_assessment_summary"], lid
        assert rerun["evidence_summary"] == base["evidence_summary"], lid


# ---------------------------------------------------------------------------
# 9. No lookahead
# ---------------------------------------------------------------------------


def test_no_lookahead_green(bundle) -> None:
    dates_by_id = {}
    import csv

    with LESSONS.open("r", encoding="utf-8", newline="") as fh:
        for row in csv.DictReader(fh):
            dates_by_id[row["lesson_id"]] = row["event_date"]
    for lid in SMOKE_IDS:
        assert bundle["trends_safe"][lid] is True, lid
        cutoff = bundle["cases"][lid].evaluation_date.isoformat()
        for name in ("pre", "full_a", "no_history", "full_b"):
            r = bundle[name][lid]
            assert all(r["no_lookahead_checks"].values()), (lid, name)
            assert all(r["payload_lookahead_checks"].values()), (lid, name)
        checks = bundle["full_a"][lid]["briefing_asof_checks"]
        assert all(checks.values()), (lid, checks)
        for lesson_id in bundle["full_a"][lid]["analogue_match_ids"]:
            assert lesson_id != lid
            assert dates_by_id[lesson_id] < cutoff


# ---------------------------------------------------------------------------
# 10. Production artifacts unchanged
# ---------------------------------------------------------------------------


def test_production_artifacts_unchanged(bundle) -> None:
    # Run-003: the working-tree check from Correction 047 is superseded by
    # the sanctioned repair wave; the replay's read-only guarantee is
    # pinned by the file digests below.
    assert bundle["before_files"] == bundle["after_files"]
    assert bundle["before_state"] == bundle["after_state"], "data/state listing changed"
