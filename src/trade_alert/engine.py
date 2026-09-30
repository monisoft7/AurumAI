"""Deterministic M15/H1 setup assessment. Candle indices are UTC close times."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from math import isfinite
from typing import Protocol

import pandas as pd

from technical.engine import TechnicalEngine
from technical.market_structure import analyze_structure
from paper_trading.ledger import REQUIRED_PAPER_SOURCES


class CandleProvider(Protocol):
    def completed(self, timeframe: str, as_of: datetime) -> pd.DataFrame:
        """Return UTC close-indexed completed OHLCV with no row after as_of."""


def macro_is_fresh(paper_evaluation: dict) -> bool:
    """Consume the existing canonical source freshness contract."""
    sources = paper_evaluation.get("source_freshness") or {}
    return all((sources.get(name) or {}).get("status") == "fresh"
               for name in REQUIRED_PAPER_SOURCES)


@dataclass(frozen=True)
class Alert:
    action: str
    setup: str
    entry_low: float
    entry_high: float
    current_price: float
    sl: float
    tp1: float
    tp2: float
    tp3: float
    rr1: float
    rr2: float
    rr3: float
    directional_conviction: float
    execution_quality: float
    strongest_counterargument: str
    invalidation: str
    valid_until: datetime
    reason: str
    initial_allocation: float = 0.25
    risk_budget_pct: float = 0.25

    def __post_init__(self) -> None:
        if self.action not in {"TRADE_ALERT BUY", "TRADE_ALERT SELL"}:
            raise ValueError("invalid action")
        values = (self.entry_low, self.entry_high, self.current_price, self.sl,
                  self.tp1, self.tp2, self.tp3, self.rr1, self.rr2, self.rr3)
        if not all(isfinite(v) for v in values) or self.entry_low > self.entry_high:
            raise ValueError("invalid price")
        if not self.entry_low <= self.current_price <= self.entry_high:
            raise ValueError("price has passed entry")
        entry = self.current_price
        if self.action.endswith("BUY"):
            risk = entry - self.sl
            rewards = [tp - entry for tp in (self.tp1, self.tp2, self.tp3)]
        else:
            risk = self.sl - entry
            rewards = [entry - tp for tp in (self.tp1, self.tp2, self.tp3)]
        if risk <= 0 or not 0 < rewards[0] < rewards[1] < rewards[2]:
            raise ValueError("contradictory SL/TP")
        if any(abs(actual - expected / risk) > 1e-8 for actual, expected in
               zip((self.rr1, self.rr2, self.rr3), rewards)):
            raise ValueError("incorrect R:R")
        if not 0 < self.initial_allocation <= 1 or not 0 < self.risk_budget_pct <= 0.5:
            raise ValueError("paper risk cap exceeded")


def _frame(provider: CandleProvider, timeframe: str, as_of: datetime) -> pd.DataFrame:
    frame = provider.completed(timeframe, as_of)
    if not isinstance(frame.index, pd.DatetimeIndex) or frame.index.tz is None:
        raise ValueError("UTC close timestamps required")
    if str(frame.index.tz) not in {"UTC", "datetime.timezone.utc"}:
        raise ValueError("UTC timestamps required")
    if frame.empty or not frame.index.is_monotonic_increasing or not frame.index.is_unique:
        raise ValueError("ordered unique completed candles required")
    if frame.index.max().to_pydatetime() > as_of.astimezone(timezone.utc):
        raise ValueError("lookahead candle")
    required = ["open", "high", "low", "close", "volume"]
    if not set(required).issubset(frame) or frame[required].isna().any().any():
        raise ValueError("incomplete OHLCV")
    if (frame.high < frame.low).any() or (frame.high < frame[["open", "close"]].max(axis=1)).any() or (frame.low > frame[["open", "close"]].min(axis=1)).any() or (frame.volume < 0).any():
        raise ValueError("invalid OHLCV")
    return frame.copy()


def evaluate(provider: CandleProvider, technical: TechnicalEngine, as_of: datetime,
             *, macro_fresh: bool, event_blocked: bool = False,
             macro_modifier: float = 0.0, spread: float = 0.0,
             slippage: float = 0.0) -> Alert | None:
    """Return an alert or NO_OUTPUT (None); macro inputs only filter/modify."""
    if as_of.tzinfo is None or not macro_fresh or event_blocked or not -0.1 <= macro_modifier <= 0.1:
        return None
    m15, h1 = (_frame(provider, tf, as_of) for tf in ("M15", "H1"))
    utc = as_of.astimezone(timezone.utc)
    if utc - m15.index[-1].to_pydatetime() > timedelta(minutes=15) or utc - h1.index[-1].to_pydatetime() > timedelta(hours=1):
        return None
    if len(m15) < 220 or len(h1) < 220 or spread < 0 or slippage < 0:
        return None
    a, b = technical.compute(m15), technical.compute(h1)
    if not {"ema_20", "ema_50", "ema_200", "atr_14"}.issubset(a) or not {"ema_20", "ema_50", "ema_200"}.issubset(b):
        raise ValueError("technical engine columns missing")
    last, previous = m15.iloc[-1], m15.iloc[-2]
    ind, h_ind = a.iloc[-1], b.iloc[-1]
    atr = float(ind.atr_14)
    if not isfinite(atr) or atr <= 0:
        return None
    structure = analyze_structure(h1.close)
    bullish = h_ind.ema_20 > h_ind.ema_50 > h_ind.ema_200 and structure.structure_state == "uptrend"
    bearish = h_ind.ema_20 < h_ind.ema_50 < h_ind.ema_200 and structure.structure_state == "downtrend"
    if not (bullish or bearish):
        return None
    direction = 1 if bullish else -1
    conviction = min(1.0, 0.65 + abs(float(h_ind.ema_20 - h_ind.ema_50)) / (4 * atr) + macro_modifier)
    if conviction < 0.7:
        return None
    close = float(last.close)
    prior_high = float(m15.high.iloc[-21:-1].max())
    prior_low = float(m15.low.iloc[-21:-1].min())
    ema = float(ind.ema_20)
    # Boundaries exclude the latest candle. A sweep must reclaim its level.
    pullback = abs(float(previous.close) - ema) <= 0.35 * atr and direction * (close - ema) > 0 and direction * (close - float(last.open)) > 0
    breakout = (close > prior_high + 0.1 * atr if bullish else close < prior_low - 0.1 * atr) and abs(close - (prior_high if bullish else prior_low)) <= 0.6 * atr
    sweep = (float(last.low) < prior_low - 0.1 * atr and close > prior_low + 0.1 * atr if bullish else float(last.high) > prior_high + 0.1 * atr and close < prior_high - 0.1 * atr)
    setup = "trend_pullback" if pullback else "confirmed_breakout" if breakout else "failed_breakout_liquidity_sweep_reversal" if sweep else None
    if setup is None:
        return None
    quality = 0.8 - (spread + slippage) / atr - abs(close - ema) / (5 * atr)
    if quality < 0.65:
        return None
    risk = max(1.2 * atr, (close - float(last.low)) if bullish else (float(last.high) - close))
    if spread + slippage >= 0.1 * risk:
        return None
    sl = close - direction * risk
    targets = [close + direction * risk * rr for rr in (1.5, 2.0, 3.0)]
    width = 0.1 * atr
    return Alert(
        action="TRADE_ALERT BUY" if bullish else "TRADE_ALERT SELL", setup=setup,
        entry_low=close - width, entry_high=close + width, current_price=close,
        sl=sl, tp1=targets[0], tp2=targets[1], tp3=targets[2],
        rr1=1.5, rr2=2.0, rr3=3.0, directional_conviction=conviction,
        execution_quality=quality, strongest_counterargument="H1 trend can reverse before TP1",
        invalidation=f"M15 closes beyond {sl:.2f}",
        valid_until=as_of.astimezone(timezone.utc) + timedelta(minutes=15),
        reason=f"{setup}: H1 EMA alignment and confirmed structure with M15 price trigger",
    )


def format_alert(alert: Alert) -> str:
    """Render the complete executable paper alert, with no market commentary."""
    action = alert.action.replace("TRADE_ALERT ", "")
    return "\n".join((
        "🚨 TRADE ALERT — XAU/USD",
        f"ACTION: {action}",
        f"SETUP: {alert.setup}",
        f"ENTRY: {alert.entry_low:.2f}-{alert.entry_high:.2f}",
        f"INITIAL ALLOCATION: {alert.initial_allocation:.0%}",
        f"RISK BUDGET: {alert.risk_budget_pct:.2f}%",
        f"SL: {alert.sl:.2f}",
        f"TP1: {alert.tp1:.2f}",
        f"TP2: {alert.tp2:.2f}",
        f"TP3: {alert.tp3:.2f}",
        f"R:R: {alert.rr1:.2f}/{alert.rr2:.2f}/{alert.rr3:.2f}",
        f"CONVICTION: {alert.directional_conviction:.2f}",
        f"DIRECTIONAL CONVICTION: {alert.directional_conviction:.2f}",
        f"EXECUTION QUALITY: {alert.execution_quality:.2f}",
        f"RISK: {alert.strongest_counterargument}",
        f"WHY: {alert.reason}",
        f"INVALIDATION: {alert.invalidation}",
        f"NEXT TRIGGER: {alert.current_price:.2f}",
        f"VALID UNTIL: {alert.valid_until.isoformat()}"
    ))
