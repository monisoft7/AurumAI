from __future__ import annotations

import numpy as np

from forecasting.context import ForecastContext
from forecasting.models import ForecastPoint, ForecastResult
from forecasting.position_sizing import PositionSizing
from orchestration.stages import _position_sizing, _risk_gate

# Legacy deterministic synthetic outputs (removed; must never recur):
LEGACY_SYNTHETIC_SCALE = 0.432555
LEGACY_SYNTHETIC_CURRENT_VOL = 0.346777
LEGACY_SYNTHETIC_BUDGET_WEIGHTS = (0.464102, 0.535898)


def _forecast_result(ys: list[float], freq: str = "ME") -> ForecastResult:
    points = tuple(
        ForecastPoint(
            ds=f"2026-{i:02d}-28",
            y=float(y),
            y_lo=float(y) * 0.99,
            y_hi=float(y) * 1.01,
        )
        for i, y in enumerate(ys, start=1)
    )
    return ForecastResult(
        model_name="AutoARIMA",
        confidence_level=0.95,
        points=points,
        metadata={"freq": freq, "h": len(ys)},
    )


def _context(regime: str = "EXPANSION", confidence: float = 0.9) -> ForecastContext:
    return ForecastContext(
        current_regime=regime,
        regime_confidence=confidence,
        recent_events=(),
        news_mood=None,
        news_confidence=0.0,
        fomc_mood=None,
        fomc_confidence=0.0,
        context_timestamp="2026-01-01T00:00:00",
        source_variable="gold",
        data_date_range=("2025-01-01", "2026-01-01"),
    )


class TestPositionSizingStageRealInput:

    def test_status_ok(self) -> None:
        out = _position_sizing({}, {"forecast": _forecast_result([100.0, 102.0, 101.0, 103.0])})
        assert out["status"] == "ok"
        assert out["position_sizing"] is not None
        assert out["risk_budget"] is not None

    def test_scaling_derived_from_real_returns(self) -> None:
        ys = [100.0, 102.0, 101.0, 103.0, 104.0, 106.0, 105.0, 108.0]
        out = _position_sizing({}, {"forecast": _forecast_result(ys)})
        sizing = out["position_sizing"]
        ys_arr = np.array(ys, dtype=float)
        returns = ys_arr[1:] / ys_arr[:-1] - 1.0
        current_vol = float(np.std(returns, ddof=1)) * np.sqrt(12.0)
        expected_scale = 0.0 if current_vol == 0.0 else max(0.0, min(0.15 / current_vol, 1.0))
        assert sizing.current_vol == round(current_vol, 6)
        assert sizing.scaling_factor == round(expected_scale, 6)

    def test_drawdown_state_derived_from_real_forecast(self) -> None:
        ys = [100.0, 50.0, 45.0]
        out = _position_sizing({}, {"forecast": _forecast_result(ys)})
        assert out["position_sizing"].drawdown_state == "halted"

    def test_risk_budget_from_real_covariance_single_asset(self) -> None:
        out = _position_sizing({}, {"forecast": _forecast_result([100.0, 102.0, 101.0, 103.0])})
        assert out["risk_budget"].weights == (1.0,)
        assert out["risk_budget"].risk_contributions == (1.0,)

    def test_accepts_serialized_dict_forecast(self) -> None:
        ys = [100.0, 102.0, 104.0, 106.0]
        fr = _forecast_result(ys)
        as_dict = {
            "model_name": fr.model_name,
            "confidence_level": fr.confidence_level,
            "points": [{"ds": p.ds, "y": p.y, "y_lo": p.y_lo, "y_hi": p.y_hi} for p in fr.points],
            "metadata": dict(fr.metadata),
        }
        out = _position_sizing({}, {"forecast": as_dict})
        assert out["status"] == "ok"
        assert out["position_sizing"].scaling_factor == _position_sizing(
            {}, {"forecast": fr}
        )["position_sizing"].scaling_factor

    def test_deterministic_repeatable(self) -> None:
        ys = [100.0, 102.0, 101.0, 103.0, 104.0]
        a = _position_sizing({}, {"forecast": _forecast_result(ys)})
        b = _position_sizing({}, {"forecast": _forecast_result(ys)})
        assert a["position_sizing"] == b["position_sizing"]
        assert a["risk_budget"] == b["risk_budget"]


