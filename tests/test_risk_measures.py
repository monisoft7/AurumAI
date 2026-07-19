from __future__ import annotations

import numpy as np
import pytest

from forecasting.risk_measures import (
    RiskMetrics,
    TailRiskDetector,
    _norm_ppf,
    compute_cvar,
    compute_var,
)

_SEED = 42


def _normal_returns(n: int = 1000) -> np.ndarray:
    rng = np.random.default_rng(_SEED)
    return rng.normal(loc=0.0, scale=0.01, size=n)


def _t_returns(n: int = 1000, df: float = 3.0) -> np.ndarray:
    rng = np.random.default_rng(_SEED)
    return rng.standard_t(df=df, size=n) * 0.01


# ── helpers used in tests ───────────────────────────────────────────── #


def test_norm_ppf_symmetry() -> None:
    assert abs(_norm_ppf(0.05) + _norm_ppf(0.95)) < 1e-4


def test_norm_ppf_known() -> None:
    assert abs(_norm_ppf(0.5)) < 1e-4
    assert abs(_norm_ppf(0.841344746) - 1.0) < 0.001


# ── RiskMetrics ─────────────────────────────────────────────────────── #


class TestRiskMetrics:

    def test_frozen(self) -> None:
        m = RiskMetrics(var_95=-0.01, var_99=-0.02, cvar_95=-0.015, tail_index=0.3, method="historical")
        with pytest.raises(AttributeError):
            m.var_95 = -0.02  # type: ignore[misc]

    def test_all_fields(self) -> None:
        m = RiskMetrics(var_95=-0.0123, var_99=-0.0256, cvar_95=-0.0189, tail_index=0.45, method="parametric")
        assert m.var_95 == -0.0123
        assert m.var_99 == -0.0256
        assert m.cvar_95 == -0.0189
        assert m.tail_index == 0.45
        assert m.method == "parametric"

    def test_to_dict(self) -> None:
        m = RiskMetrics(var_95=-0.01, var_99=-0.02, cvar_95=-0.015, tail_index=None, method="historical")
        d = m.to_dict()
        assert d["var_95"] == -0.01
        assert d["tail_index"] is None

    def test_tail_index_none(self) -> None:
        m = RiskMetrics(var_95=0.0, var_99=0.0, cvar_95=0.0, tail_index=None, method="historical")
        assert m.tail_index is None


# ── compute_var ─────────────────────────────────────────────────────── #


class TestComputeVar:

    def test_historical_normal(self) -> None:
        r = _normal_returns()
        var = compute_var(r, 0.95, "historical")
        assert var < 0.0
        assert var > -0.05

    def test_parametric_normal(self) -> None:
        r = _normal_returns()
        var = compute_var(r, 0.95, "parametric")
        assert var < 0.0
        assert var > -0.05

    def test_historical_known(self) -> None:
        r = np.array([-0.03, -0.02, -0.01, 0.0, 0.01, 0.02, 0.03])
        var = compute_var(r, 0.90, "historical")
        expected = round(float(np.percentile(r, 10.0)), 6)
        assert var == expected

    def test_parametric_sigma_zero(self) -> None:
        r = np.ones(10) * 0.01
        var = compute_var(r, 0.95, "parametric")
        assert var == 0.01

    def test_empty_returns(self) -> None:
        var = compute_var(np.array([]), 0.95, "historical")
        assert var == 0.0

    def test_constant_returns_historical(self) -> None:
        r = np.array([0.005] * 50)
        var = compute_var(r, 0.95, "historical")
        assert var == 0.005

    def test_invalid_method(self) -> None:
        with pytest.raises(ValueError, match="Unknown method"):
            compute_var(np.array([1.0]), 0.95, "unknown")

    def test_invalid_confidence(self) -> None:
        with pytest.raises(ValueError, match="confidence"):
            compute_var(np.array([1.0]), 1.0, "historical")


# ── compute_cvar ────────────────────────────────────────────────────── #


class TestComputeCvar:

    def test_historical(self) -> None:
        r = _normal_returns()
        cvar = compute_cvar(r, 0.95, "historical")
        var = compute_var(r, 0.95, "historical")
        assert cvar <= var

    def test_parametric(self) -> None:
        r = _normal_returns()
        cvar = compute_cvar(r, 0.95, "parametric")
        var = compute_var(r, 0.95, "parametric")
        assert cvar <= var

    def test_empty_returns(self) -> None:
        cvar = compute_cvar(np.array([]), 0.95, "historical")
        assert cvar == 0.0

    def test_constant_returns(self) -> None:
        r = np.array([0.005] * 50)
        cvar = compute_cvar(r, 0.95, "historical")
        assert cvar == 0.005

    def test_cvar_stricter_than_var_historical(self) -> None:
        r = np.array([-0.10, -0.08, -0.05, -0.01, 0.0, 0.01, 0.02])
        var = compute_var(r, 0.90, "historical")
        cvar = compute_cvar(r, 0.90, "historical")
        assert cvar <= var

    def test_invalid_method(self) -> None:
        with pytest.raises(ValueError, match="Unknown method"):
            compute_cvar(np.array([1.0]), 0.95, "unknown")

    def test_invalid_confidence(self) -> None:
        with pytest.raises(ValueError, match="confidence"):
            compute_cvar(np.array([1.0]), 0.0, "historical")


