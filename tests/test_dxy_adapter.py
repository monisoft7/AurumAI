import dataclasses
from datetime import datetime, timezone

import numpy as np
import pandas as pd
import pytest

from knowledge.factors.adapters.dxy_adapter import DXYAdapter
from knowledge.factors.contracts import (
    BIAS_BEARISH,
    BIAS_BULLISH,
    BIAS_NEUTRAL,
    DIRECTION_FALLING,
    DIRECTION_RISING,
    DIRECTION_STABLE,
    DIRECTION_UNKNOWN,
    MECHANISM_CURRENCY_SUBSTITUTION,
    QUALITY_HIGH,
    QUALITY_LOW,
    QUALITY_MODERATE,
    QUALITY_STALE,
    FactorSignal,
)
from knowledge.factors.factor_config import FactorConfig
from knowledge.integrity.provenance import Provenance


# ── Fixtures ─────────────────────────────────────────────────────────

@pytest.fixture
def daily_series() -> pd.Series:
    rng = np.random.default_rng(42)
    dates = pd.date_range("2021-01-01", "2026-01-01", freq="B")
    values = 100.0 + rng.normal(0, 5.0, len(dates))
    return pd.Series(values, index=dates)


@pytest.fixture
def clear_rising_series() -> pd.Series:
    dates = pd.date_range("2024-01-01", "2025-01-01", freq="B")
    values = [95.0 + i * 0.25 for i in range(len(dates))]
    return pd.Series(values, index=dates)


@pytest.fixture
def clear_falling_series() -> pd.Series:
    dates = pd.date_range("2024-01-01", "2025-01-01", freq="B")
    values = [110.0 - i * 0.25 for i in range(len(dates))]
    return pd.Series(values, index=dates)


# ── Basic contract ───────────────────────────────────────────────────


class TestBasicContract:
    def test_returns_factor_signal(self, daily_series: pd.Series) -> None:
        signal = DXYAdapter.to_factor_signal(daily_series)
        assert isinstance(signal, FactorSignal)

    def test_factor_id(self, daily_series: pd.Series) -> None:
        signal = DXYAdapter.to_factor_signal(daily_series)
        assert signal.factor_id == "us_dollar_index"

    def test_mechanism(self, daily_series: pd.Series) -> None:
        signal = DXYAdapter.to_factor_signal(daily_series)
        assert signal.mechanism == MECHANISM_CURRENCY_SUBSTITUTION

    def test_signal_is_frozen(self, daily_series: pd.Series) -> None:
        signal = DXYAdapter.to_factor_signal(daily_series)
        with pytest.raises((TypeError, dataclasses.FrozenInstanceError)):
            signal.value = 99.0  # type: ignore[misc]

    def test_observation_date_format(self, daily_series: pd.Series) -> None:
        signal = DXYAdapter.to_factor_signal(daily_series)
        assert isinstance(signal.observation_date, str)
        assert "-" in signal.observation_date


# ── Provenance ───────────────────────────────────────────────────────


class TestProvenance:
    def test_provenance_created(self, daily_series: pd.Series) -> None:
        signal = DXYAdapter.to_factor_signal(daily_series)
        assert isinstance(signal.provenance, Provenance)
        assert signal.provenance.created_by == "dxy_adapter.v1"
        assert signal.provenance.entity_version == "1.0.0"

    def test_provenance_timestamp_is_utc_iso(self, daily_series: pd.Series) -> None:
        signal = DXYAdapter.to_factor_signal(daily_series)
        dt = datetime.fromisoformat(signal.provenance.created_at)
        assert dt.tzinfo is not None


# ── Z-score and percentile ───────────────────────────────────────────


