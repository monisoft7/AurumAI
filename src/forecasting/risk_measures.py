from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

import numpy as np

_VALID_METHODS = ("historical", "parametric")


def _norm_ppf(p: float) -> float:
    if p <= 0.0 or p >= 1.0:
        raise ValueError("p must be in (0, 1)")
    if p < 0.5:
        return -_norm_ppf(1.0 - p)
    c = [2.515517, 0.802853, 0.010328]
    d = [1.432788, 0.189269, 0.001308]
    t = math.sqrt(-2.0 * math.log(1.0 - p))
    return t - (c[0] + c[1] * t + c[2] * t * t) / (
        1.0 + d[0] * t + d[1] * t * t + d[2] * t * t * t
    )


@dataclass(frozen=True)
class RiskMetrics:
    var_95: float
    var_99: float
    cvar_95: float
    tail_index: float | None
    method: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "var_95": self.var_95,
            "var_99": self.var_99,
            "cvar_95": self.cvar_95,
            "tail_index": self.tail_index,
            "method": self.method,
        }


def compute_var(
    returns: np.ndarray,
    confidence: float = 0.95,
    method: str = "historical",
) -> float:
    if method not in _VALID_METHODS:
        raise ValueError(
            f"Unknown method: {method!r}. Must be one of {_VALID_METHODS}"
        )
    if returns.size == 0:
        return 0.0
    if confidence <= 0.0 or confidence >= 1.0:
        raise ValueError("confidence must be in (0, 1)")
    if method == "historical":
        return round(float(np.percentile(returns, (1.0 - confidence) * 100.0)), 6)
    mu = float(np.mean(returns))
    sigma = float(np.std(returns, ddof=1))
    if sigma == 0.0:
        return round(mu, 6)
    return round(mu - _norm_ppf(confidence) * sigma, 6)


def compute_cvar(
    returns: np.ndarray,
    confidence: float = 0.95,
    method: str = "historical",
) -> float:
    if method not in _VALID_METHODS:
        raise ValueError(
            f"Unknown method: {method!r}. Must be one of {_VALID_METHODS}"
        )
    if returns.size == 0:
        return 0.0
    if confidence <= 0.0 or confidence >= 1.0:
        raise ValueError("confidence must be in (0, 1)")
    var = compute_var(returns, confidence, method)
    tail = returns[returns <= var]
    if tail.size == 0:
        return round(var, 6)
    return round(float(np.mean(tail)), 6)


class TailRiskDetector:

    def detect(
        self,
        returns: np.ndarray,
        threshold_percentile: float = 90.0,
        tail: str = "left",
        min_exceedances: int = 10,
    ) -> dict[str, Any]:
        if returns.size == 0:
            return self._empty_result()
        if not (0 < threshold_percentile < 100):
            raise ValueError("threshold_percentile must be in (0, 100)")
        if tail not in ("left", "right"):
            raise ValueError("tail must be 'left' or 'right'")
        if min_exceedances < 1:
            raise ValueError("min_exceedances must be >= 1")

        p_low = 100.0 - threshold_percentile
        threshold = float(np.percentile(returns, p_low))
        if tail == "left":
            exceedances = returns[returns <= threshold]
            excesses = threshold - exceedances
        else:
            exceedances = returns[returns > threshold]
            excesses = exceedances - threshold

        n_exceed = exceedances.size
        if n_exceed < min_exceedances:
            return {
                "tail_index": None,
                "threshold": round(threshold, 6),
                "n_exceedances": n_exceed,
                "has_tail_risk": False,
                "note": f"Insufficient exceedances ({n_exceed} < {min_exceedances})",
            }

        excess_mean = float(np.mean(excesses))
        excess_var = float(np.var(excesses, ddof=1))
        if excess_var == 0.0 or excess_mean == 0.0:
            return {
                "tail_index": 0.0,
                "threshold": round(threshold, 6),
                "n_exceedances": n_exceed,
                "has_tail_risk": False,
                "note": "Zero variance in excesses — no tail risk detected",
            }
        xi = 0.5 * (1.0 - (excess_mean * excess_mean) / excess_var)
        has_risk = bool(xi > 0.5)
        note = (
            f"Heavy tail detected (ξ={xi:.4f})" if has_risk
            else f"No heavy tail (ξ={xi:.4f})"
        )
        return {
            "tail_index": round(xi, 6),
            "threshold": round(threshold, 6),
            "n_exceedances": n_exceed,
            "has_tail_risk": has_risk,
            "note": note,
        }

    @staticmethod
    def _empty_result() -> dict[str, Any]:
        return {
            "tail_index": None,
            "threshold": 0.0,
            "n_exceedances": 0,
            "has_tail_risk": False,
            "note": "No data provided",
        }
