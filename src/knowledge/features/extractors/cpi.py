import pandas as pd

from knowledge.features.feature import Feature, FeatureSet
from knowledge.features.extractor import FeatureExtractor


class CPIFeatureExtractor(FeatureExtractor):
    @property
    def feature_definitions(self) -> dict[str, Feature]:
        return {
            "previous_value": Feature(
                name="previous_value",
                dtype="float64",
                description="CPI value from the previous release",
                source_columns=("Value",),
            ),
            "cpi_change_pct": Feature(
                name="cpi_change_pct",
                dtype="float64",
                description="Month-over-month CPI change in percent",
                source_columns=("Value", "previous_value"),
            ),
            "cpi_pressure": Feature(
                name="cpi_pressure",
                dtype="object",
                description="Inflation pressure classification: up, down, or flat",
                source_columns=("cpi_change_pct",),
            ),
        }

    def extract(self, raw: pd.DataFrame) -> FeatureSet:
        df = raw.copy()
        df["previous_value"] = df["Value"].shift(1)
        df["cpi_change_pct"] = (
            (df["Value"] - df["previous_value"]) / df["previous_value"]
        ) * 100.0
        df["cpi_pressure"] = df["cpi_change_pct"].apply(self._classify_pressure)
        df = df.dropna(subset=["previous_value", "cpi_change_pct"])
        return FeatureSet(data=df, features=self.feature_definitions)

    @staticmethod
    def _classify_pressure(cpi_change_pct: float) -> str:
        if cpi_change_pct > 0:
            return "inflation_pressure_up"
        if cpi_change_pct < 0:
            return "inflation_pressure_down"
        return "inflation_pressure_flat"
