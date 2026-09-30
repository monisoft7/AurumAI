"""Separate append-only alert shadow ledger; no broker or network calls."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from pathlib import Path
from uuid import uuid4

import pandas as pd

from .engine import Alert


@dataclass(frozen=True)
class ShadowOutcome:
    """Paper outcome: net_pnl and risk_budget_pct are percent of equity.

    For example, net_pnl=-0.25 means a 0.25% equity loss. Spread, slippage,
    transaction_costs, MAE and MFE are USD per oz. Commission in the evaluator
    is USD per lot per side and is converted using 100 oz per XAUUSD lot.
    """
    alert_id: str
    entry_time: datetime
    exit_time: datetime
    entry: float
    sl: float
    tp1: float
    tp2: float
    tp3: float
    exit_price: float
    exit_reason: str  # SL, TP1, TP2, TP3, TIME
    spread: float
    slippage: float
    transaction_costs: float
    mae: float
    mfe: float
    net_pnl: float
    risk_budget_pct: float

    def __post_init__(self) -> None:
        if self.exit_time <= self.entry_time or self.exit_reason not in {"SL", "TP1", "TP2", "TP3", "TIME"}:
            raise ValueError("invalid exit")
        if min(self.spread, self.slippage, self.transaction_costs, self.mae, self.mfe) < 0:
            raise ValueError("negative cost or excursion")
        if not 0 < self.risk_budget_pct <= 0.5:
            raise ValueError("risk cap exceeded")


def evaluate_exit(alert: Alert, future: pd.DataFrame, *, spread: float,
                  slippage: float, commission_per_lot_per_side: float = 0.0,
                  max_bars: int = 16, target: int = 1,
                  alert_id: str | None = None) -> ShadowOutcome | None:
    """Next-open paper fill; conservative stop-first if both levels touch."""
    if not isinstance(future.index, pd.DatetimeIndex) or future.index.tz is None:
        raise ValueError("future candles need timezone-aware close timestamps")
    if not future.index.is_monotonic_increasing or not future.index.is_unique:
        raise ValueError("future candles must be ordered and unique")
    if future.empty or future.index[0].to_pydatetime() <= alert.valid_until - timedelta(minutes=15):
        raise ValueError("future must begin after signal candle")
    if min(spread, slippage, commission_per_lot_per_side) < 0 or max_bars < 1 or target not in (1, 2, 3):
        raise ValueError("invalid paper execution parameters")
    if not {"open", "high", "low", "close"}.issubset(future):
        raise ValueError("OHLC required")
    entry = float(future.iloc[0].open)
    if not alert.entry_low <= entry <= alert.entry_high or future.index[0].to_pydatetime() > alert.valid_until:
        return None
    sign = 1 if alert.action.endswith("BUY") else -1
    risk = abs(entry - alert.sl)
    if risk <= 0:
        return None
    tp = (alert.tp1, alert.tp2, alert.tp3)[target - 1]
    mae = mfe = 0.0
    exit_price = None
    exit_reason = "TIME"
    exit_time = None
    for timestamp, bar in future.iloc[:max_bars].iterrows():
        mae = max(mae, max(0.0, -sign * (float(bar.low if sign == 1 else bar.high) - entry)))
        mfe = max(mfe, max(0.0, sign * (float(bar.high if sign == 1 else bar.low) - entry)))
        stop_hit = float(bar.low) <= alert.sl if sign == 1 else float(bar.high) >= alert.sl
        target_hit = float(bar.high) >= tp if sign == 1 else float(bar.low) <= tp
        if stop_hit or target_hit:
            exit_price = alert.sl if stop_hit else tp
            exit_reason = "SL" if stop_hit else f"TP{target}"
            exit_time = timestamp.to_pydatetime()
            break
    if exit_price is None:
        bar = future.iloc[min(max_bars, len(future)) - 1]
        exit_price = float(bar.close)
        exit_time = future.index[min(max_bars, len(future)) - 1].to_pydatetime()
    costs = spread + 2 * slippage + 2 * commission_per_lot_per_side / 100.0
    net_r = (sign * (exit_price - entry) - costs) / risk
    return ShadowOutcome(
        alert_id or uuid4().hex, alert.valid_until - timedelta(minutes=15), exit_time,
        entry, alert.sl, alert.tp1, alert.tp2, alert.tp3, exit_price,
        exit_reason, spread, slippage, costs, mae, mfe,
        net_r * alert.risk_budget_pct * alert.initial_allocation,
        alert.risk_budget_pct,
    )


def append(directory: Path, outcome: ShadowOutcome) -> Path:
    """Write exactly one new ID in a dedicated directory; never overwrite."""
    if not outcome.alert_id or not all(c.isalnum() or c in "-_" for c in outcome.alert_id):
        raise ValueError("invalid alert ID")
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    target = directory / f"{outcome.alert_id}.json"
    with target.open("x", encoding="utf-8") as file:
        json.dump(asdict(outcome), file, default=str, sort_keys=True)
    return target


def metrics(outcomes: list[ShadowOutcome]) -> dict[str, float | int | None]:
    """Expectancy is mean net equity %, drawdown is peak-to-trough equity %."""
    pnl = [item.net_pnl for item in sorted(outcomes, key=lambda x: x.exit_time)]
    gains = sum(v for v in pnl if v > 0)
    losses = -sum(v for v in pnl if v < 0)
    equity = peak = 1.0
    drawdown = 0.0
    for value in pnl:
        equity *= 1 + value / 100.0
        peak = max(peak, equity)
        drawdown = max(drawdown, 100.0 * (peak - equity) / peak)
    return {"trades": len(pnl), "expectancy": sum(pnl) / len(pnl) if pnl else None,
            "profit_factor": gains / losses if losses else None,
            "max_drawdown": drawdown}


def pass_gate(outcomes: list[ShadowOutcome], *, independent_periods: int,
              market_regimes: int, fold_expectancies: tuple[float, ...] | None = None,
              slippage_sensitivity_ok: bool = False) -> str:
    result = metrics(outcomes)
    if (len(outcomes) < 100 or independent_periods < 3 or market_regimes < 2
            or fold_expectancies is None or len(fold_expectancies) < 3
            or sum(value > 0 for value in fold_expectancies) < 2
            or min(fold_expectancies) < 0 or not slippage_sensitivity_ok):
        return "NO_GO"
    pnl = [abs(x.net_pnl) for x in outcomes]
    if max(pnl) > 0.25 * sum(pnl):
        return "NO_GO"
    if result["expectancy"] is None or result["expectancy"] <= 0:
        return "NO_GO"
    if result["profit_factor"] is None or result["profit_factor"] < 1.2:
        return "NO_GO"
    if result["max_drawdown"] > 10:
        return "NO_GO"
    return "READY_FOR_SHADOW"
