"""Point-in-time-safe, append-only paper-trading records.

This module consumes completed runtime artifacts.  It does not import or call
the production pipeline and it has no broker or network integration.
"""

from __future__ import annotations

import csv
import datetime as dt
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable


PREDICTION_SCHEMA_VERSION = "1.0"
OUTCOME_SCHEMA_VERSION = "1.0"
ALLOWED_DECISIONS = {"BUY", "SELL", "NO_TRADE"}
FRESH_STATUSES = {"fresh", "current"}
INELIGIBLE_FRESHNESS = {"stale", "unavailable", "missing", "unknown"}
REQUIRED_PAPER_SOURCES = (
    "DGS10",
    "DFII10",
    "T5YIE",
    "CPI",
    "Gold",
    "DXY",
)
RELIABILITY_CATEGORIES = {"very_low", "low", "moderate", "high"}


class PaperTradingError(ValueError):
    """The requested ledger operation would violate its integrity contract."""


class HorizonNotComplete(PaperTradingError):
    """The requested session horizon has not yet completed."""


def _read_object(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise PaperTradingError(f"invalid JSON artifact: {path.name}") from exc
    if not isinstance(value, dict):
        raise PaperTradingError(f"artifact must be a JSON object: {path.name}")
    return value


def _canonical_bytes(value: Any) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        + "\n"
    ).encode("utf-8")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_new_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open("xb") as handle:
            handle.write(_canonical_bytes(value))
            handle.flush()
    except FileExistsError as exc:
        raise PaperTradingError(f"immutable record already exists: {path.name}") from exc


def _parse_utc(value: str, field: str) -> dt.datetime:
    try:
        parsed = dt.datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError) as exc:
        raise PaperTradingError(f"{field} must be an ISO-8601 timestamp") from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=dt.timezone.utc)
    return parsed.astimezone(dt.timezone.utc)


def _utc_text(value: dt.datetime) -> str:
    return value.astimezone(dt.timezone.utc).isoformat().replace("+00:00", "Z")


def _safe_relative(path: Path, parent: Path) -> str:
    try:
        return path.resolve().relative_to(parent.resolve()).as_posix()
    except ValueError as exc:
        raise PaperTradingError(f"artifact is outside runtime directory: {path}") from exc


def _normalise_decision(value: Any) -> str:
    raw = str(value or "").strip().upper()
    aliases = {
        "POSITIVE": "BUY",
        "STRONG_POSITIVE": "BUY",
        "NEGATIVE": "SELL",
        "STRONG_NEGATIVE": "SELL",
        "HOLD": "NO_TRADE",
        "NEUTRAL": "NO_TRADE",
        "INSUFFICIENT_EVIDENCE": "NO_TRADE",
    }
    result = aliases.get(raw, raw)
    if result not in ALLOWED_DECISIONS:
        raise PaperTradingError(f"unsupported decision: {raw or '<missing>'}")
    return result


def _validate_config(config: dict[str, Any], baseline_commit: str) -> None:
    required = {
        "evaluation_id",
        "cohort_id",
        "baseline_commit",
        "instrument",
        "timezone",
        "evaluation_horizons_sessions",
        "entry_rule",
        "transaction_costs",
        "minimum_completed_trades",
        "minimum_calendar_days",
        "go_thresholds",
    }
    missing = sorted(required - set(config))
    if missing:
        raise PaperTradingError(f"baseline config missing fields: {', '.join(missing)}")
    expected = str(config["baseline_commit"]).lower()
    supplied = str(baseline_commit).lower()
    if supplied != expected:
        raise PaperTradingError("baseline commit does not match locked configuration")
    if len(expected) != 40 or any(c not in "0123456789abcdef" for c in expected):
        raise PaperTradingError("baseline_commit must be a full 40-character SHA")
    horizons = config["evaluation_horizons_sessions"]
    if horizons != [1, 3, 5]:
        raise PaperTradingError("locked session horizons must be exactly [1, 3, 5]")
    if config["instrument"] != "XAU/USD":
        raise PaperTradingError("paper-trading instrument must be XAU/USD")
    automation = config.get("automation_context")
    if automation is not None:
        if not isinstance(automation, dict):
            raise PaperTradingError("automation_context must be an object")
        if automation.get("strategy_baseline_commit") != expected:
            raise PaperTradingError("automation strategy baseline mismatch")
        harness_commit = str(automation.get("harness_commit") or "").lower()
        if len(harness_commit) != 40 or any(
            character not in "0123456789abcdef" for character in harness_commit
        ):
            raise PaperTradingError("automation harness_commit must be a full SHA")
        github_actions = automation.get("github_actions")
        if not isinstance(github_actions, dict) or not all(
            github_actions.get(field)
            for field in ("run_id", "run_attempt", "run_url", "run_created_at_utc")
        ):
            raise PaperTradingError("automation GitHub Actions provenance is incomplete")
        _parse_utc(github_actions["run_created_at_utc"], "GitHub run creation timestamp")
        attempt = str(github_actions["run_attempt"])
        if not attempt.isdecimal() or int(attempt) < 1:
            raise PaperTradingError("automation GitHub run attempt is invalid")


