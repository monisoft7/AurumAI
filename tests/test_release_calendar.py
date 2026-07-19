from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

import pandas as pd
import pytest

from knowledge.builders.lesson_builder import LessonBuilder, LessonBuilderConfig
from knowledge.events.base import ReleaseCalendar
from knowledge.events.cpi import CPIEvent
from knowledge.events.release_calendar import ReleaseRecord


# ===========================================================================
# Helpers
# ===========================================================================


def runtime_dir(name: str) -> Path:
    path = Path(__file__).resolve().parent / "_runtime" / name
    if path.exists():
        shutil.rmtree(path)
    path.mkdir(parents=True)
    return path


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(path, index=False)


def write_gold(path: Path, n: int = 300, start: str = "2020-01-02") -> None:
    """Write a gold CSV with *n* weekly trading days starting at *start*."""
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = ["Date,Close"]
    price = 1000.0
    dt = pd.Timestamp(start)
    for _ in range(n):
        if dt.weekday() < 5:
            lines.append(f"{dt.date().isoformat()},{price:.1f}")
            price += 2.0 if _ % 2 == 0 else -1.0
        dt += pd.Timedelta(days=1)
    path.write_text("\n".join(lines), encoding="utf-8")


PROJECT_ROOT = Path(__file__).resolve().parents[1]
CPI_RELEASE_CSV = PROJECT_ROOT / "data" / "calendar" / "cpi_releases.csv"


# ===========================================================================
# Criterion 1 – ReleaseCalendar CSV load
# ===========================================================================


class TestReleaseCalendarLoading:
    def test_calendar_csv_exists(self) -> None:
        assert CPI_RELEASE_CSV.exists(), f"Missing: {CPI_RELEASE_CSV}"

    def test_calendar_loads(self) -> None:
        cal = ReleaseCalendar.from_csv(str(CPI_RELEASE_CSV))
        assert len(cal.records) > 0

    def test_calendar_columns(self) -> None:
        df = pd.read_csv(CPI_RELEASE_CSV)
        assert "reference_period" in df.columns
        assert "release_date" in df.columns
        assert "release_time" in df.columns

    def test_calendar_release_after_reference(self) -> None:
        df = pd.read_csv(CPI_RELEASE_CSV)
        ref = pd.to_datetime(df["reference_period"])
        rel = pd.to_datetime(df["release_date"])
        assert (rel >= ref).all(), "release_date must be >= reference_period"

    def test_calendar_no_duplicate_reference_periods(self) -> None:
        df = pd.read_csv(CPI_RELEASE_CSV)
        assert df["reference_period"].is_unique, "duplicate reference_period"

    def test_calendar_release_record_model(self) -> None:
        cal = ReleaseCalendar.from_csv(str(CPI_RELEASE_CSV))
        rec = cal.records[0]
        assert isinstance(rec, ReleaseRecord)
        assert rec.timezone is not None


# ===========================================================================
# Criterion 2 – Manual CPIEvent release calendar integration
# ===========================================================================


class TestCPIEventCalendar:
    def test_cpi_event_accepts_calendar_path(self) -> None:
        event = CPIEvent(release_calendar_path=str(CPI_RELEASE_CSV))
        assert event.release_calendar is not None

    def test_cpi_event_default_no_calendar(self) -> None:
        event = CPIEvent()
        assert event.release_calendar is None

    def test_cpi_event_supports_default_constant(self) -> None:
        from knowledge.events.cpi import DEFAULT_CPI_RELEASE_CALENDAR
        assert DEFAULT_CPI_RELEASE_CALENDAR == "data/calendar/cpi_releases.csv"


# ===========================================================================
# Criterion 3 – Extra column passthrough (release_timestamp in feature set)
# ===========================================================================


