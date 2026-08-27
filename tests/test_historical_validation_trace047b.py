"""Focused tests for Correction 047-B -- enriched-corpus smoke revalidation."""

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
    retrieval_layer_record,
    run_enriched_variant,
)
from historical_validation.snapshot import build_snapshot

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

    records, full_a, no_history, full_b = {}, {}, {}, {}
    for lid in SMOKE_IDS:
        case = cases[lid]
        snap = build_snapshot(case)
        records[lid] = retrieval_layer_record(case, snapshot=snap)
        full_a[lid] = run_enriched_variant(
            case, history_enabled=True, run_label="a", snapshot=snap
        )
        no_history[lid] = run_enriched_variant(
            case, history_enabled=False, run_label="a", snapshot=snap
        )
        full_b[lid] = run_enriched_variant(
            case, history_enabled=True, run_label="b", snapshot=snap
        )

    after_files = {rel: _digest(rel) for rel in WATCHED_FILES}
    after_state = sorted(p.name for p in (ROOT / "data" / "state").glob("*"))
    return {
        "records": records,
        "full_a": full_a,
        "no_history": no_history,
        "full_b": full_b,
        "comparisons": {
            lid: compare_variants(full_a[lid], no_history[lid]) for lid in SMOKE_IDS
        },
        "before_files": before_files,
        "after_files": after_files,
        "before_state": before_state,
        "after_state": after_state,
    }


# ---------------------------------------------------------------------------
# 1. PRE vs POST cohort differentiation
# ---------------------------------------------------------------------------


def test_pre_post_cohort_differentiation(bundle) -> None:
    pre_cohorts, post_cohorts = [], []
    for lid in SMOKE_IDS:
        rec = bundle["records"][lid]
        assert rec["episode_trends_asof_safe"] is True, lid
        d = rec["deltas"]
        assert d["cohort_changed_ordered"] is True, lid
        pre_cohorts.append(tuple(rec["pre_run001_baseline"]["match_ids"]))
        post_cohorts.append(tuple(rec["post_047a_enriched"]["match_ids"]))
    assert len(set(pre_cohorts)) == 1, "PRE cohorts not collapsed onto artifact order"
    assert len(set(post_cohorts)) == 3, "POST cohorts failed to differentiate"
    set_changed = sum(
        1 for lid in SMOKE_IDS
        if bundle["records"][lid]["deltas"]["cohort_changed_set"] is True
    )
    assert set_changed >= 2


# ---------------------------------------------------------------------------
# 2. Exact-condition matching on the enriched corpus
# ---------------------------------------------------------------------------


def test_exact_condition_matching(bundle) -> None:
    for lid in SMOKE_IDS:
        post = bundle["records"][lid]["post_047a_enriched"]
        pre = bundle["records"][lid]["pre_run001_baseline"]
        query_condition = post["query_configuration"]["condition"]
        assert len(query_condition) == 3, lid
        assert post["condition_exact_match_count"] >= 1, lid
        assert pre["condition_exact_match_count"] in (None, 0), lid
        top = max(
            post["similarity_breakdown"],
            key=lambda k: post["similarity_breakdown"][k]["overall_similarity"],
        )
        breakdown = post["similarity_breakdown"][top]
        assert breakdown["condition_similarity"] == 1.0, lid
        assert top in post["actual_gold_outcomes_attached"], lid
        assert post["match_ids"][0] == top, lid
        full = bundle["full_a"][lid]
        assert full["lesson_id"] not in full["analogue_match_ids"], lid
        assert post["eligible_episode_count"] == (
            pre["eligible_episode_count"]
        ) > 0, lid


# ---------------------------------------------------------------------------
# 3. Retrieval-method honesty
# ---------------------------------------------------------------------------


def test_retrieval_method_honesty(bundle) -> None:
    for lid in SMOKE_IDS:
        rec = bundle["records"][lid]
        pre_methods = rec["pre_run001_baseline"]["retrieval_method_distribution"]
        assert set(pre_methods) == {"broadened"}, lid
        post = rec["post_047a_enriched"]
        post_methods = post["retrieval_method_distribution"]
        assert "broadened" not in post_methods, lid
        assert set(post_methods) <= {"exact", "contextual"}, lid
        assert post["context_relaxed"] is False, lid

        regime = bundle["full_a"][lid]["snapshot_summary"]["institutional_regime"]
        query_condition = post["query_configuration"]["condition"]
        for m in post["match_honesty"]:
            full_cond = m["historical_condition"] == query_condition
            same_regime = (
                m["historical_regime"].get("regime") == regime
            )
            if m["retrieval_method"] == "exact":
                assert full_cond and same_regime, (lid, m["lesson_id"])
            else:
                assert m["retrieval_method"] == "contextual", (lid, m["lesson_id"])
                assert not (full_cond and same_regime), (lid, m["lesson_id"])
        assert post["actual_gold_outcomes_attached"], lid


# ---------------------------------------------------------------------------
# 4. Similarity differentiation
# ---------------------------------------------------------------------------


