import tempfile
from datetime import date, timedelta
from pathlib import Path

import pandas as pd
import pytest

from connectors.fomc_calendar import FOMCCalendarConnector, FOMCMeeting


SAMPLE_ROWS = [
    {"start_date": "2023-01-31", "end_date": "2023-02-01", "event_type": "FOMC",
     "meeting_type": "scheduled", "is_two_day": 1, "has_press_conference": 1,
     "statement_time": "2:00 p.m.", "year": 2023, "month": "2023-01"},
    {"start_date": "2023-03-21", "end_date": "2023-03-22", "event_type": "FOMC",
     "meeting_type": "scheduled", "is_two_day": 1, "has_press_conference": 1,
     "statement_time": "2:00 p.m.", "year": 2023, "month": "2023-03"},
    {"start_date": "2024-09-17", "end_date": "2024-09-18", "event_type": "FOMC",
     "meeting_type": "scheduled", "is_two_day": 1, "has_press_conference": 1,
     "statement_time": "2:00 p.m.", "year": 2024, "month": "2024-09"},
    {"start_date": "2024-11-06", "end_date": "2024-11-07", "event_type": "FOMC",
     "meeting_type": "scheduled", "is_two_day": 1, "has_press_conference": 1,
     "statement_time": "2:00 p.m.", "year": 2024, "month": "2024-11"},
    {"start_date": "2025-01-29", "end_date": "2025-01-29", "event_type": "FOMC",
     "meeting_type": "scheduled", "is_two_day": 0, "has_press_conference": 1,
     "statement_time": "2:00 p.m.", "year": 2025, "month": "2025-01"},
    {"start_date": "2025-07-30", "end_date": "2025-07-30", "event_type": "FOMC",
     "meeting_type": "scheduled", "is_two_day": 0, "has_press_conference": 1,
     "statement_time": "2:00 p.m.", "year": 2025, "month": "2025-07"},
]


@pytest.fixture
def sample_calendar() -> FOMCCalendarConnector:
    path = Path(tempfile.mktemp(suffix=".csv"))
    pd.DataFrame(SAMPLE_ROWS).to_csv(path, index=False)
    cal = FOMCCalendarConnector(path)
    yield cal
    path.unlink(missing_ok=True)


class TestFOMCCalendarConnectorInit:

    def test_loads_from_path(self, sample_calendar: FOMCCalendarConnector) -> None:
        assert sample_calendar.count == 6
        assert sample_calendar.is_loaded

    def test_loads_default_path(self) -> None:
        cal = FOMCCalendarConnector()
        assert cal.count > 0

    def test_refresh_clears_cache(self, sample_calendar: FOMCCalendarConnector) -> None:
        assert sample_calendar.count == 6
        assert sample_calendar.is_loaded
        sample_calendar.refresh()
        assert not sample_calendar.is_loaded
        assert sample_calendar.count == 6

    def test_raises_on_missing_required_columns(self) -> None:
        path = Path(tempfile.mktemp(suffix=".csv"))
        pd.DataFrame({"x": [1]}).to_csv(path, index=False)
        with pytest.raises(ValueError, match="missing required columns"):
            FOMCCalendarConnector(path).count
        path.unlink(missing_ok=True)


class TestFOMCMeetingDataclass:

    def test_is_frozen(self) -> None:
        m = FOMCMeeting(
            start_date=date(2024, 9, 17),
            end_date=date(2024, 9, 18),
            is_two_day=True,
            has_press_conference=True,
            statement_time="2:00 p.m.",
            meeting_type="scheduled",
            minutes_release_date=date(2024, 10, 9),
        )
        with pytest.raises((AttributeError, TypeError)):
            m.start_date = date(2025, 1, 1)

    def test_includes_minutes_release_date(self) -> None:
        m = FOMCMeeting(
            start_date=date(2024, 9, 17),
            end_date=date(2024, 9, 18),
            is_two_day=True,
            has_press_conference=True,
            statement_time="2:00 p.m.",
            meeting_type="scheduled",
            minutes_release_date=date(2024, 10, 9),
        )
        assert m.minutes_release_date == date(2024, 10, 9)


class TestGetMeeting:

    def test_returns_meeting_for_start_date(
        self, sample_calendar: FOMCCalendarConnector
    ) -> None:
        m = sample_calendar.get_meeting(date(2023, 1, 31))
        assert m is not None
        assert m.start_date == date(2023, 1, 31)
        assert m.has_press_conference

    def test_returns_meeting_for_end_date(
        self, sample_calendar: FOMCCalendarConnector
    ) -> None:
        m = sample_calendar.get_meeting(date(2023, 2, 1))
        assert m is not None
        assert m.end_date == date(2023, 2, 1)

    def test_returns_none_for_non_meeting_date(
        self, sample_calendar: FOMCCalendarConnector
    ) -> None:
        m = sample_calendar.get_meeting(date(2023, 2, 15))
        assert m is None

    def test_is_fomc_meeting_true(
        self, sample_calendar: FOMCCalendarConnector
    ) -> None:
        assert sample_calendar.is_fomc_meeting(date(2023, 1, 31))

    def test_is_fomc_meeting_false(
        self, sample_calendar: FOMCCalendarConnector
    ) -> None:
        assert not sample_calendar.is_fomc_meeting(date(2023, 2, 15))


