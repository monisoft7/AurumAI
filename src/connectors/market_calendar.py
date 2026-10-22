"""Run-local, source-attributed calendar for a declared set of US releases.

FRED publishes BLS release dates, BEA supplies its official ICS, and the Fed
supplies its official FOMC calendar. News headlines never establish coverage.
No cached or hardcoded schedule can silently become a verified live calendar.
"""

from __future__ import annotations

import json
import os
import re
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta, timezone
from typing import Any, Callable
from zoneinfo import ZoneInfo

BEA_URL = "https://www.bea.gov/news/schedule/ics/online-calendar-subscription.ics"
FED_URL = "https://www.federalreserve.gov/json/calendar.json"
FRED_URL = "https://api.stlouisfed.org/fred/release/dates"
FRED_RELEASES = {"CPI": 10, "NFP": 50, "PPI": 46}
SCOPE = ("CPI", "NFP", "PPI", "GDP", "PCE", "FOMC", "FOMC_MINUTES")
SOURCE_URLS = {
    "FRED_BLS": [f"https://fred.stlouisfed.org/release?rid={rid}" for rid in FRED_RELEASES.values()],
    "BEA": [BEA_URL], "FederalReserve": [FED_URL],
}
ET = ZoneInfo("America/New_York")


def _read(url: str) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": "AurumAI/1.0"})
    with urllib.request.urlopen(request, timeout=20) as response:
        return response.read(2_000_001).decode("utf-8-sig")


def _fred_events(read: Callable[[str], str], year: int) -> list[dict[str, str]]:
    key = os.environ.get("FRED_API_KEY", "").strip()
    if not key:
        raise ValueError("FRED_API_KEY_missing")
    events = []
    for kind, release_id in FRED_RELEASES.items():
        query = urllib.parse.urlencode({
            "release_id": release_id, "api_key": key, "file_type": "json",
            "include_release_dates_with_no_data": "true", "limit": 1000,
            "realtime_start": f"{year - 1}-01-01", "realtime_end": f"{year + 1}-12-31",
        })
        payload = json.loads(read(f"{FRED_URL}?{query}"))
        rows = payload["release_dates"]
        if not isinstance(rows, list) or not rows or payload.get("count", len(rows)) > len(rows):
            raise ValueError("FRED_calendar_empty_or_truncated")
        for row in rows:
            if int(row["release_id"]) != release_id:
                raise ValueError("FRED_release_mismatch")
            events.append({"event": kind, "date": date.fromisoformat(row["date"]).isoformat(),
                           "source": f"https://fred.stlouisfed.org/release?rid={release_id}"})
    return events


def _bea_events(text: str) -> list[dict[str, str]]:
    if "BEGIN:VCALENDAR" not in text or "END:VCALENDAR" not in text:
        raise ValueError("BEA_calendar_invalid")
    # RFC 5545 line unfolding, including summaries wrapped mid-word.
    text = re.sub(r"\r?\n[ \t]", "", text)
    events = []
    for block in text.split("BEGIN:VEVENT")[1:]:
        block = block.split("END:VEVENT", 1)[0]
        summary = re.search(r"(?m)^SUMMARY:(.+)\r?$", block)
        if not summary:
            raise ValueError("BEA_event_without_summary")
        title = summary.group(1).lower()
        if "personal income and outlays" in title:
            kind = "PCE"
        elif "gross domestic product" in title or re.match(r"gdp\b", title):
            # State/county GDP is outside this national release scope.
            if any(word in title for word in ("by state", "by county")):
                continue
            kind = "GDP"
        else:
            continue
        start = re.search(r"(?m)^DTSTART([^:]*):([^\r\n]+)", block)
        if not start:
            raise ValueError("BEA_event_without_date")
        attrs, value = start.groups()
        timestamp = datetime.strptime(value.rstrip("Z"), "%Y%m%dT%H%M%S")
        if value.endswith("Z"):
            timestamp = timestamp.replace(tzinfo=timezone.utc)
        else:
            tzid = re.search(r"TZID=([^;]+)", attrs)
            if not tzid:
                raise ValueError("BEA_event_without_timezone")
            timestamp = timestamp.replace(tzinfo=ZoneInfo(tzid.group(1)))
        events.append({"event": kind, "date": timestamp.astimezone(ET).date().isoformat(),
                       "source": BEA_URL})
    return events


