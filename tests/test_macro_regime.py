"""Tests for MacroRegimeDetector and MacroRegimeFeatureExtractor."""

from datetime import datetime, timedelta

import numpy as np
import pandas as pd
import pytest

from knowledge.features.feature import FeatureSet
from knowledge.features.extractors.macro_regime import (
    MacroRegimeFeatureExtractor,
)
from knowledge.regime.macro_regime_detector import (
    EXPANSION,
    LATE_CYCLE,
    CONTRACTION,
    RECOVERY,
    REGIMES,
    MacroRegimeDetector,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_synthetic_data(
    n_period: int = 12,
    random_state: int = 42,
) -> pd.DataFrame:
    """Generate monthly composite_score data with 4 clear regime phases."""
    rng = np.random.default_rng(random_state)
    dates = pd.date_range(
        start="2000-01-01", periods=n_period * 4, freq="ME"
    )

    # Four regimes with distinct means
    scores = np.concatenate([
        rng.normal(2.0, 0.3, n_period),    # EXPANSION
        rng.normal(0.5, 0.3, n_period),    # LATE_CYCLE
        rng.normal(-2.0, 0.4, n_period),   # CONTRACTION
        rng.normal(-0.5, 0.3, n_period),   # RECOVERY
    ])

    return pd.DataFrame({"Date": dates, "composite_score": scores})


# Shared fitted detector to avoid repeated fitting across tests
_SHARED_DATA = _make_synthetic_data(n_period=12, random_state=42)
_SHARED_DETECTOR = MacroRegimeDetector(random_state=42).fit(_SHARED_DATA)


# ---------------------------------------------------------------------------
# MacroRegimeDetector
# ---------------------------------------------------------------------------


class TestMacroRegimeDetectorFit:

    def test_fit_returns_self(self):
        data = _make_synthetic_data()
        detector = MacroRegimeDetector(random_state=42)
        result = detector.fit(data)
        assert result is detector

    def test_raises_before_fit(self):
        detector = MacroRegimeDetector()
        with pytest.raises(RuntimeError, match="Must call fit"):
            detector.get_regime_data()

    def test_raises_without_composite_score(self):
        df = pd.DataFrame({"Date": ["2000-01-01"], "other": [1.0]})
        detector = MacroRegimeDetector()
        with pytest.raises(ValueError, match="composite_score"):
            detector.fit(df)

    def test_get_regime_data_returns_expected_columns(self):
        rd = _SHARED_DETECTOR.get_regime_data()
        assert list(rd.columns) == ["Date", "macro_regime"]
        assert len(rd) == len(_SHARED_DATA)

    def test_all_four_regimes_present(self):
        rd = _SHARED_DETECTOR.get_regime_data()
        found = set(rd["macro_regime"].unique())
        for r in REGIMES:
            assert r in found, f"Missing regime: {r}"

    def test_deterministic_identical_seed(self):
        data = _make_synthetic_data()
        d1 = MacroRegimeDetector(random_state=42).fit(data)
        d2 = MacroRegimeDetector(random_state=42).fit(data)
        pd.testing.assert_series_equal(
            d1.get_regime_data()["macro_regime"],
            d2.get_regime_data()["macro_regime"],
        )

    def test_different_seed_different_labels(self):
        """Different seeds may converge to different label orderings."""
        data = _make_synthetic_data()
        d1 = MacroRegimeDetector(random_state=42).fit(data)
        d2 = MacroRegimeDetector(random_state=99).fit(data)
        r1 = d1.get_regime_data()["macro_regime"]
        r2 = d2.get_regime_data()["macro_regime"]
        # Must not be a warning; this is a sanity check
        assert not r1.isna().any()
        assert not r2.isna().any()

    def test_regime_labels_property(self):
        labels = _SHARED_DETECTOR.regime_labels
        assert labels is not None
        assert len(labels) == len(_SHARED_DATA)

    def test_regime_labels_none_before_fit(self):
        detector = MacroRegimeDetector()
        assert detector.regime_labels is None


# ---------------------------------------------------------------------------
# MacroRegimeFeatureExtractor
# ---------------------------------------------------------------------------


class TestMacroRegimeFeatureExtractor:

    @pytest.fixture
    def detector(self) -> MacroRegimeDetector:
        return _SHARED_DETECTOR

    def test_feature_definitions(self, detector):
        ext = MacroRegimeFeatureExtractor(detector)
        defs = ext.feature_definitions
        assert "macro_regime" in defs
        assert defs["macro_regime"].dtype == "object"

    def test_extract_adds_macro_regime_column(self, detector):
        ext = MacroRegimeFeatureExtractor(detector)
        event_df = detector.get_regime_data()[["Date"]].head(10).copy()
        event_df["Value"] = 1.0
        fs = ext.extract(event_df)
        assert isinstance(fs, FeatureSet)
        assert "macro_regime" in fs.data.columns
        assert not fs.data["macro_regime"].isna().any()
        assert fs.data["macro_regime"].iloc[0] in REGIMES

    def test_extract_validates(self, detector):
        ext = MacroRegimeFeatureExtractor(detector)
        event_df = detector.get_regime_data()[["Date"]].head(5).copy()
        event_df["Value"] = 1.0
        fs = ext.extract(event_df)
        # validate() should not raise
        fs.validate()

    def test_extract_raises_without_date_column(self, detector):
        ext = MacroRegimeFeatureExtractor(detector)
        df = pd.DataFrame({"Value": [1.0]})
        with pytest.raises(ValueError, match="Date"):
            ext.extract(df)

    def test_extract_unknown_date_returns_unknown(self, detector):
        ext = MacroRegimeFeatureExtractor(detector)
        df = pd.DataFrame({
            "Date": [pd.Timestamp("1999-01-01")],
            "Value": [1.0],
        })
        fs = ext.extract(df)
        assert fs.data["macro_regime"].iloc[0] == "UNKNOWN"


# ---------------------------------------------------------------------------
# Integration
# ---------------------------------------------------------------------------


class TestMacroRegimeIntegration:

    def test_full_pipeline_synthetic_data(self):
        """Fit detector, extract regimes, verify structure."""
        ext = MacroRegimeFeatureExtractor(_SHARED_DETECTOR)

        # Simulate event data
        regime_data = _SHARED_DETECTOR.get_regime_data()
        event_df = regime_data.rename(columns={"macro_regime": "Value"}).copy()
        event_df = event_df.drop(columns=["Value"])
        event_df["Value"] = 100.0

        fs = ext.extract(event_df)
        assert len(fs.data) == len(regime_data)
        assert fs.data["macro_regime"].nunique() == 4
        assert all(r in REGIMES for r in fs.data["macro_regime"].unique())

    def test_building_synthetic_data_has_ordered_phases(self):
        """Verify the synthetic data helper creates distinct phases."""
        data = _make_synthetic_data(n_period=12, random_state=42)
        # Phase means should be clearly separated
        phase_means = [
            data["composite_score"].iloc[0:12].mean(),
            data["composite_score"].iloc[12:24].mean(),
            data["composite_score"].iloc[24:36].mean(),
            data["composite_score"].iloc[36:48].mean(),
        ]
        assert phase_means[0] > 1.0  # EXPANSION
        assert phase_means[2] < -1.0  # CONTRACTION
