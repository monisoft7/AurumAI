"""AurumAI daily scheduler.

Runs the complete daily institutional workflow:

1. Execute ``run.py`` (the runtime entry point) and wait for completion.
2. Generate the Institutional Daily Report from the fresh run outputs.
3. Verify the run: exit code 0, ``institutional_report.md`` exists, and a
   new immutable record was appended to the run registry.
4. Send the report to Telegram (output channel only; failures never affect
   the pipeline).
5. Print a concise execution summary and exit with a proper exit code.

This file is the scheduling/runtime layer only. It executes the existing
``run.py`` and ``scripts/generate_institutional_report.py`` as subprocesses;
it does not modify any workflow, algorithm, contract, report, or registry
behavior.

Usage:
    python scripts/run_daily.py

Exit codes:
    0  daily run completed and verified
    1  pipeline failed or verification failed
    2  scheduler precondition error (missing scripts)
"""

from __future__ import annotations

import datetime
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from runtime_registry.outputs import latest_run_dir  # noqa: E402

EXIT_OK = 0
EXIT_RUN_FAILED = 1
EXIT_CONFIG_ERROR = 2

PIPELINE_SCRIPT = ROOT / "run.py"
REPORT_SCRIPT = ROOT / "scripts" / "generate_institutional_report.py"
REGISTRY_PATH = ROOT / "runtime" / "run_registry.jsonl"


def _run_date() -> str:
    return datetime.date.today().isoformat()


def _run_dir(run_date: str) -> Path:
    return ROOT / "outputs" / run_date


def _resolve_run_dir(run_date: str) -> Path | None:
    return latest_run_dir(ROOT / "outputs", run_date)


def _registry_records() -> list[dict[str, Any]]:
    if not REGISTRY_PATH.exists():
        return []
    records: list[dict[str, Any]] = []
    for line in REGISTRY_PATH.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            record = json.loads(line)
        except ValueError:
            continue
        if isinstance(record, dict):
            records.append(record)
    return records


def _refresh_gold() -> None:
    """Refresh local gold history before the pipeline (fail-safe, idempotent)."""
    try:
        from connectors.gold_data_provider import GoldDataProvider

        report = GoldDataProvider().refresh()
        print(
            f"run_daily: gold refresh {report.status} "
            f"(rows {report.rows_before} -> {report.rows_after}, "
            f"last {report.last_date_before} -> {report.last_date_after})"
        )
        if report.status != "ok":
            print(
                f"run_daily: gold refresh incomplete ({report.message}); "
                "proceeding with existing dataset",
                file=sys.stderr,
            )
    except Exception as exc:  # pragma: no cover - defensive
        print(
            f"run_daily: gold refresh failed ({exc}); "
            "proceeding with existing dataset",
            file=sys.stderr,
        )


def _run_pipeline() -> int:
    _refresh_gold()
    return subprocess.run(
        [sys.executable, str(PIPELINE_SCRIPT), "--no-refresh"],
        cwd=str(ROOT),
    ).returncode


def _generate_report(run_dir: Path) -> int:
    return subprocess.run(
        [sys.executable, str(REPORT_SCRIPT), "--output-dir", str(run_dir)],
        cwd=str(ROOT),
    ).returncode


def _report_exists(run_dir: Path) -> bool:
    path = run_dir / "institutional_report.md"
    return path.exists() and path.stat().st_size > 0


def _load_summary(run_dir: Path) -> dict[str, Any]:
    path = run_dir / "summary.json"
    if not path.exists():
        return {}
    try:
        summary = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return summary if isinstance(summary, dict) else {}


def _send_telegram(run_dir: Path) -> tuple[bool, str]:
    """Send the report to Telegram. Never raises; never affects the pipeline."""
    sys.path.insert(0, str(ROOT / "src"))
    try:
        from notifications.telegram_notifier import TelegramConfigurationError, send_report

        report_path = run_dir / "institutional_report.md"
        message_count = send_report(report_path)
        return True, f"sent in {message_count} message(s)"
    except TelegramConfigurationError:
        return False, "not configured (set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID)"
    except Exception as exc:  # pragma: no cover - defensive
        return False, f"failed (pipeline unaffected): {exc}"


def _print_summary(run_dir: Path, rc: int, report_ok: bool,
                   registry_ok: bool, telegram_note: str, success: bool) -> None:
    summary = _load_summary(run_dir)
    decision = summary.get("decision", "n/a")
    confidence = summary.get("decision_confidence")
    confidence_text = "n/a" if confidence is None else f"{confidence:.4f}"
    wall = summary.get("wall_time_seconds")

    print()
    print("AurumAI Daily Run Summary")
    print("=" * 60)
    print(f"Date               : {run_dir.parent.name}")
    print(f"Pipeline ID        : {summary.get('pipeline_id', 'n/a')}")
    print(f"Decision           : {decision} (confidence {confidence_text})")
    if wall is not None:
        print(f"Pipeline wall time : {wall:.1f} s")
    print(f"Exit code          : {rc}")
    print(f"Report generated   : {run_dir / 'institutional_report.md'}")
    print(f"Registry path      : {REGISTRY_PATH}")
    print(f"Verification       : exit_code={rc == 0}, report={report_ok}, "
          f"registry={registry_ok}")
    print(f"Telegram           : {telegram_note}")
    print(f"Result             : {'SUCCESS' if success else 'FAILED'}")
    print("=" * 60)


def main(argv: list[str] | None = None) -> int:
    if not PIPELINE_SCRIPT.exists():
        print(f"run_daily: pipeline script not found: {PIPELINE_SCRIPT}",
              file=sys.stderr)
        return EXIT_CONFIG_ERROR
    if not REPORT_SCRIPT.exists():
        print(f"run_daily: report script not found: {REPORT_SCRIPT}",
              file=sys.stderr)
        return EXIT_CONFIG_ERROR

    run_date = _run_date()
    records_before = len(_registry_records())

    print(f"run_daily: executing pipeline (date={run_date})")
    rc = _run_pipeline()

    report_ok = False
    registry_ok = False
    run_dir = _resolve_run_dir(run_date) or _run_dir(run_date)

    if rc == 0:
        report_rc = _generate_report(run_dir)
        report_ok = report_rc == 0 and _report_exists(run_dir)

        records = _registry_records()
        appended = len(records) - records_before
        registry_ok = (
            appended == 1
            and records[-1].get("exit_code") == 0
            and records[-1].get("output_directory") == str(run_dir)
        )

    success = rc == 0 and report_ok and registry_ok

    telegram_note = "skipped (run not verified)"
    if success:
        telegram_sent, telegram_note = _send_telegram(run_dir)
    _print_summary(run_dir, rc, report_ok, registry_ok, telegram_note, success)

    return EXIT_OK if success else EXIT_RUN_FAILED


if __name__ == "__main__":
    sys.exit(main())