def _validate_runtime(
    stage_outputs: dict[str, Any], summary: dict[str, Any], outcome: dict[str, Any]
) -> str:
    runtime_id = str(summary.get("pipeline_id") or "")
    if not runtime_id:
        raise PaperTradingError("summary is missing pipeline_id")
    if summary.get("success") is not True:
        raise PaperTradingError("runtime is incomplete or failed")
    if summary.get("errors") or summary.get("failed_stages"):
        raise PaperTradingError("runtime contains errors or failed stages")
    if stage_outputs.get("schema_version") != "1.0":
        raise PaperTradingError("unsupported stage_outputs schema")
    outputs = stage_outputs.get("outputs")
    stage_ids = stage_outputs.get("stage_ids")
    count = stage_outputs.get("stage_count")
    if not isinstance(outputs, dict) or not isinstance(stage_ids, list):
        raise PaperTradingError("invalid stage_outputs contract")
    if count != len(outputs) or count != len(stage_ids):
        raise PaperTradingError("stage_outputs count mismatch")
    if sorted(stage_ids) != sorted(outputs) or len(set(stage_ids)) != len(stage_ids):
        raise PaperTradingError("stage_outputs identifiers mismatch")
    if stage_outputs.get("pipeline_id") != runtime_id:
        raise PaperTradingError("stage_outputs runtime mismatch")
    if summary.get("stage_output_count") not in (None, count):
        raise PaperTradingError("summary stage count mismatch")
    if outcome.get("run_id") != runtime_id or outcome.get("status") != "pending":
        raise PaperTradingError("outcome is not a pending record for this runtime")
    if outcome.get("schema_version") != "1.1":
        raise PaperTradingError("unsupported outcome schema")
    return runtime_id


def _nested(mapping: dict[str, Any], *keys: str) -> Any:
    value: Any = mapping
    for key in keys:
        if not isinstance(value, dict):
            return None
        value = value.get(key)
    return value


def _status_from_output(value: Any) -> str:
    if not isinstance(value, dict):
        return "unknown"
    for key in ("freshness_status", "data_freshness", "freshness"):
        status = value.get(key)
        if isinstance(status, dict):
            status = status.get("status")
        if isinstance(status, str):
            return status.strip().lower()
    if value.get("available") is False:
        return "unavailable"
    return "unknown"


def _freshness_snapshot(
    outputs: dict[str, Any], summary: dict[str, Any]
) -> dict[str, str]:
    snapshot: dict[str, str] = {}
    def visit(value: Any) -> None:
        if isinstance(value, dict):
            source_map = value.get("source_freshness")
            if isinstance(source_map, dict):
                for source, status in sorted(source_map.items()):
                    if isinstance(status, dict):
                        status = status.get("status")
                    snapshot[str(source)] = str(status or "unknown").lower()
            source = value.get("source") or value.get("provider")
            if isinstance(source, str):
                snapshot[source] = _status_from_output(value)
            for child in value.values():
                visit(child)
        elif isinstance(value, list):
            for child in value:
                visit(child)

    visit(outputs)
    for key in ("data_path", "gold_path"):
        path = summary.get(key)
        if isinstance(path, str) and path and path not in snapshot:
            snapshot[path] = "unknown"
    if not snapshot:
        snapshot["runtime_sources"] = "unknown"
    return snapshot


def _structured_freshness_records(outputs: dict[str, Any]) -> dict[str, Any]:
    """Collect only explicitly structured source-freshness contracts."""
    records: dict[str, Any] = {}
    canonical = {name.casefold(): name for name in REQUIRED_PAPER_SOURCES}

    finalize = outputs.get("finalize")
    authoritative = (
        finalize.get("source_freshness") if isinstance(finalize, dict) else None
    )
    if isinstance(authoritative, dict):
        for name in REQUIRED_PAPER_SOURCES:
            if name in authoritative:
                records[name] = authoritative[name]
        for source, record in authoritative.items():
            name = canonical.get(str(source).casefold())
            if name is not None and name not in records:
                records[name] = record

    def visit(value: Any) -> None:
        if isinstance(value, dict):
            source_map = value.get("source_freshness")
            if isinstance(source_map, dict):
                for source, record in source_map.items():
                    name = canonical.get(str(source).casefold())
                    if name is not None and name not in records:
                        records[name] = record
            for child in value.values():
                visit(child)
        elif isinstance(value, list):
            for child in value:
                visit(child)

    visit(outputs)
    return records


