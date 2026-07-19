import numpy as np
import pandas as pd
import pytest

from forecasting.macro_forecaster import MacroForecaster
from forecasting.models import ForecastPoint, ForecastResult


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_N_OBS = 48
_SEED = 42


def _make_data(n: int = _N_OBS, seed: int = _SEED) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    dates = pd.date_range("2020-01-01", periods=n, freq="ME")
    values = np.cumsum(rng.normal(0, 1, n)) + 100
    return pd.DataFrame({"ds": dates, "y": values})


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def sample_data() -> pd.DataFrame:
    return _make_data()


@pytest.fixture
def forecaster() -> MacroForecaster:
    return MacroForecaster()


# ---------------------------------------------------------------------------
# Model contract
# ---------------------------------------------------------------------------


class TestModelContract:

    def test_default_models_three(self, forecaster: MacroForecaster) -> None:
        assert forecaster.model_names == ["AutoARIMA", "AutoETS", "AutoTheta"]

    def test_returns_three_results(self, forecaster: MacroForecaster, sample_data: pd.DataFrame) -> None:
        results = forecaster.forecast(sample_data, h=6)
        assert set(results) == {"AutoARIMA", "AutoETS", "AutoTheta"}


# ---------------------------------------------------------------------------
# ForecastResult contract
# ---------------------------------------------------------------------------


class TestForecastResultContract:

    def test_frozen_dataclass(self, forecaster: MacroForecaster, sample_data: pd.DataFrame) -> None:
        results = forecaster.forecast(sample_data, h=6)
        for r in results.values():
            with pytest.raises(AttributeError):
                r.model_name = "other"  # type: ignore[misc]

    def test_confidence_level(self, forecaster: MacroForecaster, sample_data: pd.DataFrame) -> None:
        for r in forecaster.forecast(sample_data, h=6).values():
            assert r.confidence_level == 0.95

    def test_model_name_present(self, forecaster: MacroForecaster, sample_data: pd.DataFrame) -> None:
        for name, r in forecaster.forecast(sample_data, h=6).items():
            assert r.model_name == name

    def test_points_is_tuple(self, forecaster: MacroForecaster, sample_data: pd.DataFrame) -> None:
        for r in forecaster.forecast(sample_data, h=6).values():
            assert isinstance(r.points, tuple)

    def test_metadata_contains_keys(self, forecaster: MacroForecaster, sample_data: pd.DataFrame) -> None:
        for r in forecaster.forecast(sample_data, h=6).values():
            assert "season_length" in r.metadata
            assert "freq" in r.metadata
            assert "h" in r.metadata
            assert "n_obs" in r.metadata


# ---------------------------------------------------------------------------
# ForecastPoint contract
# ---------------------------------------------------------------------------


class TestForecastPointContract:

    def test_frozen_dataclass(self) -> None:
        p = ForecastPoint(ds="2024-01-01", y=100.0, y_lo=95.0, y_hi=105.0)
        with pytest.raises(AttributeError):
            p.y = 200.0  # type: ignore[misc]

    def test_fields(self) -> None:
        p = ForecastPoint(ds="2024-01-01", y=100.0, y_lo=95.0, y_hi=105.0)
        assert p.ds == "2024-01-01"
        assert p.y == 100.0
        assert p.y_lo == 95.0
        assert p.y_hi == 105.0


# ---------------------------------------------------------------------------
# Point count
# ---------------------------------------------------------------------------


class TestForecastHorizon:

    def test_forecast_h_6(self, forecaster: MacroForecaster, sample_data: pd.DataFrame) -> None:
        for r in forecaster.forecast(sample_data, h=6).values():
            assert len(r.points) == 6

    def test_forecast_h_12(self, forecaster: MacroForecaster, sample_data: pd.DataFrame) -> None:
        for r in forecaster.forecast(sample_data, h=12).values():
            assert len(r.points) == 12

    def test_forecast_h_1(self, forecaster: MacroForecaster, sample_data: pd.DataFrame) -> None:
        for r in forecaster.forecast(sample_data, h=1).values():
            assert len(r.points) == 1


# ---------------------------------------------------------------------------
# Prediction intervals
# ---------------------------------------------------------------------------


