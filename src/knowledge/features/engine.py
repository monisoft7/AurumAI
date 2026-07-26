from typing import ClassVar

import pandas as pd

from knowledge.features.feature import FeatureSet
from knowledge.features.extractor import FeatureExtractor


class FeatureExtractionEngine:
    _global_extractors: ClassVar[list[FeatureExtractor]] = []

    @classmethod
    def register_global(cls, extractor: FeatureExtractor) -> None:
        cls._global_extractors.append(extractor)

    @classmethod
    def clear_global(cls) -> None:
        cls._global_extractors.clear()

    def process(self, raw: pd.DataFrame, extractor: FeatureExtractor) -> FeatureSet:
        feature_set = extractor.extract(raw)
        feature_set.validate()
        data = feature_set.data
        for gx in self._global_extractors:
            feature_set = gx.extract(data)
            feature_set.validate()
            data = feature_set.data
        return feature_set