def _optional_date(value: Any) -> dt.date | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        return dt.datetime.fromisoformat(value.strip().replace("Z", "+00:00")).date()
    except ValueError:
        try:
            return dt.date.fromisoformat(value.strip())
        except ValueError:
            return None


def _normalise_source_freshness(value: Any) -> dict[str, Any]:
    missing = {
        "status": "unknown",
        "observation_date": None,
        "retrieved_at": None,
        "age_days": None,
        "max_age_days": None,
        "availability": "unknown",
        "reason": "structured freshness metadata missing",
    }
    if not isinstance(value, dict):
        return missing

    raw_status = str(value.get("status") or "unknown").strip().lower()
    observation_text = (
        value.get("observation_date")
        or value.get("last_observation_date")
        or value.get("latest_observation_date")
        or value.get("refreshed_last_date")
        or value.get("cache_last_date")
    )
    retrieved_text = (
        value.get("retrieved_at")
        or value.get("retrieved_at_utc")
        or value.get("checked_at")
    )
    observation = _optional_date(observation_text)
    retrieved = _optional_date(retrieved_text)
    threshold = value.get("max_age_days")
    threshold = threshold if type(threshold) is int and threshold >= 0 else None
    declared_reason = value.get("reason") or value.get("freshness_reason")
    age_days = (
        (retrieved - observation).days
        if observation is not None and retrieved is not None
        else None
    )
    availability = value.get("availability")
    if value.get("available") is False or availability in {"missing", "unavailable"}:
        status = "unavailable" if availability != "missing" else "missing"
        reason = str(declared_reason or "source is not available")
    elif raw_status in {"missing", "unavailable"}:
        status = raw_status
        reason = str(declared_reason or f"source status is {raw_status}")
    elif raw_status in {"stale", "fallback_stale"}:
        status = "stale"
        reason = str(declared_reason or f"source status is {raw_status}")
    elif raw_status in {"fresh", "current", "refreshed", "ok"}:
        if observation is None or retrieved is None or threshold is None:
            status = "unknown"
            reason = "positive status lacks observation/retrieval date or max_age_days"
        elif age_days is None or age_days < 0:
            status = "unknown"
            reason = "source freshness dates are inconsistent"
        elif age_days <= threshold:
            status = "fresh"
            reason = str(
                declared_reason
                or "explicit observation is within the declared age limit"
            )
        else:
            status = "stale"
            reason = str(
                declared_reason
                or "explicit observation exceeds the declared age limit"
            )
    else:
        status = "unknown"
        reason = str(declared_reason or "source status is not recognized")

    return {
        "status": status,
        "observation_date": str(observation_text) if observation is not None else None,
        "retrieved_at": str(retrieved_text) if retrieved is not None else None,
        "age_days": age_days,
        "max_age_days": threshold,
        "availability": (
            "unavailable" if status in {"missing", "unavailable"} else "available"
        ),
        "reason": reason,
    }


def _selected_reliability_category(outputs: dict[str, Any]) -> str | None:
    decision = outputs.get("decision_engine")
    decision = decision if isinstance(decision, dict) else {}
    confidence = outputs.get("confidence_engine")
    confidence = confidence if isinstance(confidence, dict) else {}
    selected = decision.get("selected_thesis_id") or confidence.get(
        "primary_thesis_id"
    )
    records = confidence.get("theses_confidence")
    if not isinstance(records, list):
        return None
    for record in records:
        if not isinstance(record, dict) or record.get("thesis_id") != selected:
            continue
        category = str(record.get("reliability_category") or "").strip().lower()
        return category if category in RELIABILITY_CATEGORIES else None
    return None


def build_paper_evaluation(
    outputs: dict[str, Any], summary: dict[str, Any], outcome: dict[str, Any]
) -> dict[str, Any]:
    """Build canonical decision-time metadata without consulting logs or mtimes."""
    del summary, outcome  # Reserved for versioned structured contracts only.
    raw_sources = _structured_freshness_records(outputs)
    sources = {
        name: _normalise_source_freshness(raw_sources.get(name))
        for name in REQUIRED_PAPER_SOURCES
    }
    exclusions = [
        f"{name}:{record['status']}:{record['reason']}"
        for name, record in sources.items()
        if record["status"] != "fresh"
    ]
    return {
        "reliability_category": _selected_reliability_category(outputs),
        "financially_eligible": not exclusions,
        "integrity_exclusions": exclusions,
        "source_freshness": sources,
    }


