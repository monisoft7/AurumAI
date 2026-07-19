from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class SlippageResult:
    executed_price: float
    slippage_amount: float
    slippage_bps: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "executed_price": self.executed_price,
            "slippage_amount": self.slippage_amount,
            "slippage_bps": self.slippage_bps,
        }


class SlippageModel(ABC):
    @abstractmethod
    def apply(
        self,
        price: float,
        quantity: float,
    ) -> SlippageResult: ...

    @abstractmethod
    def to_dict(self) -> dict[str, Any]: ...


class FixedSlippageModel(SlippageModel):
    def __init__(self, slippage_per_unit: float = 0.01) -> None:
        if slippage_per_unit < 0:
            raise ValueError("slippage_per_unit must be non-negative")
        self._slippage_per_unit = slippage_per_unit

    @property
    def slippage_per_unit(self) -> float:
        return self._slippage_per_unit

    def apply(self, price: float, quantity: float) -> SlippageResult:
        slippage_amount = self._slippage_per_unit * abs(quantity)
        if quantity >= 0:
            executed_price = price + self._slippage_per_unit
        else:
            executed_price = price - self._slippage_per_unit
        slippage_bps = (
            (self._slippage_per_unit / price) * 10_000 if price != 0.0 else 0.0
        )
        return SlippageResult(
            executed_price=executed_price,
            slippage_amount=slippage_amount,
            slippage_bps=slippage_bps,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": "fixed",
            "slippage_per_unit": self._slippage_per_unit,
        }


class PercentageSlippageModel(SlippageModel):
    def __init__(self, slippage_pct: float = 0.001) -> None:
        if slippage_pct < 0:
            raise ValueError("slippage_pct must be non-negative")
        self._slippage_pct = slippage_pct

    @property
    def slippage_pct(self) -> float:
        return self._slippage_pct

    def apply(self, price: float, quantity: float) -> SlippageResult:
        per_unit = price * self._slippage_pct
        slippage_amount = per_unit * abs(quantity)
        if quantity >= 0:
            executed_price = price * (1.0 + self._slippage_pct)
        else:
            executed_price = price * (1.0 - self._slippage_pct)
        slippage_bps = self._slippage_pct * 10_000
        return SlippageResult(
            executed_price=executed_price,
            slippage_amount=slippage_amount,
            slippage_bps=slippage_bps,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": "percentage",
            "slippage_pct": self._slippage_pct,
        }
