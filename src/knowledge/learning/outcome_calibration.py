"""Final Hardening (Group E, D-05) -- outcome-driven confidence calibration.

Closes the learning loop that Corrections 054 / 055-A started:

    decision -> outcome -> evaluation -> aggregation/calibration
             -> future confidence (via the existing W9 ``oos_ece`` cap)

This module aggregates the immutable ``outcome.evaluated.json`` artifacts
(point-in-time-safe by construction -- decision-time inputs are frozen and
never recomputed) into a single calibration error statistic, persisted to
``runtime/calibration.json``.  The next run reads that file and passes the
value into the pipeline as ``oos_ece``; the W9 ConfidenceEngine already
caps institutional confidence when observed calibration error is high
(> 0.15 -> cap at 0.60, > 0.25 -> cap at 0.35).  No new ML loop, no new
scoring semantics: only existing infrastructure is connected.

Only SCORED decisions contribute (``decision_correct`` is not None);
abstentions (NO_TRADE / INSUFFICIENT_EVIDENCE) are excluded exactly as the
055-A abstention policy prescribes.  Records whose entry_date is not
strictly before the calibration date are excluded -- the loop never learns
from a window that was not point-in-time safe.
"""

from __future__ import annotations

import datetime
import json
from pathlib import Path
from typing import Any

CALIBRATION_FILENAME = "calibration.json"

# Below this many scored outcomes the statistic is not published (the W9 cap
# must not be driven by noise).
MIN_CALIBRATION_SAMPLES = 10


def collect_evaluated_outcomes(
    outputs_root: str | Path,
    *,
    as_of_date: datetime.date | None = None,
) -> list[dict[str, Any]]:
    """Collect evaluated, scored, point-in-time-safe outcome records.

    A record qualifies when:
    - it is an ``outcome.evaluated.json`` with ``status == "evaluated"``;
    - it carries a scored verdict (``decision_correct`` is True/False);
    - ``entry_date`` parses and is strictly before ``as_of_date``
      (default: today UTC) -- decisions evaluated never look ahead.
    """
    root = Path(outputs_root)
    effective_as_of = as_of_date or datetime.datetime.now(
        datetime.timezone.utc
    ).date()
    records: list[dict[str, Any]] = []
    if not root.is_dir():
        return records
    for evaluated_path in sorted(root.glob(f"*/*/{'outcome.evaluated.json'}")):
        try:
            data = json.loads(evaluated_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if not isinstance(data, dict):
            continue
        if data.get("status") != "evaluated":
            continue
        correct = data.get("decision_correct")
        if not isinstance(correct, bool):
            continue
        entry = _parse_entry_date(data.get("entry_date"))
        if entry is None or entry >= effective_as_of:
            continue
        confidence = data.get("institutional_confidence")
        if not isinstance(confidence, (int, float)) or isinstance(confidence, bool):
            continue
        records.append(data)
    return records


def compute_calibration(records: list[dict[str, Any]]) -> dict[str, Any]:
    """Aggregate scored outcome records into calibration statistics.

    ``mean_abs_error`` is the mean absolute gap between emitted institutional
    confidence and realized correctness (1.0/0.0) -- the same statistic the
    W9 ``oos_ece`` cap is designed to consume.
    """
    scored = [
        (float(r["institutional_confidence"]), 1.0 if r["decision_correct"] else 0.0)
        for r in records
    ]
    sample_count = len(scored)
    stats: dict[str, Any] = {
        "sample_count": sample_count,
        "min_samples_required": MIN_CALIBRATION_SAMPLES,
        "mean_abs_error": None,
        "brier": None,
        "accuracy": None,
        "mean_confidence": None,
        "oos_ece": None,
    }
    if sample_count == 0:
        return stats
    confidences = [c for c, _ in scored]
    corrects = [k for _, k in scored]
    mean_abs = sum(abs(c - k) for c, k in scored) / sample_count
    brier = sum((c - k) ** 2 for c, k in scored) / sample_count
    accuracy = sum(corrects) / sample_count
    mean_conf = sum(confidences) / sample_count
    stats.update(
        {
            "mean_abs_error": round(mean_abs, 6),
            "brier": round(brier, 6),
            "accuracy": round(accuracy, 6),
            "mean_confidence": round(mean_conf, 6),
        }
    )
    if sample_count >= MIN_CALIBRATION_SAMPLES:
        stats["oos_ece"] = stats["mean_abs_error"]
    return stats


def update_calibration_file(
    outputs_root: str | Path,
    calibration_path: str | Path,
    *,
    as_of_date: datetime.date | None = None,
) -> dict[str, Any]:
    """Recompute and persist ``runtime/calibration.json``.  Idempotent."""
    effective_as_of = as_of_date or datetime.datetime.now(
        datetime.timezone.utc
    ).date()
    records = collect_evaluated_outcomes(outputs_root, as_of_date=effective_as_of)
    stats = compute_calibration(records)
    payload = {
        "schema_version": "1.0",
        "artifact": "outcome_calibration",
        "as_of": effective_as_of.isoformat(),
        "source": "outcome.evaluated.json sweep",
        "sample_count": stats["sample_count"],
        "oos_ece": stats["oos_ece"],
        "statistics": stats,
        "source_run_ids": [
            str(r.get("run_id"))
            for r in records
            if r.get("run_id")
        ],
    }
    path = Path(calibration_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8"
    )
    return payload


def load_oos_ece(calibration_path: str | Path) -> float | None:
    """Read the published calibration error for the next run's confidence
    engine.  Returns None when no usable calibration exists (feature off --
    exactly the pre-hardening behaviour)."""
    path = Path(calibration_path)
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(data, dict):
        return None
    value = data.get("oos_ece")
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        return None
    value = float(value)
    if value < 0.0 or value > 1.0:
        return None
    return value


def _parse_entry_date(value: Any) -> datetime.date | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        return datetime.date.fromisoformat(value[:10])
    except ValueError:
        return None