class TestPositionSizingStageInsufficientData:

    def test_no_forecast(self) -> None:
        out = _position_sizing({}, {})
        assert out["status"] == "insufficient_data"
        assert out["position_sizing"] is None
        assert out["risk_budget"] is None

    def test_single_forecast_point(self) -> None:
        out = _position_sizing({}, {"forecast": _forecast_result([100.0])})
        assert out["status"] == "insufficient_data"

    def test_non_finite_price(self) -> None:
        out = _position_sizing({}, {"forecast": _forecast_result([100.0, np.nan, 110.0])})
        assert out["status"] == "insufficient_data"

    def test_non_positive_first_price(self) -> None:
        out = _position_sizing({}, {"forecast": _forecast_result([0.0, 100.0, 110.0])})
        assert out["status"] == "insufficient_data"

    def test_unknown_frequency(self) -> None:
        out = _position_sizing({}, {"forecast": _forecast_result([100.0, 102.0, 105.0], freq="CUSTOM")})
        assert out["status"] == "insufficient_data"

    def test_missing_frequency(self) -> None:
        fr = _forecast_result([100.0, 102.0, 105.0])
        import dataclasses

        no_freq = dataclasses.replace(fr, metadata={})
        out = _position_sizing({}, {"forecast": no_freq})
        assert out["status"] == "insufficient_data"


class TestPositionSizingStageSyntheticRemoved:

    def test_no_legacy_synthetic_scaling(self) -> None:
        ys = [
            4335.636102257506, 4341.389110539252, 4347.97347888328,
            4353.956776177412, 4360.279958843628, 4367.295972504141,
            4373.803284949964, 4379.853897590357, 4386.477649883688,
            4390.2469922648015, 4396.83117847564, 4402.403603551001,
        ]
        out = _position_sizing({}, {"forecast": _forecast_result(ys)})
        sizing = out["position_sizing"]
        assert sizing.scaling_factor != LEGACY_SYNTHETIC_SCALE
        assert sizing.current_vol != LEGACY_SYNTHETIC_CURRENT_VOL
        assert out["risk_budget"].weights != LEGACY_SYNTHETIC_BUDGET_WEIGHTS

    def test_stage_has_no_rng_or_hardcoded_covariance(self) -> None:
        import inspect

        src = inspect.getsource(_position_sizing)
        assert "default_rng" not in src
        assert "0.005, 0.02" not in src
        assert "0.0004" not in src

    def test_sizer_has_no_hardcoded_drawdown(self) -> None:
        import inspect

        from forecasting.position_sizing import VolatilityTargetSizer

        src = inspect.getsource(VolatilityTargetSizer.compute)
        assert 'drawdown_state="normal"' not in src


class TestRiskGateRealPositionSizing:

    def test_uses_real_scaling_factor_from_sizing(self) -> None:
        sizing = PositionSizing(
            scaling_factor=1.0,
            target_vol=0.15,
            current_vol=0.001,
            drawdown_state="normal",
            kelly_cap=None,
        )
        results = {
            "build_context": _context("EXPANSION", 0.9),
            "risk_measures": None,
            "position_sizing": {"position_sizing": sizing, "status": "ok"},
        }
        gate = _risk_gate({}, results)
        assert gate.action == "proceed"
        assert gate.score == round(0.9 * 0.40 * 1.0, 4)

    def test_uses_real_drawdown_state_from_sizing(self) -> None:
        sizing = PositionSizing(
            scaling_factor=1.0,
            target_vol=0.15,
            current_vol=0.001,
            drawdown_state="halted",
            kelly_cap=None,
        )
        results = {
            "build_context": _context("EXPANSION", 0.9),
            "risk_measures": None,
            "position_sizing": {"position_sizing": sizing, "status": "ok"},
        }
        gate = _risk_gate({}, results)
        assert gate.action == "halt"
        assert gate.score == 0.0

    def test_falls_back_when_sizing_absent(self) -> None:
        results = {"build_context": _context("EXPANSION", 0.9), "risk_measures": None}
        gate = _risk_gate({}, results)
        assert gate.action == "proceed"
        assert gate.score == round(0.9 * 0.40 * 0.5, 4)

    def test_falls_back_when_sizing_insufficient_data(self) -> None:
        results = {
            "build_context": _context("EXPANSION", 0.9),
            "risk_measures": None,
            "position_sizing": {
                "position_sizing": None,
                "risk_budget": None,
                "status": "insufficient_data",
            },
        }
        gate = _risk_gate({}, results)
        assert gate.action == "proceed"
        assert gate.score == round(0.9 * 0.40 * 0.5, 4)
