"""One final, auditable execution decision for a completed daily run.

The institutional decision is a research signal.  This policy applies the
risk and data-availability gates before any consumer treats it as actionable.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any, Mapping
from zoneinfo import ZoneInfo

from connectors.gold_freshness import assess_gold_freshness
from connectors.market_calendar import SCOPE

from forecasting.decision_gate import apply_institutional_risk_gate

REQUIRED_SOURCES = ("Gold", "CPI", "DGS10", "DFII10", "T5YIE", "DXY")
GOOD_FRESHNESS = frozenset({"ok", "fresh", "refreshed"})


def final_execution_decision(
    decision: str | None,
    confidence: float | None,
    risk_status: str | None,
    freshness: Mapping[str, Mapping[str, Any]] | None,
    *,
    as_of: date,
    structure: str | None = None,
    human_review: bool = False,
    human_review_approved: bool = False,
    asset: str | None = None,
    price_source: str | None = None,
    plan_ready: bool = True,
    event_calendar: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Fail closed when required evidence or a risk gate is unavailable."""
    direction = str(decision or "NO_TRADE").upper()
    reasons: list[str] = []
    bad_sources: list[str] = []
    records = freshness or {}
    for source in REQUIRED_SOURCES:
        record = records.get(source) or {}
        if source == "Gold":
            record = assess_gold_freshness(record, as_of)
        status = str(record.get("status") or "unknown").lower()
        if status not in GOOD_FRESHNESS:
            bad_sources.append(f"{source}:{status}")
            continue
        observed = record.get("observation_date")
        max_age = record.get("max_age_days")
        try:
            observation_date = date.fromisoformat(str(observed)[:10])
            age = (as_of - observation_date).days
            if age < 0 or not isinstance(max_age, (int, float)) or age > max_age:
                bad_sources.append(f"{source}:age_{age}d")
        except (TypeError, ValueError):
            bad_sources.append(f"{source}:missing_observation_date")
    if bad_sources:
        reasons.append("data_unavailable_or_stale")
    if str(asset or "").upper() in {"XAU/USD", "XAUUSD"}:
        source_symbol = str(price_source or "").upper().replace("/", "").replace("_", "")
        if "XAUUSD" not in source_symbol:
            bad_sources.append("Gold:instrument_mismatch_or_unknown_source")
            reasons.append("instrument_mismatch")
        calendar = event_calendar or {}
        calendar_verified = (
            calendar.get("status") == "verified"
            and set(calendar.get("scope") or ()) == set(SCOPE)
            and all((calendar.get("sources") or {}).get(s, {}).get("status") == "verified"
                    for s in ("FRED_BLS", "BEA", "FederalReserve"))
        )
        try:
            checked = datetime.fromisoformat(str(calendar.get("checked_at")))
            calendar_date = checked.astimezone(ZoneInfo("America/New_York")).date()
            calendar_verified = (
                calendar_verified and checked.tzinfo is not None
                and checked.astimezone(timezone.utc).date() == as_of
                and calendar.get("as_of_date") == calendar_date.isoformat()
                and isinstance(calendar.get("events_today"), list)
            )
        except (TypeError, ValueError):
            calendar_verified = False
        if not calendar_verified:
            reasons.append("event_calendar_unverified_or_stale")
        elif calendar["events_today"]:
            reasons.append("scheduled_high_impact_event_day")

    if direction not in {"BUY", "SELL"}:
        reasons.append("no_directional_research_signal")
    elif not plan_ready:
        reasons.append("trade_plan_unavailable")
    if confidence is None:
        reasons.append("confidence_unavailable")

    gate = apply_institutional_risk_gate(
        decision=direction,
        confidence=confidence if confidence is not None else 0.0,
        structure=structure,
        current_risk_status=str(risk_status or "unknown"),
        human_review=human_review,
    )
    if gate["action"] not in {"BUY", "SELL"}:
        reasons.append(str(gate["gate_reason"] or "institutional_gate_wait"))
    if str(gate["risk_status"]).lower() not in {"proceed", "scale_down"}:
        reasons.append(f"risk_status_{gate['risk_status']}")
    if gate["human_review"] and not human_review_approved:
        reasons.append("human_review_required")

    allowed = not reasons
    return {
        "research_direction": direction,
        "action": direction if allowed else "WAIT",
        "execution_allowed": allowed,
        "confidence": confidence,
        "risk_status": gate["risk_status"],
        "gate_reason": "approved" if allowed else reasons[0],
        "reasons": list(dict.fromkeys(reasons)),
        "unavailable_sources": bad_sources,
        "price_source": price_source,
        "human_review": bool(gate["human_review"]),
        "human_review_reason": gate["human_review_reason"],
        "as_of": as_of.isoformat(),
    }


def publishable_recommendation(
    recommendation: Mapping[str, Any], execution: Mapping[str, Any]
) -> dict[str, Any]:
    """Publish an actionable plan only after the final gate approves it."""
    result = dict(recommendation)
    result["execution_decision"] = dict(execution)
    if not execution.get("execution_allowed"):
        result["recommendation_action"] = "WAIT"
        result["entry_zone"] = []
        for key in ("stop_loss", "take_profit_1", "take_profit_2", "position_size_recommendation"):
            result[key] = ""
        result["risk_pct"] = 0.0
        metadata = result.get("metadata")
        if isinstance(metadata, Mapping):
            result["metadata"] = {
                key: value for key, value in metadata.items()
                if key != "market_risk_summary"
            }
    return result
