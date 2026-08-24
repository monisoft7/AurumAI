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

Contract:
- The first evaluation writes the canonical sibling
  ``outcome.evaluated.json``. While that sibling is still ``pending``
  (horizon not elapsed) it may be rewritten by later attempts.
- Once a sibling is ``evaluated`` it is immutable. Re-evaluation requires
  ``--force`` and writes a new versioned sibling
  (``outcome.evaluated.v2.json``, ``outcome.evaluated.v3.json``, ...);
  the canonical evaluated artifact is never overwritten.
- ``gold_source_sha256`` records the SHA-256 of the exact gold CSV bytes
  consulted, so any re-evaluation can be checked for reproducibility.
- ``NO_TRADE`` / ``INSUFFICIENT_EVIDENCE`` abstentions are intentionally
  never scored by ``decision_correct`` (it stays ``null``). Their quality
  is assessed by the Correction 055-A taxonomy via ``abstention_verdict``
  (``justified_abstention`` / ``missed_opportunity`` / ``unresolvable`` /
  ``unevaluable``; ``unscored`` only when the run predates the
  decision-time snapshot). Any binary abstention scoring policy remains
  DEFERRED. Verdicts are computed solely from the frozen
  ``decision_snapshot`` recorded at emit time plus the realized window;
  decision-time inputs are never recomputed or reinterpreted.
- ``HOLD`` is a scored flat decision class (correct iff the realized move
  is within the existing ±0.10% dead zone) and never enters the
  abstention taxonomy.

Usage:
    python scripts/evaluate_outcome.py [--output-dir PATH]
    python scripts/evaluate_outcome.py [--output-dir PATH] [--force]
    python scripts/evaluate_outcome.py [--output-dir BASE] [--all-pending]

``--output-dir`` may point at a run directory or at a date directory;
without it the latest run holding an ``outcome.json`` is used.
``--all-pending`` sweeps every run under the outputs base (default:
``<repo>/outputs``) whose horizon has elapsed and whose outcome has not
been evaluated yet, and evaluates each one idempotently. This is the
entry point wired into the daily execution path.

Exit codes:
    0  evaluated (or pending while the horizon has not yet elapsed)
    2  inputs missing or invalid
