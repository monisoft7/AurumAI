from __future__ import annotations

import pytest

from execution.models import PortfolioSnapshot, VirtualPosition, VirtualTrade
from execution.portfolio import VirtualPortfolio


# ═════════════════════════════════════════════════════════════════════════════
# 1. Model construction and serialization
# ═════════════════════════════════════════════════════════════════════════════

class TestVirtualPosition:
    def test_construction(self) -> None:
        p = VirtualPosition("XAU/USD", 10.0, 1950.0, 2000.0)
        assert p.asset_id == "XAU/USD"
        assert p.quantity == 10.0
        assert p.cost_basis == 1950.0
        assert p.current_price == 2000.0

    def test_unrealized_pnl_long(self) -> None:
        p = VirtualPosition("XAU/USD", 10.0, 1950.0, 2000.0)
        assert p.unrealized_pnl == 500.0  # (2000-1950) * 10

    def test_unrealized_pnl_short(self) -> None:
        p = VirtualPosition("XAU/USD", -10.0, 2000.0, 1950.0)
        assert p.unrealized_pnl == 500.0  # (1950-2000) * -10

    def test_unrealized_pnl_loss(self) -> None:
        p = VirtualPosition("XAU/USD", 10.0, 2000.0, 1950.0)
        assert p.unrealized_pnl == -500.0

    def test_market_value_long(self) -> None:
        p = VirtualPosition("XAU/USD", 10.0, 1950.0, 2000.0)
        assert p.market_value == 20_000.0

    def test_market_value_short(self) -> None:
        p = VirtualPosition("XAU/USD", -10.0, 2000.0, 1950.0)
        assert p.market_value == -19_500.0

    def test_to_dict(self) -> None:
        p = VirtualPosition("XAU/USD", 10.0, 1950.0, 2000.0)
        d = p.to_dict()
        assert d["asset_id"] == "XAU/USD"
        assert d["quantity"] == 10.0
        assert d["unrealized_pnl"] == 500.0
        assert d["market_value"] == 20_000.0

    def test_frozen(self) -> None:
        p = VirtualPosition("XAU/USD", 10.0, 1950.0, 2000.0)
        with pytest.raises(AttributeError):
            p.quantity = 20.0  # type: ignore[misc]


class TestVirtualTrade:
    def test_construction(self) -> None:
        t = VirtualTrade("T000001", "XAU/USD", "BUY", 10.0, 1950.0, "2026-01-01T00:00:00")
        assert t.trade_id == "T000001"
        assert t.action == "BUY"
        assert t.quantity == 10.0
        assert t.price == 1950.0
        assert t.realized_pnl is None

    def test_with_realized_pnl(self) -> None:
        t = VirtualTrade("T000001", "XAU/USD", "SELL", 5.0, 2000.0, "2026-01-01T00:00:00", realized_pnl=250.0)
        assert t.realized_pnl == 250.0

    def test_to_dict_no_realized(self) -> None:
        t = VirtualTrade("T000001", "XAU/USD", "BUY", 10.0, 1950.0, "2026-01-01T00:00:00")
        d = t.to_dict()
        assert "realized_pnl" not in d

    def test_to_dict_with_realized(self) -> None:
        t = VirtualTrade("T000001", "XAU/USD", "SELL", 5.0, 2000.0, "2026-01-01T00:00:00", realized_pnl=250.0)
        d = t.to_dict()
        assert d["realized_pnl"] == 250.0

    def test_frozen(self) -> None:
        t = VirtualTrade("T000001", "XAU/USD", "BUY", 10.0, 1950.0, "2026-01-01T00:00:00")
        with pytest.raises(AttributeError):
            t.quantity = 20.0  # type: ignore[misc]


class TestPortfolioSnapshot:
    def test_construction(self) -> None:
        s = PortfolioSnapshot("2026-01-01T00:00:00", 80_000.0, 100_000.0, 500.0, 250.0)
        assert s.cash == 80_000.0
        assert s.equity == 100_000.0
        assert s.unrealized_pnl == 500.0
        assert s.realized_pnl == 250.0

    def test_with_positions(self) -> None:
        pos = (VirtualPosition("XAU/USD", 10.0, 1950.0, 2000.0),)
        s = PortfolioSnapshot("2026-01-01T00:00:00", 80_000.0, 100_000.0, 500.0, 250.0, positions=pos)
        assert len(s.positions) == 1
        assert s.positions[0].asset_id == "XAU/USD"

    def test_to_dict(self) -> None:
        s = PortfolioSnapshot("2026-01-01T00:00:00", 80_000.0, 100_000.0, 500.0, 250.0)
        d = s.to_dict()
        assert d["cash"] == 80_000.0
        assert d["equity"] == 100_000.0


