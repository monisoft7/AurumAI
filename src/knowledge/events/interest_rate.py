from pathlib import Path

import pandas as pd

from knowledge.events.base import MacroEvent, StandardEventMetadata
from knowledge.features.engine import FeatureExtractionEngine
from knowledge.features.extractors.interest_rate import InterestRateFeatureExtractor


class InterestRateEvent(MacroEvent):
    """Lesson-building logic for central bank interest rate decisions."""

    event_type = "INTEREST_RATE"
    lesson_version = "interest_rate_gold_v1"
    condition_columns = ['interest_rate_trend']
    knowledge_version = "interest_rate_gold_summary_v1"

    @property
    def metadata(self) -> StandardEventMetadata:
        return StandardEventMetadata(
            country='US',
            currency='USD',
            unit='percent',
            importance=3,
            source='Federal Reserve',
            reference_period_type='meeting',
        )

    def __init__(self) -> None:
        self._extraction_engine = FeatureExtractionEngine()
        self._extractor = InterestRateFeatureExtractor()

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
        return {
            "interest_rate_value": round(float(event_row["Value"]), 6),
            "previous_interest_rate_value": round(
                float(event_row["previous_value"]), 6
            ),
            "interest_rate_change": round(
                float(event_row["interest_rate_change"]), 6
            ),
            **self.build_reasoning_condition(event_row),
        }

    def lesson_text(self, lesson: dict[str, object]) -> str:
        horizon = int(lesson["primary_horizon_days"])
        direction = lesson[f"gold_direction_{horizon}d"]
        move = lesson[f"gold_return_{horizon}d_pct"]
        rate_value = lesson["interest_rate_value"]
        rate_trend = lesson["interest_rate_trend"]
        return (
            f"After rates moved to {rate_value}% ({rate_trend}) "
            f"on {lesson['event_date']}, "
            f"gold moved {move}% over {horizon} trading days "
            f"({direction})."
        )