"""

from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import sys
from pathlib import Path
from typing import Any, Iterator

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

SCHEMA_VERSION = "1.1"
ARTIFACT = "decision_outcome"
PENDING_STATUS = "pending"
EVALUATED_STATUS = "evaluated"

ABSTENTION_DECISIONS = frozenset({"NO_TRADE", "INSUFFICIENT_EVIDENCE"})
ABSTENTION_VERDICT_UNSCORED = "unscored"
VERDICT_JUSTIFIED_ABSTENTION = "justified_abstention"
VERDICT_MISSED_OPPORTUNITY = "missed_opportunity"
VERDICT_UNRESOLVABLE = "unresolvable"
VERDICT_UNEVALUABLE = "unevaluable"
ABSTENTION_NOTE = (
    "abstention: decision intentionally not scored by decision_correct "
    "(binary abstention scoring policy DEFERRED); quality is assessed by "
    "abstention_verdict per Correction 055-A"
)
CANDIDATE_DIRECTION_SIGNS = {"bullish": 1.0, "bearish": -1.0}


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


def _file_sha256(path: Path) -> str | None:
    try:
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(65536), b""):
                digest.update(chunk)
        return digest.hexdigest()
    except OSError:
        return None


def _versioned_evaluated_path(run_dir: Path) -> Path:
    version = 2
    while (run_dir / f"outcome.evaluated.v{version}.json").exists():
        version += 1
    return run_dir / f"outcome.evaluated.v{version}.json"


def _candidate_sign(direction: Any) -> float | None:
    if not isinstance(direction, str):
        return None
    return CANDIDATE_DIRECTION_SIGNS.get(direction.strip().lower())


def _abstention_basis(gates: dict[str, Any], *, g4: bool) -> list[str]:
    """Decision-time abstention bases, restated verbatim from the snapshot.

    Bases never override the outcome verdict (Correction 055-A).
    """
    basis: list[str] = []
    if g4:
        basis.append("no_eligible_thesis")
        if gates.get("bias_review_blocked"):
            basis.append("bias_review")
        return basis
    if gates.get("bias_review_blocked"):
        basis.append("bias_review")
    if gates.get("conviction_gate_pass") is False:
        basis.append("low_conviction")
    if gates.get("rr_gate_pass") is False:
        basis.append("rr_asymmetry")
    return basis


def _resolve_abstention(
    snapshot: dict[str, Any],
    *,
    pending: bool,
    realized: float | None,
) -> tuple[str, list[str]]:
    """Map (frozen decision-time snapshot, realized window) to a verdict.

    Order per Correction 055-A: structural unresolvable first, then
    outcome observability, then the dead-zone opportunity-cost rule using
    only the existing ±0.10% classification. Runs emitted before the
    decision-time snapshot existed stay ``unscored``.
    """
    if not snapshot:
        return ABSTENTION_VERDICT_UNSCORED, []
    gates = snapshot.get("gate_reasons") or {}
    rr_pass = gates.get("rr_gate_pass")
    sign = _candidate_sign((snapshot.get("best_rejected") or {}).get("direction"))
    if rr_pass is None:
        verdict = VERDICT_UNRESOLVABLE
    elif pending or realized is None:
        verdict = VERDICT_UNEVALUABLE
    elif sign is None:
        verdict = VERDICT_UNRESOLVABLE
    else:
        opportunity_cost = sign * float(realized)
        if _classify_actual_direction(opportunity_cost) == "UP":
            verdict = VERDICT_MISSED_OPPORTUNITY
        else:
            verdict = VERDICT_JUSTIFIED_ABSTENTION
    basis = _abstention_basis(gates, g4=(rr_pass is None))
    return verdict, basis


def evaluate_run(run_dir: Path, force: bool = False) -> dict[str, Any]:
    """Evaluate one pending outcome record in *run_dir*.

    Returns ``{"record": ..., "wrote": bool, "path": Path}``.  The pending
    decision-time artifact is never modified.  The canonical sibling
    ``outcome.evaluated.json`` is written on first evaluation and may be
    rewritten while its status is ``pending`` (retry until the horizon
    elapses).  Once it is ``evaluated`` it is immutable: without *force*
    the existing record is returned unchanged; with *force* a new
    versioned sibling is written instead.
    """
    outcome_path = run_dir / "outcome.json"
    data = _load_json(outcome_path)

    evaluated_path = run_dir / "outcome.evaluated.json"
    existing: dict[str, Any] | None = None
    if evaluated_path.exists():
        try:
            loaded = _load_json(evaluated_path)
        except (OSError, ValueError):
            loaded = None
        if isinstance(loaded, dict):
            existing = loaded
    if existing is not None and existing.get("status") == EVALUATED_STATUS:
        if not force:
            return {"record": existing, "wrote": False, "path": evaluated_path}
        target_path = _versioned_evaluated_path(run_dir)
    else:
        target_path = evaluated_path

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
        "decision_snapshot": data.get("decision_snapshot")
        if isinstance(data.get("decision_snapshot"), dict)
        else {},
        "gold_source_sha256": None,
        "abstention_evaluable": False,
        "abstention_verdict": None,
        "abstention_return": None,
        "abstention_basis": [],
    }

    gold_ref = str(record["gold_path"] or "")
    if gold_ref:
        record["gold_source_sha256"] = _file_sha256(_resolve_gold_path(gold_ref))

    decision_value = record["decision"]
    is_abstention = (
        isinstance(decision_value, str)
        and decision_value.strip().upper() in ABSTENTION_DECISIONS
    )
    record["abstention_evaluable"] = is_abstention
    if is_abstention:
        notes.append(ABSTENTION_NOTE)

    decision = record["decision"]
    entry = _entry_datetime(record["entry_date"])
    if entry is None:
        notes.append("entry_date missing or invalid; cannot evaluate")
        record["status"] = EVALUATED_STATUS
        record["evaluation_timestamp"] = _utc_now_iso()
    else:
        horizon = int(record["horizon_days"] or 0)
        gold = _load_gold(_resolve_gold_path(gold_ref)) if gold_ref else pd.DataFrame()
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
                if is_abstention:
                    record["abstention_return"] = record["realized_gold_return"]
            record["status"] = EVALUATED_STATUS
            record["evaluation_timestamp"] = _utc_now_iso()

    if is_abstention:
        verdict, basis = _resolve_abstention(
            record["decision_snapshot"],
            pending=(record["status"] == PENDING_STATUS),
            realized=record["realized_gold_return"],
        )
        record["abstention_verdict"] = verdict
        record["abstention_basis"] = basis

    _write_json(target_path, record)
    return {"record": record, "wrote": True, "path": target_path}


# ---------------------------------------------------------------------------
# Pending sweep (automatic evaluation over all runs)
# ---------------------------------------------------------------------------


def _has_outcome(path: Path) -> bool:
    return (path / "outcome.json").is_file()


def _iter_outcome_run_dirs(outputs_base: Path) -> Iterator[Path]:
    """Yield every directory under *outputs_base* holding ``outcome.json``.

    Supports the current per-run layout (``<base>/<date>/<pipeline_id>/``),
    legacy flat runs (``<base>/<date>/``), and *base* itself being a run
    directory — mirroring ``runtime_registry.outputs.latest_run_dir``.
    """
    if not outputs_base.is_dir():
        return
    if _has_outcome(outputs_base):
        yield outputs_base
    for date_path in sorted(outputs_base.iterdir()):
        if not date_path.is_dir():
            continue
        if _has_outcome(date_path):
            yield date_path
        for child in sorted(date_path.iterdir()):
            if child.is_dir() and _has_outcome(child):
                yield child


def _needs_evaluation(run_dir: Path) -> bool:
    evaluated_path = run_dir / "outcome.evaluated.json"
    if not evaluated_path.is_file():
        return True
    try:
        existing = _load_json(evaluated_path)
    except (OSError, ValueError):
        return True
    return existing.get("status") != EVALUATED_STATUS


def evaluate_pending_outcomes(
    outputs_base: Path | None = None,
) -> list[dict[str, Any]]:
    """Evaluate every pending outcome under *outputs_base*.

    Idempotent: runs whose canonical sibling already has status
    ``evaluated`` are skipped; runs still ``pending`` (horizon not yet
    elapsed) are retried. Never forces re-evaluation of an evaluated
    record. One malformed run neither blocks nor fails the others
    (fail-one-isolated); such runs yield an ``error`` entry.
    """
    base = Path(outputs_base) if outputs_base is not None else ROOT / "outputs"
    results: list[dict[str, Any]] = []
    for run_dir in _iter_outcome_run_dirs(base):
        if not _needs_evaluation(run_dir):
            continue
        try:
            results.append(evaluate_run(run_dir))
        except Exception as exc:
            results.append({
                "record": None,
                "wrote": False,
                "path": run_dir / "outcome.evaluated.json",
                "error": str(exc),
            })
    return results


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
             "(writes a new versioned sibling file; the canonical "
             "outcome.evaluated.json is never overwritten).",
    )
    parser.add_argument(
        "--all-pending",
        action="store_true",
        help="Sweep every run under the outputs base whose horizon has "
             "elapsed and evaluate it idempotently (evaluated runs are "
             "skipped; --force is ignored in this mode).",
    )
    args = parser.parse_args(argv)

    if args.all_pending:
        base = Path(args.output_dir) if args.output_dir else ROOT / "outputs"
        results = evaluate_pending_outcomes(base)
        written = 0
        errors = 0
        for result in results:
            if result.get("error"):
                errors += 1
                print(f"error {result['path']}: {result['error']}", file=sys.stderr)
                continue
            if result["wrote"]:
                written += 1
            print(f"{'wrote' if result['wrote'] else 'skipped'} {result['path']} "
                  f"status={result['record']['status']}")
        print(f"outcome sweep: processed={len(results)} written={written} errors={errors}")
        return EXIT_OK

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
        print(f"already evaluated at {result['path']} (re-run with --force to write a versioned sibling)")
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
