"""AurumAI runtime entry point.

Executes one complete institutional run through the existing
``InstitutionalOrchestrator`` and persists every output under
``outputs/YYYY-MM-DD/<pipeline_id>/``. Each run gets its own directory, so no
run ever sees or overwrites artifacts produced by another run.

This file is the runtime layer only. It does not modify any analysis
algorithm, workflow, or contract.

Usage:
    python run.py [--config runtime_config.json]

Exit codes:
    0  run completed (all stages ok)
    1  run completed with stage failures or errors
    2  configuration or environment validation failed
"""

from __future__ import annotations

import argparse
import dataclasses
import datetime
import json
import logging
import os
import sys
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from dotenv import load_dotenv  # noqa: E402

from knowledge.events.registry import EventRegistry  # noqa: E402
from orchestration.orchestrator import InstitutionalOrchestrator  # noqa: E402
from runtime_registry.outputs import date_dir  # noqa: E402
from runtime_registry.registry import append_record, baseline_tag, build_record, git_head_commit  # noqa: E402

LOG = logging.getLogger("aurumai.runtime")

DEFAULT_CONFIG_PATH = ROOT / "runtime_config.json"

REQUIRED_ENV_VARS = ("FRED_API_KEY",)
NOTICE_ENV_VARS = ("NEWS_API_KEY",)

EXIT_OK = 0
EXIT_RUN_FAILED = 1
EXIT_CONFIG_ERROR = 2

DEFAULT_CONFIG: dict[str, Any] = {
    "event_type": "CPI",
    "data_path": "data/economic/CPIAUCSL.csv",
    "gold_path": "data/history/gold/gold.csv",
    "gold_lessons_path": None,
    "release_calendar_path": "data/calendar/cpi_releases.csv",
    "yield_data_path": "data/economic/DFII10.csv",
    "dxy_data_path": "data/context/dxy/dxy.csv",
    "breakeven_data_path": "data/economic/T5YIE.csv",
    "output_base_dir": "outputs",
    "asset": "XAU/USD",
    "horizon": 12,
    "max_workers": 4,
    "checkpoint_dir": None,
    "trigger": "runtime",
    "query": "",
}


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------


def _load_config(path: Path) -> dict[str, Any]:
    if not path.exists():
        LOG.error("Configuration file not found: %s", path)
        sys.exit(EXIT_CONFIG_ERROR)
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        LOG.error("Failed to parse configuration file %s: %s", path, exc)
        sys.exit(EXIT_CONFIG_ERROR)
    if not isinstance(raw, dict):
        LOG.error("Configuration file %s must contain a JSON object", path)
        sys.exit(EXIT_CONFIG_ERROR)
    config = dict(DEFAULT_CONFIG)
    config.update(raw)
    return config


def _validate_config(config: dict[str, Any]) -> list[str]:
    errors: list[str] = []

    event_type = config.get("event_type")
    if event_type not in EventRegistry.list_events():
        errors.append(
            "event_type {!r} is not registered; available event types: {}".format(
                event_type, ", ".join(EventRegistry.list_events())
            )
        )

    for key in ("data_path", "gold_path"):
        value = config.get(key)
        if not value:
            errors.append(f"{key} is required")
        elif not (ROOT / str(value)).exists():
            errors.append(f"{key} not found: {value}")

    for key in ("gold_lessons_path", "release_calendar_path", "yield_data_path", "dxy_data_path", "breakeven_data_path"):
        value = config.get(key)
        if value and not (ROOT / str(value)).exists():
            errors.append(f"{key} not found: {value}")

    try:
        if int(config.get("horizon", 12)) < 1:
            errors.append("horizon must be a positive integer")
    except (TypeError, ValueError):
        errors.append("horizon must be an integer")

    try:
        if int(config.get("max_workers", 4)) < 1:
            errors.append("max_workers must be a positive integer")
    except (TypeError, ValueError):
        errors.append("max_workers must be an integer")

    return errors