def _first_gate(outcome: dict[str, Any], finalize: dict[str, Any]) -> dict[str, Any] | None:
    gates = _nested(outcome, "decision_snapshot", "gate_reasons")
    if not isinstance(gates, dict):
        return None
    selected: tuple[str, Any] | None = None
    for name, value in gates.items():
        blocked = value is False or (name.endswith("blocked") and value is True)
        if blocked:
            selected = (str(name), value)
            break
    if selected is None and gates:
        selected = next(iter(gates.items()))
    if selected is None:
        return None
    explanation = _nested(finalize, "decision", "decision_explanation")
    return {
        "gate": selected[0],
        "recorded_value": selected[1],
        "rejection_reason": explanation if isinstance(explanation, str) else None,
    }


def _artifact_records(run_dir: Path, summary: dict[str, Any]) -> list[dict[str, str]]:
    names = ["stage_outputs.json", "outcome.json", "summary.json"]
    report_value = summary.get("report_path")
    if isinstance(report_value, str) and report_value:
        report_path = Path(report_value)
        if not report_path.is_absolute():
            report_path = run_dir / report_path
        if report_path.is_file():
            names.append(_safe_relative(report_path, run_dir))
    else:
        for candidate in ("report.md", "report.html", "report.pdf"):
            if (run_dir / candidate).is_file():
                names.append(candidate)
                break
    records = []
    for name in names:
        path = run_dir / name
        if not path.is_file():
            raise PaperTradingError(f"required runtime artifact missing: {name}")
        records.append({"path": _safe_relative(path, run_dir), "sha256": _sha256(path)})
    return records


def create_prediction_manifest(
    runtime_dir: Path,
    registry_dir: Path,
    config_path: Path,
    *,
    baseline_commit: str,
    created_at_utc: str | None = None,
) -> Path:
    """Freeze one successful runtime into a new immutable prediction file."""
    runtime_dir = Path(runtime_dir)
    config = _read_object(Path(config_path))
    _validate_config(config, baseline_commit)
    required = {
        name: runtime_dir / name
        for name in ("stage_outputs.json", "summary.json", "outcome.json")
    }
    for name, path in required.items():
        if not path.is_file():
            raise PaperTradingError(f"required runtime artifact missing: {name}")
    stage_outputs = _read_object(required["stage_outputs.json"])
    summary = _read_object(required["summary.json"])
    outcome = _read_object(required["outcome.json"])
    runtime_id = _validate_runtime(stage_outputs, summary, outcome)
    decision_time = _parse_utc(str(summary.get("timestamp") or ""), "decision timestamp")
    created = _parse_utc(
        created_at_utc or _utc_text(dt.datetime.now(dt.timezone.utc)), "created_at_utc"
    )
    if created < decision_time:
        raise PaperTradingError("manifest creation cannot precede the decision")
    github_actions = (config.get("automation_context") or {}).get("github_actions")
    if github_actions and _parse_utc(
        github_actions["run_created_at_utc"], "GitHub run creation timestamp"
    ) > created:
        raise PaperTradingError("manifest creation cannot precede the GitHub run")
    evaluation_id = str(config["evaluation_id"])
    prediction_id = "pred_" + hashlib.sha256(
        f"{evaluation_id}\0{runtime_id}".encode("utf-8")
    ).hexdigest()[:24]
    target = Path(registry_dir) / "predictions" / f"{prediction_id}.json"
    if target.exists():
        raise PaperTradingError("prediction already exists for runtime/evaluation_id")

    outputs = stage_outputs["outputs"]
    finalize = outputs.get("finalize") if isinstance(outputs.get("finalize"), dict) else {}
    recommendation = outputs.get("trade_recommendation")
    recommendation = recommendation if isinstance(recommendation, dict) else {}
    decision = _normalise_decision(summary.get("decision") or outcome.get("decision"))
    direction = _nested(finalize, "decision", "metadata", "selected_thesis_direction")
    if direction is None:
        direction = {"BUY": "bullish", "SELL": "bearish"}.get(decision)
    paper_evaluation = build_paper_evaluation(outputs, summary, outcome)
    freshness = {
        source: record["status"]
        for source, record in paper_evaluation["source_freshness"].items()
    }
    eligible = paper_evaluation["financially_eligible"]
    risk_size = {
        key: recommendation[key]
        for key in ("risk", "risk_pct", "size", "position_size", "recommended_size")
        if key in recommendation
    }
    confidence = summary.get("decision_confidence")
    reliability = recommendation.get("reliability")
    if reliability is None:
        reliability = recommendation.get("reliability_score")
    manifest: dict[str, Any] = {
        "schema_version": PREDICTION_SCHEMA_VERSION,
        "artifact": "paper_trading_prediction",
        "status": "pending",
        "prediction_id": prediction_id,
        "evaluation_id": evaluation_id,
        "cohort_id": str(config["cohort_id"]),
        "baseline_commit": str(config["baseline_commit"]),
        "strategy_baseline_commit": str(
            (config.get("automation_context") or {}).get(
                "strategy_baseline_commit", config["baseline_commit"]
            )
        ),
        "harness_commit": (config.get("automation_context") or {}).get(
            "harness_commit"
        ),
        "github_actions": (config.get("automation_context") or {}).get(
            "github_actions"
        ),
        "runtime_id": runtime_id,
        "created_at_utc": _utc_text(created),
        "decision_timestamp": _utc_text(decision_time),
        "decision_timezone": str(config["timezone"]),
        "instrument": "XAU/USD",
        "decision": decision,
        "direction": direction,
        "confidence": confidence if isinstance(confidence, (int, float)) else None,
        "reliability": reliability if isinstance(reliability, (int, float)) else None,
        "reliability_category": paper_evaluation["reliability_category"],
        "paper_evaluation": paper_evaluation,
        "recommended_risk_size": risk_size or None,
        "first_decision_gate": _first_gate(outcome, finalize),
        "entry_rule": config["entry_rule"],
        "evaluation_horizons_sessions": config["evaluation_horizons_sessions"],
        "transaction_costs": config["transaction_costs"],
        "economic_gate": {
            "minimum_completed_trades": config["minimum_completed_trades"],
            "minimum_calendar_days": config["minimum_calendar_days"],
            **config["go_thresholds"],
        },
        "freshness_status": freshness,
        "financially_eligible": eligible,
        "artifacts": _artifact_records(runtime_dir, summary),
    }
    _write_new_json(target, manifest)
    return target


