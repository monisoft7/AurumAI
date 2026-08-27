"""Focused tests for Historical Validation Run 001 -- Step 4 FULL vs NO_HISTORY.

Covers: identical snapshots between variants, identical candidate generation,
identical non-historical numerics, historical metadata present only in FULL,
no unexpected numeric leakage, deterministic repeated execution, exact
measured decision difference/invariance (including no-lookahead of the
FULL analogue payload), and no production source changes.

Each pipeline execution takes roughly two minutes; the module-scoped bundle
runs exactly three executions (FULL a, NO_HISTORY, FULL b).
"""

from __future__ import annotations

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

from historical_validation.cases import (
    build_validation_cases,
    load_lessons,
)
from historical_validation.compare import (
    HISTORICAL_METADATA_KEYS,
    compare_variants,
    numeric_leaf_comparison,
    run_variant,
)
from historical_validation.snapshot import build_snapshot


@pytest.fixture(scope="module")
def case():
    cases = build_validation_cases(path=ROOT / "data" / "lessons" / "cpi_gold_lessons.csv")
    return cases[0]


@pytest.fixture(scope="module")
def case_snapshot(case):
    return build_snapshot(case)


@pytest.fixture(scope="module")
def bundle(case, case_snapshot):
    """Three pipeline executions shared by every test in this module."""
    full_a = run_variant(
        case, history_enabled=True, run_label="t4a", snapshot=case_snapshot
    )
    no_history = run_variant(
        case, history_enabled=False, run_label="t4n", snapshot=case_snapshot
    )
    full_b = run_variant(
        case, history_enabled=True, run_label="t4b", snapshot=case_snapshot
    )
    return {
        "full_a": full_a,
        "no_history": no_history,
        "full_b": full_b,
        "comparison": compare_variants(full_a, no_history),
    }


# ---------------------------------------------------------------------------
# 1. Identical snapshot between FULL and NO_HISTORY
# ---------------------------------------------------------------------------


def test_identical_snapshot_between_variants(bundle) -> None:
    full, nohist = bundle["full_a"], bundle["no_history"]
    assert not full["history_enabled"] is nohist["history_enabled"]
    assert full["snapshot_summary"] == nohist["snapshot_summary"]
    assert full["evaluation_date"] == nohist["evaluation_date"]
    assert full["lesson_id"] == nohist["lesson_id"] == "CPI_GOLD_2015-06-01"
    assert all(full["no_lookahead_checks"].values())
    assert all(nohist["no_lookahead_checks"].values())


# ---------------------------------------------------------------------------
# 2. Identical candidate generation
# ---------------------------------------------------------------------------


def test_identical_candidate_generation(bundle) -> None:
    full, nohist = bundle["full_a"], bundle["no_history"]
    assert (
        full["evaluated_thesis_directions"] == nohist["evaluated_thesis_directions"]
    )
    assert (
        full["institutional_support_by_direction"]
        == nohist["institutional_support_by_direction"]
    )
    assert full["selected_thesis_direction"] == nohist["selected_thesis_direction"]
    assert bundle["comparison"]["history_changed_thesis"] is False


# ---------------------------------------------------------------------------
# 3. Identical non-historical numeric inputs
# ---------------------------------------------------------------------------


def test_identical_non_historical_numeric_inputs(bundle) -> None:
    full, nohist = bundle["full_a"], bundle["no_history"]
    nums_full = numeric_leaf_comparison(full["serialized_outputs"])
    nums_nohist = numeric_leaf_comparison(nohist["serialized_outputs"])
    assert set(nums_full) == set(nums_nohist)
    assert nums_full == nums_nohist
    assert full["institutional_confidence"] == nohist["institutional_confidence"]
    assert full["confidence_payload_summary"] == nohist["confidence_payload_summary"]
    assert full["risk_reward_summary"] == nohist["risk_reward_summary"]
    assert full["risk_reward_ratios"] == nohist["risk_reward_ratios"]


# ---------------------------------------------------------------------------
# 4. Historical metadata exists only in FULL
# ---------------------------------------------------------------------------


