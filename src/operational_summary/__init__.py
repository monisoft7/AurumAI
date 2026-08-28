"""AurumAI daily operational summary (additive measurement layer).

Builds ``daily_operational_summary.json`` inside an existing run directory
(``outputs/YYYY-MM-DD/<pipeline_id>/``) by *reading only* artifacts the
pipeline already wrote:

- ``summary.json``            (run identity)
- ``finalize.json``           (regime, decision, news, risk, trade recommendation)
- ``artifacts/technical_assessment.json``
- ``outcome.evaluated.json``
- ``runtime/calibration.json``
- ``runtime/run_registry.jsonl`` (git commit provenance)

This module never recomputes, re-derives, or simulates any value.  Every
number is copied verbatim from an existing producer.  When a producer is
absent the corresponding field is ``null`` and an explicit
``"unavailable"`` status is recorded instead of a fabricated healthy
default.

The summary is strictly additive: writing it never mutates any existing
file, and building it never changes any decision, confidence, risk, or
news semantic.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "1.0"
SUMMARY_FILENAME = "daily_operational_summary.json"

_UNAVAILABLE = "unavailable"


def _read_json(path: Path) -> Any | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _clean(value: Any) -> Any:
    """Normalize empty producer values to explicit nulls."""
    if value is None:
        return None
    if isinstance(value, str) and value.strip() == "":
        return None
    return value


def _load_registry_record(root: Path, run_id: str) -> dict[str, Any] | None:
    registry = root / "runtime" / "run_registry.jsonl"
    if not registry.exists() or not run_id:
        return None
    try:
        lines = registry.read_text(encoding="utf-8").splitlines()
    except OSError:
        return None
    record: dict[str, Any] | None = None
    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            parsed = json.loads(line)
        except ValueError:
            continue
        if isinstance(parsed, dict) and parsed.get("run_id") == run_id:
            record = parsed
    return record


def _build_decision(finalize: dict[str, Any]) -> dict[str, Any]:
    decision = finalize.get("decision") or {}
    metadata = decision.get("metadata") or {}
    return {
        "action": _clean(decision.get("decision")),
        "confidence": _clean(decision.get("institutional_confidence")),
        "selected_thesis_id": _clean(decision.get("selected_thesis_id")),
        "gate_reason": _clean(metadata.get("gate_reason")),
    }


def _build_news(finalize: dict[str, Any]) -> dict[str, Any]:
    news = finalize.get("news_intelligence")
    if not isinstance(news, dict) or not news:
        return {
            "status": _UNAVAILABLE,
            "article_count": None,
            "relevant_count": None,
            "directional_count": None,
            "unknown_count": None,
            "sentiment_status": None,
        }
    items = news.get("items") or []
    if not isinstance(items, list):
        items = []
    directional_count = 0
    unknown_count = 0
    relevant_count = 0
    for item in items:
        if not isinstance(item, dict):
            continue
        implication = str(item.get("directional_implication", ""))
        if implication == "unknown":
            unknown_count += 1
        elif implication:
            directional_count += 1
        relevance = str(item.get("gold_relevance", ""))
        if relevance in ("high", "medium"):
            relevant_count += 1
    return {
        "status": _clean(news.get("status")),
        "article_count": len(items),
        "relevant_count": relevant_count,
        "directional_count": directional_count,
        "unknown_count": unknown_count,
        "sentiment_status": _clean(news.get("sentiment_status")),
    }


def _build_technical(run_dir: Path) -> dict[str, Any]:
    technical = _read_json(run_dir / "artifacts" / "technical_assessment.json")
    if not isinstance(technical, dict) or not technical:
        return {
            "status": _UNAVAILABLE,
            "trend_direction": None,
            "momentum_direction": None,
            "structure_state": None,
            "technical_confidence": None,
        }
    return {
        "status": "ok",
        "trend_direction": _clean(technical.get("trend_direction")),
        "momentum_direction": _clean(technical.get("momentum_direction")),
        "structure_state": _clean(technical.get("structure_state")),
        "technical_confidence": _clean(technical.get("technical_confidence")),
    }


def _build_risk(finalize: dict[str, Any]) -> dict[str, Any]:
    recommendation = finalize.get("trade_recommendation") or {}
    metadata = recommendation.get("metadata") or {}
    atr_provenance = metadata.get("atr_provenance") or {}
    market_summary = metadata.get("market_risk_summary") or {}
    risk_decision = finalize.get("risk_decision") or {}
    reference_price = _clean(metadata.get("reference_price"))
    atr = _clean(atr_provenance.get("atr_14"))
    if atr is None and market_summary:
        atr = _clean(market_summary.get("atr_14"))
    return {
        "status": "ok" if recommendation else _UNAVAILABLE,
        "reference_price": reference_price,
        "atr": atr,
        "stop": _clean(recommendation.get("stop_loss")),
        "tp1": _clean(recommendation.get("take_profit_1")),
        "tp2": _clean(recommendation.get("take_profit_2")),
        "market_risk_reward": _clean(market_summary.get("market_reward_risk_ratio")),
        "risk_status": _clean(risk_decision.get("action")),
    }


def _build_governance(finalize: dict[str, Any]) -> dict[str, Any]:
    decision = finalize.get("decision") or {}
    metadata = decision.get("metadata") or {}
    bias_review = metadata.get("bias_review") or {}
    provenance_chain = decision.get("provenance_chain") or []
    return {
        "bias_review_flag": _clean(bias_review.get("human_review_flag")),
        "bias_severity": _clean(bias_review.get("overall_severity")),
        "provenance_status": "ok" if provenance_chain else _UNAVAILABLE,
    }


def _build_outcome(run_dir: Path) -> dict[str, Any]:
    outcome = _read_json(run_dir / "outcome.evaluated.json")
    if not isinstance(outcome, dict) or not outcome:
        return {
            "status": _UNAVAILABLE,
            "decision_correct": None,
            "abstention_verdict": None,
            "realized_return": None,
        }
    return {
        "status": _clean(outcome.get("status")),
        "decision_correct": _clean(outcome.get("decision_correct")),
        "abstention_verdict": _clean(outcome.get("abstention_verdict")),
        "realized_return": _clean(outcome.get("realized_gold_return")),
    }


def _build_calibration(root: Path) -> dict[str, Any]:
    calibration = _read_json(root / "runtime" / "calibration.json")
    if not isinstance(calibration, dict) or not calibration:
        return {
            "sample_count": None,
            "oos_ece": None,
            "calibration_status": _UNAVAILABLE,
        }
    statistics = calibration.get("statistics") or {}
    sample_count = _clean(calibration.get("sample_count"))
    if sample_count is None:
        sample_count = _clean(statistics.get("sample_count"))
    minimum = statistics.get("min_samples_required")
    if sample_count is not None and isinstance(minimum, (int, float)):
        calibration_status = (
            "dormant" if sample_count < minimum else "active"
        )
    elif sample_count == 0:
        calibration_status = "dormant"
    else:
        calibration_status = _UNAVAILABLE
    return {
        "sample_count": sample_count,
        "oos_ece": _clean(calibration.get("oos_ece")),
        "calibration_status": calibration_status,
    }


def _build_provenance(run_dir: Path, root: Path, run_id: str) -> dict[str, Any]:
    source_hashes: dict[str, str] = {}
    outcome = _read_json(run_dir / "outcome.evaluated.json") or {}
    if isinstance(outcome, dict):
        gold_hash = _clean(outcome.get("gold_source_sha256"))
        if gold_hash:
            source_hashes["gold_history"] = str(gold_hash)
    technical = _read_json(run_dir / "artifacts" / "technical_assessment.json") or {}
    if isinstance(technical, dict):
        technical_hash = _clean(technical.get("source_data_hash"))
        if technical_hash:
            source_hashes["technical_assessment"] = str(technical_hash)
    record = _load_registry_record(root, run_id)
    git_commit = _clean(record.get("git_commit")) if record else None
    return {
        "git_commit": git_commit,
        "source_hashes": source_hashes,
    }


def build_summary(run_dir: Path, root: Path | None = None) -> dict[str, Any]:
    """Build the daily operational summary dict from existing artifacts.

    Pure function of the run directory contents (plus the registry and
    calibration state under ``root``).  No recomputation of any pipeline
    value.
    """
    run_dir = Path(run_dir)
    root = Path(root) if root is not None else run_dir
    summary = _read_json(run_dir / "summary.json") or {}
    finalize = _read_json(run_dir / "finalize.json") or {}
    if not isinstance(summary, dict):
        summary = {}
    if not isinstance(finalize, dict):
        finalize = {}

    run_id = _clean(summary.get("pipeline_id"))
    outcome = _read_json(run_dir / "outcome.evaluated.json") or {}
    entry_date = (
        _clean(outcome.get("entry_date"))
        if isinstance(outcome, dict)
        else None
    )
    if entry_date is None and run_dir.parent.name:
        entry_date = run_dir.parent.name

    context = finalize.get("context") or {}

    return {
        "schema_version": SCHEMA_VERSION,
        "run_id": run_id,
        "entry_date": entry_date,
        "event_type": _clean(summary.get("event_type")),
        "regime": _clean(context.get("current_regime")),
        "decision": _build_decision(finalize),
        "news": _build_news(finalize),
        "technical": _build_technical(run_dir),
        "risk": _build_risk(finalize),
        "governance": _build_governance(finalize),
        "outcome": _build_outcome(run_dir),
        "calibration": _build_calibration(root),
        "provenance": _build_provenance(run_dir, root, str(run_id) if run_id else ""),
    }


def write_summary(run_dir: Path, root: Path | None = None) -> Path:
    """Write ``daily_operational_summary.json`` into the run directory.

    Write-isolated: creates only the summary file; never touches any
    existing artifact.
    """
    summary = build_summary(run_dir, root)
    path = Path(run_dir) / SUMMARY_FILENAME
    path.write_text(
        json.dumps(summary, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return path


def format_telegram_compact(summary: dict[str, Any]) -> str:
    """Render the compact phone-readable Telegram snapshot.

    Presentation only; every value is read from the summary dict built by
    :func:`build_summary`.  Missing values render as ``n/a`` so an
    unavailable channel can never pose as healthy.
    """
    decision = summary.get("decision") or {}
    news = summary.get("news") or {}
    technical = summary.get("technical") or {}
    risk = summary.get("risk") or {}
    governance = summary.get("governance") or {}
    outcome = summary.get("outcome") or {}
    calibration = summary.get("calibration") or {}

    def fmt(value: Any) -> str:
        if value is None:
            return "n/a"
        if isinstance(value, float):
            return f"{value:.4f}".rstrip("0").rstrip(".")
        return str(value)

    lines = [
        "AURUMAI DAILY SNAPSHOT",
        f"Date: {fmt(summary.get('entry_date'))} | Event: {fmt(summary.get('event_type'))}",
        f"Regime: {fmt(summary.get('regime'))}",
        f"Decision: {fmt(decision.get('action'))} "
        f"(confidence {fmt(decision.get('confidence'))})",
        f"Gate: {fmt(decision.get('gate_reason'))}",
        f"Technical: {fmt(technical.get('trend_direction'))} / "
        f"{fmt(technical.get('momentum_direction'))} / "
        f"{fmt(technical.get('structure_state'))} "
        f"(conf {fmt(technical.get('technical_confidence'))})",
        f"News: {fmt(news.get('status'))} | "
        f"articles {fmt(news.get('article_count'))} | "
        f"directional {fmt(news.get('directional_count'))} | "
        f"unknown {fmt(news.get('unknown_count'))} | "
        f"sentiment {fmt(news.get('sentiment_status'))}",
        f"Execution: ref {fmt(risk.get('reference_price'))} | "
        f"stop {fmt(risk.get('stop'))} | "
        f"tp1 {fmt(risk.get('tp1'))} | tp2 {fmt(risk.get('tp2'))}",
        f"Market RR: {fmt(risk.get('market_risk_reward'))} | "
        f"risk gate: {fmt(risk.get('risk_status'))}",
        f"Bias: severity {fmt(governance.get('bias_severity'))} | "
        f"human review {fmt(governance.get('bias_review_flag'))}",
        f"Outcome: {fmt(outcome.get('status'))} | "
        f"Calibration: {fmt(calibration.get('calibration_status'))} "
        f"({fmt(calibration.get('sample_count'))} samples)",
    ]
    return "\n".join(lines)


__all__ = [
    "SCHEMA_VERSION",
    "SUMMARY_FILENAME",
    "build_summary",
    "write_summary",
    "format_telegram_compact",
]