class TestExtraColumnPassthrough:
    def test_release_timestamp_survives_load_and_extract(self, tmp_path: Path) -> None:
        cpi_csv = tmp_path / "cpi.csv"
        cpi_csv.write_text(
            "Date,Value,release_timestamp\n"
            "2019-12-01,99.0,2020-01-14 08:30:00\n"
            "2020-01-01,100.0,2020-02-13 08:30:00\n"
            "2020-02-01,101.0,2020-03-12 08:30:00\n",
            encoding="utf-8",
        )
        from knowledge.events.cpi import CPIEvent
        event = CPIEvent()
        df = event.load_and_extract(cpi_csv)
        assert "release_timestamp" in df.columns
        # After shift+dropna, the first row is dropped; second row survives
        survived = df["release_timestamp"].dropna()
        assert len(survived) >= 1

    def test_load_and_extract_with_calendar_adds_release_ts(
        self, tmp_path: Path,
    ) -> None:
        cpi_csv = tmp_path / "cpi.csv"
        cpi_csv.write_text(
            "Date,Value\n2020-01-01,100.0\n2020-02-01,101.0\n",
            encoding="utf-8",
        )
        cal_csv = tmp_path / "cal.csv"
        cal_csv.write_text(
            "reference_period,release_date,release_time,timezone\n"
            "2020-01-01,2020-02-13,08:30,US/Eastern\n"
            "2020-02-01,2020-03-12,08:30,US/Eastern\n",
            encoding="utf-8",
        )
        cal = ReleaseCalendar.from_csv(str(cal_csv))
        from knowledge.events.cpi import CPIEvent
        event = CPIEvent()
        df = event.load_and_extract_with_calendar(cpi_csv, cal)
        assert "release_timestamp" in df.columns
        assert "release_timezone" in df.columns


# ===========================================================================
# Criterion 4 – LessonBuilder release-timestamp anchor alignment
# ===========================================================================


def _calendar_anchor_fixture(
    base_path: Path,
    cpi_rows: list[dict],
) -> LessonBuilder:
    cpi_path = base_path / "economic" / "CPIAUCSL.csv"
    gold_path = base_path / "history" / "gold.csv"
    output_path = base_path / "lessons" / "cpi_gold_lessons.csv"

    write_csv(cpi_path, cpi_rows)
    write_gold(gold_path, start="2020-01-02")

    config = LessonBuilderConfig(
        event_data_path=cpi_path,
        gold_path=gold_path,
        output_path=output_path,
    )
    return LessonBuilder(config)


class TestLessonBuilderCalendarAnchoring:
    """Verify that when release_timestamp is present the lesson anchors on
    the release timestamp rather than the reference-period date."""

    def test_anchors_on_release_timestamp_when_present(self) -> None:
        builder = _calendar_anchor_fixture(
            runtime_dir("anchor_release"),
            [
                {"Date": "2019-12-01", "Value": 99.0, "release_timestamp": "2020-01-14 08:30:00"},
                {"Date": "2020-01-01", "Value": 100.0, "release_timestamp": "2020-02-13 08:30:00"},
                {"Date": "2020-02-01", "Value": 101.0, "release_timestamp": "2020-03-12 08:30:00"},
            ],
        )
        lessons = builder.build()

        row1 = lessons[lessons["event_date"] == "2020-01-01"].iloc[0]
        assert row1["anchor_gold_date"] == "2020-02-13", (
            f"Expected 2020-02-13 (release timestamp), got {row1['anchor_gold_date']}"
        )
        assert row1["alignment_method"] == "first_gold_session_on_or_after_release_timestamp"
        assert "release_timestamp" in row1

    def test_legacy_path_uses_event_date(self) -> None:
        base = runtime_dir("anchor_legacy")
        cpi_path = base / "economic" / "CPIAUCSL.csv"
        gold_path = base / "history" / "gold.csv"
        output_path = base / "lessons" / "cpi_gold_lessons.csv"
        # Gold starts before CPI dates so that the legacy Date-based
        # filter (row["Date"] < first_gold_date) does not skip 2020-01-01.
        write_csv(
            cpi_path,
            [
                {"Date": "2019-12-01", "Value": 99.0},
                {"Date": "2020-01-01", "Value": 100.0},
                {"Date": "2020-02-01", "Value": 101.0},
            ],
        )
        write_gold(gold_path, start="2019-11-01")
        config = LessonBuilderConfig(
            event_data_path=cpi_path,
            gold_path=gold_path,
            output_path=output_path,
        )
        builder = LessonBuilder(config)
        lessons = builder.build()

        row1 = lessons[lessons["event_date"] == "2020-01-01"].iloc[0]
        assert row1["anchor_gold_date"] == "2020-01-01", (
            f"Expected 2020-01-01 (same-day gold session), got {row1['anchor_gold_date']}"
        )
        assert row1["alignment_method"] == "first_gold_session_on_or_after_event_date"
        assert "release_timestamp" not in row1

    def test_calendar_config_passed_to_builder(self) -> None:
        base = runtime_dir("anchor_cal_config")
        cpi_path = base / "economic" / "CPIAUCSL.csv"
        gold_path = base / "history" / "gold.csv"
        output_path = base / "lessons" / "cpi_gold_lessons.csv"
        cal_path = base / "calendar" / "cpi_releases.csv"

        write_csv(
            cpi_path,
            [
                {"Date": "2019-12-01", "Value": 99.0},
                {"Date": "2020-01-01", "Value": 100.0},
            ],
        )
        write_gold(gold_path, start="2019-11-01")
        write_csv(
            cal_path,
            [
                {"reference_period": "2019-12-01", "release_date": "2020-01-14", "release_time": "08:30", "timezone": "US/Eastern"},
                {"reference_period": "2020-01-01", "release_date": "2020-02-13", "release_time": "08:30", "timezone": "US/Eastern"},
            ],
        )

        config = LessonBuilderConfig(
            event_data_path=cpi_path,
            gold_path=gold_path,
            output_path=output_path,
            release_calendar_path=str(cal_path),
        )
        builder = LessonBuilder(config)
        lessons = builder.build()

        assert len(lessons) == 1
        assert lessons.iloc[0]["anchor_gold_date"] == "2020-02-13"
        assert lessons.iloc[0]["alignment_method"] == "first_gold_session_on_or_after_release_timestamp"


