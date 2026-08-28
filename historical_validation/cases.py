"""Read-only historical validation cases for Run 001 (Step 1 skeleton).

This module implements the deterministic Trace 044-B cohort selection over
the existing historical lesson artifact and builds a structured, read-only
``ValidationCase`` representation.  It performs NO regime computation, NO
retrieval, and NO orchestration calls.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Iterable

from .spec import (
    BASELINE_ID,
    COHORT_SIZE,
    EVENT_DATE_SORT_KEY,
    FROZEN_COHORT_IDS,
    POSITION_DENOMINATOR,
    POSITIONS,
    TOTAL_EPISODES,
)

_LESSONS_CSV = Path(__file__).resolve().parents[1] / "data" / "lessons" / "cpi_gold_lessons.csv"

_BASELINE_MANIFEST = Path(__file__).resolve().parent / "baseline_manifest.json"


class CohortIntegrityError(ValueError):
    """Raised when the lesson artifact no longer reproduces the pinned
    Run-001 cohort identity (count, content witness, or artifact hash).

    A deliberate baseline upgrade must update ``FROZEN_COHORT_IDS`` and
    ``baseline_manifest.json`` together; this guard never upgrades silently.
    """


def verify_cohort_integrity(rows: list[dict[str, str]], path: Path) -> None:
    """Three-layer integrity lock over the canonical corpus (Sprint 064-A).

    L1 count-lock      : len(rows) == TOTAL_EPISODES
    L2 content witness : position-derived selection == FROZEN_COHORT_IDS
    L3 artifact hash   : sha256(canonical csv) == manifest hash
                         (enforced only for the default corpus path and only
                         when ``baseline_manifest.json`` exists)

    Raises :class:`CohortIntegrityError` naming the violated layer.
    """
    if len(rows) != TOTAL_EPISODES:
        raise CohortIntegrityError(
            f"COHORT L1 COUNT-LOCK FAILED: corpus has {len(rows)} rows, "
            f"baseline {BASELINE_ID} pins TOTAL_EPISODES={TOTAL_EPISODES}. "
            "The cohort selection is positional -- a corpus change re-maps "
            "mid-cohort episodes. Re-derive the Trace 044-B spec consciously "
            "(spec.FROZEN_COHORT_IDS + baseline_manifest.json together)."
        )

    selected_ids = sorted(select_cohort(rows)[i]["lesson_id"] for i in range(COHORT_SIZE))
    frozen_sorted = sorted(FROZEN_COHORT_IDS)
    if selected_ids != frozen_sorted:
        extra = sorted(set(selected_ids) - set(frozen_sorted))
        missing = sorted(set(frozen_sorted) - set(selected_ids))
        raise CohortIntegrityError(
            f"COHORT L2 CONTENT-WITNESS FAILED: position-derived cohort does "
            f"not reproduce baseline {BASELINE_ID}. extra={extra} missing={missing}. "
            "Positions are content-blind: update spec.FROZEN_COHORT_IDS AND "
            "baseline_manifest.json together for a conscious upgrade."
        )

    try:
        resolved = Path(path).resolve()
        default_resolved = _LESSONS_CSV.resolve()
    except OSError:  # pragma: no cover - pathological path
        return
    if resolved != default_resolved or not _BASELINE_MANIFEST.is_file():
        return

    import hashlib
    import json as _json

    manifest = _json.loads(_BASELINE_MANIFEST.read_text(encoding="utf-8"))
    expected = manifest.get("input_artifact_hashes", {}).get(
        "data/lessons/cpi_gold_lessons.csv"
    )
    if not expected:
        return
    actual = hashlib.sha256(Path(path).read_bytes()).hexdigest()
    if actual != expected:
        raise CohortIntegrityError(
            f"COHORT L3 ARTIFACT-HASH LOCK FAILED: sha256(cpi_gold_lessons.csv)"
            f"={actual[:16]}... manifest expects {expected[:16]}.... "
            "Update baseline_manifest.json explicitly to accept a new vintage."
        )

_HORIZON_COLUMNS: tuple[tuple[str, str, str], ...] = (
    ("1d", "gold_return_1d_pct", "gold_direction_1d"),
    ("5d", "gold_return_5d_pct", "gold_direction_5d"),
    ("20d", "gold_return_20d_pct", "gold_direction_20d"),
)

# Validation-only metadata placeholders (Step 1: never filled by this module).
_METADATA_PLACEHOLDERS = ("as_of_date", "regime_cutoff", "knowledge_cutoff", "historical_analogue_cutoff")


@dataclass(frozen=True)
class ActualOutcome:
    """Actual realized outcome for one horizon (evaluation-only)."""

    horizon: str
    return_pct: float
    direction: str


@dataclass(frozen=True)
class ValidationCase:
    """A single structured historical validation case (read-only)."""

    lesson_id: str
    evaluation_date: date
    cpi_pressure: str
    actual_1d: ActualOutcome
    actual_5d: ActualOutcome
    actual_20d: ActualOutcome

    # Validation-only metadata placeholders.
    as_of_date: date | None = None
    regime_cutoff: date | None = None
    knowledge_cutoff: date | None = None
    historical_analogue_cutoff: date | None = None

    @property
    def outcomes(self) -> tuple[ActualOutcome, ActualOutcome, ActualOutcome]:
        return (self.actual_1d, self.actual_5d, self.actual_20d)


def cohort_positions() -> list[int]:
    """Return the Trace 044-B half-open 1-based positions.

    Complements the module constant ``POSITIONS`` with a defensive
    recomputation so the algorithm is verifiable at runtime.
    """
    return [round(TOTAL_EPISODES * i / POSITION_DENOMINATOR) for i in range(1, COHORT_SIZE + 1)]


def load_lessons(path: str | Path | None = None) -> list[dict[str, str]]:
    """Load the historical lesson artifact as a list of row dicts (read-only).

    Uses the standard ``csv`` reader; values are returned as raw strings so
    the downstream coercion is explicit and deterministic.  Rows are sorted
    chronologically by ``event_date`` exactly as Trace 044-B requires.
    """
    lesson_path = Path(path) if path is not None else _LESSONS_CSV
    with lesson_path.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    rows.sort(key=lambda row: row[EVENT_DATE_SORT_KEY])
    return rows


def select_cohort(lessons: list[dict[str, str]]) -> list[dict[str, str]]:
    """Deterministically select the exact 25-episode cohort.

    ``lessons`` must already be sorted chronologically (as returned by
    ``load_lessons``).  Positions are 1-based indices into that ordering, so
    the positional ring is ``pos - 1``.
    """
    selected: list[dict[str, str]] = []
    for pos in cohort_positions():
        selected.append(lessons[pos - 1])
    return selected


def _parse_pressure(row: dict[str, str]) -> str:
    pressure = (row.get("cpi_pressure") or "").strip()
    if not pressure:
        raise ValueError(f"missing cpi_pressure for lesson {row.get('lesson_id', '<unknown>')}")
    return pressure


def _parse_outcome(row: dict[str, str], horizon: str, return_col: str, direction_col: str) -> ActualOutcome:
    return_pct = (row.get(return_col) or "").strip()
    direction = (row.get(direction_col) or "").strip()
    if not return_pct or not direction:
        raise ValueError(
            f"incomplete {horizon}d outcome for lesson {row.get('lesson_id', '<unknown>')}"
        )
    return ActualOutcome(horizon=horizon, return_pct=float(return_pct), direction=direction)


def _case_from_row(row: dict[str, str]) -> ValidationCase:
    lesson_id = row.get("lesson_id")
    if not lesson_id:
        raise ValueError("missing lesson_id in lesson artifact row")
    event_date_str = row.get(EVENT_DATE_SORT_KEY)
    if not event_date_str:
        raise ValueError(f"missing event_date for lesson {lesson_id}")
    evaluation_date = date.fromisoformat(event_date_str)

    outcomes: dict[str, ActualOutcome] = {}
    for horizon, return_col, direction_col in _HORIZON_COLUMNS:
        outcomes[horizon] = _parse_outcome(row, horizon, return_col, direction_col)

    return ValidationCase(
        lesson_id=lesson_id,
        evaluation_date=evaluation_date,
        cpi_pressure=_parse_pressure(row),
        actual_1d=outcomes["1d"],
        actual_5d=outcomes["5d"],
        actual_20d=outcomes["20d"],
    )


def build_validation_cases(
    lessons: list[dict[str, str]] | None = None,
    path: str | Path | None = None,
) -> list[ValidationCase]:
    """Build the structured validation cases for Run 001 (read-only).

    Loads the lesson artifact (unless ``lessons`` is supplied), runs the
    three-layer cohort integrity lock (L1 count / L2 content witness /
    L3 artifact hash against ``baseline_manifest.json``), selects the
    Trace 044-B cohort deterministically, and returns one frozen
    ``ValidationCase`` per selected episode.

    Guards apply only to file-loaded corpora; programmatically supplied
    ``lessons`` (synthetic tests) bypass them by design.
    """
    if lessons is None:
        path = Path(path) if path is not None else _LESSONS_CSV
        episode_rows = load_lessons(path)
        verify_cohort_integrity(episode_rows, path)
    else:
        episode_rows = lessons
    cohort = select_cohort(episode_rows)
    return [_case_from_row(row) for row in cohort]


def group_cases_by_lesson_id(cases: Iterable[ValidationCase]) -> dict[str, ValidationCase]:
    return {case.lesson_id: case for case in cases}
