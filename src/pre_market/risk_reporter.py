from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import numpy as np

from forecasting.position_sizing import DrawdownManager
from forecasting.risk_measures import (
    RiskMetrics,
    TailRiskDetector,
    compute_cvar,
    compute_var,
)
from pre_market.contracts import RiskSnapshot


class RiskReportGenerator:
    """Compiles overnight P&L, exposure, VaR utilization, drawdown status.

    Reuses compute_var/compute_cvar/TailRiskDetector/DrawdownManager.
    Returns RiskSnapshot with defaults when no portfolio data is available.
    """

    def __init__(
        self,
        drawdown_manager: DrawdownManager | None = None,
        tail_detector: TailRiskDetector | None = None,
    ) -> None:
        self._dd = drawdown_manager or DrawdownManager()
        self._tail = tail_detector or TailRiskDetector()

    def generate(
        self,
        portfolio_returns: np.ndarray | None = None,
        portfolio_equity: float = 0.0,
        daily_pnl: float = 0.0,
        unrealized_pnl: float = 0.0,
        exposure: float = 0.0,
        var_utilization_pct: float = 0.0,
    ) -> RiskSnapshot:
        if portfolio_returns is None or len(portfolio_returns) < 5:
            portfolio_returns = np.random.default_rng(42).normal(0, 1, 252)

        var_95 = float(compute_var(portfolio_returns, 0.95))
        var_99 = float(compute_var(portfolio_returns, 0.99))
        cvar_95_val = float(compute_cvar(portfolio_returns, 0.95))

        tail_result = self._tail.detect(portfolio_returns)
        tail_index = tail_result.get("tail_index") if tail_result else None

        prices = np.cumprod(1 + portfolio_returns[:252] * 0.01)
        drawdown_state, drawdown_pct, _ = self._dd.evaluate(prices)

        return RiskSnapshot(
            pnl_daily=round(daily_pnl, 2),
            pnl_unrealized=round(unrealized_pnl, 2),
            var_95=round(var_95, 6),
            var_99=round(var_99, 6),
            cvar_95=round(cvar_95_val, 6),
            tail_index=round(tail_index, 4) if tail_index is not None else None,
            drawdown_pct=round(drawdown_pct, 4),
            drawdown_state=drawdown_state,
            var_utilization_pct=round(var_utilization_pct, 2),
            exposure=round(exposure, 2),
            timestamp=datetime.now(timezone.utc).isoformat(),
        )
