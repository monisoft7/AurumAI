"""Focused tests for Historical Validation Run 001 -- Step 1 skeleton.

Covers: exact 25-episode selection, determinism, chronological order,
unique lesson_ids, complete 1d/5d/20d outcome presence, evaluation date
correctness, validation-only metadata placeholders, same-event exclusion
boundary (strictly < evaluation_date), and no production pipeline changes.
"""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from historical_validation.assertions import (
    assert_analogue_cutoff_strictly_before_evaluation,
    assert_cohort_selection_is_deterministic,
    assert_evaluation_date_valid,
    assert_event_dates_are_chronological,
    assert_future_outcomes_evaluation_only,
    assert_lesson_ids_are_unique,
)
from historical_validation.cases import (
    ValidationCase,
    build_validation_cases,
    cohort_positions,
    load_lessons,
    select_cohort,
)
from historical_validation.spec import COHORT_SIZE, TOTAL_EPISODES

LESSONS_PATH = ROOT / "data" / "lessons" / "cpi_gold_lessons.csv"

EXPECTED_COHORT_LESSON_IDS: tuple[str, ...] = (
    "CPI_GOLD_2015-06-01",
    "CPI_GOLD_2015-12-01",
    "CPI_GOLD_2016-05-01",
    "CPI_GOLD_2016-10-01",
    "CPI_GOLD_2017-03-01",
    "CPI_GOLD_2017-09-01",
    "CPI_GOLD_2018-02-01",
    "CPI_GOLD_2018-07-01",
    "CPI_GOLD_2018-12-01",
    "CPI_GOLD_2019-06-01",
    "CPI_GOLD_2019-11-01",
    "CPI_GOLD_2020-04-01",
    "CPI_GOLD_2020-09-01",
    "CPI_GOLD_2021-03-01",
    "CPI_GOLD_2021-08-01",
    "CPI_GOLD_2022-01-01",
    "CPI_GOLD_2022-07-01",
    "CPI_GOLD_2022-12-01",
    "CPI_GOLD_2023-05-01",
    "CPI_GOLD_2023-10-01",
    "CPI_GOLD_2024-04-01",
    "CPI_GOLD_2024-09-01",
    "CPI_GOLD_2025-02-01",
    "CPI_GOLD_2025-07-01",
    "CPI_GOLD_2026-02-01",
)


def _build() -> list[ValidationCase]:
    return build_validation_cases(path=LESSONS_PATH)


def test_lesson_artifact_has_137_episodes() -> None:
    rows = load_lessons(LESSONS_PATH)
    assert len(rows) == TOTAL_EPISODES == 137


def test_exact_25_episode_selection() -> None:
    cases = _build()
    assert len(cases) == COHORT_SIZE == 25
    assert [c.lesson_id for c in cases] == list(EXPECTED_COHORT_LESSON_IDS)


def test_deterministic_repeated_selection() -> None:
    first = [c.lesson_id for c in _build()]
    second = [c.lesson_id for c in _build()]
    assert first == second
    assert cohort_positions() == cohort_positions()


def test_chronological_ordering() -> None:
    cases = _build()
    dates = [c.evaluation_date for c in cases]
    assert dates == sorted(dates)
    assert_event_dates_are_chronological(cases)


def test_unique_lesson_ids() -> None:
    cases = _build()
    assert_lesson_ids_are_unique(cases)
    ids = [c.lesson_id for c in cases]
    assert len(ids) == len(set(ids))


def test_complete_1d_5d_20d_outcome_presence() -> None:
    for case in _build():
        for horizon in ("1d", "5d", "20d"):
            outcomes = {o.horizon: o for o in case.outcomes}
            outcome = outcomes[horizon]
            assert outcome.return_pct is not None
            assert outcome.direction in {"UP", "DOWN", "FLAT"}


def test_evaluation_date_correctness() -> None:
    cases = _build()
    rows_by_id = {r["lesson_id"]: r for r in load_lessons(LESSONS_PATH)}
    for case in cases:
        expected = date.fromisoformat(rows_by_id[case.lesson_id]["event_date"])
        assert case.evaluation_date == expected
        assert case.evaluation_date.year >= 2015
    assert_evaluation_date_valid(cases)


def test_validation_only_metadata_placeholders() -> None:
    for case in _build():
        # Placeholders are present and, in Step 1, unset (None).
        for attr in (
            "as_of_date",
            "regime_cutoff",
            "knowledge_cutoff",
            "historical_analogue_cutoff",
        ):
            assert hasattr(case, attr)
            assert getattr(case, attr) is None
        # cpi_pressure from artifact is preserved.
        assert case.cpi_pressure in {"inflation_pressure_up", "inflation_pressure_down"}


def test_same_event_exclusion_boundary_strictly_less_than_eval() -> None:
    cases = _build()
    for case in cases:
        # Same-event boundary: analogue cutoff at evaluation_date is INVALID.
        import dataclasses

        same_event = dataclasses.replace(
            case, historical_analogue_cutoff=case.evaluation_date
        )
        try:
            assert_analogue_cutoff_strictly_before_evaluation([same_event])
        except AssertionError:
            pass
        else:
            raise AssertionError(
                f"cutoff == evaluation_date must fail for {case.lesson_id}"
            )

        # Cutoff strictly before evaluation_date is valid.
        prior = dataclasses.replace(
            case,
            historical_analogue_cutoff=date.fromordinal(
                case.evaluation_date.toordinal() - 1
            ),
        )
        assert_analogue_cutoff_strictly_before_evaluation([prior])

    assert_future_outcomes_evaluation_only(cases)


def test_no_production_pipeline_changes() -> None:
    # The skeleton must live outside the production source tree.
    assert ROOT.joinpath("historical_validation").is_dir()
    assert not list(ROOT.joinpath("historical_validation").rglob("*orchestration*"))
    # No source file under src/ imports this analysis module.
    # AST-based: docstring/comment mentions are not imports (the facts-layer
    # contracts legitimately reference the semantics by name in prose).
    import ast as _ast

    src = ROOT / "src"
    if src.is_dir():
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
