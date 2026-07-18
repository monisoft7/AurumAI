import pandas as pd

from knowledge.features.feature import Feature, FeatureSet
from knowledge.features.extractor import FeatureExtractor


class InterestRateFeatureExtractor(FeatureExtractor):
    @property
    def feature_definitions(self) -> dict[str, Feature]:
        return {
            "previous_value": Feature(
                name="previous_value",
                dtype="float64",
                description="Interest rate from the previous meeting",
                source_columns=("Value",),
            ),
            "interest_rate_change": Feature(
                name="interest_rate_change",
                dtype="float64",
                description="Change in interest rate since previous meeting (percentage points)",
                source_columns=("Value", "previous_value"),
            ),
            "interest_rate_trend": Feature(
                name="interest_rate_trend",
                dtype="object",
                description="Rate decision: hike, cut, or hold",
                source_columns=("interest_rate_change",),
            ),
        }

    def extract(self, raw: pd.DataFrame) -> FeatureSet:
        df = raw.copy()
        df["previous_value"] = df["Value"].shift(1)
        df["interest_rate_change"] = df["Value"] - df["previous_value"]
        df["interest_rate_trend"] = df["interest_rate_change"].apply(
            self._classify_trend
        )
        df = df.dropna(subset=["previous_value", "interest_rate_change"])
        return FeatureSet(data=df, features=self.feature_definitions)

    @staticmethod
    def _classify_trend(change: float) -> str:
        if change > 0:
            return "rate_hike"
        if change < 0:
            return "rate_cut"
        return "rate_hold"
