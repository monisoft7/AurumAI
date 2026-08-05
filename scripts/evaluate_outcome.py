"""AurumAI institutional outcome evaluator.

Reads the pending ``outputs/YYYY-MM-DD/<pipeline_id>/outcome.json`` record
emitted by the runtime, computes the realized gold (XAU/USD) return over the
configured horizon using the existing simulation correctness engine, and
writes ``outputs/YYYY-MM-DD/<pipeline_id>/outcome.evaluated.json``.

The evaluator is strictly additive:
- It reuses only the existing simulation helpers ``_compute_gold_return``,
  ``_classify_actual_direction``, and ``_decision_is_correct``.
- It never modifies ``outcome.json``, ``summary.json``, ``finalize.json``,
  or any checkpoint.

Usage:
    python scripts/evaluate_outcome.py [--output-dir PATH]
    python scripts/evaluate_outcome.py [--output-dir PATH] [--force]

``--output-dir`` may point at a run directory or at a date directory;
without it the latest run holding an ``outcome.json`` is used.

Exit codes:
    0  evaluated (or pending while the horizon has not yet elapsed)
    2  inputs missing or invalid
"""

from __future__ import annotations

import argparse
import datetime
import json
import sys
from pathlib import Path
from typing import Any

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from runtime_registry.outputs import latest_run_dir  # noqa: E402
from simulation.historical_replay import (  # noqa: E402
    _classify_actual_direction,
    _compute_gold_return,
    _decision_is_correct,
)

EXIT_OK = 0
EXIT_INPUT_ERROR = 2

SCHEMA_VERSION = "1.0"
ARTIFACT = "decision_outcome"
PENDING_STATUS = "pending"
EVALUATED_STATUS = "evaluated"


def _write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def _load_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as fh:
        data = json.load(fh)
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return data


def _resolve_gold_path(raw: str) -> Path:
    path = Path(raw)
    if not path.is_absolute():
        path = ROOT / path
    return path


def _load_gold(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    gold = pd.read_csv(path)
    if "Date" not in gold.columns or "Close" not in gold.columns:
        return pd.DataFrame()
    gold["Date"] = pd.to_datetime(gold["Date"], errors="coerce")
    gold = gold.dropna(subset=["Date"]).sort_values("Date")
    return gold


def _entry_datetime(entry_date: str | None) -> datetime.datetime | None:
    if not entry_date:
        return None
    try:
        return datetime.datetime.fromisoformat(str(entry_date))
    except (TypeError, ValueError):
        return None


def _gold_failure_reason(
    gold: pd.DataFrame,
    entry: datetime.datetime,
    horizon_days: int,
) -> str | None:
    if gold.empty:
        return "gold data unavailable"
    if not bool((gold["Date"] <= entry).any()):
        return "entry date before gold data range"
    target = entry + datetime.timedelta(days=int(horizon_days or 0))
    if not bool((gold["Date"] >= target).any()):
        return "evaluation horizon not yet elapsed in gold data"
    return None


def _utc_now_iso() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def evaluate_run(run_dir: Path, force: bool = False) -> dict[str, Any]:
    """Evaluate one pending outcome record in *run_dir*.

    Returns ``{"record": ..., "wrote": bool, "path": Path}``.  The pending
    artifact is never modified.  An already evaluated run is not re-evaluated
    unless *force* is true; the evaluated artifact is written by this function.
    """
    outcome_path = run_dir / "outcome.json"
    data = _load_json(outcome_path)

    evaluated_path = run_dir / "outcome.evaluated.json"
    if evaluated_path.exists() and not force:
        existing = _load_json(evaluated_path)
        if existing.get("status") == EVALUATED_STATUS:
            return {"record": existing, "wrote": False, "path": evaluated_path}

    notes: list[str] = []
    record: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "artifact": ARTIFACT,
        "status": PENDING_STATUS,
        "run_id": data.get("run_id"),
        "decision": data.get("decision"),
        "institutional_confidence": data.get("institutional_confidence"),
        "event_type": data.get("event_type"),
        "asset": data.get("asset", "XAU/USD"),
        "horizon_days": data.get("horizon_days"),
        "gold_path": data.get("gold_path"),
        "entry_date": data.get("entry_date"),
        "realized_gold_return": None,
        "decision_correct": None,
        "evaluation_timestamp": None,
        "notes": notes,
        "decision_id": data.get("decision_id"),
    }

    decision = record["decision"]
    entry = _entry_datetime(record["entry_date"])
    if entry is None:
        notes.append("entry_date missing or invalid; cannot evaluate")
        record["status"] = EVALUATED_STATUS
        record["evaluation_timestamp"] = _utc_now_iso()
    else:
        horizon = int(record["horizon_days"] or 0)
        gold = _load_gold(_resolve_gold_path(str(record["gold_path"] or "")))
        reason = _gold_failure_reason(gold, entry, horizon)
        if reason is not None:
            notes.append(reason)
            if reason == "evaluation horizon not yet elapsed in gold data":
                record["status"] = PENDING_STATUS
            else:
                record["status"] = EVALUATED_STATUS
                record["evaluation_timestamp"] = _utc_now_iso()
        else:
            realized = _compute_gold_return(gold, entry, horizon_days=horizon)
            if realized is not None:
                record["realized_gold_return"] = round(float(realized), 4)
                direction = _classify_actual_direction(float(realized))
                record["decision_correct"] = _decision_is_correct(decision, direction)
            record["status"] = EVALUATED_STATUS
            record["evaluation_timestamp"] = _utc_now_iso()

    _write_json(evaluated_path, record)
    return {"record": record, "wrote": True, "path": evaluated_path}


