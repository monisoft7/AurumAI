import math

import numpy as np
import pandas as pd
import pytest

from technical.indicators import TechnicalIndicatorExtractor


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

_TREND_DAYS = 252 * 2  # ~2 years of daily data


@pytest.fixture
def uptrend_data() -> pd.DataFrame:
    """Close price rising steadily from 100 to 200, with daily noise."""
    rng = np.random.default_rng(42)
    n = _TREND_DAYS
    base = np.linspace(100, 200, n)
    noise = rng.normal(0, 1, n).cumsum() * 0.3
    close = base + noise
    close = np.clip(close, 50, None)
    return pd.DataFrame({"close": close})


@pytest.fixture
def constant_data() -> pd.DataFrame:
    return pd.DataFrame({"close": [150.0] * 300})


@pytest.fixture
def extractor() -> TechnicalIndicatorExtractor:
    return TechnicalIndicatorExtractor()


# ---------------------------------------------------------------------------
# Feature definitions
# ---------------------------------------------------------------------------


class TestFeatureDefinitions:

    def test_defines_all_indicators(self, extractor: TechnicalIndicatorExtractor) -> None:
        defs = extractor.feature_definitions
        expected = {
            "rsi_14", "macd", "macd_signal", "macd_hist",
            "ema_20", "ema_50", "ema_200",
            "sma_20", "sma_50", "sma_200",
            "bb_upper", "bb_middle", "bb_lower",
        }
        assert set(defs) == expected

    def test_each_feature_has_metadata(self, extractor: TechnicalIndicatorExtractor) -> None:
        for name, f in extractor.feature_definitions.items():
            assert f.name == name
            assert f.dtype == "float64"
            assert f.source_columns == ("close",)


# ---------------------------------------------------------------------------
# Column presence
# ---------------------------------------------------------------------------


class TestOutputColumns:

    def test_all_indicator_columns_present(self, extractor: TechnicalIndicatorExtractor, uptrend_data: pd.DataFrame) -> None:
        fs = extractor.extract(uptrend_data)
        expected = set(extractor.feature_definitions)
        assert expected.issubset(set(fs.data.columns))

    def test_original_close_preserved(self, extractor: TechnicalIndicatorExtractor, uptrend_data: pd.DataFrame) -> None:
        fs = extractor.extract(uptrend_data)
        assert "close" in fs.data.columns
        assert fs.data["close"].iloc[0] == uptrend_data["close"].iloc[0]


# ---------------------------------------------------------------------------
# NaN behavior (warm-up periods)
# ---------------------------------------------------------------------------


class TestNanBehavior:

    def test_early_rows_have_nans(self, extractor: TechnicalIndicatorExtractor, uptrend_data: pd.DataFrame) -> None:
        fs = extractor.extract(uptrend_data)
        assert math.isnan(fs.data["sma_200"].iloc[0])
        assert math.isnan(fs.data["bb_upper"].iloc[0])
        assert math.isnan(fs.data["rsi_14"].iloc[0])

    def test_later_rows_have_values(self, extractor: TechnicalIndicatorExtractor, uptrend_data: pd.DataFrame) -> None:
        fs = extractor.extract(uptrend_data)
        assert not math.isnan(fs.data["sma_200"].iloc[-1])
        assert not math.isnan(fs.data["rsi_14"].iloc[-1])


# ---------------------------------------------------------------------------
# RSI range
# ---------------------------------------------------------------------------


class TestRSI:

    def test_rsi_between_0_and_100(self, extractor: TechnicalIndicatorExtractor, uptrend_data: pd.DataFrame) -> None:
        fs = extractor.extract(uptrend_data)
        rsi = fs.data["rsi_14"].dropna()
        assert (rsi >= 0).all()
        assert (rsi <= 100).all()

    def test_rsi_constant_price_50(self, extractor: TechnicalIndicatorExtractor, constant_data: pd.DataFrame) -> None:
        fs = extractor.extract(constant_data)
        rsi = fs.data["rsi_14"].dropna()
        assert rsi.iloc[-1] == 50.0


# ---------------------------------------------------------------------------
# MACD consistency
# ---------------------------------------------------------------------------


class TestMACD:

    def test_histogram_equals_macd_minus_signal(self, extractor: TechnicalIndicatorExtractor, uptrend_data: pd.DataFrame) -> None:
        fs = extractor.extract(uptrend_data)
        d = fs.data.dropna(subset=["macd_hist"])
        assert np.allclose(d["macd_hist"], d["macd"] - d["macd_signal"], equal_nan=True)

    def test_macd_above_zero_in_uptrend(self, extractor: TechnicalIndicatorExtractor, uptrend_data: pd.DataFrame) -> None:
        fs = extractor.extract(uptrend_data)
        d = fs.data.dropna(subset=["macd"])
        assert (d["macd"] > 0).mean() > 0.7


# ---------------------------------------------------------------------------
# EMA vs SMA ordering
# ---------------------------------------------------------------------------


class TestMovingAverages:

    def test_ema_responds_faster_than_sma(self, extractor: TechnicalIndicatorExtractor, uptrend_data: pd.DataFrame) -> None:
        fs = extractor.extract(uptrend_data)
        d = fs.data.dropna(subset=["ema_20", "sma_20"]).iloc[:50]
        # In early uptrend, EMA > SMA because EMA weights recent prices more
        assert (d["ema_20"] > d["sma_20"]).mean() > 0.5


# ---------------------------------------------------------------------------
# Bollinger Bands
# ---------------------------------------------------------------------------


class TestBollingerBands:

    def test_bands_ordering(self, extractor: TechnicalIndicatorExtractor, uptrend_data: pd.DataFrame) -> None:
        fs = extractor.extract(uptrend_data)
        d = fs.data.dropna(subset=["bb_upper"])
        assert (d["bb_upper"] >= d["bb_middle"]).all()
        assert (d["bb_middle"] >= d["bb_lower"]).all()

    def test_band_width_is_4_std(self, extractor: TechnicalIndicatorExtractor, uptrend_data: pd.DataFrame) -> None:
        fs = extractor.extract(uptrend_data)
        full = fs.data
        expected_width = 4 * full["close"].rolling(20).std(ddof=1)
        actual_width = full["bb_upper"] - full["bb_lower"]
        both_valid = actual_width.notna() & expected_width.notna()
        assert both_valid.sum() > 0
        assert np.allclose(
            actual_width[both_valid], expected_width[both_valid]
        )


# ---------------------------------------------------------------------------
# Deterministic
# ---------------------------------------------------------------------------


class TestDeterministic:

    def test_same_input_same_output(self, extractor: TechnicalIndicatorExtractor, uptrend_data: pd.DataFrame) -> None:
        fs1 = extractor.extract(uptrend_data)
        fs2 = extractor.extract(uptrend_data)
        assert fs1.data["rsi_14"].equals(fs2.data["rsi_14"])


# ---------------------------------------------------------------------------
# FeatureSet contract
# ---------------------------------------------------------------------------


class TestFeatureSetContract:

    def test_validate_passes(self, extractor: TechnicalIndicatorExtractor, uptrend_data: pd.DataFrame) -> None:
        fs = extractor.extract(uptrend_data)
        fs.validate()

    def test_get_feature_works(self, extractor: TechnicalIndicatorExtractor, uptrend_data: pd.DataFrame) -> None:
        fs = extractor.extract(uptrend_data)
        f = fs.get_feature("rsi_14")
        assert f.name == "rsi_14"
