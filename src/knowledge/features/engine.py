import pandas as pd

from knowledge.features.feature import FeatureSet
from knowledge.features.extractor import FeatureExtractor


class FeatureExtractionEngine:
    def process(self, raw: pd.DataFrame, extractor: FeatureExtractor) -> FeatureSet:
        feature_set = extractor.extract(raw)
        feature_set.validate()
        return feature_set
