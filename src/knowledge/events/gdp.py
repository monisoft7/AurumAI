from pathlib import Path

import pandas as pd

from knowledge.events.base import MacroEvent, StandardEventMetadata
from knowledge.features.engine import FeatureExtractionEngine
from knowledge.features.extractors.gdp import GDPFeatureExtractor


class GDPEvent(MacroEvent):
    """Lesson-building logic for GDP releases."""

    event_type = "GDP"
    lesson_version = "gdp_gold_v1"
    condition_columns = ['gdp_trend']
    knowledge_version = "gdp_gold_summary_v1"

    @property
    def metadata(self) -> StandardEventMetadata:
        return StandardEventMetadata(
            country='US',
            currency='USD',
            unit='annualized_percent',
            importance=3,
            source='Bureau of Economic Analysis',
            reference_period_type='quarterly',
        )

    def __init__(self) -> None:
        self._extraction_engine = FeatureExtractionEngine()
        self._extractor = GDPFeatureExtractor()

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

    def build_lesson_fields(
        self, event_row: pd.Series, anchor_date: str
    ) -> dict[str, object]:
        condition_col = self.condition_columns[0]
        return {
            "gdp_value": round(float(event_row["Value"]), 6),
            "previous_gdp_value": round(
                float(event_row["previous_value"]), 6
            ),
            "gdp_change": round(
                float(event_row["gdp_change"]), 6
            ),
            condition_col: str(event_row[condition_col]),
        }

    def lesson_text(self, lesson: dict[str, object]) -> str:
        horizon = int(lesson["primary_horizon_days"])
        direction = lesson[f"gold_direction_{horizon}d"]
        move = lesson[f"gold_return_{horizon}d_pct"]
        gdp_value = lesson["gdp_value"]
        gdp_trend = lesson["gdp_trend"]
        return (
            f"After US GDP grew at {gdp_value}% ({gdp_trend}) "
            f"on {lesson['event_date']}, "
            f"gold moved {move}% over {horizon} trading days "
            f"({direction})."
        )
