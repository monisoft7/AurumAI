"""AurumAI run history viewer.

Reads the append-only registry ``runtime/run_registry.jsonl`` and reports
run history plus summary statistics.

Usage:
    python scripts/show_run_history.py [--last N] [--json]

Capabilities:
    - list the last N runs (default 10; --last 0 lists every run)
    - summary statistics
    - success rate
    - average runtime
    - decision distribution

Exit codes:
    0  history shown
    2  registry missing or unreadable
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_REGISTRY_PATH = ROOT / "runtime" / "run_registry.jsonl"

EXIT_OK = 0
EXIT_REGISTRY_ERROR = 2


def _fmt(value: Any) -> str:
    if value is None:
        return "n/a"
    if isinstance(value, float):
        return f"{value:.4f}".rstrip("0").rstrip(".")
    return str(value)


def _load_records(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    records: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
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


def _print_runs(records: list[dict[str, Any]]) -> None:
    if not records:
        print("(no runs recorded)")
        return
    headers = ["run_id", "timestamp", "event_type", "decision", "confidence",
               "duration_s", "exit_code", "baseline_tag"]
    widths = {header: len(header) for header in headers}
    rows: list[list[str]] = []
    for record in records:
        row = [
            str(record.get("run_id", "")),
            str(record.get("timestamp", "")),
            str(record.get("event_type", "")),
            str(record.get("institutional_decision", "")),
            _fmt(record.get("confidence")),
            _fmt(record.get("execution_duration_seconds")),
            str(record.get("exit_code", "")),
            str(record.get("baseline_tag", "")),
        ]
        for header, cell in zip(headers, row):
            widths[header] = max(widths[header], len(cell))
        rows.append(row)

    print(" | ".join(h.ljust(widths[h]) for h in headers))
    print("-+-".join("-" * widths[h] for h in headers))
    for row in rows:
        print(" | ".join(cell.ljust(widths[h]) for h, cell in zip(headers, row)))


def _print_stats(records: list[dict[str, Any]]) -> None:
    total = len(records)
    if total == 0:
        print("No runs recorded in the registry.")
        return

    successful = sum(
        1
        for record in records
        if record.get("exit_code") == 0
        and record.get("pipeline_status") == "success"
    )
    success_rate = successful / total if total else 0.0

    runtimes = [
        float(record["execution_duration_seconds"])
        for record in records
        if isinstance(record.get("execution_duration_seconds"), (int, float))
    ]
    avg_runtime = statistics.mean(runtimes) if runtimes else 0.0

    decision_counts = Counter(
        str(record.get("institutional_decision", "")) for record in records
    )
    event_counts = Counter(str(record.get("event_type", "")) for record in records)

    print("Summary statistics")
    print("=" * 60)
    print(f"Total runs           : {total}")
    print(f"Successful runs      : {successful}")
    print(f"Success rate         : {success_rate * 100.0:.2f}%")
    if runtimes:
        print(f"Average runtime (s)  : {avg_runtime:.2f}")
        print(f"Min / Max runtime (s): {min(runtimes):.2f} / {max(runtimes):.2f}")
    else:
        print("Average runtime (s)  : n/a")
    print()
    print("Decision distribution")
    print("-" * 60)
    for decision, count in decision_counts.most_common():
        print(f"{decision:30s} {count:4d}  {count / total * 100.0:.1f}%")
    print()
    print("Event type distribution")
    print("-" * 60)
    for event, count in event_counts.most_common():
        print(f"{event:30s} {count:4d}  {count / total * 100.0:.1f}%")


def _print_json(records: list[dict[str, Any]]) -> None:
    print(json.dumps(records, ensure_ascii=False, indent=2, sort_keys=True))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python scripts/show_run_history.py",
        description="Shows the AurumAI run history from the runtime registry.",
    )
    parser.add_argument(
        "--last",
        type=int,
        default=10,
        help="Number of most recent runs to list (default: 10; 0 lists all).",
    )
    parser.add_argument(
        "--registry",
        default=str(DEFAULT_REGISTRY_PATH),
        help="Path to the run registry JSONL file "
             f"(default: {DEFAULT_REGISTRY_PATH}).",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print all registry records as JSON instead of the table view.",
    )
    args = parser.parse_args(argv)

    registry_path = Path(args.registry)
    if not registry_path.exists():
        print(
            f"show_run_history: registry not found: {registry_path}",
            file=sys.stderr,
        )
        return EXIT_REGISTRY_ERROR

    records = _load_records(registry_path)
    if args.json:
        _print_json(records)
        return EXIT_OK

    if args.last and args.last > 0:
        recent = records[-args.last:]
    else:
        recent = list(records)

    print("AurumAI Run History")
    print("=" * 60)
    _print_runs(recent)
    print()
    if len(records) > len(recent):
        print(f"(showing last {len(recent)} of {len(records)} recorded runs)")
        print()
    _print_stats(records)
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
