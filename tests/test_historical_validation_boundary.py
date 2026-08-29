"""Focused tests for the Historical Validation boundary correction.

Proves the validation package cannot reach forbidden runtime side-effect
components (static + AST inspection), mutates no production data, and that
the pure-path FULL vs NO_HISTORY harness keeps all prior invariants:
same snapshot, difference only by historical memory, numeric invariance,
determinism, valid first-case result, green no-lookahead assertions.
"""

from __future__ import annotations

import ast
import hashlib
import re
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
from historical_validation.pure_path import run_variant
from historical_validation.snapshot import build_snapshot

FORBIDDEN_TOKENS: tuple[str, ...] = (
    "InstitutionalOrchestrator",
    "with_default_pipeline",
    "_pre_market_scan",
    "PreMarketBriefingAssembler",
    "PositioningDataFetcher",
    "OvernightNewsIngestion",
    "NewsCollector",
    "FOMCCalendarConnector",
    "CheckpointManager",
    "runtime_registry",
    "append_record",
    # runtime fetcher CALL paths (pure static helpers are explicitly allowed)
    "yfinance",
    "fetch_all",
    "_fetch_yfinance_change",
    "_persist_oi_level",
    "FredClient(",
)
FORBIDDEN_IMPORT_ROOTS: frozenset[str] = frozenset(
    {
        "orchestration",
        "news",
        "runtime_registry",
        "simulation",
    }
)
# pre_market/signal_assessment contain PURE components reused by the
# validation adapter (contracts, assembler, static formulas); only their
# runtime fetcher modules are forbidden.
FORBIDDEN_IMPORT_MODULES: frozenset[str] = frozenset(
    {
        "pre_market.briefing_assembler",
        "pre_market.positioning",
        "pre_market.news_ingestion",
        "connectors.dxy_fetcher",
        "connectors.fred_client",
    }
)

WATCHED_FILES: tuple[str, ...] = (
    "data/economic/gold_oi_state.json",
    "data/economic/CPIAUCSL.csv",
    "data/economic/DFII10.csv",
    "data/economic/T5YIE.csv",
    "data/context/dxy/dxy.csv",
    "data/lessons/cpi_gold_lessons.csv",
    "data/economic/output/knowledge.json",
    "data/calendar/cpi_releases.csv",
    "runtime/run_registry.jsonl",
)


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _production_state() -> dict:
    state: dict = {"files": {}, "state_dir": [], "outputs_count": None}
    for rel in WATCHED_FILES:
        p = ROOT / rel
        state["files"][rel] = _digest(p) if p.is_file() else "<missing>"
    state_dir = ROOT / "data" / "state"
    state["state_dir"] = sorted(p.name for p in state_dir.glob("*")) if state_dir.is_dir() else []
    outputs = ROOT / "outputs"
    state["outputs_count"] = sum(1 for _ in outputs.rglob("*")) if outputs.is_dir() else 0
    return state


@pytest.fixture(scope="module")
def case():
    cases = build_validation_cases(path=ROOT / "data" / "lessons" / "cpi_gold_lessons.csv")
    return cases[0]


@pytest.fixture(scope="module")
def case_snapshot(case):
    return build_snapshot(case)


@pytest.fixture(scope="module")
def guarded_bundle(case, case_snapshot):
    """Run the pure harness with production state hashed around it."""
    before = _production_state()
    full_a = run_variant(case, history_enabled=True, run_label="b1", snapshot=case_snapshot)
    no_history = run_variant(case, history_enabled=False, run_label="b1", snapshot=case_snapshot)
    full_b = run_variant(case, history_enabled=True, run_label="b2", snapshot=case_snapshot)
    after = _production_state()
    return {
        "full_a": full_a,
        "no_history": no_history,
        "full_b": full_b,
        "comparison": compare_variants(full_a, no_history),
        "before": before,
        "after": after,
    }


# ---------------------------------------------------------------------------
# 1. Forbidden runtime path is unreachable (static + AST inspection)
# ---------------------------------------------------------------------------


def test_forbidden_runtime_path_unreachable() -> None:
    pkg = ROOT / "historical_validation"
    py_files = sorted(pkg.rglob("*.py"))
    assert py_files, "validation package missing"
    for py in py_files:
        source = py.read_text(encoding="utf-8")
        for token in FORBIDDEN_TOKENS:
            assert token not in source, f"forbidden runtime reference {token!r} in {py.name}"
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    root = alias.name.split(".")[0]
                    assert root not in FORBIDDEN_IMPORT_ROOTS, (
                        f"forbidden import '{alias.name}' in {py.name}"
                    )
            elif isinstance(node, ast.ImportFrom):
                if node.module and node.level == 0:
                    root = node.module.split(".")[0]
                    assert root not in FORBIDDEN_IMPORT_ROOTS, (
                        f"forbidden import from '{node.module}' in {py.name}"
                    )


