from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

import numpy as np


@dataclass(frozen=True)
class PositionSizing:
    scaling_factor: float
    target_vol: float
    current_vol: float
    drawdown_state: str
    kelly_cap: float | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "scaling_factor": self.scaling_factor,
            "target_vol": self.target_vol,
            "current_vol": self.current_vol,
            "drawdown_state": self.drawdown_state,
            "kelly_cap": self.kelly_cap,
        }


class VolatilityTargetSizer:

    def compute(
        self,
        returns: np.ndarray,
        target_vol: float = 0.15,
        window: int = 60,
        annualization_factor: float = 252.0,
    ) -> PositionSizing:
        if returns.size == 0:
            return PositionSizing(
                scaling_factor=0.0,
                target_vol=target_vol,
                current_vol=0.0,
                drawdown_state="normal",
                kelly_cap=None,
            )
        if target_vol <= 0.0:
            raise ValueError("target_vol must be positive")
        if window < 2:
            raise ValueError("window must be >= 2")
        if annualization_factor <= 0.0:
            raise ValueError("annualization_factor must be positive")

        recent = returns[-min(window, returns.size):]
        current_vol = float(np.std(recent, ddof=1)) * math.sqrt(annualization_factor)

        if current_vol == 0.0:
            scale = 0.0
        else:
            scale = target_vol / current_vol

        scale = max(0.0, min(scale, 1.0))
        current_vol = round(current_vol, 6)
        scale = round(scale, 6)

        return PositionSizing(
            scaling_factor=scale,
            target_vol=target_vol,
            current_vol=current_vol,
            drawdown_state="normal",
            kelly_cap=None,
        )


class DrawdownManager:

    def __init__(
        self,
        caution_threshold: float = 0.10,
        halt_threshold: float = 0.20,
        recovery_period: int = 20,
    ) -> None:
        if not (0 < caution_threshold < halt_threshold <= 1.0):
            raise ValueError(
                "0 < caution_threshold < halt_threshold <= 1.0 required"
            )
        if recovery_period < 1:
            raise ValueError("recovery_period must be >= 1")
        self._caution = caution_threshold
        self._halt = halt_threshold
        self._recovery = recovery_period

    def evaluate(
        self,
        prices: np.ndarray,
        prev_state: str = "normal",
        recovery_counter: int = 0,
    ) -> tuple[str, float, int]:
        if prices.size == 0:
            return ("normal", 0.0, 0)

        peak = float(np.maximum.accumulate(prices)[-1])
        current = float(prices[-1])
        drawdown = (peak - current) / peak if peak > 0.0 else 0.0
        drawdown = round(drawdown, 6)

        if prev_state == "halted":
            new_counter = recovery_counter + 1
            if drawdown < self._caution * 0.5 and new_counter >= self._recovery:
                return ("normal", drawdown, 0)
            return ("halted", drawdown, new_counter)

        if drawdown >= self._halt:
            return ("halted", drawdown, 0)
        if drawdown >= self._caution:
            return ("caution", drawdown, 0)

        return ("normal", drawdown, 0)


class KellyCap:

    def compute(
        self,
        win_prob: float,
        payoff_ratio: float,
        fraction: float = 0.25,
    ) -> float:
        if not (0.0 < win_prob < 1.0):
            raise ValueError("win_prob must be in (0, 1)")
        if payoff_ratio <= 0.0:
            raise ValueError("payoff_ratio must be positive")
        if not (0.0 < fraction <= 1.0):
            raise ValueError("fraction must be in (0, 1]")

        b = payoff_ratio
        p = win_prob
        q = 1.0 - p
        kelly = (b * p - q) / b
        if kelly < 0.0:
            return 0.0
        return round(min(kelly * fraction, 1.0), 6)