# ═════════════════════════════════════════════════════════════════════════════
# 2. VirtualPortfolio — construction and initial state
# ═════════════════════════════════════════════════════════════════════════════

class TestVirtualPortfolioConstruction:
    def test_default_initial_capital(self) -> None:
        p = VirtualPortfolio()
        assert p.initial_capital == 100_000.0
        assert p.cash == 100_000.0
        assert p.equity == 100_000.0
        assert p.unrealized_pnl == 0.0
        assert p.realized_pnl == 0.0
        assert p.total_pnl == 0.0
        assert p.positions == ()
        assert p.trades == ()
        assert p.snapshots == ()

    def test_custom_initial_capital(self) -> None:
        p = VirtualPortfolio(50_000.0)
        assert p.initial_capital == 50_000.0
        assert p.cash == 50_000.0

    def test_negative_capital_raises(self) -> None:
        with pytest.raises(ValueError, match="non-negative"):
            VirtualPortfolio(-1000.0)

    def test_zero_capital(self) -> None:
        p = VirtualPortfolio(0.0)
        assert p.cash == 0.0
        assert p.equity == 0.0


# ═════════════════════════════════════════════════════════════════════════════
# 3. VirtualPortfolio — buy operations
# ═════════════════════════════════════════════════════════════════════════════

class TestBuy:
    def test_buy_opens_long_position(self) -> None:
        p = VirtualPortfolio(100_000.0)
        trade = p.buy("XAU/USD", 10.0, 1950.0, "2026-01-01T00:00:00")
        assert trade.action == "BUY"
        assert trade.quantity == 10.0
        assert trade.realized_pnl is None
        assert p.cash == 100_000.0 - 19_500.0
        assert len(p.positions) == 1
        assert p.positions[0].quantity == 10.0
        assert p.positions[0].cost_basis == 1950.0
        assert p.positions[0].current_price == 1950.0

    def test_buy_adds_to_existing_long(self) -> None:
        p = VirtualPortfolio(100_000.0)
        p.buy("XAU/USD", 5.0, 1900.0, "2026-01-01T00:00:00")
        p.buy("XAU/USD", 5.0, 2000.0, "2026-01-01T00:00:00")
        assert p.cash == 100_000.0 - 5 * 1900 - 5 * 2000
        assert p.positions[0].quantity == 10.0
        assert p.positions[0].cost_basis == (5 * 1900 + 5 * 2000) / 10

    def test_buy_insufficient_cash_raises(self) -> None:
        p = VirtualPortfolio(10_000.0)
        with pytest.raises(ValueError, match="Insufficient cash"):
            p.buy("XAU/USD", 10.0, 1950.0, "2026-01-01T00:00:00")
        assert p.cash == 10_000.0
        assert p.positions == ()

    def test_buy_zero_quantity_raises(self) -> None:
        p = VirtualPortfolio(100_000.0)
        with pytest.raises(ValueError, match="quantity must be positive"):
            p.buy("XAU/USD", 0.0, 1950.0, "2026-01-01T00:00:00")

    def test_buy_negative_quantity_raises(self) -> None:
        p = VirtualPortfolio(100_000.0)
        with pytest.raises(ValueError, match="quantity must be positive"):
            p.buy("XAU/USD", -5.0, 1950.0, "2026-01-01T00:00:00")

    def test_buy_multiple_assets(self) -> None:
        p = VirtualPortfolio(200_000.0)
        p.buy("XAU/USD", 10.0, 1950.0, "2026-01-01T00:00:00")
        p.buy("BTC/USD", 1.0, 60_000.0, "2026-01-01T00:00:00")
        assert len(p.positions) == 2
        assert p.cash == 200_000.0 - 19_500.0 - 60_000.0


# ═════════════════════════════════════════════════════════════════════════════
# 4. VirtualPortfolio — sell operations
# ═════════════════════════════════════════════════════════════════════════════

