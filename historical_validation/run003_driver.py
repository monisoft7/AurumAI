"""Run-003 one-off experiment driver (temporary, read-only replay).

Executes the frozen Run-003 manifest: the SAME 133 canonical cohort cases as
Run-002 x 3 variants via the EXISTING ``run_run003_variant`` machinery
(Correction-047-C enriched replay + the Run-003 institutional repairs):

    FULL_TECH        history_enabled=True,  technical_enabled=True
    NO_HISTORY_TECH  history_enabled=False, technical_enabled=True
    FULL_NO_TECH     history_enabled=True,  technical_enabled=False

Creates no production writes; artifacts land only under
``historical_validation/run003/``.  Run-002 artifacts are immutable.

Safety policy (identical to the Run-002 driver):
  * input artifact hashes are re-verified against the frozen Run-003
    manifest;
  * any no-lookahead / as-of / payload / market-context check failure
    raises immediately (STOP) -- nothing is repaired or retried;
  * non-safety engine exceptions are recorded per case as failed records
    and reported honestly in the final report.

Usage:
  python -m historical_validation.run003_driver --pass 1
  python -m historical_validation.run003_driver --pass 2
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
_MANIFEST = Path(__file__).resolve().parent / "baseline_manifest_run003.json"
_OUT_DIR = Path(__file__).resolve().parent / "run003"

VARIANTS: tuple[tuple[str, dict], ...] = (
    ("FULL_TECH", {"history_enabled": True, "technical_enabled": True}),
    ("NO_HISTORY_TECH", {"history_enabled": False, "technical_enabled": True}),
    ("FULL_NO_TECH", {"history_enabled": True, "technical_enabled": False}),
)


class SafetyViolation(AssertionError):
    """Raised when any as-of / no-lookahead check fails. STOPs the run."""


def _verify_inputs(manifest: dict) -> None:
    for rel, expected in manifest["input_artifacts_sha256"].items():
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
    return [_case_from_row(rows[lid]) for lid in cohort]


def _strip_heavy(result: dict) -> dict:
    light = {k: v for k, v in result.items() if k != "serialized_outputs"}
    light["numeric_leaves"] = numeric_leaf_comparison(result["serialized_outputs"])
    return light


def run_pass(pass_id: int) -> None:
    manifest = json.loads(_MANIFEST.read_text(encoding="utf-8"))
    _verify_inputs(manifest)
    _OUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = _OUT_DIR / f"run003_pass{pass_id}_results.jsonl"
    done: set[str] = set()
    if out_path.exists():
        done = {
            json.loads(line)["lesson_id"]
            for line in out_path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        }

    from .run003_path import run_run003_variant
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
            results: dict = {}
            for variant_name, kwargs in VARIANTS:
                res = run_run003_variant(
                    case,
                    run_label=f"p{pass_id}_{variant_name.lower()}",
                    config=cfg,
                    snapshot=snap,
                    **kwargs,
                )
                for check_group in (
                    res.get("no_lookahead_checks", {}),
                    res.get("payload_lookahead_checks", {}),
                    res.get("briefing_asof_checks", {}),
                    res.get("market_context_checks", {}),
                ):
                    bad = [k for k, ok in check_group.items() if not ok]
                    if bad:
                        raise SafetyViolation(
                            f"SAFETY VIOLATION pass={pass_id} case={case.lesson_id} "
                            f"variant={variant_name}: {bad}"
                        )
                tech_checks = res.get("technical_checks", {})
                if kwargs.get("technical_enabled") and not all(
                    tech_checks.values()
                ):
                    raise SafetyViolation(
                        f"SAFETY VIOLATION pass={pass_id} case={case.lesson_id} "
                        f"variant={variant_name} (technical as-of): "
                        f"{[k for k, ok in tech_checks.items() if not ok]}"
                    )
                results[variant_name] = _strip_heavy(res)
            record = {
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
                "FULL_TECH": results["FULL_TECH"],
                "NO_HISTORY_TECH": results["NO_HISTORY_TECH"],
                "FULL_NO_TECH": results["FULL_NO_TECH"],
                "status": "ok",
                "elapsed_seconds": round(time.time() - t0, 3),
            }
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