def test_similarity_differentiation(bundle) -> None:
    for lid in SMOKE_IDS:
        rec = bundle["records"][lid]
        pre_block = rec["pre_run001_baseline"]
        pre_sims = list(pre_block["overall_similarity_by_match"].values())
        assert pre_sims and max(pre_sims) == min(pre_sims), (
            f"{lid}: PRE similarities unexpectedly differentiated"
        )
        post = rec["post_047a_enriched"]
        breakdown = post["similarity_breakdown"]
        selected = [s["overall_similarity"] for s in breakdown.values()]
        assert selected, lid
        # Every enriched-corpus match outscores the uniform PRE similarity.
        assert min(selected) > max(pre_sims), lid
        # Exact-condition episodes sit at the top of the ranking.
        top_id = post["match_ids"][0]
        assert breakdown[top_id]["condition_similarity"] == 1.0, lid

    mixed = bundle["records"]["CPI_GOLD_2015-06-01"]["post_047a_enriched"]
    mixed_sims = {
        k: (v["overall_similarity"], v["condition_similarity"])
        for k, v in mixed["similarity_breakdown"].items()
    }
    partial = [s for s, c in mixed_sims.values() if c < 1.0]
    assert partial, "expected a mixed exact/partial cohort for 2015-06"
    assert len(set(round(s, 9) for s in mixed["raw_overall_similarities"])) >= 2
    deltas_2015 = bundle["records"]["CPI_GOLD_2015-06-01"]["deltas"]
    assert deltas_2015["post_similarity_spread"] > 0.0
    assert deltas_2015["similarity_differentiated"] is True

    for lid in ("CPI_GOLD_2020-09-01", "CPI_GOLD_2026-02-01"):
        b = bundle["records"][lid]["post_047a_enriched"]["similarity_breakdown"]
        assert all(v["condition_similarity"] == 1.0 for v in b.values()), (
            f"{lid}: cohort not purely exact-condition"
        )


# ---------------------------------------------------------------------------
# 5. Adjudication propagation through the pure chain
# ---------------------------------------------------------------------------


def test_adjudication_propagation(bundle) -> None:
    for lid in SMOKE_IDS:
        full = bundle["full_a"][lid]
        assert full["historical_metadata_present"]["historical_analogue"] is True
        assert full["historical_metadata_present"]["historical_adjudication"] is True
        assert full["historical_adjudication_present"] is True
        assessments = full["candidate_historical_assessments"]
        assert assessments, lid
        ha = next(a for a in assessments if a["historical_assessment"])
        horizons = ha["historical_assessment"]["horizon_results"]
        assert {"1d", "5d", "20d"} <= set(horizons), lid
        assert ha["historical_assessment"]["evidence_ids"] == list(
            full["analogue_match_ids"]
        ), lid
        post = bundle["records"][lid]["post_047a_enriched"]
        attached = post["adjudication_horizons"]
        assert {"1d", "5d", "20d"} <= set(attached), lid
        for hk in ("1d", "5d", "20d"):
            directions = attached[hk]["directions"]
            summary = attached[hk]["direction_summary"]
            if summary == "negative":
                assert directions and all(d == "negative" for d in directions), (lid, hk)
            if summary == "positive":
                assert "positive" in directions and "negative" not in directions, (lid, hk)
        assert bundle["records"][lid]["deltas"]["adjudication_changed"] is True, lid


# ---------------------------------------------------------------------------
# 6. Deterministic repeat (no network)
# ---------------------------------------------------------------------------


def test_deterministic_repeat_no_network(bundle, monkeypatch) -> None:
    def _blocked(*args, **kwargs):
        raise AssertionError("network/socket was opened")

    monkeypatch.setattr(socket, "socket", _blocked)
    monkeypatch.setattr(socket, "create_connection", _blocked)

    cases = {c.lesson_id: c for c in build_validation_cases(path=LESSONS)}
    for lid in SMOKE_IDS:
        snap = build_snapshot(cases[lid])
        rerun = run_enriched_variant(
            cases[lid], history_enabled=True, run_label="c", snapshot=snap
        )
        base = bundle["full_a"][lid]
        assert numeric_leaf_comparison(rerun["serialized_outputs"]) == (
            numeric_leaf_comparison(base["serialized_outputs"])
        ), lid
        assert rerun["decision"] == base["decision"], lid
        assert rerun["selected_thesis_direction"] == base["selected_thesis_direction"], lid
        assert list(rerun["analogue_match_ids"]) == list(base["analogue_match_ids"]), lid


# ---------------------------------------------------------------------------
# 7. FULL vs NO_HISTORY numeric invariance
# ---------------------------------------------------------------------------


def test_full_vs_no_history_numeric_invariance(bundle) -> None:
    for lid in SMOKE_IDS:
        full = bundle["full_a"][lid]
        noh = bundle["no_history"][lid]
        cmp_ = bundle["comparisons"][lid]
        assert full["snapshot_summary"] == noh["snapshot_summary"], lid
        assert cmp_["numeric_leaf_count_full"] == cmp_["numeric_leaf_count_no_history"]
        assert cmp_["numeric_diff_paths"] == [], lid
        assert cmp_["numeric_only_in_full"] == [], lid
        assert cmp_["numeric_only_in_no_history"] == [], lid
        assert cmp_["history_changed_thesis"] is False, lid
        assert cmp_["history_changed_confidence"] is False, lid
        assert cmp_["history_changed_decision"] is False, lid
        assert cmp_["history_changed_composite"] is False, lid

        from decision_engine.contracts import VALID_DECISIONS

        assert full["decision"] == noh["decision"] in VALID_DECISIONS, lid
        assert noh["analogue_match_ids"] == (), lid
        assert full["historical_retrieval_payload_present"] is True, lid
        assert noh["historical_retrieval_payload_present"] is False, lid
        for variant in (full, noh, bundle["full_b"][lid]):
            assert all(variant["no_lookahead_checks"].values()), lid
            assert all(variant["payload_lookahead_checks"].values()), lid


# ---------------------------------------------------------------------------
# 8. Production artifacts unchanged
# ---------------------------------------------------------------------------


def test_production_artifacts_unchanged(bundle) -> None:
    tracked = subprocess.run(
        ["git", "diff", "--name-only", "HEAD", "--", "src", "run.py"],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    assert tracked == "", f"production sources modified: {tracked}"
    assert bundle["before_files"] == bundle["after_files"]
    assert bundle["before_state"] == bundle["after_state"], "data/state listing changed"