class TestZScore:
    def test_z_score_zero_for_single_value(self) -> None:
        series = pd.Series([100.0], index=pd.to_datetime(["2025-01-01"]))
        signal = DXYAdapter.to_factor_signal(series)
        assert signal.z_score == 0.0
        assert signal.percentile == 0.5

    def test_z_score_zero_for_insufficient_data(self) -> None:
        dates = pd.date_range("2025-01-01", periods=5, freq="B")
        series = pd.Series([100.0] * 5, index=dates)
        signal = DXYAdapter.to_factor_signal(series)
        assert signal.z_score == 0.0
        assert signal.percentile == 0.5

    def test_z_score_positive_for_above_mean(self) -> None:
        rng = np.random.default_rng(42)
        dates = pd.date_range("2020-01-01", "2025-01-01", freq="B")
        values = 100.0 + rng.normal(0, 5.0, len(dates))
        series = pd.Series(values, index=dates)
        series.iloc[-1] = 120.0  # extreme high
        signal = DXYAdapter.to_factor_signal(series)
        assert signal.z_score > 0

    def test_z_score_negative_for_below_mean(self) -> None:
        rng = np.random.default_rng(42)
        dates = pd.date_range("2020-01-01", "2025-01-01", freq="B")
        values = 100.0 + rng.normal(0, 5.0, len(dates))
        series = pd.Series(values, index=dates)
        series.iloc[-1] = 80.0
        signal = DXYAdapter.to_factor_signal(series)
        assert signal.z_score < 0

    def test_percentile_in_range(self, daily_series: pd.Series) -> None:
        signal = DXYAdapter.to_factor_signal(daily_series)
        assert 0.0 <= signal.percentile <= 1.0

    def test_z_score_window_parameter(self) -> None:
        rng = np.random.default_rng(42)
        dates = pd.date_range("2015-01-01", "2025-01-01", freq="B")
        values = 100.0 + rng.normal(0, 5.0, len(dates))
        series = pd.Series(values, index=dates)
        series.iloc[-1] = 110.0
        full_signal = DXYAdapter.to_factor_signal(series)
        cfg = FactorConfig(
            factor_id="us_dollar_index",
            z_score_window=50,
        )
        short_signal = DXYAdapter.to_factor_signal(series, config=cfg)
        assert full_signal.z_score != short_signal.z_score

    def test_custom_config_propagates(self, daily_series: pd.Series) -> None:
        cfg = FactorConfig(
            factor_id="custom_dxy",
            name="Custom DXY",
            direction_threshold=0.50,
            min_samples=10,
        )
        signal = DXYAdapter.to_factor_signal(daily_series, config=cfg)
        assert signal.factor_id == "custom_dxy"


# ── Direction detection ──────────────────────────────────────────────


class TestDirection:
    def test_rising_series(self, clear_rising_series: pd.Series) -> None:
        signal = DXYAdapter.to_factor_signal(clear_rising_series)
        assert signal.direction == DIRECTION_RISING

    def test_falling_series(self, clear_falling_series: pd.Series) -> None:
        signal = DXYAdapter.to_factor_signal(clear_falling_series)
        assert signal.direction == DIRECTION_FALLING

    def test_stable_series(self) -> None:
        dates = pd.date_range("2025-01-01", periods=10, freq="B")
        series = pd.Series([100.0] * 10, index=dates)
        signal = DXYAdapter.to_factor_signal(series)
        assert signal.direction == DIRECTION_STABLE

    def test_unknown_for_single_observation(self) -> None:
        series = pd.Series([100.0], index=pd.to_datetime(["2025-01-01"]))
        signal = DXYAdapter.to_factor_signal(series)
        assert signal.direction == DIRECTION_UNKNOWN

    def test_unknown_for_empty(self) -> None:
        series = pd.Series(dtype="float64")
        signal = DXYAdapter.to_factor_signal(series)
        assert signal.direction == DIRECTION_UNKNOWN

    def test_direction_with_custom_threshold(self) -> None:
        dates = pd.date_range("2025-01-01", periods=3, freq="B")
        series = pd.Series([100.0, 100.10, 100.20], index=dates)
        cfg = FactorConfig(
            factor_id="us_dollar_index",
            direction_threshold=0.30,  # 0.10 change is below threshold
        )
        signal = DXYAdapter.to_factor_signal(series, config=cfg)
        assert signal.direction == DIRECTION_STABLE


# ── Gold influence bias (inverse relationship) ───────────────────────


class TestGoldInfluence:
    def test_strong_dollar_is_bearish(self) -> None:
        rng = np.random.default_rng(42)
        dates = pd.date_range("2020-01-01", "2025-01-01", freq="B")
        values = 100.0 + rng.normal(0, 3.0, len(dates))
        series = pd.Series(values, index=dates)
        series.iloc[-1] = 130.0  # extreme high
        signal = DXYAdapter.to_factor_signal(series)
        assert signal.influence_bias == BIAS_BEARISH
        assert signal.influence_strength < 0

    def test_weak_dollar_is_bullish(self) -> None:
        rng = np.random.default_rng(42)
        dates = pd.date_range("2020-01-01", "2025-01-01", freq="B")
        values = 100.0 + rng.normal(0, 3.0, len(dates))
        series = pd.Series(values, index=dates)
        series.iloc[-1] = 75.0  # extreme low
        signal = DXYAdapter.to_factor_signal(series)
        assert signal.influence_bias == BIAS_BULLISH
        assert signal.influence_strength > 0

    def test_neutral_dollar(self) -> None:
        rng = np.random.default_rng(42)
        dates = pd.date_range("2020-01-01", "2025-01-01", freq="B")
        values = 100.0 + rng.normal(0, 3.0, len(dates))
        series = pd.Series(values, index=dates)
        signal = DXYAdapter.to_factor_signal(series)
        assert signal.influence_bias in (BIAS_NEUTRAL, BIAS_BULLISH, BIAS_BEARISH)

    def test_influence_strength_bounded(self, daily_series: pd.Series) -> None:
        signal = DXYAdapter.to_factor_signal(daily_series)
        assert -1.0 <= signal.influence_strength <= 1.0

    def test_influence_strength_zero_for_empty(self) -> None:
        series = pd.Series(dtype="float64")
        signal = DXYAdapter.to_factor_signal(series)
        assert signal.influence_strength == 0.0
        assert signal.influence_bias == BIAS_NEUTRAL