def _fed_events(text: str) -> list[dict[str, str]]:
    # The official feed contains literal newlines in descriptions.
    rows = json.loads(text, strict=False)["events"]
    events = []
    for row in rows:
        title = str(row.get("title", "")).lower()
        if row.get("type") != "FOMC" and "fomc" not in title:
            continue
        if "minutes" in title:
            kind = "FOMC_MINUTES"
        elif "meeting" in title or "press conference" in title:
            kind = "FOMC"
        else:
            continue
        month = str(row.get("month") or "")
        if not month:
            continue  # Undated template rows in the official feed are not events.
        if not re.fullmatch(r"\d{4}-\d{2}", month):
            raise ValueError("Fed_event_month_invalid")
        # Meetings can span two days; hold on both days, including a range
        # or comma-separated representation. A press conference is day two.
        days = [int(day) for day in re.findall(r"\d+", str(row["days"]))]
        if not days:
            raise ValueError("Fed_event_without_date")
        end = date.fromisoformat(f"{month}-{days[-1]:02d}")
        description = str(row.get("description", "")).lower()
        if title == "fomc meeting" and "two-day" in description:
            event_dates = [end - timedelta(days=1), end]
        else:
            event_dates = [date.fromisoformat(f"{month}-{day:02d}") for day in days]
        for event_date in event_dates:
            events.append({"event": kind, "date": event_date.isoformat(), "source": FED_URL})
    return events


def fetch_market_calendar(*, now: datetime | None = None,
                          read: Callable[[str], str] = _read) -> dict[str, Any]:
    clock = now or datetime.now(timezone.utc)
    if clock.tzinfo is None:
        raise ValueError("calendar clock must be timezone-aware")
    today = clock.astimezone(ET).date()
    events: list[dict[str, str]] = []
    sources: dict[str, Any] = {}
    for name, load, scope in (
        ("FRED_BLS", lambda: _fred_events(read, today.year), ("CPI", "NFP", "PPI")),
        ("BEA", lambda: _bea_events(read(BEA_URL)), ("GDP", "PCE")),
        ("FederalReserve", lambda: _fed_events(read(FED_URL)), ("FOMC", "FOMC_MINUTES")),
    ):
        try:
            loaded = load()
            coverage = {}
            for kind in scope:
                dates = [date.fromisoformat(e["date"]) for e in loaded if e["event"] == kind]
                if not dates or min(dates) > today or max(dates) < today:
                    raise ValueError(f"calendar_does_not_cover_date:{kind}")
                coverage[kind] = {"first_date": min(dates).isoformat(), "last_date": max(dates).isoformat()}
            events.extend(loaded)
            sources[name] = {"status": "verified", "scope": list(scope),
                             "urls": SOURCE_URLS[name], "coverage": coverage}
        except Exception as exc:
            # Never persist exception messages: network errors can contain
            # URLs with API credentials. The failing source remains explicit.
            sources[name] = {"status": "unavailable", "scope": list(scope),
                             "urls": SOURCE_URLS[name], "error_type": type(exc).__name__}
    verified = all(s["status"] == "verified" for s in sources.values())
    unique = {(e["event"], e["date"]): e for e in events}
    ordered = sorted(unique.values(), key=lambda e: (e["date"], e["event"]))
    return {
        "status": "verified" if verified else "unavailable",
        "as_of_date": today.isoformat(), "timezone": "America/New_York",
        "checked_at": clock.astimezone(timezone.utc).isoformat(),
        "scope": list(SCOPE), "sources": sources,
        "events_today": [e for e in ordered if e["date"] == today.isoformat()],
        "upcoming_events": [e for e in ordered if e["date"] > today.isoformat()][:10],
        "execution_policy": "hold_on_covered_event_day",
    }
