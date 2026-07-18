"""Download FOMC meeting calendar from the Federal Reserve JSON API.

Data source: https://www.federalreserve.gov/json/calendar.json
This is a public government API — no API key required.
"""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import requests
import pandas as pd

CALENDAR_URL = "https://www.federalreserve.gov/json/calendar.json"
OUTPUT_PATH = Path("data/calendar/fomc_meetings.csv")
HEADERS = {"User-Agent": "AurumAI/1.0"}

# Fallback for years not covered by the Fed JSON API (all two-day with PC).
KNOWN_SCHEDULE: list[dict] = [
    {"year": 2023, "month": "2023-01", "start_day": 31, "is_two_day": 1, "has_press_conference": 1, "statement_time": "2:00 p.m."},
    {"year": 2023, "month": "2023-03", "start_day": 21, "is_two_day": 1, "has_press_conference": 1, "statement_time": "2:00 p.m."},
    {"year": 2023, "month": "2023-05", "start_day": 2, "is_two_day": 1, "has_press_conference": 1, "statement_time": "2:00 p.m."},
    {"year": 2023, "month": "2023-06", "start_day": 13, "is_two_day": 1, "has_press_conference": 1, "statement_time": "2:00 p.m."},
    {"year": 2023, "month": "2023-07", "start_day": 25, "is_two_day": 1, "has_press_conference": 1, "statement_time": "2:00 p.m."},
    {"year": 2023, "month": "2023-09", "start_day": 19, "is_two_day": 1, "has_press_conference": 1, "statement_time": "2:00 p.m."},
    {"year": 2023, "month": "2023-10", "start_day": 31, "is_two_day": 1, "has_press_conference": 1, "statement_time": "2:00 p.m."},
    {"year": 2023, "month": "2023-12", "start_day": 12, "is_two_day": 1, "has_press_conference": 1, "statement_time": "2:00 p.m."},
    {"year": 2024, "month": "2024-01", "start_day": 30, "is_two_day": 1, "has_press_conference": 1, "statement_time": "2:00 p.m."},
    {"year": 2024, "month": "2024-03", "start_day": 19, "is_two_day": 1, "has_press_conference": 1, "statement_time": "2:00 p.m."},
    {"year": 2024, "month": "2024-04", "start_day": 30, "is_two_day": 1, "has_press_conference": 1, "statement_time": "2:00 p.m."},
    {"year": 2024, "month": "2024-06", "start_day": 11, "is_two_day": 1, "has_press_conference": 1, "statement_time": "2:00 p.m."},
    {"year": 2024, "month": "2024-07", "start_day": 30, "is_two_day": 1, "has_press_conference": 1, "statement_time": "2:00 p.m."},
    {"year": 2024, "month": "2024-09", "start_day": 17, "is_two_day": 1, "has_press_conference": 1, "statement_time": "2:00 p.m."},
    {"year": 2024, "month": "2024-11", "start_day": 6, "is_two_day": 1, "has_press_conference": 1, "statement_time": "2:00 p.m."},
    {"year": 2024, "month": "2024-12", "start_day": 17, "is_two_day": 1, "has_press_conference": 1, "statement_time": "2:00 p.m."},
]


def fetch_calendar() -> list[dict]:
    r = requests.get(CALENDAR_URL, headers=HEADERS, timeout=30)
    r.raise_for_status()
    data = json.loads(r.content.decode("utf-8-sig"))
    return data.get("events", [])


def parse_fomc_meetings(events: list[dict]) -> list[dict]:
    rows = []
    for ev in events:
        title = (ev.get("title") or "").strip()
        if title.lower() != "fomc meeting":
            continue

        month_str = ev.get("month") or ""
        if not month_str:
            continue
        try:
            year, _ = map(int, month_str.split("-"))
        except (ValueError, AttributeError):
            continue

        days_str = ev.get("days") or ""
        parts = [p.strip() for p in str(days_str).split(",")]
        days = []
        for p in parts:
            try:
                days.append(int(p))
            except ValueError:
                continue
        if not days:
            continue

        desc = ev.get("description") or ""
        has_pc = "press conference" in desc.lower()

        time_str = ev.get("time") or ""

        rows.append({
            "year": year,
            "month": month_str,
            "start_day": min(days),
            "end_day": max(days),
            "is_two_day": 1 if len(days) > 1 else 0,
            "has_press_conference": 1 if has_pc else 0,
            "statement_time": time_str,
        })
    return rows


def build_dataframe(rows: list[dict]) -> pd.DataFrame:
    df = pd.DataFrame(rows)
    df = df.sort_values(["year", "month", "start_day"]).reset_index(drop=True)

    df["start_date"] = pd.to_datetime(
        df["month"] + "-" + df["start_day"].astype(str), format="%Y-%m-%d"
    )
    df["end_date"] = df.apply(
        lambda r: (
            r["start_date"] + pd.Timedelta(days=1)
            if r["is_two_day"]
            else r["start_date"]
        ),
        axis=1,
    )

    df["event_type"] = "FOMC"
    df["meeting_type"] = "scheduled"

    cols = [
        "start_date", "end_date", "event_type", "meeting_type",
        "is_two_day", "has_press_conference", "statement_time",
        "year", "month",
    ]
    return df[cols]


def main() -> None:
    events = fetch_calendar()
    rows = parse_fomc_meetings(events)

    api_years = {r["year"] for r in rows}
    for known in KNOWN_SCHEDULE:
        if known["year"] not in api_years:
            rows.append(known)

    rows.sort(key=lambda r: (r["year"], r["month"], r["start_day"]))

    if not rows:
        print("No FOMC meetings found.")
        sys.exit(1)

    df = build_dataframe(rows)
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUTPUT_PATH, index=False)
    today = datetime.now(timezone.utc).date()
    print(f"Updated: {today.isoformat()}")
    print(f"FOMC meetings saved: {len(df)} rows to {OUTPUT_PATH}")
    print(f"Year range: {df['start_date'].min().year} - {df['start_date'].max().year}")
    print(f"Columns: {list(df.columns)}")
    print(df[["start_date", "end_date", "is_two_day", "has_press_conference"]].to_string())


if __name__ == "__main__":
    main()