def prediction_sha256(path: Path) -> str:
    return _sha256(Path(path))


def _load_prices(path: Path, as_of: dt.datetime) -> list[tuple[dt.datetime, float]]:
    try:
        with Path(path).open(newline="", encoding="utf-8-sig") as handle:
            reader = csv.DictReader(handle)
            rows = list(reader)
    except OSError as exc:
        raise PaperTradingError("price data unavailable") from exc
    parsed: list[tuple[dt.datetime, float]] = []
    for row in rows:
        timestamp_raw = row.get("timestamp") or row.get("Date") or row.get("date")
        close_raw = row.get("close") or row.get("Close")
        if timestamp_raw is None or close_raw is None:
            raise PaperTradingError("prices require timestamp/Date and close/Close")
        timestamp = _parse_utc(timestamp_raw, "price timestamp")
        available_raw = row.get("available_at_utc")
        available = _parse_utc(available_raw, "available_at_utc") if available_raw else timestamp
        if available <= as_of:
            try:
                parsed.append((timestamp, float(close_raw)))
            except ValueError as exc:
                raise PaperTradingError("invalid close price") from exc
    parsed.sort(key=lambda item: item[0])
    if len({timestamp for timestamp, _ in parsed}) != len(parsed):
        raise PaperTradingError("duplicate price session timestamp")
    return parsed


