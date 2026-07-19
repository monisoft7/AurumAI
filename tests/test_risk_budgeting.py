from __future__ import annotations

import numpy as np
import pytest

from forecasting.risk_budgeting import RiskBudget, RiskParitySizer


class TestRiskBudget:

    def test_frozen(self) -> None:
        b = RiskBudget(weights=(0.5, 0.5), risk_contributions=(0.5, 0.5), method="risk_parity")
        with pytest.raises(AttributeError):
            b.weights = (0.6, 0.4)  # type: ignore[misc]

    def test_all_fields(self) -> None:
        b = RiskBudget(weights=(0.3, 0.7), risk_contributions=(0.4, 0.6), method="risk_parity")
        assert b.weights == (0.3, 0.7)
        assert b.method == "risk_parity"

    def test_to_dict(self) -> None:
        b = RiskBudget(weights=(1.0,), risk_contributions=(1.0,), method="equal_weight")
        d = b.to_dict()
        assert d["method"] == "equal_weight"
        assert d["weights"] == [1.0]


class TestRiskParitySizer:

    def test_equal_correlation_equal_weights(self) -> None:
        cov = np.array([[1.0, 0.5], [0.5, 1.0]])
        b = RiskParitySizer().compute(cov)
        assert abs(b.weights[0] - b.weights[1]) < 0.01

    def test_different_variances(self) -> None:
        cov = np.array([[1.0, 0.0], [0.0, 4.0]])
        b = RiskParitySizer().compute(cov)
        assert b.weights[0] > b.weights[1]
        assert abs(b.weights[0] - 2.0 / 3.0) < 0.01

    def test_different_variances_with_corr(self) -> None:
        cov = np.array([[1.0, 0.5], [0.5, 4.0]])
        b = RiskParitySizer().compute(cov)
        assert b.weights[0] > b.weights[1]

    def test_three_assets_equal_corr(self) -> None:
        cov = np.array([[1.0, 0.3, 0.3], [0.3, 1.0, 0.3], [0.3, 0.3, 1.0]])
        b = RiskParitySizer().compute(cov)
        for w in b.weights:
            assert abs(w - 1.0 / 3.0) < 0.05

    def test_single_asset(self) -> None:
        cov = np.array([[1.0]])
        b = RiskParitySizer().compute(cov)
        assert b.weights == (1.0,)

    def test_invalid_cov_not_square(self) -> None:
        cov = np.array([[1.0, 2.0]])
        with pytest.raises(ValueError, match="square matrix"):
            RiskParitySizer().compute(cov)

    def test_invalid_cov_empty(self) -> None:
        cov = np.empty((0, 0))
        with pytest.raises(ValueError, match="cov cannot be empty"):
            RiskParitySizer().compute(cov)

    def test_invalid_max_iter(self) -> None:
        with pytest.raises(ValueError, match="max_iter"):
            RiskParitySizer().compute(np.array([[1.0]]), max_iter=0)

    def test_invalid_tol(self) -> None:
        with pytest.raises(ValueError, match="tol"):
            RiskParitySizer().compute(np.array([[1.0]]), tol=0.0)

    def test_risk_contributions_sum_to_one(self) -> None:
        cov = np.array([[1.0, 0.5, 0.2], [0.5, 2.0, 0.3], [0.2, 0.3, 3.0]])
        b = RiskParitySizer().compute(cov)
        assert abs(sum(b.risk_contributions) - 1.0) < 0.01

    def test_weights_sum_to_one(self) -> None:
        cov = np.array([[1.0, 0.5], [0.5, 1.0]])
        b = RiskParitySizer().compute(cov)
        assert abs(sum(b.weights) - 1.0) < 1e-6

    def test_deterministic(self) -> None:
        cov = np.array([[1.0, 0.5], [0.5, 2.0]])
        sizer = RiskParitySizer()
        b1 = sizer.compute(cov)
        b2 = sizer.compute(cov)
        assert b1.weights == b2.weights
        assert b1.risk_contributions == b2.risk_contributions
