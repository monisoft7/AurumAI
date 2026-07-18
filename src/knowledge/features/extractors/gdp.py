import pandas as pd

from knowledge.features.feature import Feature, FeatureSet
from knowledge.features.extractor import FeatureExtractor

_GDP_HIGH_THRESHOLD = 3.0
_GDP_LOW_THRESHOLD = 1.0


class GDPFeatureExtractor(FeatureExtractor):
    @property
    def feature_definitions(self) -> dict[str, Feature]:
        return {
            "previous_value": Feature(
                name="previous_value",
                dtype="float64",
                description="GDP annualized growth rate from the previous quarter",
                source_columns=("Value",),
            ),
            "gdp_change": Feature(
                name="gdp_change",
                dtype="float64",
                description="Quarter-over-quarter change in GDP growth rate (percentage points)",
                source_columns=("Value", "previous_value"),
            ),
            "gdp_trend": Feature(
                name="gdp_trend",
                dtype="object",
                description="Economic phase: expansion, stable, or contraction",
                source_columns=("Value",),
            ),
        }

    def extract(self, raw: pd.DataFrame) -> FeatureSet:
        df = raw.copy()
        df["previous_value"] = df["Value"].shift(1)
        df["gdp_change"] = df["Value"] - df["previous_value"]
        df["gdp_trend"] = df["Value"].apply(self._classify_trend)
        df = df.dropna(subset=["previous_value", "gdp_change"])
        return FeatureSet(data=df, features=self.feature_definitions)

    @staticmethod
    def _classify_trend(value: float) -> str:
        if value > _GDP_HIGH_THRESHOLD:
            return "gdp_expansion"
        if value < _GDP_LOW_THRESHOLD:
            return "gdp_contraction"
        return "gdp_stable"
