from __future__ import annotations

from pathlib import Path
from typing import Any

from pre_market.contracts import WatchlistItem

DEFAULT_EVENTS: list[dict[str, Any]] = [
    {"event_type": "CPI", "priority": "Tier 1", "description": "Consumer Price Index (monthly)", "expected_impact": "high"},
    {"event_type": "PPI", "priority": "Tier 1", "description": "Producer Price Index (monthly)", "expected_impact": "high"},
    {"event_type": "FOMC", "priority": "Tier 1", "description": "Federal Reserve rate decision", "expected_impact": "high"},
    {"event_type": "NFP", "priority": "Tier 1", "description": "Non-Farm Payrolls (monthly)", "expected_impact": "high"},
    {"event_type": "GDP", "priority": "Tier 1", "description": "GDP advance estimate (quarterly)", "expected_impact": "high"},
    {"event_type": "ISM Manufacturing", "priority": "Tier 2", "description": "ISM Manufacturing PMI (monthly)", "expected_impact": "medium"},
    {"event_type": "ISM Services", "priority": "Tier 2", "description": "ISM Services PMI (monthly)", "expected_impact": "medium"},
    {"event_type": "Retail Sales", "priority": "Tier 2", "description": "Retail sales (monthly)", "expected_impact": "medium"},
    {"event_type": "Jobless Claims", "priority": "Tier 3", "description": "Initial jobless claims (weekly)", "expected_impact": "low"},
    {"event_type": "Treasury Auction", "priority": "Tier 3", "description": "US Treasury note/bond auction", "expected_impact": "low"},
]


class WatchlistBuilder:
    """Builds the day's watchlist of economic data releases and events.

    Prioritizes events into Tier 1 (high impact) through Tier 3 (routine).
    Can consume ReleaseCalendar CSV data if available.

    Final Hardening (D-11): falling back to the undated DEFAULT_EVENTS is an
    explicit state, never a silent substitution.  Use
    :meth:`build_with_status` to obtain the availability status alongside
    the items; ``build`` keeps the legacy signature.
    """

    STATUS_CALENDAR = "calendar"
    STATUS_DEFAULT_FALLBACK = "default_watchlist_fallback"
    STATUS_CALENDAR_READ_FAILED = "calendar_read_failed"

    def build_with_status(
        self,
        calendar_csv: str | Path | None = None,
    ) -> tuple[list[WatchlistItem], str]:
        events: list[dict[str, Any]] = []
        status = self.STATUS_CALENDAR

        if calendar_csv is not None:
            try:
                import csv

                with open(str(calendar_csv), newline="") as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        events.append({
                            "event_type": row.get("event_type", "Unknown"),
                            "release_date": row.get("release_date", ""),
                            "release_time": row.get("release_time", ""),
                            "priority": row.get("priority", "Tier 3"),
                            "description": row.get("description", ""),
                            "expected_impact": row.get("expected_impact", "low"),
                        })
            except Exception:
                status = self.STATUS_CALENDAR_READ_FAILED

        if not events:
            events = DEFAULT_EVENTS
            if status != self.STATUS_CALENDAR_READ_FAILED:
                status = self.STATUS_DEFAULT_FALLBACK

        items: list[WatchlistItem] = []
        for ev in events:
            items.append(WatchlistItem(
                event_type=str(ev["event_type"]),
                release_date=str(ev.get("release_date", "")),
                release_time=str(ev.get("release_time", "")),
                priority=str(ev.get("priority", "Tier 3")),
                description=str(ev.get("description", "")),
                expected_impact=str(ev.get("expected_impact", "low")),
            ))

        tier_order = {"Tier 1": 0, "Tier 2": 1, "Tier 3": 2}
        items.sort(key=lambda x: tier_order.get(x.priority, 99))
        return items, status

    def build(
        self,
        calendar_csv: str | Path | None = None,
    ) -> list[WatchlistItem]:
        items, _status = self.build_with_status(calendar_csv)
        return items