# ===========================================================================
# Criterion 5 – Determinism
# ===========================================================================


class TestDeterminism:
    def test_identical_inputs_produce_identical_lessons_with_calendar(
        self,
    ) -> None:
        base = runtime_dir("deterministic_cal")
        cpi_path = base / "economic" / "CPIAUCSL.csv"
        gold_path = base / "history" / "gold.csv"
        output_path = base / "lessons" / "cpi_gold_lessons.csv"

        write_csv(
            cpi_path,
            [
                {"Date": "2020-01-01", "Value": 100.0, "release_timestamp": "2020-02-13 08:30:00"},
                {"Date": "2020-02-01", "Value": 101.0, "release_timestamp": "2020-03-12 08:30:00"},
            ],
        )
        write_gold(gold_path, start="2020-01-02")

        config = LessonBuilderConfig(
            event_data_path=cpi_path,
            gold_path=gold_path,
            output_path=output_path,
        )
        builder = LessonBuilder(config)

        first = builder.build()
        second = builder.build()

        pd.testing.assert_frame_equal(first, second)


# ===========================================================================
# Criterion 6 – Lesson ID uniqueness
# ===========================================================================


class TestLessonIdUniqueness:
    def test_lesson_ids_unique_with_release_timestamp(self) -> None:
        base = runtime_dir("unique_ids")
        cpi_path = base / "economic" / "CPIAUCSL.csv"
        gold_path = base / "history" / "gold.csv"
        output_path = base / "lessons" / "cpi_gold_lessons.csv"

        write_csv(
            cpi_path,
            [
                {"Date": "2020-01-01", "Value": 100.0, "release_timestamp": "2020-02-13 08:30:00"},
                {"Date": "2020-02-01", "Value": 101.0, "release_timestamp": "2020-03-12 08:30:00"},
            ],
        )
        write_gold(gold_path, start="2020-01-02")

        config = LessonBuilderConfig(
            event_data_path=cpi_path,
            gold_path=gold_path,
            output_path=output_path,
        )
        builder = LessonBuilder(config)
        lessons = builder.build()

        assert lessons["lesson_id"].is_unique


# ===========================================================================
# Criterion 7 – Fail-closed behaviour
# ===========================================================================


class TestFailClosed:
    def test_missing_gold_close_column_still_fails(self) -> None:
        base = runtime_dir("fail_gold")
        write_csv(
            base / "economic" / "CPIAUCSL.csv",
            [{"Date": "2020-01-01", "Value": 100.0}],
        )
        write_csv(
            base / "history" / "gold.csv",
            [{"Date": "2020-01-02", "Open": 1000.0}],
        )

        builder = LessonBuilder(
            LessonBuilderConfig(
                event_data_path=base / "economic" / "CPIAUCSL.csv",
                gold_path=base / "history" / "gold.csv",
            )
        )
        with pytest.raises(ValueError, match="missing required columns: Close"):
            builder.build()

    def test_empty_cpi_csv_returns_empty_lessons(self, tmp_path: Path) -> None:
        cpi_csv = tmp_path / "cpi.csv"
        cpi_csv.write_text("Date,Value\n", encoding="utf-8")
        gold_csv = tmp_path / "gold.csv"
        write_gold(gold_csv, n=10)

        builder = LessonBuilder(
            LessonBuilderConfig(
                event_data_path=cpi_csv,
                gold_path=gold_csv,
            )
        )
        lessons = builder.build()
        assert len(lessons) == 0