def _has_outcome(path: Path) -> bool:
    return (path / "outcome.json").is_file()


def _latest_run_dir() -> Path | None:
    return latest_run_dir(ROOT / "outputs", predicate=_has_outcome)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python scripts/evaluate_outcome.py",
        description="Evaluate the realized outcome of an institutional run "
                    "using the existing simulation correctness engine.",
    )
    parser.add_argument(
        "--output-dir",
        default=None,
        help="Run output directory containing outcome.json "
             "(default: latest run under outputs/YYYY-MM-DD/<pipeline_id>/ "
             "holding outcome.json).",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Allow re-evaluation of an already evaluated run "
             "(writes a versioned sibling file).",
    )
    args = parser.parse_args(argv)

    if args.output_dir:
        run_dir = Path(args.output_dir)
        resolved = latest_run_dir(run_dir, predicate=_has_outcome)
        if resolved is not None:
            run_dir = resolved
    else:
        run_dir = _latest_run_dir() or Path()
    if not run_dir.exists() or not (run_dir / "outcome.json").exists():
        print(f"outcome.json not found in {run_dir}", file=sys.stderr)
        return EXIT_INPUT_ERROR

    try:
        result = evaluate_run(run_dir, force=args.force)
    except Exception as exc:  # pragma: no cover - defensive
        print(f"outcome evaluation failed for {run_dir}: {exc}", file=sys.stderr)
        return EXIT_INPUT_ERROR

    record = result["record"]
    if result["wrote"]:
        print(f"wrote {result['path']}")
        print(f"  run_id                : {record['run_id']}")
        print(f"  status                : {record['status']}")
        print(f"  decision              : {record['decision']}")
        print(f"  institutional_confidence : {record['institutional_confidence']}")
        print(f"  realized_gold_return  : {record['realized_gold_return']}")
        print(f"  decision_correct      : {record['decision_correct']}")
        print(f"  evaluation_timestamp  : {record['evaluation_timestamp']}")
        if record["notes"]:
            for note in record["notes"]:
                print(f"  note                  : {note}")
    else:
        print(f"already evaluated at {result['path']} (re-run with --force to re-evaluate)")
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
