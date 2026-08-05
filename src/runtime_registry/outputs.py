"""Per-run output directory helpers.

The runtime persists every artifact of a single run under
``outputs/YYYY-MM-DD/<pipeline_id>/`` so that no run ever sees or overwrites
another run's artifacts. Older runs may live flat at ``outputs/YYYY-MM-DD/``;
these helpers resolve both layouts so consumers work without knowing which
layout produced a run.

Runtime/output layer only: no computation, no analysis, no contracts.
"""

from __future__ import annotations

from pathlib import Path
from typing import Callable

RunDirPredicate = Callable[[Path], bool]


def date_dir(outputs_base: Path, run_date: str) -> Path:
    """Directory for one calendar date: ``<outputs_base>/<run_date>``."""
    return outputs_base / run_date


def is_run_dir(path: Path) -> bool:
    """True when *path* directly holds a run's core artifacts."""
    return (
        path.is_dir()
        and (path / "summary.json").is_file()
        and (path / "finalize.json").is_file()
    )


def latest_run_dir(
    outputs_base: Path,
    run_date: str | None = None,
    *,
    predicate: RunDirPredicate = is_run_dir,
) -> Path | None:
    """Most recent run directory, or None when nothing is available.

    With *run_date* only runs under ``outputs/<run_date>/`` are considered (a
    legacy flat run directory is itself a candidate). Without it every dated
    directory under *outputs_base* is scanned, and *outputs_base* itself is
    also a candidate when it is directly a run directory. A run directory is
    recognized by *predicate* (default: the core artifacts ``summary.json`` +
    ``finalize.json``).
    """
    if run_date is not None:
        base = date_dir(outputs_base, run_date)
        candidates = _candidates_under(base, predicate)
    else:
        if not outputs_base.is_dir():
            return None
        candidates: list[Path] = []
        if predicate(outputs_base):
            candidates.append(outputs_base)
        for date_path in sorted(outputs_base.iterdir()):
            if not date_path.is_dir():
                continue
            candidates.extend(_candidates_under(date_path, predicate))
    if not candidates:
        return None
    return max(candidates, key=lambda path: path.name)


def _candidates_under(base: Path, predicate: RunDirPredicate) -> list[Path]:
    """Run directories directly under *base* (flat legacy or per-run dirs).

    Per-run subdirectories win over a legacy flat run directory that shares
    the same *base*: when a date directory holds both a flat legacy run and
    newer per-run directories, only the per-run directories are returned.
    """
    if not base.is_dir():
        return []
    result: list[Path] = []
    for child in sorted(base.iterdir()):
        if child.is_dir() and predicate(child):
            result.append(child)
    if result:
        return result
    if predicate(base):
        return [base]
    return []