# ===========================================================================
# Criterion 8 – HistoricalReplayEngine release-by-release dispatch
# ===========================================================================


class TestReplayDispatch:
    """Verify the engine dispatches CPI to release-by-release path and
    other types to legacy path."""

    def test_release_calendar_path_for_returns_cpi(self) -> None:
        from simulation.historical_replay import HistoricalReplayEngine
        path = HistoricalReplayEngine._release_calendar_path_for("CPI")
        assert path is not None
        assert "cpi_releases" in path.name

    def test_release_calendar_path_for_returns_none_for_other(self) -> None:
        from simulation.historical_replay import HistoricalReplayEngine
        for etype in ("NFP", "GDP", "PPI", "INTEREST_RATE", "PMI", "FOMC"):
            assert HistoricalReplayEngine._release_calendar_path_for(etype) is None


# ===========================================================================
# Criterion 9 – ReleaseRecord & ReleaseCalendar model integrity
# ===========================================================================


class TestReleaseRecordModel:
    def test_release_record_creation(self) -> None:
        rec = ReleaseRecord(
            reference_period="2020-01-01",
            release_date="2020-02-13",
            release_time="08:30",
            timezone="US/Eastern",
        )
        assert rec.reference_period == "2020-01-01"
        assert rec.release_timestamp_et == "2020-02-13T08:30:00"

    def test_release_calendar_from_csv_separate_cols(self, tmp_path: Path) -> None:
        csv = tmp_path / "cal.csv"
        csv.write_text(
            "reference_period,release_date,release_time,timezone\n"
            "2020-01-01,2020-02-13,08:30,US/Eastern\n",
            encoding="utf-8",
        )
        cal = ReleaseCalendar.from_csv(str(csv))
        assert len(cal.records) == 1
        assert cal.records[0].reference_period == "2020-01-01"

    def test_release_calendar_from_csv_combined_ts(self, tmp_path: Path) -> None:
        csv = tmp_path / "cal.csv"
        csv.write_text(
            "reference_period,release_timestamp,release_timezone\n"
            "2020-01-01,2020-02-13 08:30:00,US/Eastern\n",
            encoding="utf-8",
        )
        cal = ReleaseCalendar.from_csv(str(csv))
        assert len(cal.records) == 1
        assert cal.records[0].release_timestamp_et == "2020-02-13T08:30:00"

    def test_release_calendar_empty_csv_raises(self, tmp_path: Path) -> None:
        csv = tmp_path / "empty.csv"
        csv.write_text("reference_period,release_date,release_time,timezone\n", encoding="utf-8")
        with pytest.raises(ValueError, match="at least one record"):
            ReleaseCalendar.from_csv(str(csv))


# ===========================================================================
# Criterion 10 – Backward compatibility (legacy Date-only path)
# ===========================================================================


class TestBackwardCompatibility:
    def test_lesson_builder_works_without_any_calendar(self) -> None:
        base = runtime_dir("backward_compat")
        cpi_path = base / "economic" / "CPIAUCSL.csv"
        gold_path = base / "history" / "gold.csv"
        output_path = base / "lessons" / "cpi_gold_lessons.csv"

        write_csv(
            cpi_path,
            [
                {"Date": "2019-12-01", "Value": 99.0},
                {"Date": "2020-01-01", "Value": 100.0},
            ],
        )
        write_gold(gold_path, start="2019-11-01")

        config = LessonBuilderConfig(
            event_data_path=cpi_path,
            gold_path=gold_path,
            output_path=output_path,
        )
        builder = LessonBuilder(config)
        lessons = builder.build()

        assert len(lessons) == 1
        assert "release_timestamp" not in lessons.columns

    def test_cpi_event_works_without_calendar(self) -> None:
        from knowledge.events.cpi import CPIEvent
        event = CPIEvent()
        assert event.release_calendar is None


# ===========================================================================
# Criterion 11 – Lesson schema integrity
# ===========================================================================


