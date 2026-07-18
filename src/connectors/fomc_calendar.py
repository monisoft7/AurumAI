from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

import pandas as pd

DEFAULT_CALENDAR_PATH = Path("data/calendar/fomc_meetings.csv")
_MINUTES_DELAY_DAYS = 21


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
    """Thin adapter for the FOMC meeting calendar outside Core v1.0.

    Reads from the same committed CSV snapshot as the Core adapter.
    Computes ``minutes_release_date`` as end_date + 21 calendar days
    (standard Fed practice).

    All query methods return ``FOMCMeeting`` dataclass instances.
    """

    def __init__(self, path: Path = DEFAULT_CALENDAR_PATH):
        self._path = path
        self._df: pd.DataFrame | None = None

    @property
    def df(self) -> pd.DataFrame:
        if self._df is None:
            self._df = self._load(self._path)
        return self._df

    def _load(self, path: Path) -> pd.DataFrame:
        df = pd.read_csv(path)
        required = {"start_date", "end_date"}
        missing = required.difference(df.columns)
        if missing:
            missing_text = ", ".join(sorted(missing))
            raise ValueError(f"{path} is missing required columns: {missing_text}")

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
