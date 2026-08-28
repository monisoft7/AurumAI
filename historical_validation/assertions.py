"""Safety assertions for Historical Validation Run 001 (Step 1 skeleton).

Each assertion is a small, deterministic, executable check over the cohort /
cases.  They guard the read-only skeleton against silent drift (e.g. a lesson
artifact that grows, de-duplicates, or changes ordering).
"""

from __future__ import annotations

from datetime import date as date_type
from typing import Iterable, Sequence

from .cases import ValidationCase, cohort_positions


def assert_cohort_selection_is_deterministic() -> None:
    """Positions must be stable across recomputation (no randomness)."""
    expected = [5, 11, 16, 21, 26, 32, 37, 42, 47, 53, 58, 63, 68, 74, 79, 84, 90, 95, 100, 105, 111, 116, 121, 126, 132]
    actual = cohort_positions()
    assert actual == expected, f"cohort positions drifted: {actual}"


def assert_event_dates_are_chronological(cases: Sequence[ValidationCase]) -> None:
    """Evaluation dates must be non-decreasing (chronological)."""
    dates = [case.evaluation_date for case in cases]
    assert dates == sorted(dates), "evaluation dates are not chronological"


def assert_lesson_ids_are_unique(cases: Sequence[ValidationCase]) -> None:
    """Selected lesson_ids must be unique."""
    ids = [case.lesson_id for case in cases]
    assert len(ids) == len(set(ids)), "duplicate lesson_id in cohort"


def assert_evaluation_date_valid(cases: Sequence[ValidationCase]) -> None:
    """evaluation_date must be a real calendar date matching its lesson row."""
    for case in cases:
        assert isinstance(case.evaluation_date, date_type), (
            f"invalid evaluation date for {case.lesson_id}: {case.evaluation_date!r}"
        )


def assert_analogue_cutoff_strictly_before_evaluation(cases: Sequence[ValidationCase]) -> None:
    """historical_analogue_cutoff must be strictly < evaluation_date.

    When the placeholder is unset (None), the assertion passes vacuously;
    the invariant is enforced as soon as a cutoff is materialized.
    """
    for case in cases:
        if case.historical_analogue_cutoff is None:
            continue
        assert case.historical_analogue_cutoff < case.evaluation_date, (
            f"historical analogue cutoff must be strictly < evaluation_date for {case.lesson_id}"
        )


def assert_future_outcomes_evaluation_only(cases: Sequence[ValidationCase]) -> None:
    """Future outcomes belong to the case and must not be reused as history.

    Each outcome horizon is a realized return recorded after evaluation date;
    the case marks them as evaluation-only by construction.
    """
    for case in cases:
        for outcome in case.outcomes:
            assert outcome.horizon in {"1d", "5d", "20d"}, f"unexpected horizon {outcome.horizon}"
            assert outcome.return_pct is not None, f"missing return for {case.lesson_id} {outcome.horizon}"


def run_all_assertions(cases: Iterable[ValidationCase]) -> None:
    """Run every Step-1 safety assertion over the cohort."""
    case_list = list(cases)
    assert_cohort_selection_is_deterministic()
    assert_event_dates_are_chronological(case_list)
    assert_lesson_ids_are_unique(case_list)
    assert_evaluation_date_valid(case_list)
    assert_analogue_cutoff_strictly_before_evaluation(case_list)
    assert_future_outcomes_evaluation_only(case_list)
