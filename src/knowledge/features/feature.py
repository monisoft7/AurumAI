from dataclasses import dataclass

import pandas as pd


@dataclass(frozen=True)
class Feature:
    name: str
    dtype: str
    description: str
    source_columns: tuple[str, ...]


class FeatureSet:
    def __init__(self, data: pd.DataFrame, features: dict[str, Feature]):
        self.data = data
        self.features = features

    def validate(self) -> None:
        missing = set(self.features) - set(self.data.columns)
        if missing:
            raise ValueError(
                f"FeatureSet missing required columns: {', '.join(sorted(missing))}"
            )

    def get_feature(self, name: str) -> Feature:
        if name not in self.features:
            raise ValueError(
                f"Unknown feature '{name}'. Available: {', '.join(sorted(self.features))}"
            )
        return self.features[name]

    @property
    def feature_names(self) -> list[str]:
        return list(self.features)
