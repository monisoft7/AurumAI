from __future__ import annotations

import pytest

from execution.commission import (
    CommissionResult,
    FixedCommissionModel,
    PercentageCommissionModel,
)


class TestCommissionResult:
    def test_construction(self) -> None:
        r = CommissionResult(commission=5.0, commission_per_unit=0.50)
        assert r.commission == 5.0
        assert r.commission_per_unit == 0.50

    def test_frozen(self) -> None:
        r = CommissionResult(commission=5.0, commission_per_unit=0.50)
        with pytest.raises(AttributeError):
            r.commission = 4.0  # type: ignore[misc]

    def test_to_dict(self) -> None:
        r = CommissionResult(commission=5.0, commission_per_unit=0.50)
        d = r.to_dict()
        assert d["commission"] == 5.0
        assert d["commission_per_unit"] == 0.50


class TestFixedCommissionModelConstruction:
    def test_default_constructor(self) -> None:
        m = FixedCommissionModel()
        assert m.commission_per_trade == 0.0

    def test_custom_commission(self) -> None:
        m = FixedCommissionModel(10.0)
        assert m.commission_per_trade == 10.0

    def test_negative_commission_raises(self) -> None:
        with pytest.raises(ValueError, match="commission_per_trade must be non-negative"):
            FixedCommissionModel(-5.0)


class TestFixedCommissionModelApply:
    def test_fixed_commission_applied(self) -> None:
        m = FixedCommissionModel(10.0)
        r = m.apply(price=100.0, quantity=5.0)
        assert r.commission == 10.0
        assert r.commission_per_unit == 2.0

    def test_zero_commission(self) -> None:
        m = FixedCommissionModel(0.0)
        r = m.apply(price=100.0, quantity=5.0)
        assert r.commission == 0.0
        assert r.commission_per_unit == 0.0

    def test_zero_quantity_returns_zero(self) -> None:
        m = FixedCommissionModel(10.0)
        r = m.apply(price=100.0, quantity=0.0)
        assert r.commission == 0.0
        assert r.commission_per_unit == 0.0

    def test_deterministic(self) -> None:
        m = FixedCommissionModel(10.0)
        r1 = m.apply(price=100.0, quantity=5.0)
        r2 = m.apply(price=100.0, quantity=5.0)
        assert r1 == r2

    def test_commission_independent_of_price(self) -> None:
        m = FixedCommissionModel(10.0)
        r1 = m.apply(price=100.0, quantity=5.0)
        r2 = m.apply(price=200.0, quantity=5.0)
        assert r1.commission == r2.commission

    def test_negative_quantity(self) -> None:
        m = FixedCommissionModel(10.0)
        r = m.apply(price=100.0, quantity=-5.0)
        assert r.commission == 10.0
        assert r.commission_per_unit == 2.0

    def test_large_quantity(self) -> None:
        m = FixedCommissionModel(10.0)
        r = m.apply(price=100.0, quantity=1_000.0)
        assert r.commission == 10.0
        assert r.commission_per_unit == 0.01


class TestFixedCommissionModelSerialization:
    def test_to_dict(self) -> None:
        m = FixedCommissionModel(10.0)
        d = m.to_dict()
        assert d["type"] == "fixed"
        assert d["commission_per_trade"] == 10.0


class TestPercentageCommissionModelConstruction:
    def test_default_constructor(self) -> None:
        m = PercentageCommissionModel()
        assert m.commission_pct == 0.001
        assert m.min_commission is None

    def test_custom_pct(self) -> None:
        m = PercentageCommissionModel(0.005)
        assert m.commission_pct == 0.005

    def test_with_min_commission(self) -> None:
        m = PercentageCommissionModel(0.001, min_commission=1.0)
        assert m.commission_pct == 0.001
        assert m.min_commission == 1.0

    def test_zero_pct(self) -> None:
        m = PercentageCommissionModel(0.0)
        assert m.commission_pct == 0.0

    def test_negative_pct_raises(self) -> None:
        with pytest.raises(ValueError, match="commission_pct must be non-negative"):
            PercentageCommissionModel(-0.001)

    def test_negative_min_commission_raises(self) -> None:
        with pytest.raises(ValueError, match="min_commission must be non-negative"):
            PercentageCommissionModel(0.001, min_commission=-1.0)


class TestPercentageCommissionModelApply:
    def test_commission_calculated(self) -> None:
        m = PercentageCommissionModel(0.001)
        r = m.apply(price=100.0, quantity=10.0)
        assert r.commission == 1.0
        assert r.commission_per_unit == 0.10

    def test_commission_large_trade(self) -> None:
        m = PercentageCommissionModel(0.001)
        r = m.apply(price=2000.0, quantity=100.0)
        assert r.commission == 200.0
        assert r.commission_per_unit == 2.0

    def test_zero_pct(self) -> None:
        m = PercentageCommissionModel(0.0)
        r = m.apply(price=100.0, quantity=10.0)
        assert r.commission == 0.0
        assert r.commission_per_unit == 0.0

    def test_zero_quantity(self) -> None:
        m = PercentageCommissionModel(0.001)
        r = m.apply(price=100.0, quantity=0.0)
        assert r.commission == 0.0
        assert r.commission_per_unit == 0.0

    def test_min_commission_applied(self) -> None:
        m = PercentageCommissionModel(0.001, min_commission=5.0)
        r = m.apply(price=100.0, quantity=10.0)
        assert r.commission == 5.0

    def test_min_commission_not_applied_when_exceeded(self) -> None:
        m = PercentageCommissionModel(0.001, min_commission=5.0)
        r = m.apply(price=2000.0, quantity=10.0)
        assert r.commission == 20.0

    def test_min_commission_exact_boundary(self) -> None:
        m = PercentageCommissionModel(0.001, min_commission=1.0)
        r = m.apply(price=100.0, quantity=10.0)
        assert r.commission == 1.0

    def test_deterministic(self) -> None:
        m = PercentageCommissionModel(0.001, min_commission=5.0)
        r1 = m.apply(price=100.0, quantity=10.0)
        r2 = m.apply(price=100.0, quantity=10.0)
        assert r1 == r2

    def test_negative_quantity(self) -> None:
        m = PercentageCommissionModel(0.001)
        r = m.apply(price=100.0, quantity=-10.0)
        assert r.commission == 1.0
        assert r.commission_per_unit == 0.10


class TestPercentageCommissionModelSerialization:
    def test_to_dict_no_min(self) -> None:
        m = PercentageCommissionModel(0.005)
        d = m.to_dict()
        assert d["type"] == "percentage"
        assert d["commission_pct"] == 0.005
        assert "min_commission" not in d

    def test_to_dict_with_min(self) -> None:
        m = PercentageCommissionModel(0.005, min_commission=2.0)
        d = m.to_dict()
        assert d["type"] == "percentage"
        assert d["commission_pct"] == 0.005
        assert d["min_commission"] == 2.0


class TestCommissionEdgeCases:
    def test_fixed_large_commission(self) -> None:
        m = FixedCommissionModel(1_000.0)
        r = m.apply(price=100.0, quantity=1.0)
        assert r.commission == 1_000.0
        assert r.commission_per_unit == 1_000.0

    def test_percentage_min_commission_zero(self) -> None:
        m = PercentageCommissionModel(0.001, min_commission=0.0)
        r = m.apply(price=100.0, quantity=1.0)
        assert r.commission == 0.10

    def test_percentage_very_small_pct(self) -> None:
        m = PercentageCommissionModel(1e-6)
        r = m.apply(price=1_000_000.0, quantity=1.0)
        assert r.commission == 1.0
