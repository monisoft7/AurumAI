"""Run-002 one-off experiment driver (temporary, read-only replay).

Executes the frozen Run-002 manifest: 133 cohort cases x {FULL_ENRICHED,
NO_HISTORY} via the EXISTING ``run_enriched_replay_variant`` machinery.
Creates no production writes; artifacts land only under
``historical_validation/run002/``.

Safety policy:
  * input artifact hashes are re-verified against the frozen manifest;
  * any no-lookahead / as-of / payload check failure raises immediately
    (STOP) -- nothing is repaired or retried;
  * non-safety engine exceptions are recorded per case as failed records
    and reported honestly in the final report.

Usage:
  python -m historical_validation.run002_driver --pass 1
  python -m historical_validation.run002_driver --pass 2
"""

from __future__ import annotations

import argparse
import hashlib
import json
import time
import traceback
from pathlib import Path

from .cases import _case_from_row, load_lessons
from .compare import numeric_leaf_comparison

_ROOT = Path(__file__).resolve().parents[1]
_MANIFEST = Path(__file__).resolve().parent / "baseline_manifest_run002.json"
_OUT_DIR = Path(__file__).resolve().parent / "run002"


class SafetyViolation(AssertionError):
    """Raised when any as-of / no-lookahead check fails. STOPs the run."""


def _verify_inputs(manifest: dict) -> None:
    for rel_with_note, expected in manifest["input_artifact_hashes_sha256"].items():
        rel = rel_with_note.split(" (")[0]
        path = _ROOT / rel
        if not path.is_file():
            raise SafetyViolation(f"manifest input missing: {rel}")
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
        if actual != expected:
            raise SafetyViolation(
                f"INPUT DRIFT {rel}: manifest={expected[:16]} actual={actual[:16]}"
            )


def _build_cases(manifest: dict):
    rows = {r["lesson_id"]: r for r in load_lessons(_ROOT / "data/lessons/cpi_gold_lessons.csv")}
    cohort = manifest["cohort_verification"]["included_episode_ids"]
    assert len(cohort) == manifest["cohort_verification"]["total_included_cases"] == 133
    cases = [_case_from_row(rows[lid]) for lid in cohort]  # manifest order (chronological)
    return cases


def _strip_heavy(result: dict) -> dict:
    light = {k: v for k, v in result.items() if k != "serialized_outputs"}
    light["numeric_leaves"] = numeric_leaf_comparison(result["serialized_outputs"])
    return light


def _case_record(case, snap, full, nohist, comparison, elapsed) -> dict:
    return {
        "lesson_id": case.lesson_id,
        "evaluation_date": case.evaluation_date.isoformat(),
        "cpi_pressure": case.cpi_pressure,
        "snapshot_summary": {
            "institutional_regime": snap.institutional_regime,
            "us10y_trend": snap.us10y_trend,
            "dxy_trend": snap.dxy_trend,
            "analogue_cutoff": snap.analogue_cutoff.isoformat() if snap.analogue_cutoff else None,
            "analogue_eligible_count": len(snap.analogue_eligible_lesson_ids),
        },
        "gold_outcomes": {
            o.horizon: {"return_pct": o.return_pct, "direction": o.direction}
            for o in case.outcomes
        },
        "FULL": _strip_heavy(full),
        "NO_HISTORY": _strip_heavy(nohist),
        "comparison": {
            k: v
            for k, v in comparison.items()
            if k not in {"full_summary", "no_history_summary"}
        },
        "elapsed_seconds": round(elapsed, 3),
    }


def run_pass(pass_id: int) -> None:
    manifest = json.loads(_MANIFEST.read_text(encoding="utf-8"))
    if manifest["status"] != "PENDING" and pass_id == 1:
        print(f"manifest status={manifest['status']} (continuing; registration updated post-run)")
    _verify_inputs(manifest)
    _OUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = _OUT_DIR / f"run002_pass{pass_id}_results.jsonl"
    done: set[str] = set()
    if out_path.exists():
        done = {
            json.loads(line)["lesson_id"]
            for line in out_path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        }

    from .compare import compare_variants
    from .enriched_replay import run_enriched_replay_variant
    from .snapshot import SnapshotConfig, build_snapshot

    cases = _build_cases(manifest)
    cfg = SnapshotConfig()
    t_start = time.time()
    for idx, case in enumerate(cases, 1):
        if case.lesson_id in done:
            continue
        t0 = time.time()
        try:
            snap = build_snapshot(case, cfg)  # raises on any as-of violation
            full = run_enriched_replay_variant(
                case, history_enabled=True, run_label="full", config=cfg, snapshot=snap
            )
            nohist = run_enriched_replay_variant(
                case, history_enabled=False, run_label="nohist", config=cfg, snapshot=snap
            )
            for name, res in (("FULL", full), ("NO_HISTORY", nohist)):
                for check_group in (
                    res.get("no_lookahead_checks", {}),
                    res.get("payload_lookahead_checks", {}),
                    res.get("briefing_asof_checks", {}),
                ):
                    bad = [k for k, ok in check_group.items() if not ok]
                    if bad:
                        raise SafetyViolation(
                            f"SAFETY VIOLATION pass={pass_id} case={case.lesson_id} variant={name}: {bad}"
                        )
            record = _case_record(
                case, snap, full, nohist, compare_variants(full, nohist), time.time() - t0
            )
            record["status"] = "ok"
        except SafetyViolation:
            raise
        except Exception as exc:  # non-safety engine failure: record, continue
            record = {
                "lesson_id": case.lesson_id,
                "evaluation_date": case.evaluation_date.isoformat(),
                "status": "failed",
                "error_type": type(exc).__name__,
                "error": str(exc)[:500],
                "traceback": traceback.format_exc()[-2000:],
                "elapsed_seconds": round(time.time() - t0, 3),
            }
        with out_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, default=str) + "\n")
        if idx % 10 == 0 or idx == len(cases):
            print(
                f"pass {pass_id}: {idx}/{len(cases)} cases "
                f"({time.time() - t_start:.0f}s elapsed)",
                flush=True,
            )
    print(f"pass {pass_id} complete -> {out_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--pass", dest="pass_id", type=int, required=True, choices=[1, 2])
    args = parser.parse_args()
    run_pass(args.pass_id)