class TestLessonSchemaIntegrity:
    def test_required_columns_present_with_calendar(self) -> None:
        base = runtime_dir("schema_cal")
        cpi_path = base / "economic" / "CPIAUCSL.csv"
        gold_path = base / "history" / "gold.csv"
        output_path = base / "lessons" / "cpi_gold_lessons.csv"

        write_csv(
            cpi_path,
            [
                {"Date": "2020-01-01", "Value": 100.0, "release_timestamp": "2020-02-13 08:30:00"},
                {"Date": "2020-02-01", "Value": 101.0, "release_timestamp": "2020-03-12 08:30:00"},
            ],
        )
        write_gold(gold_path, start="2020-01-02")

        config = LessonBuilderConfig(
            event_data_path=cpi_path,
            gold_path=gold_path,
            output_path=output_path,
        )
        builder = LessonBuilder(config)
        lessons = builder.build()

        required = {
            "lesson_id", "lesson_version", "event_type", "event_date",
            "anchor_gold_date", "alignment_method", "gold_close_at_event",
            "cpi_pressure", "gold_return_1d_pct", "gold_return_5d_pct",
            "gold_return_20d_pct", "gold_direction_20d", "primary_horizon_days",
            "lesson_text", "release_timestamp",
        }
        assert required.issubset(set(lessons.columns)), (
            f"Missing columns: {required - set(lessons.columns)}"
        )
        assert lessons.iloc[0]["lesson_version"] == "cpi_gold_v1"


# ===========================================================================
# Criterion 12 – Real data integration
# ===========================================================================


@pytest.mark.skipif(
    not CPI_RELEASE_CSV.exists(),
    reason="CPI release calendar CSV not found",
)
class TestRealDataIntegration:
    """Verify against the actual repository data files."""

    def test_cpi_release_calendar_matches_cpi_data(self) -> None:
        cpi_csv = PROJECT_ROOT / "data" / "economic" / "CPIAUCSL.csv"
        cal_df = pd.read_csv(CPI_RELEASE_CSV)
        cpi_df = pd.read_csv(cpi_csv)
        cal_dates = set(pd.to_datetime(cal_df["reference_period"]).dt.strftime("%Y-%m-%d"))
        cpi_dates = set(cpi_df["Date"])
        overlap = cal_dates & cpi_dates
        assert len(overlap) > 0, "No overlap between calendar and CPI data"

    def test_cpi_event_accepts_release_calendar_path(self) -> None:
        from knowledge.events.cpi import CPIEvent
        event = CPIEvent(release_calendar_path=str(CPI_RELEASE_CSV))
        assert event.release_calendar is not None
        assert len(event.release_calendar.records) > 0

    def test_feb_2025_cpi_calendar_entry_exists(self) -> None:
        cal = ReleaseCalendar.from_csv(str(CPI_RELEASE_CSV))
        feb = cal.get("2025-02-01")
        assert feb is not None
        assert feb.release_timestamp_et == "2025-03-12T08:30:00"


# ===========================================================================
# Criterion 13 – HistoricalReplayEngine per-release loop helper
# ===========================================================================


class TestHistoricalReplayEngineCalendar:
    """Verify the engine's per-release replay path."""

    @pytest.fixture
    def sim_data_with_calendar(self, tmp_path: Path) -> Path:
        d = tmp_path / "sim_cal"
        econ = d / "economic"
        cal_dir = d / "calendar"
        hist = d / "history" / "gold"
        econ.mkdir(parents=True, exist_ok=True)
        cal_dir.mkdir(parents=True, exist_ok=True)
        hist.mkdir(parents=True, exist_ok=True)

        (econ / "CPIAUCSL.csv").write_text(
            "Date,Value\n"
            "2019-12-01,99.0\n"
            "2020-01-01,100.0\n"
            "2020-02-01,101.0\n",
            encoding="utf-8",
        )
        (cal_dir / "cpi_releases.csv").write_text(
            "reference_period,release_date,release_time,timezone\n"
            "2019-12-01,2020-01-14,08:30,US/Eastern\n"
            "2020-01-01,2020-02-13,08:30,US/Eastern\n"
            "2020-02-01,2020-03-12,08:30,US/Eastern\n",
            encoding="utf-8",
        )
        write_gold(hist / "gold.csv", n=300, start="2019-11-01")

        for etype, fname in [("NFP", "PAYEMS"), ("PPI", "PPIACO"), ("INTEREST_RATE", "FEDFUNDS")]:
            (econ / f"{fname}.csv").write_text(
                "Date,Value\n2020-01-15,100.0\n2020-02-15,101.0\n",
                encoding="utf-8",
            )

        return d

    def test_engine_runs_cpi_release_by_release(self, sim_data_with_calendar: Path) -> None:
        from simulation.historical_replay import HistoricalReplayEngine
        engine = HistoricalReplayEngine(
            data_dir=sim_data_with_calendar,
            gold_path=sim_data_with_calendar / "history" / "gold" / "gold.csv",
        )
        cpi_path = sim_data_with_calendar / "economic" / "CPIAUCSL.csv"
        cal_path = sim_data_with_calendar / "calendar" / "cpi_releases.csv"

        result = engine._replay_event_release_by_release("CPI", cpi_path, cal_path)
        assert result.event_count == 3
        assert result.event_type == "CPI"