# ---------------------------------------------------------------------------
# 2/3. Validation does not mutate gold_oi_state.json or any production data
# ---------------------------------------------------------------------------


def test_gold_oi_state_not_mutated(guarded_bundle) -> None:
    b = guarded_bundle
    assert b["before"]["files"]["data/economic/gold_oi_state.json"] == (
        b["after"]["files"]["data/economic/gold_oi_state.json"]
    )


def test_no_production_data_file_mutated(guarded_bundle) -> None:
    b = guarded_bundle
    for rel, digest in b["before"]["files"].items():
        assert digest == b["after"]["files"][rel], f"mutated: {rel}"
    assert b["before"]["state_dir"] == b["after"]["state_dir"], "data/state listing changed"
    assert b["before"]["outputs_count"] == b["after"]["outputs_count"], "outputs/ changed"


# ---------------------------------------------------------------------------
# 4/5. Same snapshot; differ only by historical memory
# ---------------------------------------------------------------------------


def test_full_and_no_history_use_same_snapshot(guarded_bundle) -> None:
    a, n = guarded_bundle["full_a"], guarded_bundle["no_history"]
    assert a["snapshot_summary"] == n["snapshot_summary"]
    assert a["evaluation_date"] == n["evaluation_date"]
    assert a["lesson_id"] == n["lesson_id"]


def test_full_and_no_history_differ_only_by_historical_memory(guarded_bundle) -> None:
    a, n = guarded_bundle["full_a"], guarded_bundle["no_history"]
    assert a["historical_retrieval_payload_present"] is True
    assert a["historical_metadata_present"]["historical_analogue"] is True
    assert a["historical_adjudication_present"] is True
    assert n["historical_retrieval_payload_present"] is False
    assert n["analogue_match_ids"] == ()
    # Run-003 repair (Phase 8): the ONLY structural difference is the
    # historical payload and the ONE bounded HISTORICAL_MEMORY evidence set
    # it feeds.  The memory vote may now legitimately change the thesis,
    # confidence or decision -- those deltas are the measured memory effect,
    # not leakage.  NO_HISTORY is still the strict structural subset.
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
    # Memory is a single estimator: one set regardless of match count.
    assert len(a["analogue_match_ids"]) >= len(mem)
    # A deterministic full repeat is checked in test_deterministic_repeated_execution.


# ---------------------------------------------------------------------------
# 6. Deterministic repeated execution
# ---------------------------------------------------------------------------


def test_deterministic_repeated_execution(guarded_bundle) -> None:
    a, b = guarded_bundle["full_a"], guarded_bundle["full_b"]
    assert numeric_leaf_comparison(a["serialized_outputs"]) == numeric_leaf_comparison(
        b["serialized_outputs"]
    )
    assert a["decision"] == b["decision"]
    assert a["selected_thesis_direction"] == b["selected_thesis_direction"]
    assert a["institutional_confidence"] == b["institutional_confidence"]
    assert list(a["analogue_match_ids"]) == list(b["analogue_match_ids"])


# ---------------------------------------------------------------------------
# 7. First historical case still produces a valid result
# ---------------------------------------------------------------------------


def test_first_case_produces_valid_result(guarded_bundle, case) -> None:
    result = guarded_bundle["full_a"]
    assert result["lesson_id"] == case.lesson_id == "CPI_GOLD_2015-06-01"
    assert result["selected_thesis_direction"] in {"bullish", "bearish", "neutral"}
    assert result["evaluated_thesis_directions"], "no candidate directions evaluated"
    from decision_engine.contracts import VALID_DECISIONS

    assert result["decision"] in VALID_DECISIONS
    assert result["candidate_historical_assessments"], "assessment missing"
    entry = result["candidate_historical_assessments"][0]
    assert entry["historical_assessment"] is not None
    horizons = entry["historical_assessment"]["horizon_results"]
    assert set(("1d", "5d", "20d")) & set(horizons)


# ---------------------------------------------------------------------------
# 8. No lookahead assertions remain green
# ---------------------------------------------------------------------------


def test_no_lookahead_assertions_green(guarded_bundle, case) -> None:
    for variant in ("full_a", "no_history", "full_b"):
        r = guarded_bundle[variant]
        assert all(r["no_lookahead_checks"].values()), (
            f"{variant}: {r['no_lookahead_checks']}"
        )
        assert all(r["payload_lookahead_checks"].values()), (
            f"{variant}: {r['payload_lookahead_checks']}"
        )
    cutoff = case.evaluation_date.isoformat()
    dates_by_id = {}
    import csv

    with (ROOT / "data" / "lessons" / "cpi_gold_lessons.csv").open(
        "r", encoding="utf-8", newline=""
    ) as fh:
        for row in csv.DictReader(fh):
            dates_by_id[row["lesson_id"]] = row["event_date"]
    for lesson_id in guarded_bundle["full_a"]["analogue_match_ids"]:
        assert lesson_id != case.lesson_id
        assert dates_by_id[lesson_id] < cutoff
