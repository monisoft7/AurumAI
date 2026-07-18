import pandas as pd

from knowledge.features.feature import Feature, FeatureSet
from knowledge.features.extractor import FeatureExtractor

_PPI_HIGH_THRESHOLD = 0.5
_PPI_LOW_THRESHOLD = -0.5


class PPIFeatureExtractor(FeatureExtractor):
    @property
    def feature_definitions(self) -> dict[str, Feature]:
        return {
            "previous_value": Feature(
                name="previous_value",
                dtype="float64",
                description="PPI value from the previous release",
                source_columns=("Value",),
            ),
            "ppi_change": Feature(
                name="ppi_change",
                dtype="float64",
                description="Period-over-period PPI percent change",
                source_columns=("Value", "previous_value"),
            ),
            "ppi_trend": Feature(
                name="ppi_trend",
                dtype="object",
                description="PPI condition: up, down, or flat",
                source_columns=("ppi_change",),
            ),
        }

    def extract(self, raw: pd.DataFrame) -> FeatureSet:
        df = raw.copy()
        df["previous_value"] = df["Value"].shift(1)
        df["ppi_change"] = (
            (df["Value"] - df["previous_value"]) / df["previous_value"]
        ) * 100.0
        df["ppi_trend"] = df["ppi_change"].apply(self._classify_condition)
        df = df.dropna(subset=["previous_value", "ppi_change"])
        return FeatureSet(data=df, features=self.feature_definitions)

    @staticmethod
    def _classify_condition(change: float) -> str:
        if change > _PPI_HIGH_THRESHOLD:
            return "ppi_up"
        if change < _PPI_LOW_THRESHOLD:
            return "ppi_down"
        return "ppi_flat"
