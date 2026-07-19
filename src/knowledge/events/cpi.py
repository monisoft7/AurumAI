from pathlib import Path

import pandas as pd

from knowledge.events.base import MacroEvent, ReleaseCalendar, StandardEventMetadata
from knowledge.features.engine import FeatureExtractionEngine
from knowledge.features.extractors.cpi import CPIFeatureExtractor


DEFAULT_CPI_RELEASE_CALENDAR = "data/calendar/cpi_releases.csv"


class CPIEvent(MacroEvent):
    """Lesson-building logic for Consumer Price Index releases."""

    event_type = "CPI"
    lesson_version = "cpi_gold_v1"
    condition_columns = ["cpi_pressure"]
    knowledge_version = "cpi_gold_summary_v1"

    @property
    def metadata(self) -> StandardEventMetadata:
        return StandardEventMetadata(
            country="US",
            currency="USD",
            unit="percent",
            importance=3,
            source="Bureau of Labor Statistics",
            reference_period_type="monthly",
        )

    def __init__(
        self,
        release_calendar_path: str | None = None,
    ) -> None:
        self._extraction_engine = FeatureExtractionEngine()
        self._extractor = CPIFeatureExtractor()
        self._release_calendar: ReleaseCalendar | None = None
        if release_calendar_path:
            self._release_calendar = ReleaseCalendar.from_csv(release_calendar_path)

    @property
    def release_calendar(self) -> ReleaseCalendar | None:
        return self._release_calendar

    def load_raw(self, path: Path) -> pd.DataFrame:
        df = pd.read_csv(path)
        required = {"Date", "Value"}
        missing = required.difference(df.columns)
        if missing:
            missing_text = ", ".join(sorted(missing))
            raise ValueError(f"{path} is missing required columns: {missing_text}")

        df = df.copy()
        df["Date"] = pd.to_datetime(df["Date"], errors="raise")
        df["Value"] = pd.to_numeric(df["Value"], errors="raise")
        df = df.sort_values("Date").drop_duplicates("Date", keep="last")
        return df.reset_index(drop=True)

    def load_and_extract(self, path: Path) -> pd.DataFrame:
        raw = self.load_raw(path)
        feature_set = self._extraction_engine.process(raw, self._extractor)
        return feature_set.data

    def load_and_extract_with_calendar(
        self,
        path: Path,
        release_calendar: ReleaseCalendar | None = None,
    ) -> pd.DataFrame:
        raw = self.load_raw(path)
        cal = release_calendar or self._release_calendar
        if cal is not None:
            raw = self._enrich_with_calendar(raw, cal)
        feature_set = self._extraction_engine.process(raw, self._extractor)
        return feature_set.data

    def build_lesson_fields(
        self, event_row: pd.Series, anchor_date: str
    ) -> dict[str, object]:
        return {
            "cpi_value": round(float(event_row["Value"]), 6),
            "previous_cpi_value": round(float(event_row["previous_value"]), 6),
            "cpi_change_pct": round(float(event_row["cpi_change_pct"]), 6),
            "cpi_pressure": str(event_row["cpi_pressure"]),
        }

    def lesson_text(self, lesson: dict[str, object]) -> str:
        horizon = int(lesson["primary_horizon_days"])
        direction = lesson[f"gold_direction_{horizon}d"]
        move = lesson[f"gold_return_{horizon}d_pct"]
        cpi_change = lesson["cpi_change_pct"]
        return (
            f"After CPI changed by {cpi_change}% on {lesson['event_date']}, "
            f"gold moved {move}% over {horizon} trading days "
            f"({direction})."
        )
