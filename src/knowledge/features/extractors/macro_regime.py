import pandas as pd

from knowledge.features.feature import Feature, FeatureSet
from knowledge.features.extractor import FeatureExtractor
from knowledge.regime.macro_regime_detector import MacroRegimeDetector


class MacroRegimeFeatureExtractor(FeatureExtractor):
    """Augments event data with a macro_regime column from a fitted detector."""

    def __init__(self, detector: MacroRegimeDetector) -> None:
        self._detector = detector
        self._regime_map: dict[str, str] = {}
        self._build_regime_map()

    def _build_regime_map(self) -> None:
        regime_data = self._detector.get_regime_data()
        for _, row in regime_data.iterrows():
            date_str = row["Date"]
            if isinstance(date_str, pd.Timestamp):
                date_str = date_str.date().isoformat()
            self._regime_map[str(date_str)] = str(row["macro_regime"])

    @property
    def feature_definitions(self) -> dict[str, Feature]:
        return {
            "macro_regime": Feature(
                name="macro_regime",
                dtype="object",
                description=(
                    "Macro-economic regime classification: "
                    "EXPANSION, LATE_CYCLE, CONTRACTION, or RECOVERY"
                ),
                source_columns=("Date",),
            ),
        }

    def extract(self, raw: pd.DataFrame) -> FeatureSet:
        df = raw.copy()
        if "Date" not in df.columns:
            raise ValueError("Input DataFrame must contain a 'Date' column")

        df["macro_regime"] = df["Date"].apply(
            lambda d: self._regime_map.get(
                d.date().isoformat() if isinstance(d, pd.Timestamp) else str(d),
                "UNKNOWN",
            )
        )
        return FeatureSet(data=df, features=self.feature_definitions)
