"""AurumAI run registry: append-only JSONL record of successful runs.

Runtime layer only. After every successful ``run.py`` execution one
immutable record is appended to ``runtime/run_registry.jsonl``. Existing
records are never rewritten or removed; each line is one complete JSON
record of a single run.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent.parent

DEFAULT_REGISTRY_PATH = ROOT / "runtime" / "run_registry.jsonl"

_BASELINE_TAG_SUBSTR = "baseline"


def git_head_commit(root: Path = ROOT) -> str:
    """Short HEAD commit hash of the repository, or empty string."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=str(root),
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        return ""
    if result.returncode != 0:
        return ""
    return result.stdout.strip()


def baseline_tag(config: dict[str, Any], root: Path = ROOT) -> str | None:
    """Baseline tag for the run, or None when none is available.

    Resolution order: an explicit ``baseline_tag`` in the runtime config,
    then the newest git tag whose name contains "baseline".
    """
    configured = config.get("baseline_tag")
    if configured:
        return str(configured)
    try:
        result = subprocess.run(
            ["git", "tag", "--list"],
            cwd=str(root),
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if result.returncode != 0:
        return None
    tags = [
        tag.strip()
        for tag in result.stdout.splitlines()
        if _BASELINE_TAG_SUBSTR in tag.strip().lower()
    ]
    if not tags:
        return None
    return sorted(tags)[-1]


def build_record(
    *,
    run_id: str,
    timestamp: str,
    event_type: str,
    asset: str,
    execution_duration_seconds: float,
    exit_code: int,
    pipeline_status: str,
    institutional_decision: str,
    confidence: float | None,
    report_path: str,
    output_directory: str,
    git_commit: str,
    baseline_tag_value: str | None,
) -> dict[str, Any]:
    """Build one immutable registry record from run results."""
    return {
        "run_id": run_id,
        "timestamp": timestamp,
        "event_type": event_type,
        "asset": asset,
        "execution_duration_seconds": execution_duration_seconds,
        "exit_code": exit_code,
        "pipeline_status": pipeline_status,
        "institutional_decision": institutional_decision,
        "confidence": confidence,
        "report_path": report_path,
        "output_directory": output_directory,
        "git_commit": git_commit,
        "baseline_tag": baseline_tag_value,
    }


def append_record(
    record: dict[str, Any],
    registry_path: Path = DEFAULT_REGISTRY_PATH,
) -> Path:
    """Append one JSON record as a new line. Returns the registry path."""
    registry_path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(record, ensure_ascii=False, sort_keys=True)
    with open(registry_path, "a", encoding="utf-8") as handle:
        handle.write(line + "\n")
        handle.flush()
    return registry_path


def read_records(registry_path: Path = DEFAULT_REGISTRY_PATH) -> list[dict[str, Any]]:
    """Read all records; malformed lines are skipped."""
    if not registry_path.exists():
        return []
    records: list[dict[str, Any]] = []
    for line in registry_path.read_text(encoding="utf-8").splitlines():
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