class TestSell:
    def test_sell_reduces_long_position(self) -> None:
        p = VirtualPortfolio(100_000.0)
        p.buy("XAU/USD", 10.0, 1950.0, "2026-01-01T00:00:00")
        trade = p.sell("XAU/USD", 4.0, 2000.0, "2026-01-01T01:00:00")
        assert trade.action == "SELL"
        assert trade.quantity == 4.0
        assert trade.realized_pnl == pytest.approx(4.0 * (2000.0 - 1950.0))
        assert p.positions[0].quantity == 6.0
        assert p.cash == pytest.approx(100_000.0 - 10 * 1950.0 + 4 * 2000.0)

    def test_sell_fully_closes_position(self) -> None:
        p = VirtualPortfolio(100_000.0)
        p.buy("XAU/USD", 10.0, 1950.0, "2026-01-01T00:00:00")
        p.sell("XAU/USD", 10.0, 2000.0, "2026-01-01T01:00:00")
        assert p.positions == ()
        assert p.realized_pnl == 10.0 * (2000.0 - 1950.0)
        assert len(p.closed_positions) == 1

    def test_sell_without_position_raises(self) -> None:
        p = VirtualPortfolio(100_000.0)
        with pytest.raises(ValueError, match="[Nn]o long position"):
            p.sell("XAU/USD", 5.0, 2000.0, "2026-01-01T00:00:00")

    def test_sell_excessive_quantity_raises(self) -> None:
        p = VirtualPortfolio(100_000.0)
        p.buy("XAU/USD", 5.0, 1950.0, "2026-01-01T00:00:00")
        with pytest.raises(ValueError, match="only 5"):
            p.sell("XAU/USD", 10.0, 2000.0, "2026-01-01T01:00:00")

    def test_sell_loss_realized(self) -> None:
        p = VirtualPortfolio(100_000.0)
        p.buy("XAU/USD", 10.0, 2000.0, "2026-01-01T00:00:00")
        p.sell("XAU/USD", 5.0, 1950.0, "2026-01-01T01:00:00")
        assert p.realized_pnl == 5.0 * (1950.0 - 2000.0)


# ═════════════════════════════════════════════════════════════════════════════
# 5. VirtualPortfolio — short operations
# ═════════════════════════════════════════════════════════════════════════════

class TestShort:
    def test_short_opens_short_position(self) -> None:
        p = VirtualPortfolio(100_000.0)
        trade = p.short("XAU/USD", 10.0, 2000.0, "2026-01-01T00:00:00")
        assert trade.action == "SHORT"
        assert trade.realized_pnl is None
        assert p.cash == 100_000.0 + 20_000.0
        assert p.positions[0].quantity == -10.0
        assert p.positions[0].cost_basis == 2000.0

    def test_short_adds_to_existing_short(self) -> None:
        p = VirtualPortfolio(100_000.0)
        p.short("XAU/USD", 5.0, 2000.0, "2026-01-01T00:00:00")
        p.short("XAU/USD", 5.0, 1900.0, "2026-01-01T01:00:00")
        assert p.positions[0].quantity == -10.0
        avg_price = (5 * 2000 + 5 * 1900) / 10
        assert p.positions[0].cost_basis == pytest.approx(avg_price)

    def test_short_while_long_raises(self) -> None:
        p = VirtualPortfolio(100_000.0)
        p.buy("XAU/USD", 10.0, 1950.0, "2026-01-01T00:00:00")
        with pytest.raises(ValueError, match="already have a long"):
            p.short("XAU/USD", 5.0, 2000.0, "2026-01-01T01:00:00")

    def test_short_zero_quantity_raises(self) -> None:
        p = VirtualPortfolio(100_000.0)
        with pytest.raises(ValueError, match="quantity must be positive"):
            p.short("XAU/USD", 0.0, 2000.0, "2026-01-01T00:00:00")


# ═════════════════════════════════════════════════════════════════════════════
# 6. VirtualPortfolio — cover operations
# ═════════════════════════════════════════════════════════════════════════════

