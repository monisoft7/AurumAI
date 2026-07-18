import pandas as pd

from knowledge.features.feature import Feature, FeatureSet
from knowledge.features.extractor import FeatureExtractor


NFE_HIGH_THRESHOLD = 200
NFE_LOW_THRESHOLD = 100


class NFPEventFeatureExtractor(FeatureExtractor):
    @property
    def feature_definitions(self) -> dict[str, Feature]:
        return {
            "previous_value": Feature(
                name="previous_value",
                dtype="float64",
                description="Nonfarm payrolls level from the previous month (thousands)",
                source_columns=("Value",),
            ),
            "nfp_change": Feature(
                name="nfp_change",
                dtype="float64",
                description="Month-over-month change in nonfarm payrolls (thousands)",
                source_columns=("Value", "previous_value"),
            ),
            "nfp_trend": Feature(
                name="nfp_trend",
                dtype="object",
                description="Labor market condition: improving, stable, or deteriorating",
                source_columns=("nfp_change",),
            ),
        }

    def extract(self, raw: pd.DataFrame) -> FeatureSet:
        df = raw.copy()
        df["previous_value"] = df["Value"].shift(1)
        df["nfp_change"] = df["Value"] - df["previous_value"]
        df["nfp_trend"] = df["nfp_change"].apply(self._classify_trend)
        df = df.dropna(subset=["previous_value", "nfp_change"])
        return FeatureSet(data=df, features=self.feature_definitions)

    @staticmethod
    def _classify_trend(nfp_change: float) -> str:
        if nfp_change > NFE_HIGH_THRESHOLD:
            return "jobs_market_improving"
        if nfp_change < NFE_LOW_THRESHOLD:
            return "jobs_market_deteriorating"
        return "jobs_market_stable"
