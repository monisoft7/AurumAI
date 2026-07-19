from __future__ import annotations

import itertools
from typing import Any

from execution.models import PortfolioSnapshot, VirtualPosition, VirtualTrade


class VirtualPortfolio:
    def __init__(self, initial_capital: float = 100_000.0) -> None:
        if initial_capital < 0:
            raise ValueError("initial_capital must be non-negative")
        self._initial_capital = initial_capital
        self._cash = initial_capital
        self._positions: dict[str, VirtualPosition] = {}
        self._trades: list[VirtualTrade] = []
        self._closed_positions: list[VirtualPosition] = []
        self._snapshots: list[PortfolioSnapshot] = []
        self._total_realized_pnl = 0.0
        self._trade_counter = itertools.count(1)
        self._snapshot_counter = itertools.count(1)

    # -- property accessors ---------------------------------------------------

    @property
    def initial_capital(self) -> float:
        return self._initial_capital

    @property
    def cash(self) -> float:
        return self._cash

    @property
    def positions(self) -> tuple[VirtualPosition, ...]:
        return tuple(self._positions.values())

    @property
    def closed_positions(self) -> tuple[VirtualPosition, ...]:
        return tuple(self._closed_positions)

    @property
    def trades(self) -> tuple[VirtualTrade, ...]:
        return tuple(self._trades)

    @property
    def snapshots(self) -> tuple[PortfolioSnapshot, ...]:
        return tuple(self._snapshots)

    @property
    def equity(self) -> float:
        return self._cash + sum(p.market_value for p in self._positions.values())

    @property
    def unrealized_pnl(self) -> float:
        return sum(p.unrealized_pnl for p in self._positions.values())

    @property
    def realized_pnl(self) -> float:
        return self._total_realized_pnl

    @property
    def total_pnl(self) -> float:
        return self.unrealized_pnl + self.realized_pnl

    # -- core operations -----------------------------------------------------

    def buy(
        self,
        asset_id: str,
        quantity: float,
        price: float,
        timestamp: str,
    ) -> VirtualTrade:
        if quantity <= 0:
            raise ValueError("quantity must be positive")
        cost = quantity * price
        if cost > self._cash:
            raise ValueError(
                f"Insufficient cash: need {cost:.2f}, have {self._cash:.2f}"
            )
        return self._apply_buy(asset_id, quantity, price, cost, timestamp)

    def sell(
        self,
        asset_id: str,
        quantity: float,
        price: float,
        timestamp: str,
    ) -> VirtualTrade:
        if quantity <= 0:
            raise ValueError("quantity must be positive")
        pos = self._positions.get(asset_id)
        if pos is None or pos.quantity <= 0:
            raise ValueError(
                f"No long position in {asset_id!r} to sell"
            )
        if quantity > pos.quantity:
            raise ValueError(
                f"Cannot sell {quantity} units of {asset_id!r}: "
                f"only {pos.quantity} held"
            )
        return self._apply_sell(asset_id, quantity, price, pos, timestamp)

    def short(
        self,
        asset_id: str,
        quantity: float,
        price: float,
        timestamp: str,
    ) -> VirtualTrade:
        if quantity <= 0:
            raise ValueError("quantity must be positive")
        pos = self._positions.get(asset_id)
        if pos is not None and pos.quantity >= 0:
            raise ValueError(
                f"Cannot short {asset_id!r}: already have a long position"
            )
        return self._apply_short(asset_id, quantity, price, timestamp)

    def cover(
        self,
        asset_id: str,
        quantity: float,
        price: float,
        timestamp: str,
    ) -> VirtualTrade:
        if quantity <= 0:
            raise ValueError("quantity must be positive")
        pos = self._positions.get(asset_id)
        if pos is None or pos.quantity >= 0:
            raise ValueError(
                f"No short position in {asset_id!r} to cover"
            )
        if quantity > abs(pos.quantity):
            raise ValueError(
                f"Cannot cover {quantity} units of {asset_id!r}: "
                f"only {abs(pos.quantity)} held short"
            )
        return self._apply_cover(asset_id, quantity, price, pos, timestamp)

    def mark_to_market(
        self,
        asset_id: str,
        price: float,
        timestamp: str,
    ) -> PortfolioSnapshot:
        pos = self._positions.get(asset_id)
        if pos is None:
            raise ValueError(f"No open position in {asset_id!r}")
        self._positions[asset_id] = VirtualPosition(
            asset_id=pos.asset_id,
            quantity=pos.quantity,
            cost_basis=pos.cost_basis,
            current_price=price,
        )
        snapshot = PortfolioSnapshot(
            timestamp=timestamp,
            cash=self._cash,
            equity=self.equity,
            unrealized_pnl=self.unrealized_pnl,
            realized_pnl=self.realized_pnl,
            positions=self.positions,
        )
        self._snapshots.append(snapshot)
        return snapshot

    def reset(self) -> None:
        self._cash = self._initial_capital
        self._positions.clear()
        self._trades.clear()
        self._closed_positions.clear()
        self._snapshots.clear()
        self._total_realized_pnl = 0.0

    # -- serialization -------------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        return {
            "initial_capital": self._initial_capital,
            "cash": self._cash,
            "equity": self.equity,
            "unrealized_pnl": self.unrealized_pnl,
            "realized_pnl": self.realized_pnl,
            "total_pnl": self.total_pnl,
            "positions": [p.to_dict() for p in self.positions],
            "closed_positions": [p.to_dict() for p in self._closed_positions],
            "trades": [t.to_dict() for t in self._trades],
            "snapshots": [s.to_dict() for s in self._snapshots],
        }

    # -- internal helpers ----------------------------------------------------

    def _next_trade_id(self) -> str:
        return f"T{next(self._trade_counter):06d}"

    def _apply_buy(
        self,
        asset_id: str,
        quantity: float,
        price: float,
        cost: float,
        timestamp: str,
    ) -> VirtualTrade:
        pos = self._positions.get(asset_id)
        self._cash -= cost

        if pos is None or pos.quantity >= 0:
            new_qty = (pos.quantity if pos else 0.0) + quantity
            if pos is None:
                cost_basis = price
            else:
                total_cost = pos.cost_basis * pos.quantity + price * quantity
                cost_basis = total_cost / new_qty
            realized = None
        else:
            short_qty = abs(pos.quantity)
            if quantity <= short_qty:
                realized = quantity * (pos.cost_basis - price)
                new_qty = pos.quantity + quantity
                cost_basis = pos.cost_basis
            else:
                realized = short_qty * (pos.cost_basis - price)
                remaining = quantity - short_qty
                new_qty = remaining
                cost_basis = price

        self._update_position(asset_id, new_qty, cost_basis, price, realized)

        trade = VirtualTrade(
            trade_id=self._next_trade_id(),
            asset_id=asset_id,
            action="BUY",
            quantity=quantity,
            price=price,
            timestamp=timestamp,
            realized_pnl=realized,
        )
        self._trades.append(trade)
        return trade

    def _apply_sell(
        self,
        asset_id: str,
        quantity: float,
        price: float,
        pos: VirtualPosition,
        timestamp: str,
    ) -> VirtualTrade:
        self._cash += quantity * price
        realized = quantity * (price - pos.cost_basis)

        new_qty = pos.quantity - quantity
        if new_qty == 0:
            closed = VirtualPosition(
                asset_id=pos.asset_id,
                quantity=pos.quantity,
                cost_basis=pos.cost_basis,
                current_price=price,
            )
            self._closed_positions.append(closed)
            self._positions.pop(asset_id, None)
        else:
            self._positions[asset_id] = VirtualPosition(
                asset_id=pos.asset_id,
                quantity=new_qty,
                cost_basis=pos.cost_basis,
                current_price=price,
            )

        self._total_realized_pnl += realized

        trade = VirtualTrade(
            trade_id=self._next_trade_id(),
            asset_id=asset_id,
            action="SELL",
            quantity=quantity,
            price=price,
            timestamp=timestamp,
            realized_pnl=realized,
        )
        self._trades.append(trade)
        return trade

    def _apply_short(
        self,
        asset_id: str,
        quantity: float,
        price: float,
        timestamp: str,
    ) -> VirtualTrade:
        pos = self._positions.get(asset_id)
        self._cash += quantity * price

        if pos is None or pos.quantity <= 0:
            new_qty = (pos.quantity if pos else 0.0) - quantity
            if pos is None:
                cost_basis = price
            else:
                total_cost = (pos.cost_basis * abs(pos.quantity)
                              + price * quantity)
                cost_basis = total_cost / abs(new_qty)
            realized = None
        else:
            realized = quantity * (price - pos.cost_basis)
            new_qty = pos.quantity - quantity

        self._update_position(asset_id, new_qty, cost_basis, price, realized)

        trade = VirtualTrade(
            trade_id=self._next_trade_id(),
            asset_id=asset_id,
            action="SHORT",
            quantity=quantity,
            price=price,
            timestamp=timestamp,
            realized_pnl=realized,
        )
        self._trades.append(trade)
        return trade

    def _apply_cover(
        self,
        asset_id: str,
        quantity: float,
        price: float,
        pos: VirtualPosition,
        timestamp: str,
    ) -> VirtualTrade:
        self._cash -= quantity * price
        realized = quantity * (pos.cost_basis - price)

        new_qty = pos.quantity + quantity
        if new_qty == 0:
            closed = VirtualPosition(
                asset_id=pos.asset_id,
                quantity=pos.quantity,
                cost_basis=pos.cost_basis,
                current_price=price,
            )
            self._closed_positions.append(closed)
            self._positions.pop(asset_id, None)
        else:
            self._positions[asset_id] = VirtualPosition(
                asset_id=pos.asset_id,
                quantity=new_qty,
                cost_basis=pos.cost_basis,
                current_price=price,
            )

        self._total_realized_pnl += realized

        trade = VirtualTrade(
            trade_id=self._next_trade_id(),
            asset_id=asset_id,
            action="COVER",
            quantity=quantity,
            price=price,
            timestamp=timestamp,
            realized_pnl=realized,
        )
        self._trades.append(trade)
        return trade

    def _update_position(
        self,
        asset_id: str,
        new_qty: float,
        cost_basis: float,
        price: float,
        realized: float | None,
    ) -> None:
        if realized is not None:
            self._total_realized_pnl += realized

        if new_qty == 0:
            old = self._positions.pop(asset_id, None)
            if old is not None:
                self._closed_positions.append(old)
        else:
            self._positions[asset_id] = VirtualPosition(
                asset_id=asset_id,
                quantity=new_qty,
                cost_basis=cost_basis,
                current_price=price,
            )