class TestMeetingsBetween:

    def test_returns_all_in_range(
        self, sample_calendar: FOMCCalendarConnector
    ) -> None:
        meetings = sample_calendar.meetings_between(
            date(2023, 1, 1), date(2025, 12, 31)
        )
        assert len(meetings) == 6

    def test_returns_subset(
        self, sample_calendar: FOMCCalendarConnector
    ) -> None:
        meetings = sample_calendar.meetings_between(
            date(2024, 1, 1), date(2024, 12, 31)
        )
        assert len(meetings) == 2

    def test_empty_for_out_of_range(
        self, sample_calendar: FOMCCalendarConnector
    ) -> None:
        meetings = sample_calendar.meetings_between(
            date(2020, 1, 1), date(2020, 12, 31)
        )
        assert len(meetings) == 0


class TestMeetingsInYear:

    def test_returns_all_for_year(
        self, sample_calendar: FOMCCalendarConnector
    ) -> None:
        meetings = sample_calendar.meetings_in_year(2023)
        assert len(meetings) == 2

    def test_empty_for_no_meetings(
        self, sample_calendar: FOMCCalendarConnector
    ) -> None:
        meetings = sample_calendar.meetings_in_year(2030)
        assert len(meetings) == 0


class TestUpcomingMeetings:

    def test_returns_upcoming_from_date(
        self, sample_calendar: FOMCCalendarConnector
    ) -> None:
        meetings = sample_calendar.upcoming_meetings(
            after=date(2024, 1, 1), n=3
        )
        assert len(meetings) == 3
        assert meetings[0].start_date == date(2024, 9, 17)

    def test_returns_all_if_n_is_large(
        self, sample_calendar: FOMCCalendarConnector
    ) -> None:
        meetings = sample_calendar.upcoming_meetings(
            after=date(2023, 1, 1), n=100
        )
        assert len(meetings) == 6


class TestPastMeetings:

    def test_returns_past_before_date(
        self, sample_calendar: FOMCCalendarConnector
    ) -> None:
        meetings = sample_calendar.past_meetings(
            before=date(2025, 6, 1), n=2
        )
        assert len(meetings) == 2
        assert meetings[-1].start_date == date(2025, 1, 29)

    def test_empty_before_earliest(
        self, sample_calendar: FOMCCalendarConnector
    ) -> None:
        meetings = sample_calendar.past_meetings(
            before=date(2020, 1, 1), n=5
        )
        assert len(meetings) == 0


class TestListYears:

    def test_returns_sorted_years(
        self, sample_calendar: FOMCCalendarConnector
    ) -> None:
        years = sample_calendar.list_years()
        assert years == [2023, 2024, 2025]


class TestCount:

    def test_returns_total_count(
        self, sample_calendar: FOMCCalendarConnector
    ) -> None:
        assert sample_calendar.count == 6


class TestMinutesReleaseDate:

    def test_minutes_release_date_is_end_date_plus_21_days(
        self, sample_calendar: FOMCCalendarConnector
    ) -> None:
        m = sample_calendar.get_meeting(date(2023, 1, 31))
        assert m is not None
        assert m.minutes_release_date == m.end_date + timedelta(days=21)

    def test_upcoming_minutes_returns_tuples(
        self, sample_calendar: FOMCCalendarConnector
    ) -> None:
        releases = sample_calendar.upcoming_minutes_releases(
            after=date(2024, 1, 1), n=2
        )
        assert len(releases) == 2
        meeting_date, minutes_date = releases[0]
        assert meeting_date == date(2024, 9, 17)
        assert minutes_date == date(2024, 10, 9)


class TestUpcomingRateDecisions:

    def test_returns_meeting_date_and_statement_time(
        self, sample_calendar: FOMCCalendarConnector
    ) -> None:
        decisions = sample_calendar.upcoming_rate_decisions(
            after=date(2024, 1, 1), n=2
        )
        assert len(decisions) == 2
        meeting_date, statement_time = decisions[0]
        assert meeting_date == date(2024, 9, 17)
        assert statement_time == "2:00 p.m."


class TestWithRealData:

    def test_default_path_has_expected_years(self) -> None:
        cal = FOMCCalendarConnector()
        years = cal.list_years()
        assert 2023 in years
        assert 2024 in years
        assert 2025 in years
        assert cal.count >= 16

    def test_known_meeting_date(self) -> None:
        cal = FOMCCalendarConnector()
        m = cal.get_meeting(date(2023, 1, 31))
        assert m is not None
        assert m.has_press_conference
        assert m.end_date == date(2023, 2, 1)

    def test_has_press_conference_field(self) -> None:
        cal = FOMCCalendarConnector()
        for year in [2023, 2024, 2025]:
            meetings = cal.meetings_in_year(year)
            for m in meetings:
                assert m.has_press_conference

    def test_fomc_count_per_year(self) -> None:
        cal = FOMCCalendarConnector()
        for year in [2023, 2024, 2025]:
            meetings = cal.meetings_in_year(year)
            assert len(meetings) == 8

    def test_minutes_release_date_with_real_data(self) -> None:
        cal = FOMCCalendarConnector()
        m = cal.get_meeting(date(2023, 1, 31))
        assert m is not None
        expected_minutes = m.end_date + timedelta(days=21)
        assert m.minutes_release_date == expected_minutes

    def test_upcoming_rate_decisions_with_real_data(self) -> None:
        cal = FOMCCalendarConnector()
        decisions = cal.upcoming_rate_decisions(after=date(2025, 6, 1), n=3)
        assert len(decisions) == 3
        for meeting_date, statement_time in decisions:
            assert statement_time == "2:00 p.m."