def test_historical_metadata_exists_only_in_full(bundle) -> None:
    full, nohist = bundle["full_a"], bundle["no_history"]

    for key in ("historical_analogue", "historical_adjudication",
                "contextual_historical_adjudication"):
        assert key in HISTORICAL_METADATA_KEYS
        assert full["historical_metadata_present"][key] is True
        assert nohist["historical_metadata_present"][key] is False

    assert full["historical_retrieval_payload_present"] is True
    assert full["analogue_match_ids"], "FULL must retrieve analogues"

    assert nohist["historical_retrieval_payload_present"] is False
    assert nohist["analogue_match_ids"] == ()

    # Candidate historical assessments: populated only in FULL.
    full_assessments = full["candidate_historical_assessments"] or []
    assert full_assessments
    assert any(e.get("historical_assessment") for e in full_assessments)
    nohist_assessments = nohist["candidate_historical_assessments"] or []
    if nohist_assessments:
        assert all(e.get("historical_assessment") is None for e in nohist_assessments)


# ---------------------------------------------------------------------------
# 5. No unexpected numeric leakage
# ---------------------------------------------------------------------------


def test_no_unexpected_numeric_leakage(bundle) -> None:
    cmp = bundle["comparison"]
    assert cmp["numeric_leaf_count_full"] == cmp["numeric_leaf_count_no_history"]
    assert cmp["numeric_diff_paths"] == []
    assert cmp["numeric_only_in_full"] == []
    assert cmp["numeric_only_in_no_history"] == []
    assert cmp["history_changed_confidence"] is False
    assert cmp["history_changed_composite"] is False


# ---------------------------------------------------------------------------
# 6. Deterministic repeated execution
# ---------------------------------------------------------------------------


def test_deterministic_repeated_execution(bundle) -> None:
    a, b = bundle["full_a"], bundle["full_b"]
    assert numeric_leaf_comparison(a["serialized_outputs"]) == numeric_leaf_comparison(
        b["serialized_outputs"]
    )
    assert a["evaluated_thesis_directions"] == b["evaluated_thesis_directions"]
    assert (
        a["institutional_support_by_direction"]
        == b["institutional_support_by_direction"]
    )
    assert a["selected_thesis_direction"] == b["selected_thesis_direction"]
    assert a["decision"] == b["decision"]
    assert a["institutional_confidence"] == b["institutional_confidence"]


# ---------------------------------------------------------------------------
# 7. Exact measured decision difference / invariance (+ payload no-lookahead)
# ---------------------------------------------------------------------------


def test_exact_measured_decision_difference_invariance(bundle, case) -> None:
    cmp = bundle["comparison"]
    full, nohist = bundle["full_a"], bundle["no_history"]

    # Measured outcome for this case: decision is invariant.
    assert full["decision"] == nohist["decision"] == "NO_TRADE"
    assert full["decision_risk_reward_summary"] == nohist["decision_risk_reward_summary"]
    assert cmp["history_changed_decision"] is False

    # Consistency: recorded booleans reflect the measured payloads.
    assert cmp["history_changed_thesis"] is (
        full["selected_thesis_direction"] != nohist["selected_thesis_direction"]
        or full["evaluated_thesis_directions"]
        != nohist["evaluated_thesis_directions"]
    )

    # The FULL analogue payload itself must respect the as-of boundary:
    # no self-match and no future episode may appear as an analogue.
    cutoff = case.evaluation_date.isoformat()
    dates_by_id = {
        row["lesson_id"]: row["event_date"] for row in load_lessons(None)
    }
    for lesson_id in full["analogue_match_ids"]:
        assert lesson_id != case.lesson_id, "current episode retrieved as own analogue"
        assert dates_by_id[lesson_id] < cutoff, f"future episode analogue: {lesson_id}"


# ---------------------------------------------------------------------------
# 8. No production source changes
# ---------------------------------------------------------------------------


def test_no_production_source_changes() -> None:
    tracked = subprocess.run(
        ["git", "diff", "--name-only", "HEAD", "--", "src", "run.py"],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    assert tracked == "", f"production sources modified: {tracked}"
    # AST-based import scan (prose mentions are not imports).
    import ast as _ast

    src = ROOT / "src"
    for py in src.rglob("*.py"):
        tree = _ast.parse(py.read_text(encoding="utf-8", errors="ignore"))
        for node in _ast.walk(tree):
            if isinstance(node, _ast.Import):
                names = [alias.name for alias in node.names]
            elif isinstance(node, _ast.ImportFrom):
                names = [node.module or ""]
            else:
                continue
            for name in names:
                assert "historical_validation" not in name, (
                    f"production import: {py}: {name}"
                )
