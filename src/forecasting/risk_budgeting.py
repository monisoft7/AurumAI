from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np


@dataclass(frozen=True)
class RiskBudget:
    weights: tuple[float, ...]
    risk_contributions: tuple[float, ...]
    method: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "weights": list(self.weights),
            "risk_contributions": list(self.risk_contributions),
            "method": self.method,
        }


class RiskParitySizer:

    def compute(
        self,
        cov: np.ndarray,
        max_iter: int = 100,
        tol: float = 1e-8,
    ) -> RiskBudget:
        if cov.ndim != 2 or cov.shape[0] != cov.shape[1]:
            raise ValueError("cov must be a square matrix")
        n = cov.shape[0]
        if n == 0:
            raise ValueError("cov cannot be empty")
        if max_iter < 1:
            raise ValueError("max_iter must be >= 1")
        if tol <= 0.0:
            raise ValueError("tol must be positive")

        if n == 1:
            return RiskBudget(
                weights=(1.0,),
                risk_contributions=(1.0,),
                method="risk_parity",
            )

        w = np.ones(n) / n

        for _ in range(max_iter):
            sw = cov @ w
            with np.errstate(divide="ignore"):
                inv_sw = 1.0 / np.abs(sw)
            inv_sw[~np.isfinite(inv_sw)] = 0.0
            w_new = inv_sw / np.sum(inv_sw)
            w_new = 0.5 * w_new + 0.5 * w
            if np.max(np.abs(w - w_new)) < tol:
                w = w_new
                break
            w = w_new

        w = w / np.sum(w)
        variance = float(w @ cov @ w)
        sigma = np.sqrt(variance) if variance > 0.0 else 0.0
        if sigma == 0.0:
            rc = tuple(1.0 / n for _ in range(n))
        else:
            rc = tuple(
                float(w[i] * (cov @ w)[i] / sigma)
                for i in range(n)
            )
        rc_sum = sum(rc)
        if rc_sum > 0.0:
            rc = tuple(r / rc_sum for r in rc)

        return RiskBudget(
            weights=tuple(round(float(wi), 6) for wi in w),
            risk_contributions=tuple(round(r, 6) for r in rc),
            method="risk_parity",
        )
