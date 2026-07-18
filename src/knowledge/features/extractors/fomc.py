import pandas as pd

from knowledge.features.feature import Feature, FeatureSet
from knowledge.features.extractor import FeatureExtractor


class FOMCFeatureExtractor(FeatureExtractor):
    @property
    def feature_definitions(self) -> dict[str, Feature]:
        return {
            "previous_value": Feature(
                name="previous_value",
                dtype="float64",
                description="Federal funds rate from the previous FOMC meeting",
                source_columns=("Value",),
            ),
            "fomc_change": Feature(
                name="fomc_change",
                dtype="float64",
                description="Change in federal funds rate since previous meeting (percentage points)",
                source_columns=("Value", "previous_value"),
            ),
            "fomc_decision": Feature(
                name="fomc_decision",
                dtype="object",
                description="Rate decision: hike, cut, or hold",
                source_columns=("fomc_change",),
            ),
        }

    def extract(self, raw: pd.DataFrame) -> FeatureSet:
        df = raw.copy()
        df["previous_value"] = df["Value"].shift(1)
        df["fomc_change"] = df["Value"] - df["previous_value"]
        df["fomc_decision"] = df["fomc_change"].apply(self._classify_decision)
        df = df.dropna(subset=["previous_value", "fomc_change"])
        return FeatureSet(data=df, features=self.feature_definitions)

    @staticmethod
    def _classify_decision(change: float) -> str:
        if change > 0:
            return "rate_hike"
        if change < 0:
            return "rate_cut"
        return "rate_hold"
