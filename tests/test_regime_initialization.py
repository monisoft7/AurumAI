from __future__ import annotations

from unittest.mock import create_autospec, patch

import pandas as pd
import pytest

from knowledge.features.engine import FeatureExtractionEngine
from knowledge.regime.composite_score import CompositeScoreBuilder
from knowledge.regime.macro_regime_detector import MacroRegimeDetector
import orchestration.stages as stages


@pytest.mark.parametrize("clear_between_runs", [False, True], ids=["consecutive", "after_clear"])
def test_macro_regime_initialization_reuses_detector_for_new_params(clear_between_runs) -> None:
    """Each run receives the cached detector without rebuilding global state."""
    composite_data = pd.DataFrame(
        {
            "Date": pd.to_datetime(["2026-01-31", "2026-02-28"]),
            "composite_score": [0.1, 0.2],
        }
    )
    build = create_autospec(
        CompositeScoreBuilder.build,
        spec_set=True,
        return_value=composite_data,
    )
    def fit_detector(detector, data):
        detector._regime_labels = pd.Series(
            ["EXPANSION", "LATE_CYCLE"], index=data["Date"]
        )
        return detector

    fit = create_autospec(
        MacroRegimeDetector.fit,
        spec_set=True,
        side_effect=fit_detector,
    )
    register = create_autospec(
        FeatureExtractionEngine.register_global,
        spec_set=True,
        side_effect=FeatureExtractionEngine.register_global,
    )

    missing = object()
    previous_initialized = getattr(stages, "_regime_initialized", missing)
    previous_detector = getattr(stages, "_regime_detector_cache", missing)
    previous_extractor = getattr(stages, "_regime_extractor_cache", missing)
    previous_extractors = list(FeatureExtractionEngine._global_extractors)
    first_params: dict = {}
    second_params: dict = {}

    try:
        if previous_initialized is not missing:
            stages._regime_initialized = False
        if previous_detector is not missing:
            stages._regime_detector_cache = None
        if previous_extractor is not missing:
            stages._regime_extractor_cache = None
        FeatureExtractionEngine.clear_global()

        with (
            patch.object(CompositeScoreBuilder, "build", build),
            patch.object(MacroRegimeDetector, "fit", fit),
            patch.object(FeatureExtractionEngine, "register_global", register),
        ):
            stages._ensure_macro_regime_initialized(first_params)
            extractor = FeatureExtractionEngine._global_extractors[0]
            assert build.call_count == fit.call_count == register.call_count == 1
            if clear_between_runs:
                FeatureExtractionEngine.clear_global()
                assert FeatureExtractionEngine._global_extractors == []
            stages._ensure_macro_regime_initialized(second_params)
            stages._ensure_macro_regime_initialized(second_params)

        assert build.call_count == 1
        assert fit.call_count == 1
        assert register.call_count == (2 if clear_between_runs else 1)
        assert len(FeatureExtractionEngine._global_extractors) == 1
        assert FeatureExtractionEngine._global_extractors[0] is extractor
        assert first_params["_regime_detector"] is second_params.get(
            "_regime_detector"
        )
    finally:
        if previous_extractor is missing:
            if hasattr(stages, "_regime_extractor_cache"):
                delattr(stages, "_regime_extractor_cache")
        else:
            stages._regime_extractor_cache = previous_extractor
        if previous_initialized is missing:
            if hasattr(stages, "_regime_initialized"):
                delattr(stages, "_regime_initialized")
        else:
            stages._regime_initialized = previous_initialized
        if previous_detector is missing:
            if hasattr(stages, "_regime_detector_cache"):
                delattr(stages, "_regime_detector_cache")
        else:
            stages._regime_detector_cache = previous_detector
        FeatureExtractionEngine.clear_global()
        FeatureExtractionEngine._global_extractors.extend(previous_extractors)
