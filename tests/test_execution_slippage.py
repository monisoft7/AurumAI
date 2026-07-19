from __future__ import annotations

import pytest

from execution.slippage import (
    FixedSlippageModel,
    PercentageSlippageModel,
    SlippageResult,
)


class TestSlippageResult:
    def test_construction(self) -> None:
        r = SlippageResult(executed_price=100.0, slippage_amount=5.0, slippage_bps=50.0)
        assert r.executed_price == 100.0
        assert r.slippage_amount == 5.0
        assert r.slippage_bps == 50.0

    def test_frozen(self) -> None:
        r = SlippageResult(executed_price=100.0, slippage_amount=5.0, slippage_bps=50.0)
        with pytest.raises(AttributeError):
            r.executed_price = 99.0  # type: ignore[misc]

    def test_to_dict(self) -> None:
        r = SlippageResult(executed_price=100.0, slippage_amount=5.0, slippage_bps=50.0)
        d = r.to_dict()
        assert d["executed_price"] == 100.0
        assert d["slippage_amount"] == 5.0
        assert d["slippage_bps"] == 50.0


class TestFixedSlippageModelConstruction:
    def test_default_constructor(self) -> None:
        m = FixedSlippageModel()
        assert m.slippage_per_unit == 0.01

    def test_custom_slippage(self) -> None:
        m = FixedSlippageModel(0.05)
        assert m.slippage_per_unit == 0.05

    def test_zero_slippage(self) -> None:
        m = FixedSlippageModel(0.0)
        assert m.slippage_per_unit == 0.0

    def test_negative_slippage_raises(self) -> None:
        with pytest.raises(ValueError, match="slippage_per_unit must be non-negative"):
            FixedSlippageModel(-0.01)


class TestFixedSlippageModelApply:
    def test_buy_long(self) -> None:
        m = FixedSlippageModel(0.05)
        r = m.apply(price=100.0, quantity=10.0)
        assert r.executed_price == 100.05
        assert r.slippage_amount == 0.50

    def test_sell_long(self) -> None:
        m = FixedSlippageModel(0.05)
        r = m.apply(price=100.0, quantity=-10.0)
        assert r.executed_price == 99.95
        assert r.slippage_amount == 0.50

    def test_zero_quantity(self) -> None:
        m = FixedSlippageModel(0.05)
        r = m.apply(price=100.0, quantity=0.0)
        assert r.executed_price == 100.05
        assert r.slippage_amount == 0.0

    def test_slippage_bps_calculation(self) -> None:
        m = FixedSlippageModel(0.01)
        r = m.apply(price=100.0, quantity=10.0)
        assert r.slippage_bps == 1.0

    def test_slippage_bps_zero_price(self) -> None:
        m = FixedSlippageModel(0.01)
        r = m.apply(price=0.0, quantity=10.0)
        assert r.slippage_bps == 0.0

    def test_zero_slippage(self) -> None:
        m = FixedSlippageModel(0.0)
        r = m.apply(price=100.0, quantity=10.0)
        assert r.executed_price == 100.0
        assert r.slippage_amount == 0.0
        assert r.slippage_bps == 0.0

    def test_deterministic(self) -> None:
        m = FixedSlippageModel(0.05)
        r1 = m.apply(price=100.0, quantity=10.0)
        r2 = m.apply(price=100.0, quantity=10.0)
        assert r1 == r2

    def test_pure_function_no_side_effects(self) -> None:
        m = FixedSlippageModel(0.05)
        _ = m.apply(price=100.0, quantity=10.0)
        r2 = m.apply(price=100.0, quantity=10.0)
        assert r2.executed_price == 100.05


class TestFixedSlippageModelSerialization:
    def test_to_dict(self) -> None:
        m = FixedSlippageModel(0.05)
        d = m.to_dict()
        assert d["type"] == "fixed"
        assert d["slippage_per_unit"] == 0.05


class TestPercentageSlippageModelConstruction:
    def test_default_constructor(self) -> None:
        m = PercentageSlippageModel()
        assert m.slippage_pct == 0.001

    def test_custom_slippage(self) -> None:
        m = PercentageSlippageModel(0.005)
        assert m.slippage_pct == 0.005

    def test_zero_slippage(self) -> None:
        m = PercentageSlippageModel(0.0)
        assert m.slippage_pct == 0.0

    def test_negative_slippage_raises(self) -> None:
        with pytest.raises(ValueError, match="slippage_pct must be non-negative"):
            PercentageSlippageModel(-0.001)


class TestPercentageSlippageModelApply:
    def test_buy_long(self) -> None:
        m = PercentageSlippageModel(0.001)
        r = m.apply(price=100.0, quantity=10.0)
        assert r.executed_price == 100.10
        assert r.slippage_amount == 1.0

    def test_sell_long(self) -> None:
        m = PercentageSlippageModel(0.001)
        r = m.apply(price=100.0, quantity=-10.0)
        assert r.executed_price == 99.90
        assert r.slippage_amount == 1.0

    def test_zero_quantity(self) -> None:
        m = PercentageSlippageModel(0.001)
        r = m.apply(price=100.0, quantity=0.0)
        assert r.executed_price == 100.10
        assert r.slippage_amount == 0.0

    def test_slippage_bps(self) -> None:
        m = PercentageSlippageModel(0.001)
        r = m.apply(price=100.0, quantity=10.0)
        assert r.slippage_bps == 10.0

    def test_zero_slippage(self) -> None:
        m = PercentageSlippageModel(0.0)
        r = m.apply(price=100.0, quantity=10.0)
        assert r.executed_price == 100.0
        assert r.slippage_amount == 0.0
        assert r.slippage_bps == 0.0

    def test_high_price(self) -> None:
        m = PercentageSlippageModel(0.001)
        r = m.apply(price=2000.0, quantity=5.0)
        assert abs(r.executed_price - 2002.0) < 1e-9
        assert r.slippage_amount == 10.0

    def test_deterministic(self) -> None:
        m = PercentageSlippageModel(0.001)
        r1 = m.apply(price=100.0, quantity=10.0)
        r2 = m.apply(price=100.0, quantity=10.0)
        assert r1 == r2


class TestPercentageSlippageModelSerialization:
    def test_to_dict(self) -> None:
        m = PercentageSlippageModel(0.005)
        d = m.to_dict()
        assert d["type"] == "percentage"
        assert d["slippage_pct"] == 0.005


class TestSlippageEdgeCases:
    def test_fixed_negative_quantity(self) -> None:
        m = FixedSlippageModel(0.05)
        r = m.apply(price=100.0, quantity=-5.0)
        assert r.executed_price == 99.95
        assert r.slippage_amount == 0.25

    def test_percentage_negative_quantity(self) -> None:
        m = PercentageSlippageModel(0.01)
        r = m.apply(price=100.0, quantity=-5.0)
        assert r.executed_price == 99.0
        assert r.slippage_amount == 5.0

    def test_large_quantity_fixed(self) -> None:
        m = FixedSlippageModel(0.01)
        r = m.apply(price=100.0, quantity=1_000.0)
        assert r.slippage_amount == 10.0

    def test_large_quantity_percentage(self) -> None:
        m = PercentageSlippageModel(0.001)
        r = m.apply(price=100.0, quantity=1_000.0)
        assert r.slippage_amount == 100.0
