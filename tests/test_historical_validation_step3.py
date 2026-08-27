"""Focused tests for Historical Validation Run 001 -- Step 3 single-case replay.

Covers: first cohort case uses its ValidationSnapshot, query equals
snapshot-derived values, current lesson excluded, future lessons excluded,
current/today context functions never invoked, deterministic repeated
result, provenance preserved verbatim, honest retrieval_method, and no
production source changes.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from historical_validation.analogue import (
    DEFAULT_TOP_K,
    asof_episode_corpus,
    run_step3,
    snapshot_query,
)
from historical_validation.cases import build_validation_cases
from historical_validation.snapshot import SnapshotConfig, ValidationSnapshot, build_snapshot

LESSONS_PATH = ROOT / "data" / "lessons" / "cpi_gold_lessons.csv"
FIRST_COHORT_LESSON_ID = "CPI_GOLD_2015-06-01"
FIRST_COHORT_DATE = FIRST_COHORT_LESSON_ID.removeprefix("CPI_GOLD_")


@pytest.fixture(scope="module")
def first_case():
    cases = build_validation_cases(path=LESSONS_PATH)
    return cases[0]


@pytest.fixture(scope="module")
def first_case_snapshot(first_case) -> ValidationSnapshot:
    return build_snapshot(first_case, SnapshotConfig())


@pytest.fixture(scope="module")
def step3_result(first_case, first_case_snapshot):
    return run_step3(first_case, snapshot=first_case_snapshot)


# ---------------------------------------------------------------------------
# 1. First cohort case uses its ValidationSnapshot
# ---------------------------------------------------------------------------


def test_first_cohort_case_uses_its_snapshot(
    first_case, first_case_snapshot, step3_result
) -> None:
    assert first_case.lesson_id == FIRST_COHORT_LESSON_ID
    result = step3_result
    assert result["lesson_id"] == first_case.lesson_id == first_case_snapshot.lesson_id
    assert str(result["evaluation_date"]) == FIRST_COHORT_DATE
    summary = result["snapshot_summary"]
    assert summary["cpi_pressure"] == first_case_snapshot.cpi_pressure
    assert summary["us10y_trend"] == first_case_snapshot.us10y_trend
    assert summary["dxy_trend"] == first_case_snapshot.dxy_trend
    assert summary["institutional_regime"] == first_case_snapshot.institutional_regime
    assert summary["knowledge_cutoff"] == first_case_snapshot.knowledge_cutoff
    assert summary["analogue_cutoff"] == first_case_snapshot.analogue_cutoff


# ---------------------------------------------------------------------------
# 2. Query equals snapshot-derived values
# ---------------------------------------------------------------------------


def test_query_equals_snapshot_derived_values(
    first_case_snapshot, step3_result
) -> None:
    query = snapshot_query(first_case_snapshot)
    result_query = step3_result["query"]
    assert result_query["event_type"] == query.event_type == "CPI"
    assert result_query["condition"] == dict(query.condition) == {
        "cpi_pressure": first_case_snapshot.cpi_pressure,
        "us10y_trend": first_case_snapshot.us10y_trend,
        "dxy_trend": first_case_snapshot.dxy_trend,
    }
    assert result_query["institutional_context"] == dict(query.institutional_context) == {
        "regime": first_case_snapshot.institutional_regime
    }


# ---------------------------------------------------------------------------
# 3/4. Current lesson excluded; future lessons excluded
# ---------------------------------------------------------------------------


def test_current_lesson_excluded(first_case, first_case_snapshot, step3_result) -> None:
    indexer, eligible_ids = asof_episode_corpus(
        first_case.evaluation_date, LESSONS_PATH
    )
    corpus_ids = {s.state_id for s in indexer._ensure_sorted()}
    assert first_case.lesson_id not in corpus_ids
    assert first_case.lesson_id not in eligible_ids
    assert first_case.lesson_id not in set(step3_result["eligible_episode_ids"])
    assert first_case.lesson_id not in set(step3_result["analogue_match_ids"])
    assert step3_result["no_lookahead_verification"]["current_episode_excluded_from_corpus"]
    assert step3_result["no_lookahead_verification"]["current_episode_not_retrieved"]


def test_future_lessons_excluded(first_case, step3_result) -> None:
    cutoff = first_case.evaluation_date.isoformat()
    indexer, _ = asof_episode_corpus(first_case.evaluation_date, LESSONS_PATH)
    states = indexer._ensure_sorted()
    assert all(s.date < cutoff for s in states)
    # A strictly later episode must not be in the corpus or any match.
    future_id = "CPI_GOLD_2015-07-01"
    assert future_id not in {s.state_id for s in states}
    assert future_id not in set(step3_result["analogue_match_ids"])
    assert step3_result["no_lookahead_verification"]["corpus_strictly_before_evaluation"]
    assert step3_result["no_lookahead_verification"]["matches_within_eligible_corpus"]
    assert step3_result["no_lookahead_verification"]["future_outcomes_evaluation_only"]


# ---------------------------------------------------------------------------
# 5. Current/today context functions are not called
# ---------------------------------------------------------------------------


def test_current_context_functions_not_called(
    first_case, first_case_snapshot, monkeypatch
) -> None:
    def _forbidden(*args, **kwargs):
        raise AssertionError("today/current context function was invoked")

    import evidence_reasoning.historical_analogue as ha
    from knowledge.context.dxy import DXYContextEnricher
    from knowledge.context.yields import YieldContextEnricher
    from knowledge.regime.institutional_regime_detector import (
        InstitutionalRegimeDetector,
    )

    monkeypatch.setattr(ha, "current_context_trends", _forbidden)
    monkeypatch.setattr(YieldContextEnricher, "enrich", _forbidden)
    monkeypatch.setattr(DXYContextEnricher, "enrich", _forbidden)
    # Snapshot is built BEFORE patching; replay must not re-fit today's regime.
    monkeypatch.setattr(InstitutionalRegimeDetector, "fit", _forbidden)

    result = run_step3(first_case, snapshot=first_case_snapshot)
    assert result["lesson_id"] == FIRST_COHORT_LESSON_ID


# ---------------------------------------------------------------------------
# 6. Deterministic repeated result
# ---------------------------------------------------------------------------


def test_deterministic_repeated_result(first_case) -> None:
    first = run_step3(first_case)
    second = run_step3(first_case)
    assert first == second


# ---------------------------------------------------------------------------
# 7. Provenance preserved
# ---------------------------------------------------------------------------


def test_provenance_preserved(step3_result) -> None:
    adjudication = step3_result["historical_adjudication"]
    assert adjudication is not None
    match_provenance = step3_result["provenance"]["match_provenance"]

    # Every adjudication input carries the match provenance VERBATIM --
    # values copied through, never fabricated.
    inputs_by_lesson: dict[str, dict] = {}
    for horizon in ("1d", "5d", "20d"):
        entry = adjudication.get("horizon_results", {}).get(horizon)
        if not entry:
            continue
        for item in entry.get("inputs") or []:
            inputs_by_lesson[item["lesson_id"]] = item

    for lesson_id, prov in match_provenance.items():
        item = inputs_by_lesson[lesson_id]
        assert item.get("source_artifact_path") == prov.get("source_artifact_path")
        assert item.get("source_artifact_sha256") == prov.get("source_artifact_sha256")

    # evidence_ids derive only from actual analogue match ids -- no synthetic ids.
    assert set(adjudication["evidence_ids"]) <= set(step3_result["analogue_match_ids"])

    # Assessment sources mirror adjudication provenance verbatim.
    assessment = step3_result["candidate_historical_assessment"]
    assert assessment is not None
    source_ids = [s["lesson_id"] for s in assessment["provenance"]["sources"]]
    assert source_ids == list(dict.fromkeys(adjudication["evidence_ids"]))
    assert step3_result["provenance"]["trace_id"] == "044-B"


# ---------------------------------------------------------------------------
# 8. Honest retrieval_method
# ---------------------------------------------------------------------------


def test_honest_retrieval_method(first_case_snapshot, step3_result) -> None:
    methods = step3_result["retrieval_method_per_match"]
    assert methods, "expected at least one analogue match"
    allowed = {"exact", "contextual", "broadened", "weak"}
    query_condition = step3_result["query"]["condition"]
    query_regime = step3_result["query"]["institutional_context"].get("regime")
    breakdown = step3_result["similarity_breakdown"]
    for lesson_id, method in methods.items():
        assert method in allowed
        similarity = breakdown[lesson_id]
        assert similarity["retrieval_method"] == method
        if method == "exact":
            # "exact" may only be claimed for a TRUE full-condition match
            # including the institutional regime.
            assert step3_result["context_relaxed"] is False
            assert query_regime is not None
    # The current artifact's episodes carry only cpi_pressure (plus no regime),
    # so no match can honestly claim "exact" against the full snapshot query.
    assert "exact" not in set(methods.values())
    assert step3_result["aggregate_scope"] == "top_k"
    assert step3_result["eligible_episode_count"] > len(methods) >= 1
    assert len(methods) <= DEFAULT_TOP_K


# ---------------------------------------------------------------------------
# 9. No production source changes
# ---------------------------------------------------------------------------


def test_no_production_source_changes() -> None:
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
    adapter_source = (ROOT / "historical_validation" / "analogue.py").read_text(
        encoding="utf-8"
    )
    for forbidden in ('"w"', '"w+"', 'to_csv', 'write_text', 'atomic_write', 'data/state', 'outputs/', 'runtime/'):
        assert forbidden not in adapter_source, f"write/persist detected: {forbidden}"