class TestCover:
    def test_cover_reduces_short_position(self) -> None:
        p = VirtualPortfolio(100_000.0)
        p.short("XAU/USD", 10.0, 2000.0, "2026-01-01T00:00:00")
        trade = p.cover("XAU/USD", 4.0, 1950.0, "2026-01-01T01:00:00")
        assert trade.action == "COVER"
        assert trade.realized_pnl == pytest.approx(4.0 * (2000.0 - 1950.0))
        assert p.positions[0].quantity == -6.0

    def test_cover_fully_closes_short(self) -> None:
        p = VirtualPortfolio(100_000.0)
        p.short("XAU/USD", 10.0, 2000.0, "2026-01-01T00:00:00")
        p.cover("XAU/USD", 10.0, 1950.0, "2026-01-01T01:00:00")
        assert p.positions == ()
        assert p.realized_pnl == 10.0 * (2000.0 - 1950.0)

    def test_cover_without_short_raises(self) -> None:
        p = VirtualPortfolio(100_000.0)
        with pytest.raises(ValueError, match="[Nn]o short position"):
            p.cover("XAU/USD", 5.0, 1950.0, "2026-01-01T00:00:00")

    def test_cover_from_long_raises(self) -> None:
        p = VirtualPortfolio(100_000.0)
        p.buy("XAU/USD", 10.0, 1950.0, "2026-01-01T00:00:00")
        with pytest.raises(ValueError, match="[Nn]o short position"):
            p.cover("XAU/USD", 5.0, 2000.0, "2026-01-01T01:00:00")

    def test_cover_excessive_quantity_raises(self) -> None:
        p = VirtualPortfolio(100_000.0)
        p.short("XAU/USD", 5.0, 2000.0, "2026-01-01T00:00:00")
        with pytest.raises(ValueError, match="only 5"):
            p.cover("XAU/USD", 10.0, 1950.0, "2026-01-01T01:00:00")

    def test_cover_loss_realized(self) -> None:
        p = VirtualPortfolio(100_000.0)
        p.short("XAU/USD", 10.0, 1900.0, "2026-01-01T00:00:00")
        p.cover("XAU/USD", 5.0, 1950.0, "2026-01-01T01:00:00")
        assert p.realized_pnl == 5.0 * (1900.0 - 1950.0)


# ═════════════════════════════════════════════════════════════════════════════
# 7. VirtualPortfolio — mark-to-market and snapshots
# ═════════════════════════════════════════════════════════════════════════════

class TestMarkToMarket:
    def test_mark_to_market_updates_price(self) -> None:
        p = VirtualPortfolio(100_000.0)
        p.buy("XAU/USD", 10.0, 1950.0, "2026-01-01T00:00:00")
        snapshot = p.mark_to_market("XAU/USD", 2000.0, "2026-01-01T01:00:00")
        assert p.positions[0].current_price == 2000.0
        assert p.unrealized_pnl == 500.0
        assert snapshot.unrealized_pnl == 500.0
        assert snapshot.equity == pytest.approx(100_000.0 - 19_500.0 + 10 * 2000.0)

    def test_mark_to_market_unknown_asset_raises(self) -> None:
        p = VirtualPortfolio(100_000.0)
        with pytest.raises(ValueError, match="[Nn]o open position"):
            p.mark_to_market("XAU/USD", 2000.0, "2026-01-01T00:00:00")

    def test_snapshot_recorded(self) -> None:
        p = VirtualPortfolio(100_000.0)
        p.buy("XAU/USD", 10.0, 1950.0, "2026-01-01T00:00:00")
        p.mark_to_market("XAU/USD", 2000.0, "2026-01-01T01:00:00")
        assert len(p.snapshots) == 1
        assert p.snapshots[0].cash == 100_000.0 - 19_500.0


# ═════════════════════════════════════════════════════════════════════════════
# 8. VirtualPortfolio — equity, PnL calculations
# ═════════════════════════════════════════════════════════════════════════════

class TestEquityAndPnL:
    def test_equity_after_buy(self) -> None:
        p = VirtualPortfolio(100_000.0)
        p.buy("XAU/USD", 10.0, 1950.0, "2026-01-01T00:00:00")
        assert p.equity == pytest.approx(100_000.0)

    def test_equity_increases_with_price(self) -> None:
        p = VirtualPortfolio(100_000.0)
        p.buy("XAU/USD", 10.0, 1950.0, "2026-01-01T00:00:00")
        p.mark_to_market("XAU/USD", 2000.0, "2026-01-01T01:00:00")
        assert p.equity == pytest.approx(100_000.0 + 500.0)
        assert p.total_pnl == 500.0

    def test_equity_decreases_with_price(self) -> None:
        p = VirtualPortfolio(100_000.0)
        p.buy("XAU/USD", 10.0, 1950.0, "2026-01-01T00:00:00")
        p.mark_to_market("XAU/USD", 1900.0, "2026-01-01T01:00:00")
        assert p.equity == pytest.approx(100_000.0 - 500.0)
        assert p.total_pnl == -500.0

    def test_equity_after_full_close(self) -> None:
        p = VirtualPortfolio(100_000.0)
        p.buy("XAU/USD", 10.0, 1950.0, "2026-01-01T00:00:00")
        p.sell("XAU/USD", 10.0, 2000.0, "2026-01-01T01:00:00")
        assert p.equity == pytest.approx(100_000.0 + 500.0)
        assert p.total_pnl == 500.0
        assert p.unrealized_pnl == 0.0
        assert p.realized_pnl == 500.0

    def test_short_equity_increases_when_price_drops(self) -> None:
        p = VirtualPortfolio(100_000.0)
        p.short("XAU/USD", 10.0, 2000.0, "2026-01-01T00:00:00")
        p.mark_to_market("XAU/USD", 1900.0, "2026-01-01T01:00:00")
        assert p.equity == pytest.approx(100_000.0 + 1000.0)
        assert p.total_pnl == 1000.0