# ── TailRiskDetector ────────────────────────────────────────────────── #


class TestTailRiskDetector:

    def test_normal_no_tail(self) -> None:
        r = _normal_returns()
        d = TailRiskDetector().detect(r, threshold_percentile=90.0)
        assert d["tail_index"] is not None
        assert d["tail_index"] < 0.5
        assert d["has_tail_risk"] is False

    def test_heavy_tails_detected(self) -> None:
        r = _t_returns(2000, df=2.0)
        d = TailRiskDetector().detect(r, threshold_percentile=95.0)
        if d["tail_index"] is not None:
            assert d["tail_index"] > 0.0

    def test_insufficient_data(self) -> None:
        r = np.array([-0.01, -0.02, -0.03])
        d = TailRiskDetector().detect(r, threshold_percentile=90.0, min_exceedances=5)
        assert d["tail_index"] is None
        assert d["has_tail_risk"] is False
        assert "Insufficient" in d["note"]

    def test_empty_data(self) -> None:
        d = TailRiskDetector().detect(np.array([]))
        assert d["tail_index"] is None
        assert d["n_exceedances"] == 0
        assert d["has_tail_risk"] is False

    def test_all_same(self) -> None:
        r = np.ones(100) * 0.01
        d = TailRiskDetector().detect(r, threshold_percentile=90.0)
        assert d["tail_index"] == 0.0
        assert d["has_tail_risk"] is False

    def test_right_tail(self) -> None:
        rng = np.random.default_rng(_SEED)
        r = rng.normal(loc=0.0, scale=0.01, size=1000)
        d_left = TailRiskDetector().detect(r, tail="left")
        d_right = TailRiskDetector().detect(r, tail="right")
        assert isinstance(d_left["tail_index"], float)
        assert isinstance(d_right["tail_index"], float)

    def test_invalid_tail_param(self) -> None:
        with pytest.raises(ValueError, match="tail must be"):
            TailRiskDetector().detect(np.array([1.0]), tail="middle")

    def test_invalid_threshold(self) -> None:
        with pytest.raises(ValueError, match="threshold_percentile must be"):
            TailRiskDetector().detect(np.array([1.0]), threshold_percentile=100.0)

    def test_invalid_min_exceedances(self) -> None:
        with pytest.raises(ValueError, match="min_exceedances must be"):
            TailRiskDetector().detect(np.array([1.0]), min_exceedances=0)

    def test_threshold_sensitivity(self) -> None:
        r = _t_returns(2000, df=2.0)
        d90 = TailRiskDetector().detect(r, threshold_percentile=90.0)
        d95 = TailRiskDetector().detect(r, threshold_percentile=95.0)
        assert d90["n_exceedances"] >= d95["n_exceedances"]

    def test_return_structure(self) -> None:
        r = _normal_returns()
        d = TailRiskDetector().detect(r)
        assert set(d.keys()) == {"tail_index", "threshold", "n_exceedances", "has_tail_risk", "note"}


# ── Determinism ─────────────────────────────────────────────────────── #


class TestDeterminism:

    def test_var_deterministic(self) -> None:
        r = np.array([-0.05, -0.03, -0.01, 0.0, 0.02, 0.04])
        v1 = compute_var(r, 0.95, "historical")
        v2 = compute_var(r, 0.95, "historical")
        assert v1 == v2

    def test_cvar_deterministic(self) -> None:
        r = np.array([-0.05, -0.03, -0.01, 0.0, 0.02, 0.04])
        c1 = compute_cvar(r, 0.95, "historical")
        c2 = compute_cvar(r, 0.95, "historical")
        assert c1 == c2

    def test_tail_detector_deterministic(self) -> None:
        r = _normal_returns()
        d = TailRiskDetector()
        r1 = d.detect(r)
        r2 = d.detect(r)
        assert r1["tail_index"] == r2["tail_index"]
        assert r1["has_tail_risk"] == r2["has_tail_risk"]

    def test_parametric_deterministic(self) -> None:
        r = np.array([-0.01, 0.0, 0.01, -0.02, 0.02])
        p1 = compute_var(r, 0.95, "parametric")
        p2 = compute_var(r, 0.95, "parametric")
        assert p1 == p2
