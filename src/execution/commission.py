from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class CommissionResult:
    commission: float
    commission_per_unit: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "commission": self.commission,
            "commission_per_unit": self.commission_per_unit,
        }


class CommissionModel(ABC):
    @abstractmethod
    def apply(
        self,
        price: float,
        quantity: float,
    ) -> CommissionResult: ...

    @abstractmethod
    def to_dict(self) -> dict[str, Any]: ...


class FixedCommissionModel(CommissionModel):
    def __init__(self, commission_per_trade: float = 0.0) -> None:
        if commission_per_trade < 0:
            raise ValueError("commission_per_trade must be non-negative")
        self._commission_per_trade = commission_per_trade

    @property
    def commission_per_trade(self) -> float:
        return self._commission_per_trade

    def apply(self, price: float, quantity: float) -> CommissionResult:
        if quantity == 0.0:
            return CommissionResult(commission=0.0, commission_per_unit=0.0)
        commission = self._commission_per_trade
        return CommissionResult(
            commission=commission,
            commission_per_unit=commission / abs(quantity),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": "fixed",
            "commission_per_trade": self._commission_per_trade,
        }


class PercentageCommissionModel(CommissionModel):
    def __init__(
        self,
        commission_pct: float = 0.001,
        min_commission: float | None = None,
    ) -> None:
        if commission_pct < 0:
            raise ValueError("commission_pct must be non-negative")
        if min_commission is not None and min_commission < 0:
            raise ValueError("min_commission must be non-negative")
        self._commission_pct = commission_pct
        self._min_commission = min_commission

    @property
    def commission_pct(self) -> float:
        return self._commission_pct

    @property
    def min_commission(self) -> float | None:
        return self._min_commission

    def apply(self, price: float, quantity: float) -> CommissionResult:
        notional = abs(quantity) * price
        commission = notional * self._commission_pct
        if self._min_commission is not None:
            commission = max(commission, self._min_commission)
        return CommissionResult(
            commission=commission,
            commission_per_unit=commission / abs(quantity) if quantity != 0.0 else 0.0,
        )

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "type": "percentage",
            "commission_pct": self._commission_pct,
        }
        if self._min_commission is not None:
            d["min_commission"] = self._min_commission
        return d