# ═════════════════════════════════════════════════════════════════════════════
# 9. VirtualPortfolio — buy to reduce short (assessor closes short via buy)
# ═════════════════════════════════════════════════════════════════════════════

class TestBuyReducesShort:
    def test_buy_reduces_short_no_flip(self) -> None:
        p = VirtualPortfolio(100_000.0)
        p.short("XAU/USD", 10.0, 2000.0, "2026-01-01T00:00:00")
        trade = p.buy("XAU/USD", 4.0, 1950.0, "2026-01-01T01:00:00")
        assert trade.realized_pnl == pytest.approx(4.0 * (2000.0 - 1950.0))
        assert p.positions[0].quantity == -6.0

    def test_buy_closes_short_and_flips_to_long(self) -> None:
        p = VirtualPortfolio(100_000.0)
        p.short("XAU/USD", 5.0, 2000.0, "2026-01-01T00:00:00")
        trade = p.buy("XAU/USD", 8.0, 1950.0, "2026-01-01T01:00:00")
        assert trade.realized_pnl == pytest.approx(5.0 * (2000.0 - 1950.0))
        assert p.positions[0].quantity == 3.0
        assert p.positions[0].cost_basis == 1950.0


# ═════════════════════════════════════════════════════════════════════════════
# 10. VirtualPortfolio — sell to reduce long (assessor reduces via sell)
# ═════════════════════════════════════════════════════════════════════════════

class TestShortReducesLong:
    def test_short_while_long_not_allowed(self) -> None:
        p = VirtualPortfolio(100_000.0)
        p.buy("XAU/USD", 10.0, 1950.0, "2026-01-01T00:00:00")
        with pytest.raises(ValueError, match="already have a long"):
            p.short("XAU/USD", 4.0, 2000.0, "2026-01-01T01:00:00")

    def test_sell_is_used_to_reduce_long(self) -> None:
        p = VirtualPortfolio(100_000.0)
        p.buy("XAU/USD", 10.0, 1950.0, "2026-01-01T00:00:00")
        p.sell("XAU/USD", 4.0, 2000.0, "2026-01-01T01:00:00")
        assert p.positions[0].quantity == 6.0
        assert p.realized_pnl == 4.0 * (2000.0 - 1950.0)


# ═════════════════════════════════════════════════════════════════════════════
# 11. VirtualPortfolio — reset
# ═════════════════════════════════════════════════════════════════════════════

class TestReset:
    def test_reset_clears_everything(self) -> None:
        p = VirtualPortfolio(100_000.0)
        p.buy("XAU/USD", 10.0, 1950.0, "2026-01-01T00:00:00")
        p.mark_to_market("XAU/USD", 2000.0, "2026-01-01T01:00:00")
        p.sell("XAU/USD", 10.0, 2050.0, "2026-01-01T02:00:00")
        p.reset()
        assert p.cash == 100_000.0
        assert p.positions == ()
        assert p.trades == ()
        assert p.snapshots == ()
        assert p.realized_pnl == 0.0
        assert p.unrealized_pnl == 0.0

    def test_reset_allows_reuse(self) -> None:
        p = VirtualPortfolio(100_000.0)
        p.buy("XAU/USD", 10.0, 1950.0, "2026-01-01T00:00:00")
        p.reset()
        p.buy("BTC/USD", 1.0, 60_000.0, "2026-01-01T00:00:00")
        assert p.positions[0].asset_id == "BTC/USD"


