from __future__ import annotations

import numpy as np
import pytest

from forecasting.position_sizing import (
    DrawdownManager,
    KellyCap,
    PositionSizing,
    VolatilityTargetSizer,
)

_SEED = 42


def _vol_returns(n: int = 100, vol: float = 0.01) -> np.ndarray:
    rng = np.random.default_rng(_SEED)
    return rng.normal(loc=0.0005, scale=vol, size=n)


# ── PositionSizing dataclass ────────────────────────────────────────── #


class TestPositionSizing:

    def test_frozen(self) -> None:
        s = PositionSizing(scaling_factor=0.5, target_vol=0.15, current_vol=0.12, drawdown_state="normal", kelly_cap=0.25)
        with pytest.raises(AttributeError):
            s.scaling_factor = 0.6  # type: ignore[misc]

    def test_all_fields(self) -> None:
        s = PositionSizing(scaling_factor=0.75, target_vol=0.15, current_vol=0.10, drawdown_state="caution", kelly_cap=0.5)
        assert s.scaling_factor == 0.75
        assert s.drawdown_state == "caution"
        assert s.kelly_cap == 0.5

    def test_to_dict(self) -> None:
        s = PositionSizing(scaling_factor=0.0, target_vol=0.15, current_vol=0.0, drawdown_state="halted", kelly_cap=None)
        d = s.to_dict()
        assert d["scaling_factor"] == 0.0
        assert d["kelly_cap"] is None


# ── VolatilityTargetSizer ──────────────────────────────────────────── #


class TestVolatilityTargetSizer:

    def test_normal_vol(self) -> None:
        r = _vol_returns(100, 0.01)
        sizer = VolatilityTargetSizer()
        s = sizer.compute(r, target_vol=0.15)
        assert 0.0 < s.scaling_factor <= 1.0
        assert s.current_vol > 0.0

    def test_high_vol_reduces_scale(self) -> None:
        r_low = _vol_returns(100, 0.005)
        r_high = _vol_returns(100, 0.05)
        sizer = VolatilityTargetSizer()
        s_low = sizer.compute(r_low, target_vol=0.15)
        s_high = sizer.compute(r_high, target_vol=0.15)
        assert s_low.scaling_factor > s_high.scaling_factor

    def test_empty_returns(self) -> None:
        s = VolatilityTargetSizer().compute(np.array([]))
        assert s.scaling_factor == 0.0
        assert s.current_vol == 0.0

    def test_target_vol_zero(self) -> None:
        with pytest.raises(ValueError, match="target_vol must be positive"):
            VolatilityTargetSizer().compute(np.array([0.01, 0.02]), target_vol=0.0)

    def test_window_too_small(self) -> None:
        with pytest.raises(ValueError, match="window must be >= 2"):
            VolatilityTargetSizer().compute(np.array([0.01]), window=1)

    def test_scale_clamped_at_1(self) -> None:
        r = np.array([0.0001] * 100)
        s = VolatilityTargetSizer().compute(r, target_vol=2.0)
        assert s.scaling_factor <= 1.0

    def test_deterministic(self) -> None:
        r = _vol_returns(100, 0.01)
        sizer = VolatilityTargetSizer()
        s1 = sizer.compute(r)
        s2 = sizer.compute(r)
        assert s1.scaling_factor == s2.scaling_factor
        assert s1.current_vol == s2.current_vol


# ── DrawdownManager ─────────────────────────────────────────────────── #


class TestDrawdownManager:

    def test_normal_state(self) -> None:
        prices = np.linspace(100, 105, 50)
        state, dd, _ = DrawdownManager().evaluate(prices)
        assert state == "normal"
        assert dd < 0.10

    def test_caution_state(self) -> None:
        prices = np.array([100, 102, 98, 95, 93, 91, 89])
        state, dd, _ = DrawdownManager(caution_threshold=0.05, halt_threshold=0.15).evaluate(prices)
        assert state == "caution"
        assert dd >= 0.05

    def test_halted_state(self) -> None:
        prices = np.array([100, 105, 90, 80, 75, 70])
        state, dd, _ = DrawdownManager(caution_threshold=0.05, halt_threshold=0.10).evaluate(prices)
        assert state == "halted"
        assert dd >= 0.10

    def test_recovery_from_halted(self) -> None:
        mgr = DrawdownManager(caution_threshold=0.05, halt_threshold=0.10, recovery_period=3)
        prices = np.array([100, 105, 80, 82, 84, 86, 88, 90])
        state, _, counter = mgr.evaluate(prices, prev_state="halted", recovery_counter=0)
        assert state == "halted"
        assert counter == 1

    def test_recovery_complete(self) -> None:
        mgr = DrawdownManager(caution_threshold=0.10, halt_threshold=0.20, recovery_period=3)
        prices = np.array([100, 110, 115, 118, 120])
        state, dd, _ = mgr.evaluate(prices, prev_state="halted", recovery_counter=5)
        assert state == "normal"
        assert dd < 0.05

    def test_empty_prices(self) -> None:
        state, dd, counter = DrawdownManager().evaluate(np.array([]))
        assert state == "normal"
        assert dd == 0.0
        assert counter == 0

    def test_invalid_thresholds(self) -> None:
        with pytest.raises(ValueError, match="caution_threshold < halt_threshold"):
            DrawdownManager(caution_threshold=0.20, halt_threshold=0.10)

    def test_invalid_recovery_period(self) -> None:
        with pytest.raises(ValueError, match="recovery_period must be >= 1"):
            DrawdownManager(recovery_period=0)

    def test_no_drawdown_peak_at_end(self) -> None:
        prices = np.array([90, 95, 100])
        state, dd, _ = DrawdownManager().evaluate(prices)
        assert state == "normal"
        assert dd == 0.0


# ── KellyCap ───────────────────────────────────────────────────────── #


class TestKellyCap:

    def test_positive_edge(self) -> None:
        cap = KellyCap().compute(win_prob=0.60, payoff_ratio=2.0, fraction=0.25)
        assert 0.0 < cap <= 1.0

    def test_no_edge_returns_zero(self) -> None:
        cap = KellyCap().compute(win_prob=0.40, payoff_ratio=1.0, fraction=0.25)
        assert cap == 0.0

    def test_full_kelly_known_value(self) -> None:
        cap = KellyCap().compute(win_prob=0.90, payoff_ratio=10.0, fraction=1.0)
        expected = (10.0 * 0.90 - 0.10) / 10.0
        assert cap == round(expected, 6)

    def test_fractional_kelly_scales(self) -> None:
        full = KellyCap().compute(win_prob=0.60, payoff_ratio=2.0, fraction=1.0)
        half = KellyCap().compute(win_prob=0.60, payoff_ratio=2.0, fraction=0.5)
        assert abs(half - full * 0.5) < 1e-6

    def test_invalid_win_prob(self) -> None:
        with pytest.raises(ValueError, match="win_prob must be"):
            KellyCap().compute(win_prob=0.0, payoff_ratio=2.0)

    def test_invalid_payoff_ratio(self) -> None:
        with pytest.raises(ValueError, match="payoff_ratio must be positive"):
            KellyCap().compute(win_prob=0.6, payoff_ratio=0.0)

    def test_invalid_fraction(self) -> None:
        with pytest.raises(ValueError, match="fraction must be"):
            KellyCap().compute(win_prob=0.6, payoff_ratio=2.0, fraction=0.0)

    def test_deterministic(self) -> None:
        k1 = KellyCap().compute(0.55, 1.5)
        k2 = KellyCap().compute(0.55, 1.5)
        assert k1 == k2
