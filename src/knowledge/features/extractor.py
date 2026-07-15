from abc import ABC, abstractmethod

import pandas as pd

from knowledge.features.feature import Feature, FeatureSet


class FeatureExtractor(ABC):
    @property
    @abstractmethod
    def feature_definitions(self) -> dict[str, Feature]:
        ...

    @abstractmethod
    def extract(self, raw: pd.DataFrame) -> FeatureSet:
        ...