class TestPredictionIntervals:

    def test_y_between_lo_and_hi(self, forecaster: MacroForecaster, sample_data: pd.DataFrame) -> None:
        for r in forecaster.forecast(sample_data, h=6).values():
            for p in r.points:
                assert p.y_lo <= p.y <= p.y_hi, f"{r.model_name}: {p.y_lo} <= {p.y} <= {p.y_hi}"

    def test_interval_wider_at_end_than_start(self, forecaster: MacroForecaster, sample_data: pd.DataFrame) -> None:
        for r in forecaster.forecast(sample_data, h=12).values():
            widths = [p.y_hi - p.y_lo for p in r.points]
            # Uncertainty grows over time — last interval wider than first
            assert widths[-1] >= widths[0] - 1e-8, f"{r.model_name}: final interval narrower than initial"


# ---------------------------------------------------------------------------
# Deterministic
# ---------------------------------------------------------------------------


class TestDeterministic:

    def test_same_input_same_output(self, forecaster: MacroForecaster, sample_data: pd.DataFrame) -> None:
        r1 = forecaster.forecast(sample_data, h=6)
        r2 = forecaster.forecast(sample_data, h=6)
        for name in r1:
            p1 = r1[name].points
            p2 = r2[name].points
            for a, b in zip(p1, p2):
                assert a.ds == b.ds
                assert abs(a.y - b.y) < 1e-8
                assert abs(a.y_lo - b.y_lo) < 1e-8
                assert abs(a.y_hi - b.y_hi) < 1e-8

    def test_different_seed_different_result(self) -> None:
        f = MacroForecaster()
        d1 = _make_data(seed=42)
        d2 = _make_data(seed=99)
        r1 = f.forecast(d1, h=6)
        r2 = f.forecast(d2, h=6)
        # Different data should produce different forecasts
        p1_y = [p.y for p in r1["AutoARIMA"].points]
        p2_y = [p.y for p in r2["AutoARIMA"].points]
        assert not np.allclose(p1_y, p2_y)


# ---------------------------------------------------------------------------
# Input validation
# ---------------------------------------------------------------------------


class TestInputValidation:

    def test_missing_ds_column(self) -> None:
        f = MacroForecaster()
        bad = pd.DataFrame({"date": pd.date_range("2020-01-01", periods=10, freq="ME"), "y": range(10)})
        with pytest.raises(ValueError, match="ds"):
            f.forecast(bad)

    def test_missing_y_column(self) -> None:
        f = MacroForecaster()
        bad = pd.DataFrame({"ds": pd.date_range("2020-01-01", periods=10, freq="ME"), "value": range(10)})
        with pytest.raises(ValueError, match="y"):
            f.forecast(bad)

    def test_empty_dataframe(self) -> None:
        f = MacroForecaster()
        empty = pd.DataFrame({"ds": pd.Series(dtype="datetime64[ns]"), "y": pd.Series(dtype="float64")})
        with pytest.raises(Exception):
            f.forecast(empty, h=1)


# ---------------------------------------------------------------------------
# Custom models
# ---------------------------------------------------------------------------


class TestCustomModels:

    def test_single_model(self) -> None:
        try:
            from statsforecast.models import AutoARIMA
        except ImportError:
            pytest.skip("statsforecast not installed")
        f = MacroForecaster(models=[AutoARIMA(season_length=12)])
        assert f.model_names == ["AutoARIMA"]
        data = _make_data(48)
        results = f.forecast(data, h=6)
        assert set(results) == {"AutoARIMA"}

    def test_model_names_match(self) -> None:
        try:
            from statsforecast.models import AutoETS
        except ImportError:
            pytest.skip("statsforecast not installed")
        custom = [AutoETS(season_length=6, model="AAA")]
        f = MacroForecaster(season_length=6, models=custom)
        assert f.model_names == ["AutoETS"]
        data = _make_data(48)
        results = f.forecast(data, h=3)
        assert results["AutoETS"].metadata["season_length"] == 6


# ---------------------------------------------------------------------------
# Dates are futures
# ---------------------------------------------------------------------------


class TestFutureDates:

    def test_all_dates_after_last_obs(self, forecaster: MacroForecaster, sample_data: pd.DataFrame) -> None:
        last_obs = sample_data["ds"].max()
        for r in forecaster.forecast(sample_data, h=6).values():
            for p in r.points:
                assert pd.Timestamp(p.ds) > last_obs
