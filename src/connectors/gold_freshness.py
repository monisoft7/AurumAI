"""Eligibility of completed daily gold bars, independently of download success."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any, Mapping


def previous_trading_date(as_of: date) -> date:
    """Minimum expected bar: previous weekday; holidays fail closed if missing.

    This is not an exchange holiday calendar. A provider holiday without a new
    bar remains ineligible until verified, rather than granting a seven-day grace.
    """
    expected = as_of - timedelta(days=1)
    while expected.weekday() >= 5:
        expected -= timedelta(days=1)
    return expected


def assess_gold_freshness(record: Mapping[str, Any], as_of: date) -> dict[str, Any]:
    expected = previous_trading_date(as_of)
    result = dict(record)
    result.update({
        "contract": "completed_daily_bar",
        "expected_observation_date": expected.isoformat(),
        "max_age_days": (as_of - expected).days,
    })
    if str(record.get("status", "unknown")).lower() not in {"ok", "fresh", "refreshed"}:
        return result
    try:
        observed = date.fromisoformat(str(record.get("observation_date"))[:10])
    except ValueError:
        result.update(status="unavailable", reason="gold_bar_date_missing_or_invalid")
        return result
    if observed >= as_of:
        result.update(status="unavailable", reason="gold_daily_bar_not_completed")
    elif observed < expected:
        result.update(status="stale", reason=f"gold_bar_before_expected:{expected.isoformat()}")
    return result