def evaluate_prediction(
    prediction_path: Path,
    outcomes_dir: Path,
    prices_path: Path,
    *,
    horizon_sessions: int,
    as_of_utc: str,
    freshness_status: str = "fresh",
) -> Path:
    """Write one immutable, per-horizon outcome without touching prediction."""
    prediction_path = Path(prediction_path)
    prediction = _read_object(prediction_path)
    if prediction.get("schema_version") != PREDICTION_SCHEMA_VERSION:
        raise PaperTradingError("unsupported prediction schema")
    horizon = int(horizon_sessions)
    if horizon not in prediction.get("evaluation_horizons_sessions", []):
        raise PaperTradingError("horizon is not locked for this cohort")
    prediction_id = str(prediction.get("prediction_id") or "")
    target = Path(outcomes_dir) / f"{prediction_id}.h{horizon}.outcome.json"
    if target.exists():
        raise PaperTradingError("this prediction horizon is already evaluated")
    decision = _normalise_decision(prediction.get("decision"))
    as_of = _parse_utc(as_of_utc, "as_of_utc")
    decision_time = _parse_utc(prediction["decision_timestamp"], "decision_timestamp")
    pred_hash = _sha256(prediction_path)
    status = str(freshness_status).strip().lower()
    if not Path(prices_path).is_file():
        status = "missing"
    manifest_fresh = bool(prediction.get("financially_eligible"))
    base: dict[str, Any] = {
        "schema_version": OUTCOME_SCHEMA_VERSION,
        "artifact": "paper_trading_outcome",
        "outcome_id": f"{prediction_id}.h{horizon}",
        "prediction_id": prediction_id,
        "prediction_sha256": pred_hash,
        "evaluation_id": prediction.get("evaluation_id"),
        "cohort_id": prediction.get("cohort_id"),
        "baseline_commit": prediction.get("baseline_commit"),
        "runtime_id": prediction.get("runtime_id"),
        "decision": decision,
        "horizon_sessions": horizon,
        "evaluated_at_utc": _utc_text(as_of),
        "price_data": {
            "path": Path(prices_path).name,
            "sha256": _sha256(Path(prices_path)) if Path(prices_path).is_file() else None,
            "freshness_status": status,
        },
        "status": "unevaluable",
        "eligible_trade": False,
        "exclusion_reason": None,
        "entry": None,
        "exit": None,
        "gross_return_pct": None,
        "transaction_cost_pct": None,
        "net_return_pct": None,
        "hit": None,
        "integrity": {"lookahead_safe": True, "prediction_unchanged": True},
    }
    if not Path(prices_path).is_file():
        base["exclusion_reason"] = "outcome_data_not_fresh"
        _write_new_json(target, base)
        return target
    prices = _load_prices(Path(prices_path), as_of)
    entry_index = next(
        (index for index, (timestamp, _) in enumerate(prices) if timestamp > decision_time),
        None,
    )
    if entry_index is None or entry_index + horizon >= len(prices):
        raise HorizonNotComplete("evaluation horizon has not completed")
    if status not in FRESH_STATUSES or not manifest_fresh:
        base["exclusion_reason"] = (
            "outcome_data_not_fresh" if status not in FRESH_STATUSES
            else "decision_inputs_not_fresh"
        )
        _write_new_json(target, base)
        return target
    entry_time, entry_price = prices[entry_index]
    exit_time, exit_price = prices[entry_index + horizon]
    created = _parse_utc(prediction.get("created_at_utc"), "created_at_utc")
    if not (decision_time <= created < entry_time < exit_time <= as_of):
        raise PaperTradingError("lookahead_or_timestamp_violation")
    if entry_price <= 0 or exit_price <= 0:
        raise PaperTradingError("prices must be positive")
    base["entry"] = {"timestamp": _utc_text(entry_time), "close": entry_price}
    base["exit"] = {"timestamp": _utc_text(exit_time), "close": exit_price}
    base["status"] = "completed"
    if decision == "NO_TRADE":
        base["exclusion_reason"] = "no_trade"
    else:
        market_return = (exit_price - entry_price) / entry_price * 100.0
        gross = market_return if decision == "BUY" else -market_return
        costs = prediction.get("transaction_costs") or {}
        round_trip = float(costs.get("round_trip_cost_bps", 0.0))
        slippage = 2.0 * float(costs.get("slippage_bps_per_side", 0.0))
        cost_pct = (round_trip + slippage) / 100.0
        net = gross - cost_pct
        base.update(
            {
                "eligible_trade": True,
                "gross_return_pct": round(gross, 10),
                "transaction_cost_pct": round(cost_pct, 10),
                "net_return_pct": round(net, 10),
                "hit": net > 0.0,
            }
        )
    _write_new_json(target, base)
    return target


def _bucket(value: Any) -> str:
    if not isinstance(value, (int, float)):
        return "unknown"
    if value < 0.5:
        return "low_[0,0.5)"
    if value < 0.75:
        return "medium_[0.5,0.75)"
    return "high_[0.75,1]"


