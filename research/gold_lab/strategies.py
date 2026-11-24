"""Causal M15/H1/H4 signals and minute bid-side paper execution for the locked registry."""

import sys
from dataclasses import replace

import numpy as np
import pandas as pd

from .data import ROOT

sys.path.insert(0, str(ROOT / "src"))
from gold_shadow.market import Bar, STEP
from gold_shadow.strategy import Plan, decide

H = pd.Timedelta(hours=1)
OHLC = {"open": "first", "high": "max", "low": "min", "close": "last"}


def completed(frame, minutes):
    groups = frame.resample(f"{minutes}min")
    result = groups.agg(OHLC)
    result = result.loc[groups.size() == minutes]
    result.index += pd.Timedelta(minutes=minutes)
    return result


def market(side, price, risk, regime, reason):
    return Plan(
        ("BUY" if side > 0 else "SELL") + " NOW",
        regime,
        reason,
        price,
        price - side * risk,
        price + 1.5 * side * risk,
    )


class Market:
    def __init__(self, minutes):
        self.bid = minutes[["open", "high", "low", "close"]].to_numpy()
        self.clock = minutes.index.as_unit("ns").asi8 // 60_000_000_000
        # A constant baseline half-spread translates bid candles into indicative mids.
        # Stress changes execution only. No future spread enters a feature.
        mid = minutes + 0.25
        self.m15 = completed(mid, 15)
        self.bars = [
            Bar(t.to_pydatetime() - STEP, *r)
            for t, r in zip(self.m15.index, self.m15.to_numpy())
        ]
        self.hour = completed(mid, 60)
        self.four = completed(mid, 240)
        self.hour_range = (self.hour.high - self.hour.low).rolling(16).mean().shift()
        self.h4_range = (self.four.high - self.four.low).rolling(5).mean().shift()
        # Use candles starting at 00:00 through 05:45 UTC.
        asia = self.m15[
            (self.m15.index.hour * 60 + self.m15.index.minute).isin(range(15, 361, 15))
        ]
        self.asia = {
            day: (g.high.max(), g.low.min())
            for day, g in asia.groupby(asia.index.date)
            if len(g) == 24
        }

    def signals(self, family, scale=1):
        signals = []
        for i, t in enumerate(self.m15.index):
            if t.weekday() >= 5:
                continue
            price = self.bars[i].close
            if family in ("pullback_replication", "long_only", "momentum"):
                if not 6 <= t.hour < 16:
                    continue
                policy = "combined" if family == "pullback_replication" else family
                plan = decide(
                    self.bars[max(0, i - 32) : i + 1], t.to_pydatetime(), policy
                )
                if not plan.entry:
                    continue
                if scale != 1 and plan.regime == "trend":
                    offset = (plan.entry - price) * (scale - 1)
                    plan = replace(
                        plan,
                        entry=plan.entry + offset,
                        stop=plan.stop + offset,
                        target=plan.target + offset,
                    )
            elif family == "london_asia":
                local = t.tz_convert("Europe/London")
                if (
                    not 480
                    <= local.hour * 60 + local.minute
                    < 600 + round((scale - 1) * 150)
                ):
                    continue
                limits = self.asia.get(t.date())
                if (
                    not limits
                    or i == 0
                    or t - self.m15.index[i - 1] != pd.Timedelta(minutes=15)
                ):
                    continue
                hi, lo = limits
                prev = self.bars[i - 1].close
                if prev <= hi < price:
                    side = 1
                elif prev >= lo > price:
                    side = -1
                else:
                    continue
                plan = market(
                    side, price, max(hi - lo, 0.01), "London", "Asian range break"
                )
            else:
                if t.minute or t not in self.hour.index:
                    continue
                avg = self.hour_range.get(t)
                if not np.isfinite(avg) or avg <= 0:
                    continue
                if family == "ny_exhaustion":
                    if not 9 <= t.tz_convert("America/New_York").hour < 12:
                        continue
                    impulse = price - self.hour.at[t, "open"]
                    if abs(impulse) < 2 * scale * avg:
                        continue
                    plan = market(
                        -np.sign(impulse), price, avg, "NY", "hourly shock fade"
                    )
                elif family == "h4_compression":
                    boundary = (t - H).floor("4h")
                    normal = self.h4_range.get(boundary, np.nan)
                    if not np.isfinite(normal) or boundary not in self.four.index:
                        continue
                    row = self.four.loc[boundary]
                    if row.high - row.low >= 0.8 * scale * normal:
                        continue
                    prev = self.hour.at[t, "open"]
                    if prev <= row.high < price:
                        side = 1
                    elif prev >= row.low > price:
                        side = -1
                    else:
                        continue
                    plan = market(
                        side,
                        price,
                        avg,
                        "compression",
                        "H1 close outside compressed H4",
                    )
                else:
                    raise ValueError("unregistered strategy")
            signals.append((t, plan))
        return signals

    def outcome(self, issued, p, cost=1):
        start = issued.value // 60_000_000_000
        pos = self.clock.searchsorted(start)
        side = 1 if p.action.startswith("BUY") else -1
        spread, slip = 0.5 * cost, 0.1 * cost
        risk = abs(p.entry - p.stop)
        fill = None
        holding = 0
        for elapsed in range(300):
            j = pos + elapsed
            if j >= len(self.clock) or self.clock[j] != start + elapsed:
                return "unobserved", None, 300, fill is not None
            op, hi, lo, cl = self.bid[j]
            # Signed prices increase in the trade's favour for both sides.
            a, b = (lo, hi) if side == 1 else (-hi, -lo)
            entry_adj = spread if side == 1 else 0.0
            exit_adj = 0.0 if side == 1 else -spread
            op, cl = side * op, side * cl
            whole = fill is not None
            if fill is None:
                if p.action.endswith("NOW"):
                    fill = op + entry_adj + slip
                    whole = True
                elif a + entry_adj <= side * p.entry:
                    fill = min(op + entry_adj, side * p.entry)
                    whole = op + entry_adj <= side * p.entry
                elif elapsed + 1 == 60:
                    return "expired", None, 60, False
                else:
                    continue
            holding += 1
            stop, target = side * p.stop, side * p.target
            if whole and op + exit_adj >= target:
                status, exit_at = "target", target
            elif a + exit_adj <= stop:
                status, exit_at = (
                    "stop",
                    (min(op + exit_adj, stop) if whole else stop) - slip,
                )
            elif (b if whole else cl) + exit_adj >= target:
                status, exit_at = "target", target
            elif holding == 240:
                status, exit_at = "timeout", cl + exit_adj - slip
            else:
                continue
            return status, (exit_at - fill) / risk, elapsed + 1, True
        raise AssertionError("order exceeded declared horizon")


def simulate(market_data, signals, family, first, end, cost=1):
    busy = first
    records = []
    for t, p in signals:
        if t < max(first + pd.Timedelta(days=1), busy) or t >= end - pd.Timedelta(
            days=1
        ):
            continue
        status, net, duration, filled = market_data.outcome(t, p, cost)
        busy = t + pd.Timedelta(minutes=duration)
        # Keep the prior combined policy's range-order occupancy when testing its trend subset.
        if family != "pullback_replication" or p.regime == "trend":
            records.append((t, net, status, filled))
    return records
