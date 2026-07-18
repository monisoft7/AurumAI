import pandas as pd

from knowledge.features.feature import Feature, FeatureSet
from knowledge.features.extractor import FeatureExtractor

_PMI_THRESHOLD = 50


class PMIFeatureExtractor(FeatureExtractor):
    @property
    def feature_definitions(self) -> dict[str, Feature]:
        return {
            "previous_value": Feature(
                name="previous_value",
                dtype="float64",
                description="PMI value from the previous release",
                source_columns=("Value",),
            ),
            "pmi_change": Feature(
                name="pmi_change",
                dtype="float64",
                description="Month-over-month change in PMI (points)",
                source_columns=("Value", "previous_value"),
            ),
            "pmi_trend": Feature(
                name="pmi_trend",
                dtype="object",
                description="Economic phase: expansion, contraction, or neutral",
                source_columns=("Value",),
            ),
        }

    def extract(self, raw: pd.DataFrame) -> FeatureSet:
        df = raw.copy()
        df["previous_value"] = df["Value"].shift(1)
        df["pmi_change"] = df["Value"] - df["previous_value"]
        df["pmi_trend"] = df["Value"].apply(self._classify_condition)
        df = df.dropna(subset=["previous_value", "pmi_change"])
        return FeatureSet(data=df, features=self.feature_definitions)

    @staticmethod
    def _classify_condition(value: float) -> str:
        if value > _PMI_THRESHOLD:
            return "pmi_expansion"
        if value < _PMI_THRESHOLD:
            return "pmi_contraction"
        return "pmi_neutral"