def _validate_env() -> list[str]:
    warnings: list[str] = []
    for name in REQUIRED_ENV_VARS:
        if not os.environ.get(name):
            warnings.append(
                f"Environment variable {name} is not set. "
                "Live FRED refreshes will fail; the run proceeds on cached "
                "committed data (data/economic/*.csv)."
            )
    for name in NOTICE_ENV_VARS:
        value = os.environ.get(name)
        if value:
            LOG.info(
                "Environment variable %s is set but not consumed by the runtime.",
                name,
            )
    return warnings


def _new_pipeline_id(output_base: Path, run_date: str) -> str:
    """Unique pipeline id whose name mirrors the run's output directory.

    The id is ``runtime_YYYYMMDD_HHMMSS``. On a same-second collision with an
    existing output directory a numeric suffix is appended so every run still
    gets its own directory under ``outputs/YYYY-MM-DD/<pipeline_id>/``.
    """
    base = "runtime_" + datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    candidate = base
    counter = 1
    while (date_dir(output_base, run_date) / candidate).exists():
        counter += 1
        candidate = f"{base}_{counter}"
    return candidate


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------


def _init_logging(run_dir: Path) -> None:
    run_dir.mkdir(parents=True, exist_ok=True)
    fmt = logging.Formatter(
        "%(asctime)s %(levelname)-7s %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    console = logging.StreamHandler(sys.stdout)
    console.setLevel(logging.INFO)
    console.setFormatter(fmt)
    file_handler = logging.FileHandler(run_dir / "run.log", encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(fmt)

    root = logging.getLogger()
    root.setLevel(logging.DEBUG)
    root.addHandler(console)
    root.addHandler(file_handler)


# ---------------------------------------------------------------------------
# Serialization
# ---------------------------------------------------------------------------


def _serialize(obj: Any) -> Any:
    if obj is None or isinstance(obj, (str, int, float, bool)):
        return obj
    if isinstance(obj, dict):
        return {str(key): _serialize(value) for key, value in obj.items()}
    if isinstance(obj, (list, tuple, set)):
        return [_serialize(value) for value in obj]
    if isinstance(obj, (datetime.date, datetime.datetime)):
        return obj.isoformat()
    if hasattr(obj, "to_dict"):
        return _serialize(obj.to_dict())
    if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
        return _serialize(dataclasses.asdict(obj))
    if hasattr(obj, "__dict__"):
        return _serialize(vars(obj))
    return str(obj)


def _write_json(path: Path, payload: Any) -> None:
    path.write_text(
        json.dumps(_serialize(payload), indent=2, sort_keys=True),
        encoding="utf-8",
    )


# ---------------------------------------------------------------------------
# Summary helpers
# ---------------------------------------------------------------------------


def _decision_label(decision: Any) -> str:
    if decision is None:
        return "none"
    for attr in ("decision", "decision_type", "action"):
        if hasattr(decision, attr):
            value = getattr(decision, attr)
            if value is not None:
                return str(value)
    if isinstance(decision, dict):
        for key in ("decision", "decision_type", "action"):
            if decision.get(key) is not None:
                return str(decision[key])
    return "present"


def _decision_confidence(decision: Any) -> float | None:
    if decision is None:
        return None
    for attr in ("institutional_confidence", "confidence", "overall"):
        value = getattr(decision, attr, None)
        if isinstance(value, (int, float)):
            return float(value)
    if isinstance(decision, dict):
        for key in ("institutional_confidence", "confidence", "overall"):
            value = decision.get(key)
            if isinstance(value, (int, float)):
                return float(value)
    return None


def _decision_id(finalize: dict[str, Any]) -> str | None:
    decision = finalize.get("decision")
    if hasattr(decision, "decision_id"):
        return getattr(decision, "decision_id", None)
    if isinstance(decision, dict):
        return decision.get("decision_id")
    return None


def _outcome_record(
    *,
    run_id: str,
    event_type: str,
    asset: str,
    horizon: int,
    gold_path: str,
    entry_date: str,
    decision: str,
    institutional_confidence: float | None,
    decision_id: str | None,
) -> dict[str, Any]:
    return {
        "schema_version": "1.0",
        "artifact": "decision_outcome",
        "status": "pending",
        "run_id": run_id,
        "decision": decision,
        "institutional_confidence": institutional_confidence,
        "event_type": event_type,
        "asset": asset,
        "horizon_days": horizon,
        "gold_path": gold_path,
        "entry_date": entry_date,
        "realized_gold_return": None,
        "decision_correct": None,
        "evaluation_timestamp": None,
        "notes": [],
        "decision_id": decision_id,
    }


def _print_summary(assessment: Any, run_dir: Path, decision_label: str,
                   decision_confidence: float | None, success: bool) -> None:
    stage_counts: dict[str, int] = {}
    for record in assessment.stages:
        stage_counts[record.status] = stage_counts.get(record.status, 0) + 1
    failed = [r.stage_id for r in assessment.stages if r.status == "failed"]

    print()
    print("AurumAI Runtime Execution Summary")
    print("=" * 60)
    print(f"Pipeline ID       : {assessment.pipeline_id}")
    print(f"Trigger           : {assessment.trigger}")
    print(f"Event type        : {assessment.outputs.get('ingest_event', {}).get('event_type') if isinstance(assessment.outputs.get('ingest_event'), dict) else 'n/a'}")
    print(f"Stage records     : {stage_counts}")
    print(f"Errors            : {assessment.errors if assessment.errors else 'none'}")
    print(f"Decision          : {decision_label}")
    if decision_confidence is not None:
        print(f"Decision conf.    : {decision_confidence:.4f}")
    print(f"Output directory  : {run_dir}")
    print(f"Wall time         : {assessment.wall_time_ms / 1000.0:.1f} s")
    print(f"Result            : {'SUCCESS' if success else 'FAILED'}")
    if failed:
        print("Failed stages     : " + ", ".join(failed))
    print("=" * 60)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python run.py",
        description="AurumAI runtime entry point — executes one complete "
                    "institutional run and persists outputs under "
                    "outputs/YYYY-MM-DD/<pipeline_id>/.",
    )
    parser.add_argument(
        "--config",
        default=str(DEFAULT_CONFIG_PATH),
        help=f"Path to the runtime configuration JSON "
             f"(default: {DEFAULT_CONFIG_PATH.name}).",
    )
    parser.add_argument(
        "--no-refresh",
        action="store_true",
        help="Skip the gold data refresh before the run (offline mode).",
    )
    args = parser.parse_args(argv)

    load_dotenv(ROOT / ".env")

    config_path = Path(args.config)
    if not config_path.is_absolute():
        config_path = Path.cwd() / config_path

    config = _load_config(config_path)

    # Validate environment variables (warnings do not abort cached runs).
    for warning in _validate_env():
        LOG.warning(warning)

    # Validate configuration.
    config_errors = _validate_config(config)
    if config_errors:
        for error in config_errors:
            LOG.error("Configuration error: %s", error)
        return EXIT_CONFIG_ERROR

    run_date = datetime.date.today().isoformat()
    output_base = ROOT / str(config["output_base_dir"])
    pipeline_id = _new_pipeline_id(output_base, run_date)
    run_dir = date_dir(output_base, run_date) / pipeline_id
    run_dir.mkdir(parents=True, exist_ok=True)

    _init_logging(run_dir)

    LOG.info("AurumAI runtime starting (config: %s)", config_path)
    LOG.info("Event type: %s | data: %s | gold: %s",
             config["event_type"], config["data_path"], config["gold_path"])

    effective_config = {
        "config_path": str(config_path),
        "config": dict(config),
        "resolved_against": str(ROOT),
    }
    _write_json(run_dir / "config.json", effective_config)

    if not args.no_refresh:
        _refresh_gold_before_run(config, run_dir)
        _refresh_fred_yields_before_run()
        _refresh_dxy_before_run()

    checkpoint_dir = config.get("checkpoint_dir")
    if checkpoint_dir is not None:
        checkpoint_dir = str(ROOT / str(checkpoint_dir))
    orch = InstitutionalOrchestrator.with_default_pipeline(
        checkpoint_dir=checkpoint_dir,
        max_workers=int(config["max_workers"]),
    )

    artifacts_dir = run_dir / "artifacts"
    artifacts_dir.mkdir(parents=True, exist_ok=True)

    params: dict[str, Any] = {
        "trigger": config.get("trigger", "runtime"),
        "pipeline_id": pipeline_id,
        "force": True,
        "event_type": config["event_type"],
        "data_path": str(ROOT / str(config["data_path"])),
        "gold_path": str(ROOT / str(config["gold_path"])),
        "output_dir": str(artifacts_dir),
        "asset": config.get("asset", "XAU/USD"),
        "horizon": int(config["horizon"]),
        "query": config.get("query", ""),
    }
    for key in ("gold_lessons_path", "release_calendar_path", "yield_data_path", "dxy_data_path", "breakeven_data_path"):
        value = config.get(key)
        if value:
            params[key] = str(ROOT / str(value))

    LOG.info("Executing institutional run (pipeline_id=%s)", pipeline_id)
    t0 = time.monotonic()
    try:
        assessment = orch.run_all(**params)
    except Exception as exc:  # pragma: no cover - defensive
        LOG.exception("Institutional run failed unexpectedly: %s", exc)
        _write_json(run_dir / "summary.json", {
            "pipeline_id": pipeline_id,
            "success": False,
            "fatal_error": str(exc),
        })
        return EXIT_RUN_FAILED
    wall_seconds = time.monotonic() - t0
    LOG.info("Institutional run completed in %.1f s", wall_seconds)

    finalize = assessment.outputs.get("finalize", {}) or {}
    decision = finalize.get("decision")
    decision_label = _decision_label(decision)
    decision_confidence = _decision_confidence(decision)

    stage_records = [r.to_dict() for r in assessment.stages]
    success = not assessment.errors and all(
        r.status != "failed" for r in assessment.stages
    )

    _write_json(run_dir / "stages.json", stage_records)
    _write_json(run_dir / "finalize.json", finalize)
    _write_json(run_dir / "summary.json", {
        "pipeline_id": assessment.pipeline_id,
        "trigger": assessment.trigger,
        "timestamp": assessment.timestamp,
        "success": success,
        "event_type": config["event_type"],
        "data_path": config["data_path"],
        "gold_path": config["gold_path"],
        "output_directory": str(run_dir),
        "artifacts_directory": str(artifacts_dir),
        "wall_time_ms": assessment.wall_time_ms,
        "wall_time_seconds": round(assessment.wall_time_ms / 1000.0, 1),
        "cache_hits": assessment.cache_hits,
        "stage_counts": {
            status: count
            for status, count in _stage_counts(assessment).items()
        },
        "decision": decision_label,
        "decision_confidence": decision_confidence,
        "errors": list(assessment.errors),
        "failed_stages": [
            r.stage_id for r in assessment.stages if r.status == "failed"
        ],
    })

    if success:
        _write_json(run_dir / "outcome.json", _outcome_record(
            run_id=assessment.pipeline_id,
            event_type=config["event_type"],
            asset=config.get("asset", "XAU/USD"),
            horizon=int(config["horizon"]),
            gold_path=config["gold_path"],
            entry_date=run_date,
            decision=decision_label,
            institutional_confidence=decision_confidence,
            decision_id=_decision_id(finalize),
        ))
        LOG.info("Outcome record written to %s", run_dir / "outcome.json")

    LOG.info("Outputs written to %s", run_dir)
    _print_summary(assessment, run_dir, decision_label,
                   decision_confidence, success)

    exit_code = EXIT_OK if success else EXIT_RUN_FAILED

    if success:
        try:
            record = build_record(
                run_id=assessment.pipeline_id,
                timestamp=assessment.timestamp,
                event_type=config["event_type"],
                asset=config.get("asset", "XAU/USD"),
                execution_duration_seconds=round(wall_seconds, 4),
                exit_code=exit_code,
                pipeline_status="success",
                institutional_decision=decision_label,
                confidence=decision_confidence,
                report_path=str(run_dir / "institutional_report.md"),
                output_directory=str(run_dir),
                git_commit=git_head_commit(),
                baseline_tag_value=baseline_tag(config),
            )
            registry_path = append_record(record)
            LOG.info("Run registry record appended to %s", registry_path)
        except Exception as exc:  # pragma: no cover - defensive
            LOG.error("Failed to append run registry record: %s", exc)

    return exit_code


def _stage_counts(assessment: Any) -> dict[str, int]:
    counts: dict[str, int] = {}
    for record in assessment.stages:
        counts[record.status] = counts.get(record.status, 0) + 1
    return counts


def _refresh_gold_before_run(config: dict[str, Any], run_dir: Path) -> None:
    """Refresh local gold history before a production run (fail-safe)."""
    from connectors.gold_data_provider import refresh_gold_data

    gold_path = ROOT / str(config["gold_path"])
    try:
        report = refresh_gold_data(gold_path, logger=LOG)
        LOG.info(
            "Gold data refresh: status=%s rows %d -> %d (+%d), "
            "last date %s -> %s",
            report.status, report.rows_before, report.rows_after,
            report.rows_added, report.last_date_before, report.last_date_after,
        )
        if report.status != "ok":
            LOG.warning(
                "Gold data refresh incomplete (%s); proceeding with existing "
                "dataset", report.message,
            )
    except Exception as exc:  # pragma: no cover - defensive
        LOG.error(
            "Gold data refresh failed (%s); proceeding with existing dataset",
            exc,
        )


def _refresh_fred_yields_before_run() -> None:
    """Warm FRED yield caches before a production run (fail-safe).

    Refreshes a series only when its cached last observation is older than
    ``FRED_DAILY_SERIES_MAX_AGE_DAYS``; fresh caches are used without any
    network call. On refresh failure the stale cache is kept and recorded
    as ``fallback_stale`` so it is never presented as current data.
    """
    from connectors.fred_client import (
        FRED_DAILY_SERIES_MAX_AGE_DAYS,
        FredClient,
    )

    series_ids = ("DFII10", "DGS10", "T5YIE")
    client = FredClient()
    for series_id in series_ids:
        try:
            client.get_series(
                series_id, use_cache=True,
                max_age_days=FRED_DAILY_SERIES_MAX_AGE_DAYS,
            )
        except Exception as exc:  # pragma: no cover - defensive
            LOG.error(
                "FRED %s fetch failed (%s); proceeding with cached data",
                series_id, exc,
            )
    for series_id, record in client.freshness_report().items():
        status = record.get("status")
        if status == "fallback_stale":
            LOG.warning(
                "FRED freshness %s: status=fallback_stale "
                "cache_last_date=%s cache_age_days=%s error=%s",
                series_id, record.get("cache_last_date"),
                record.get("cache_age_days"), record.get("error"),
            )
        else:
            LOG.info(
                "FRED freshness %s: status=%s cache_last_date=%s "
                "cache_age_days=%s refreshed_last_date=%s",
                series_id, status, record.get("cache_last_date"),
                record.get("cache_age_days"),
                record.get("refreshed_last_date"),
            )


def _refresh_dxy_before_run() -> None:
    """Warm the DXY cache before a production run (fail-safe).

    Follows the same freshness contract as FRED yields: a fresh cache is
    used unchanged; a stale cache triggers a refresh; on refresh failure the
    stale cache is kept and recorded as ``fallback_stale`` so it is never
    presented as current data.
    """
    from connectors.dxy_fetcher import (
        DXY_DAILY_SERIES_MAX_AGE_DAYS,
        DXYFetcher,
    )

    fetcher = DXYFetcher()
    try:
        fetcher.get_series(
            use_cache=True,
            max_age_days=DXY_DAILY_SERIES_MAX_AGE_DAYS,
        )
    except Exception as exc:  # pragma: no cover - defensive
        LOG.error(
            "DXY fetch failed (%s); proceeding with cached data", exc,
        )
    for series_id, record in fetcher.freshness_report().items():
        status = record.get("status")
        if status == "fallback_stale":
            LOG.warning(
                "DXY freshness %s: status=fallback_stale "
                "cache_last_date=%s cache_age_days=%s error=%s",
                series_id, record.get("cache_last_date"),
                record.get("cache_age_days"), record.get("error"),
            )
        else:
            LOG.info(
                "DXY freshness %s: status=%s cache_last_date=%s "
                "cache_age_days=%s refreshed_last_date=%s",
                series_id, status, record.get("cache_last_date"),
                record.get("cache_age_days"),
                record.get("refreshed_last_date"),
            )


if __name__ == "__main__":
    sys.exit(main())