def _trade_metrics(records: Iterable[dict[str, Any]]) -> dict[str, Any]:
    ordered = sorted(records, key=lambda row: row.get("evaluated_at_utc", ""))
    returns = [float(row["net_return_pct"]) for row in ordered]
    wins = [value for value in returns if value > 0]
    losses = [value for value in returns if value < 0]
    flats = [value for value in returns if value == 0]
    equity = peak = 1.0
    max_drawdown = 0.0
    for value in returns:
        equity *= 1.0 + value / 100.0
        peak = max(peak, equity)
        if peak:
            max_drawdown = max(max_drawdown, (peak - equity) / peak * 100.0)
    return {
        "completed_trades": len(returns),
        "winning_trades": len(wins),
        "losing_trades": len(losses),
        "flat_trades": len(flats),
        "hit_rate": len(wins) / len(returns) if returns else None,
        "average_win_pct": sum(wins) / len(wins) if wins else None,
        "average_loss_pct": sum(losses) / len(losses) if losses else None,
        "net_expectancy_pct": sum(returns) / len(returns) if returns else None,
        "cumulative_net_return_pct": (equity - 1.0) * 100.0 if returns else None,
        "profit_factor": (
            sum(wins) / abs(sum(losses))
            if losses and sum(losses) < 0
            else None
        ),
        "maximum_drawdown_pct": max_drawdown if returns else None,
    }


def _outcome_integrity(
    outcome: dict[str, Any], prediction: dict[str, Any], prediction_hash: str
) -> str | None:
    if outcome.get("prediction_sha256") != prediction_hash:
        return "prediction_hash_mismatch"
    if outcome.get("evaluation_id") != prediction.get("evaluation_id"):
        return "evaluation_id_mismatch"
    if outcome.get("status") == "completed":
        entry = outcome.get("entry")
        exit_value = outcome.get("exit")
        if not isinstance(entry, dict) or not isinstance(exit_value, dict):
            return "missing_entry_or_exit"
        decision_time = _parse_utc(prediction["decision_timestamp"], "decision_timestamp")
        entry_time = _parse_utc(entry.get("timestamp"), "entry timestamp")
        exit_time = _parse_utc(exit_value.get("timestamp"), "exit timestamp")
        evaluated = _parse_utc(outcome.get("evaluated_at_utc"), "evaluated_at_utc")
        try:
            created = _parse_utc(prediction.get("created_at_utc"), "created_at_utc")
        except PaperTradingError:
            return "lookahead_or_timestamp_violation"
        if not (decision_time <= created < entry_time < exit_time <= evaluated):
            return "lookahead_or_timestamp_violation"
    return None