# ═════════════════════════════════════════════════════════════════════════════
# 12. VirtualPortfolio — serialization
# ═════════════════════════════════════════════════════════════════════════════

class TestSerialization:
    def test_to_dict_empty_portfolio(self) -> None:
        p = VirtualPortfolio(50_000.0)
        d = p.to_dict()
        assert d["initial_capital"] == 50_000.0
        assert d["cash"] == 50_000.0
        assert d["positions"] == []
        assert d["trades"] == []

    def test_to_dict_after_trades(self) -> None:
        p = VirtualPortfolio(100_000.0)
        p.buy("XAU/USD", 10.0, 1950.0, "2026-01-01T00:00:00")
        p.sell("XAU/USD", 5.0, 2000.0, "2026-01-01T01:00:00")
        d = p.to_dict()
        assert len(d["positions"]) == 1
        assert len(d["closed_positions"]) == 0
        assert len(d["trades"]) == 2
        assert len(d["snapshots"]) == 0
        assert d["realized_pnl"] == pytest.approx(5.0 * 50.0)

    def test_to_dict_after_full_close(self) -> None:
        p = VirtualPortfolio(100_000.0)
        p.buy("XAU/USD", 10.0, 1950.0, "2026-01-01T00:00:00")
        p.sell("XAU/USD", 10.0, 2000.0, "2026-01-01T01:00:00")
        d = p.to_dict()
        assert d["positions"] == []
        assert len(d["closed_positions"]) == 1


# ═════════════════════════════════════════════════════════════════════════════
# 13. VirtualPortfolio — determinism
# ═════════════════════════════════════════════════════════════════════════════

class TestDeterminism:
    def test_same_sequence_same_state(self) -> None:
        def run_sequence() -> VirtualPortfolio:
            p = VirtualPortfolio(100_000.0)
            p.buy("XAU/USD", 10.0, 1950.0, "2026-01-01T00:00:00")
            p.mark_to_market("XAU/USD", 2000.0, "2026-01-01T01:00:00")
            p.sell("XAU/USD", 5.0, 2050.0, "2026-01-01T02:00:00")
            p.mark_to_market("XAU/USD", 2100.0, "2026-01-01T03:00:00")
            return p

        p1 = run_sequence()
        p2 = run_sequence()
        assert p1.cash == p2.cash
        assert p1.equity == p2.equity
        assert p1.unrealized_pnl == p2.unrealized_pnl
        assert p1.realized_pnl == p2.realized_pnl
        assert p1.to_dict() == p2.to_dict()


# ═════════════════════════════════════════════════════════════════════════════
# 14. Edge cases
# ═════════════════════════════════════════════════════════════════════════════

class TestEdgeCases:
    def test_exact_cash_available(self) -> None:
        p = VirtualPortfolio(19_500.0)
        p.buy("XAU/USD", 10.0, 1950.0, "2026-01-01T00:00:00")
        assert p.cash == 0.0

    def test_trade_ids_increment(self) -> None:
        p = VirtualPortfolio(100_000.0)
        t1 = p.buy("XAU/USD", 5.0, 1950.0, "2026-01-01T00:00:00")
        t2 = p.buy("XAU/USD", 5.0, 2000.0, "2026-01-01T01:00:00")
        assert t1.trade_id == "T000001"
        assert t2.trade_id == "T000002"

    def test_short_cover_then_re_short(self) -> None:
        p = VirtualPortfolio(100_000.0)
        p.short("XAU/USD", 10.0, 2000.0, "2026-01-01T00:00:00")
        p.cover("XAU/USD", 10.0, 1900.0, "2026-01-01T01:00:00")
        p.short("XAU/USD", 5.0, 1950.0, "2026-01-01T02:00:00")
        assert p.positions[0].quantity == -5.0
        assert p.positions[0].cost_basis == 1950.0

    def test_buy_then_sell_then_buy_again(self) -> None:
        p = VirtualPortfolio(100_000.0)
        p.buy("XAU/USD", 10.0, 1950.0, "2026-01-01T00:00:00")
        p.sell("XAU/USD", 10.0, 2000.0, "2026-01-01T01:00:00")
        p.buy("XAU/USD", 5.0, 2050.0, "2026-01-01T02:00:00")
        assert p.positions[0].quantity == 5.0
        assert p.positions[0].cost_basis == 2050.0
        assert p.realized_pnl == 500.0
