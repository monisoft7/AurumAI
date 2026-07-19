from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class VirtualPosition:
    asset_id: str
    quantity: float
    cost_basis: float
    current_price: float

    @property
    def unrealized_pnl(self) -> float:
        return (self.current_price - self.cost_basis) * self.quantity

    @property
    def market_value(self) -> float:
        return self.quantity * self.current_price

    def to_dict(self) -> dict[str, Any]:
        return {
            "asset_id": self.asset_id,
            "quantity": self.quantity,
            "cost_basis": self.cost_basis,
            "current_price": self.current_price,
            "unrealized_pnl": self.unrealized_pnl,
            "market_value": self.market_value,
        }


@dataclass(frozen=True)
class VirtualTrade:
    trade_id: str
    asset_id: str
    action: str
    quantity: float
    price: float
    timestamp: str
    realized_pnl: float | None = None

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "trade_id": self.trade_id,
            "asset_id": self.asset_id,
            "action": self.action,
            "quantity": self.quantity,
            "price": self.price,
            "timestamp": self.timestamp,
        }
        if self.realized_pnl is not None:
            d["realized_pnl"] = self.realized_pnl
        return d


@dataclass(frozen=True)
class PortfolioSnapshot:
    timestamp: str
    cash: float
    equity: float
    unrealized_pnl: float
    realized_pnl: float
    positions: tuple[VirtualPosition, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "cash": self.cash,
            "equity": self.equity,
            "unrealized_pnl": self.unrealized_pnl,
            "realized_pnl": self.realized_pnl,
            "positions": [p.to_dict() for p in self.positions],
        }