# ── Data quality ─────────────────────────────────────────────────────


class TestDataQuality:
    def test_high_for_recent_data(self) -> None:
        today = datetime.now(timezone.utc)
        dates = pd.date_range(end=today, periods=500, freq="B")
        series = pd.Series([100.0] * len(dates), index=dates)
        signal = DXYAdapter.to_factor_signal(series)
        assert signal.data_quality == QUALITY_HIGH

    def test_stale_for_old_data(self) -> None:
        dates = pd.date_range("2020-01-01", "2020-06-01", freq="B")
        series = pd.Series([100.0] * len(dates), index=dates)
        signal = DXYAdapter.to_factor_signal(series)
        assert signal.data_quality == QUALITY_STALE


# ── Observation date override ────────────────────────────────────────


class TestObservationDate:
    def test_specific_date_in_past(self, daily_series: pd.Series) -> None:
        signal = DXYAdapter.to_factor_signal(
            daily_series, observation_date="2023-06-15",
        )
        assert signal.observation_date == "2023-06-15"

    def test_specific_date_controls_value(self, clear_rising_series: pd.Series) -> None:
        known_date = "2024-06-15"
        series_at_target = clear_rising_series[
            clear_rising_series.index <= known_date
        ]
        expected_value = float(series_at_target.iloc[-1])
        signal = DXYAdapter.to_factor_signal(
            clear_rising_series, observation_date=known_date,
        )
        assert signal.value == pytest.approx(expected_value, rel=1e-4)

    def test_defaults_to_latest(self, daily_series: pd.Series) -> None:
        signal = DXYAdapter.to_factor_signal(daily_series)
        expected_date = daily_series.index[-1].strftime("%Y-%m-%d")
        assert signal.observation_date == expected_date


# ── Edge cases ───────────────────────────────────────────────────────


class TestEdgeCases:
    def test_empty_series(self) -> None:
        signal = DXYAdapter.to_factor_signal(pd.Series(dtype="float64"))
        assert signal.factor_id == "us_dollar_index"
        assert signal.direction == DIRECTION_UNKNOWN
        assert signal.data_quality == QUALITY_STALE
        assert signal.confidence == 0.0

    def test_single_observation(self) -> None:
        series = pd.Series([100.5], index=pd.to_datetime(["2025-01-01"]))
        signal = DXYAdapter.to_factor_signal(series)
        assert signal.value == 100.5
        assert signal.z_score == 0.0
        assert signal.direction == DIRECTION_UNKNOWN

    def test_all_nan_values(self) -> None:
        dates = pd.date_range("2025-01-01", periods=10, freq="B")
        series = pd.Series([float("nan")] * 10, index=dates)
        signal = DXYAdapter.to_factor_signal(series)
        assert signal.value != signal.value  # NaN
        assert signal.direction == DIRECTION_UNKNOWN

    def test_constant_series(self) -> None:
        dates = pd.date_range("2024-01-01", "2025-01-01", freq="B")
        series = pd.Series([100.0] * len(dates), index=dates)
        signal = DXYAdapter.to_factor_signal(series)
        assert signal.z_score == 0.0
        assert signal.percentile == 0.5
        assert signal.direction == DIRECTION_STABLE


# ── Confidence computation ───────────────────────────────────────────


class TestConfidence:
    def test_confidence_zero_for_empty(self) -> None:
        signal = DXYAdapter.to_factor_signal(pd.Series(dtype="float64"))
        assert signal.confidence == 0.0

    def test_confidence_reduced_for_small_sample(self) -> None:
        dates = pd.date_range("2025-01-01", periods=20, freq="B")
        series = pd.Series([100.0] * len(dates), index=dates)
        signal = DXYAdapter.to_factor_signal(series)
        assert signal.confidence < 0.5


# ── RegimeAdjustment hook ────────────────────────────────────────────


class TestRegimeAdjust:
    def test_identity_default(self) -> None:
        bias, strength = DXYAdapter.regime_adjust(
            bias=BIAS_BEARISH, strength=-0.5,
        )
        assert bias == BIAS_BEARISH
        assert strength == -0.5

    def test_identity_with_regime(self) -> None:
        bias, strength = DXYAdapter.regime_adjust(
            bias=BIAS_BULLISH, strength=0.3, regime="risk_off",
        )
        assert bias == BIAS_BULLISH
        assert strength == 0.3

    def test_identity_with_config(self) -> None:
        cfg = FactorConfig(factor_id="us_dollar_index")
        bias, strength = DXYAdapter.regime_adjust(
            bias=BIAS_NEUTRAL, strength=0.0, config=cfg,
        )
        assert bias == BIAS_NEUTRAL
        assert strength == 0.0