# ===========================================================================
# Criterion 14 – CPIEvent.load_and_extract_with_calendar
# ===========================================================================


class TestLoadAndExtractWithCalendar:
    def test_returns_dataframe_with_calendar_columns(self, tmp_path: Path) -> None:
        cpi_csv = tmp_path / "cpi.csv"
        cpi_csv.write_text(
            "Date,Value\n2020-01-01,100.0\n",
            encoding="utf-8",
        )
        cal_csv = tmp_path / "cal.csv"
        cal_csv.write_text(
            "reference_period,release_date,release_time,timezone\n"
            "2020-01-01,2020-02-13,08:30,US/Eastern\n",
            encoding="utf-8",
        )
        cal = ReleaseCalendar.from_csv(str(cal_csv))
        from knowledge.events.cpi import CPIEvent
        event = CPIEvent()
        df = event.load_and_extract_with_calendar(cpi_csv, cal)
        assert isinstance(df, pd.DataFrame)
        assert "release_timestamp" in df.columns
        assert "release_timezone" in df.columns


# ===========================================================================
# Criterion 15 – No calendar match
# ===========================================================================


class TestCalendarMismatch:
    def test_no_calendar_match_raises(self, tmp_path: Path) -> None:
        cal_csv = tmp_path / "cal.csv"
        cal_csv.write_text(
            "reference_period,release_date,release_time,timezone\n"
            "1999-01-01,1999-02-13,08:30,US/Eastern\n",
            encoding="utf-8",
        )
        cpi_csv = tmp_path / "cpi.csv"
        cpi_csv.write_text(
            "Date,Value\n2020-01-01,100.0\n",
            encoding="utf-8",
        )

        cal = ReleaseCalendar.from_csv(str(cal_csv))
        event = CPIEvent()
        with pytest.raises(ValueError, match="Release calendar matched zero reference periods"):
            event.load_and_extract_with_calendar(cpi_csv, cal)


# ===========================================================================
# Criterion 16 – Reference period vs release period in lesson_id
# ===========================================================================


class TestLessonIdFormat:
    def test_lesson_id_uses_event_date_reference_period(self) -> None:
        base = runtime_dir("lesson_id_ref")
        cpi_path = base / "economic" / "CPIAUCSL.csv"
        gold_path = base / "history" / "gold.csv"
        output_path = base / "lessons" / "cpi_gold_lessons.csv"

        write_csv(
            cpi_path,
            [
                {"Date": "2019-12-01", "Value": 99.0, "release_timestamp": "2020-01-14 08:30:00"},
                {"Date": "2020-01-01", "Value": 100.0, "release_timestamp": "2020-02-13 08:30:00"},
            ],
        )
        write_gold(gold_path, start="2019-11-01")

        config = LessonBuilderConfig(
            event_data_path=cpi_path,
            gold_path=gold_path,
            output_path=output_path,
        )
        builder = LessonBuilder(config)
        lessons = builder.build()

        assert lessons.iloc[0]["lesson_id"] == "CPI_GOLD_2020-01-01"
        assert lessons.iloc[0]["event_date"] == "2020-01-01"
        assert "release_timestamp" in lessons.columns


# ===========================================================================
# Criterion 17 – Extra columns in feature extraction
# ===========================================================================


class TestFeatureExtractionPassthrough:
    def test_unknown_columns_survive_feature_extraction(self, tmp_path: Path) -> None:
        cpi_csv = tmp_path / "cpi.csv"
        cpi_csv.write_text(
            "Date,Value,my_custom_col,release_timestamp\n"
            "2019-11-01,98.0,first,2020-01-14 08:30:00\n"
            "2019-12-01,99.0,second,2020-02-13 08:30:00\n"
            "2020-01-01,100.0,third,2020-03-12 08:30:00\n",
            encoding="utf-8",
        )
        from knowledge.events.cpi import CPIEvent
        event = CPIEvent()
        df = event.load_and_extract(cpi_csv)
        assert "my_custom_col" in df.columns
        assert "release_timestamp" in df.columns
        assert "third" in df["my_custom_col"].values
