from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

import pandas as pd
import requests

DEFAULT_CALENDAR_PATH = Path("data/calendar/fomc_meetings.csv")
_CALENDAR_URL = "https://www.federalreserve.gov/json/calendar.json"
_MINUTES_DELAY_DAYS = 21
_HEADERS = {"User-Agent": "AurumAI/1.0"}

_KNOWN_SCHEDULE: list[dict] = [
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


@dataclass(frozen=True)
class FOMCMeeting:
    start_date: date
    end_date: date
    is_two_day: bool
    has_press_conference: bool
    statement_time: str
    meeting_type: str
    minutes_release_date: date


class FOMCCalendarConnector:
    """Thin adapter for the FOMC meeting calendar.

    Reads from a committed CSV snapshot, with optional live refresh
    from the Federal Reserve public JSON API.

    All query methods return ``FOMCMeeting`` dataclass instances.
    """

    def __init__(
        self,
        path: Path = DEFAULT_CALENDAR_PATH,
        auto_refresh: bool = True,
    ):
        self._path = path
        self._auto_refresh = auto_refresh
        self._df: pd.DataFrame | None = None

    @property
    def df(self) -> pd.DataFrame:
        if self._df is None:
            if self._auto_refresh and self._path.exists():
                try:
                    self._refresh_from_api()
                except Exception:
                    self._df = self._load_csv(self._path)
            else:
                self._df = self._load_csv(self._path)
        return self._df

    def _load_csv(self, path: Path) -> pd.DataFrame:
        df = pd.read_csv(path)
        required = {"start_date", "end_date"}
        missing = required.difference(df.columns)
        if missing:
            missing_text = ", ".join(sorted(missing))
            raise ValueError(f"{path} is missing required columns: {missing_text}")

        return self._normalize(df)

    def _refresh_from_api(self) -> None:
        r = requests.get(_CALENDAR_URL, headers=_HEADERS, timeout=30)
        r.raise_for_status()
        data = json.loads(r.content.decode("utf-8-sig"))
        events = data.get("events", [])

        rows: list[dict] = []
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

        api_years = {r["year"] for r in rows}
        for known in _KNOWN_SCHEDULE:
            if known["year"] not in api_years:
                rows.append(known)

        rows.sort(key=lambda r: (r["year"], r["month"], r["start_day"]))
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

        self._path.parent.mkdir(parents=True, exist_ok=True)
        cols = [
            "start_date", "end_date", "event_type", "meeting_type",
            "is_two_day", "has_press_conference", "statement_time",
            "year", "month",
        ]
        df[cols].to_csv(self._path, index=False)

        self._df = self._normalize(df)

    def _normalize(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        df["start_date"] = pd.to_datetime(df["start_date"], errors="raise").dt.date
        df["end_date"] = pd.to_datetime(df["end_date"], errors="raise").dt.date
        df["minutes_release_date"] = df["end_date"].apply(
            lambda d: d + timedelta(days=_MINUTES_DELAY_DAYS)
        )
        df["is_two_day"] = df["is_two_day"].astype(bool)
        df["has_press_conference"] = df["has_press_conference"].astype(bool)
        df = df.sort_values("start_date").reset_index(drop=True)
        return df

    def _to_meeting(self, row: pd.Series) -> FOMCMeeting:
        return FOMCMeeting(
            start_date=row["start_date"],
            end_date=row["end_date"],
            is_two_day=bool(row["is_two_day"]),
            has_press_conference=bool(row["has_press_conference"]),
            statement_time=str(row.get("statement_time", "")),
            meeting_type=str(row.get("meeting_type", "scheduled")),
            minutes_release_date=row["minutes_release_date"],
        )

    def refresh(self) -> None:
        self._df = None

    @property
    def is_loaded(self) -> bool:
        return self._df is not None

    def get_meeting(self, dt: date) -> FOMCMeeting | None:
        mask = (self.df["start_date"] == dt) | (self.df["end_date"] == dt)
        matches = self.df[mask]
        if matches.empty:
            return None
        return self._to_meeting(matches.iloc[0])

    def is_fomc_meeting(self, dt: date) -> bool:
        return self.get_meeting(dt) is not None

    def meetings_between(self, start: date, end: date) -> list[FOMCMeeting]:
        mask = (self.df["start_date"] >= start) & (self.df["end_date"] <= end)
        return [self._to_meeting(row) for _, row in self.df[mask].iterrows()]

    def meetings_in_year(self, year: int) -> list[FOMCMeeting]:
        return [
            self._to_meeting(row)
            for _, row in self.df.iterrows()
            if row["start_date"].year == year
        ]

    def upcoming_meetings(
        self, after: date | None = None, n: int = 5
    ) -> list[FOMCMeeting]:
        if after is None:
            after = date.today()
        mask = self.df["end_date"] >= after
        subset = self.df[mask].head(n)
        return [self._to_meeting(row) for _, row in subset.iterrows()]

    def past_meetings(
        self, before: date | None = None, n: int = 5
    ) -> list[FOMCMeeting]:
        if before is None:
            before = date.today()
        mask = self.df["start_date"] <= before
        subset = self.df[mask].tail(n)
        return [self._to_meeting(row) for _, row in subset.iterrows()]

    def list_years(self) -> list[int]:
        return sorted({row["start_date"].year for _, row in self.df.iterrows()})

    @property
    def count(self) -> int:
        return len(self.df)

    def upcoming_rate_decisions(
        self, after: date | None = None, n: int = 5
    ) -> list[tuple[date, str]]:
        return [
            (m.start_date, m.statement_time)
            for m in self.upcoming_meetings(after=after, n=n)
        ]

    def upcoming_minutes_releases(
        self, after: date | None = None, n: int = 5
    ) -> list[tuple[date, date]]:
        return [
            (m.start_date, m.minutes_release_date)
            for m in self.upcoming_meetings(after=after, n=n)
        ]
