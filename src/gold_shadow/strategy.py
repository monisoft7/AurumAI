"""Fixed policies and conservative candle-based paper fills. Prices are USD per ounce."""
from dataclasses import dataclass
from datetime import datetime, timedelta
from statistics import fmean

from .market import STEP, Bar

POLICIES = ("combined", "trend_only", "range_only", "without_h4", "momentum", "long_only", "breakout", "market_momentum")
HOUR = timedelta(hours=1)


@dataclass(frozen=True)
class Plan:
    action: str
    regime: str
    reason: str
    entry: float | None = None
    stop: float | None = None
    target: float | None = None


def decide(history: list[Bar], issued: datetime, policy="combined") -> Plan:
    if policy not in POLICIES:
        raise ValueError("unknown policy")
    window = history[-17:]
    if len(window) < 17 or window[-1].start - window[0].start != STEP * 16:
        return Plan("WAIT", "unknown", "incomplete M15 window")
    age = issued - (window[-1].start + STEP)
    if not timedelta(0) <= age < STEP:
        return Plan("WAIT", "unknown", "future or stale M15 close")
    pairs = list(zip(window, window[1:]))
    movement = sum(abs(b.close - a.close) for a, b in pairs)
    price = window[-1].close
    change = price - window[0].close
    atr = fmean(max(b.high - b.low, abs(b.high - a.close), abs(b.low - a.close)) for a, b in pairs)
    if not movement or not atr:
        return Plan("WAIT", "flat", "no price movement")
    regime = "trend" if abs(change) / movement >= 0.35 else "range"
    side = 1 if change > 0 else -1
    kind = "LIMIT"
    if policy == "long_only":
        side = 1
    elif policy in ("momentum", "breakout", "market_momentum"):
        if change == 0:
            return Plan("WAIT", regime, "no net displacement")
    elif regime == "trend":
        if policy == "range_only":
            return Plan("WAIT", regime, "range strategy inactive")
        if policy != "without_h4":
            last_close = window[-1].start + STEP
            boundary = last_close.replace(hour=last_close.hour // 4 * 4, minute=0)
            h4 = [b for b in history[-33:] if boundary - 4 * HOUR <= b.start < boundary]
            if len(h4) != 16 or (h4[-1].close - h4[0].open) * side <= 0:
                return Plan("WAIT", regime, "completed H4 missing or disagrees")
    elif policy == "trend_only":
        return Plan("WAIT", regime, "trend strategy inactive")
    high = max(b.high for b in window[1:])
    low = min(b.low for b in window[1:])
    if policy == "market_momentum":
        kind = "NOW"
        entry = price
        reason = "market momentum reference"
    elif policy == "breakout":
        kind = "STOP"
        entry = high if side > 0 else low
        if (entry - price) * side <= 0:
            return Plan("WAIT", regime, "breakout already reached")
        reason = "break of 16-bar extreme"
    elif regime == "range" and policy in ("range_only", "combined", "without_h4"):
        side = 1 if price - low < high - price else -1
        entry = low if side > 0 else high
        reason = "fade nearest range boundary"
    else:
        entry = price - side * atr / 2
        reason = "half ATR pullback"
    if entry == price and kind != "NOW":
        return Plan("WAIT", regime, "entry already reached")
    return Plan(("BUY " if side > 0 else "SELL ") + kind, regime, reason,
                entry, entry - side * atr, entry + side * atr * 1.5)


def activation(issued):
    floor = issued.replace(minute=issued.minute // 15 * 15, second=0, microsecond=0)
    return floor if floor == issued else floor + STEP


def evaluate(plan, issued, bars, *, spread=0.50, slippage=0.10):
    """Evaluate in chronology, using executable half-spread offsets on mid-price proxies."""
    start = activation(issued)
    expiry = start + HOUR
    side = 1 if plan.action.startswith("BUY") else -1
    kind = plan.action.split()[-1]
    risk = abs(plan.entry - plan.stop)
    fill = None
    filled_at = None
    favorable = adverse = 0.0
    expected = start
    last = None
    exit_price = None
    status = "pending"
    for bar in bars:
        if bar.start < start:
            continue
        if bar.start != expected:
            status = "unobserved_gap"
            break
        expected = bar.start + STEP
        last = expected
        entry_offset = side * spread / 2
        # Work in signed, executable prices so buys and sells are symmetric.
        opening = side * (bar.open + entry_offset)
        hi = max(side * bar.high, side * bar.low)
        lo = min(side * bar.high, side * bar.low)
        if fill is None:
            level = side * plan.entry
            if kind == "NOW":
                fill = side * (opening + slippage)
            elif kind == "LIMIT" and lo + spread / 2 <= level:
                fill = side * min(opening, level)  # a limit cannot fill beyond its limit
            elif kind == "STOP" and hi + spread / 2 >= level:
                fill = side * (max(opening, level) + slippage)
            if fill is None:
                if expected >= expiry:
                    status = "expired_unfilled"
                    break
                continue
            filled_at = bar.start
        held_at_open = bar.start > filled_at
        opened_marketable = kind == "NOW" or (kind == "LIMIT" and opening <= side * plan.entry) or (kind == "STOP" and opening >= side * plan.entry)
        whole_bar = held_at_open or opened_marketable
        bid_open = side * bar.open - spread / 2
        worst = lo - spread / 2
        best = hi - spread / 2
        close = side * bar.close - spread / 2
        # A known opening quote precedes both extremes. For unknown
        # intrabar order, take the adverse path compatible with the bar.
        if whole_bar and bid_open >= side * plan.target:
            exit_price = plan.target
            status = "target"
        elif worst <= side * plan.stop:
            exit_price = side * (min(bid_open, side * plan.stop) - slippage) if whole_bar else plan.stop - side * slippage
            status = "stop"
        elif (best if whole_bar else close) >= side * plan.target:
            exit_price = plan.target
            status = "target"
        elif expected >= filled_at + 4 * HOUR:
            exit_price = side * (close - slippage)
            status = "timeout"
        # Excursions are observed lower bounds. Exclude unknown pre-fill/post-exit extremes.
        if exit_price is None:
            favorable = max(favorable, (best if whole_bar else close) - side * fill)
            adverse = max(adverse, side * fill - (worst if whole_bar else close))
        else:
            favorable = max(favorable, side * (exit_price - fill))
            adverse = max(adverse, side * (fill - exit_price))
            break
    return {
        "status": status, "filled": fill is not None, "fill": fill,
        "fill_bar": filled_at.isoformat() if filled_at else None,
        "observed_until": last.isoformat() if last else None, "exit": exit_price,
        "net_r": side * (exit_price - fill) / risk if exit_price is not None else None,
        "mfe_lower_usd": favorable if fill is not None else None,
        "mae_lower_usd": adverse if fill is not None else None,
        "duration_upper_minutes": (last - filled_at).total_seconds() / 60 if filled_at and last else None,
        "assumed_spread": spread, "assumed_slippage_per_market_fill": slippage,
    }