def summarize_cohort(
    registry_dir: Path,
    evaluation_id: str | None = None,
    *,
    cohort_id: str | None = None,
) -> dict[str, Any]:
    """Aggregate one cohort and apply the precommitted economic gates."""
    if bool(evaluation_id) == bool(cohort_id):
        raise PaperTradingError("select exactly one evaluation_id or cohort_id")
    root = Path(registry_dir)
    predictions: dict[str, tuple[dict[str, Any], str]] = {}
    exclusions: Counter[str] = Counter()
    for path in sorted((root / "predictions").glob("*.json")):
        try:
            item = _read_object(path)
            selected = (
                item.get("evaluation_id") == evaluation_id
                if evaluation_id
                else item.get("cohort_id") == cohort_id
            )
            if selected:
                predictions[item["prediction_id"]] = (item, _sha256(path))
        except (PaperTradingError, KeyError):
            exclusions["invalid_prediction_record"] += 1
    outcomes: list[dict[str, Any]] = []
    seen_horizons: set[tuple[str, int]] = set()
    for path in sorted((root / "outcomes").glob("*.json")):
        try:
            item = _read_object(path)
            selected = (
                item.get("evaluation_id") == evaluation_id
                if evaluation_id
                else item.get("cohort_id") == cohort_id
            )
            if not selected:
                continue
            pred_pair = predictions.get(item.get("prediction_id"))
            if pred_pair is None:
                exclusions["orphan_outcome"] += 1
                continue
            key = (item["prediction_id"], int(item["horizon_sessions"]))
            if key in seen_horizons:
                exclusions["duplicate_horizon"] += 1
                continue
            seen_horizons.add(key)
            integrity_error = _outcome_integrity(item, pred_pair[0], pred_pair[1])
            if integrity_error:
                exclusions[integrity_error] += 1
                continue
            if item.get("status") != "completed":
                exclusions[str(item.get("exclusion_reason") or "unevaluable_outcome")] += 1
                continue
            outcomes.append(item)
        except (PaperTradingError, KeyError, TypeError, ValueError):
            exclusions["invalid_outcome_record"] += 1

    prediction_values = [pair[0] for pair in predictions.values()]
    counts = Counter(item["decision"] for item in prediction_values)
    config_like = prediction_values[0] if prediction_values else {}
    horizons = config_like.get("evaluation_horizons_sessions", [1, 3, 5])
    primary = int(horizons[0])
    eligible_predictions = {
        item["prediction_id"]
        for item in prediction_values
        if item.get("decision") in {"BUY", "SELL"} and item.get("financially_eligible")
    }
    primary_trades = [
        item
        for item in outcomes
        if item.get("eligible_trade") and int(item["horizon_sessions"]) == primary
    ]
    by_horizon = {
        str(horizon): _trade_metrics(
            item
            for item in outcomes
            if item.get("eligible_trade") and int(item["horizon_sessions"]) == horizon
        )
        for horizon in horizons
    }
    by_confidence: dict[str, list[dict[str, Any]]] = defaultdict(list)
    by_reliability: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in primary_trades:
        prediction = predictions[item["prediction_id"]][0]
        by_confidence[_bucket(prediction.get("confidence"))].append(item)
        by_reliability[_bucket(prediction.get("reliability"))].append(item)
    headline = _trade_metrics(primary_trades)
    decision_times = [
        _parse_utc(item["decision_timestamp"], "decision_timestamp")
        for item in prediction_values
    ]
    evaluation_times = [
        _parse_utc(item["evaluated_at_utc"], "evaluated_at_utc") for item in outcomes
    ]
    calendar_days = (
        (max(evaluation_times).date() - min(decision_times).date()).days + 1
        if decision_times and evaluation_times
        else 0
    )
    locked_gate = config_like.get("economic_gate") or {}
    min_trades = int(locked_gate.get("minimum_completed_trades", 30))
    min_days = int(locked_gate.get("minimum_calendar_days", 60))
    thresholds = {
        "net_expectancy_pct_gt": float(locked_gate.get("net_expectancy_pct_gt", 0.0)),
        "profit_factor_gte": float(locked_gate.get("profit_factor_gte", 1.2)),
        "max_drawdown_pct_lte": float(locked_gate.get("max_drawdown_pct_lte", 10.0)),
    }
    reasons: list[str] = []
    integrity_failures = ("prediction_hash_mismatch", "lookahead_or_timestamp_violation")
    if any(key in exclusions for key in integrity_failures):
        gate_status = "NO_GO"
        reasons.append("data_integrity_failure")
    elif len(primary_trades) < min_trades or calendar_days < min_days:
        gate_status = "INSUFFICIENT_SAMPLE"
        reasons.append("minimum_sample_or_duration_not_met")
    else:
        if (
            headline["net_expectancy_pct"] is None
            or headline["net_expectancy_pct"] <= 0
        ):
            reasons.append("non_positive_net_expectancy")
        profit_factor = headline["profit_factor"]
        no_losses = headline["losing_trades"] == 0 and headline["winning_trades"] > 0
        if not no_losses and (
            profit_factor is None or profit_factor < thresholds["profit_factor_gte"]
        ):
            reasons.append("profit_factor_below_1_20")
        drawdown = headline["maximum_drawdown_pct"]
        if drawdown is None or drawdown > thresholds["max_drawdown_pct_lte"]:
            reasons.append("maximum_drawdown_above_10_pct")
        gate_status = "NO_GO" if reasons else "GO"
    total = len(prediction_values)
    completed_ids = {item["prediction_id"] for item in primary_trades}
    return {
        "schema_version": "1.0",
        "artifact": "paper_trading_cohort_summary",
        "evaluation_id": evaluation_id,
        "cohort_id": cohort_id,
        "primary_horizon_sessions": primary,
        "total_decisions": total,
        "decision_counts": {
            key: counts.get(key, 0) for key in ("BUY", "SELL", "NO_TRADE")
        },
        "eligible_trades": len(eligible_predictions),
        "completed_trades": len(completed_ids),
        "coverage_rate": (
            len(completed_ids) / len(eligible_predictions)
            if eligible_predictions
            else 0.0
        ),
        "abstention_rate": counts.get("NO_TRADE", 0) / total if total else 0.0,
        **headline,
        "results_by_horizon": by_horizon,
        "results_by_confidence_bucket": {
            key: _trade_metrics(value)
            for key, value in sorted(by_confidence.items())
        },
        "results_by_reliability_bucket": {
            key: _trade_metrics(value)
            for key, value in sorted(by_reliability.items())
        },
        "data_integrity_exclusions": dict(sorted(exclusions.items())),
        "calendar_days_observed": calendar_days,
        "economic_gate": {
            "status": gate_status,
            "reasons": reasons,
            "minimum_completed_trades": min_trades,
            "minimum_calendar_days": min_days,
            **thresholds,
            "disclaimer": (
                "Eligibility screen only; not a profit guarantee or "
                "live-trading authorization."
            ),
        },
    }
