"""Read-only MT5 quote adapter. Interpret terminal wall clocks in the configured broker zone."""

import time
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

from .data import clean

UTC = timezone.utc


def broker_utc(raw_ms, zone):
    wall = datetime.fromtimestamp(raw_ms / 1000, UTC).replace(tzinfo=None)
    a = wall.replace(tzinfo=zone, fold=0)
    b = wall.replace(tzinfo=zone, fold=1)
    if a.utcoffset() != b.utcoffset():
        raise ValueError("ambiguous or nonexistent broker wall time")
    return a.astimezone(UTC)


class Feed:
    def __init__(self, zone):
        self.zone = ZoneInfo(zone)

    def __enter__(self):
        import MetaTrader5 as mt

        self.mt = mt
        if not self.mt.initialize(timeout=15000):
            raise RuntimeError("terminal unavailable")
        return self

    def __exit__(self, *unused):
        self.mt.shutdown()

    def quote(self):
        # Demand evidence the feed is advancing now, even when a cached quote looks recent.
        first = self.mt.symbol_info_tick("XAUUSD")
        for _ in range(24):
            time.sleep(0.25)
            q = self.mt.symbol_info_tick("XAUUSD")
            if first and q and q.time_msc > first.time_msc:
                event = broker_utc(q.time_msc, self.zone)
                observed = datetime.now(UTC)
                age = (observed - event).total_seconds()
                # A small broker clock lead can be resolved by waiting until the
                # timestamp is actually in the past. Larger discrepancies fail closed.
                if -2 <= age < 0:
                    time.sleep(-age + 0.01)
                    observed = datetime.now(UTC)
                    age = (observed - event).total_seconds()
                if not 0 <= age <= 90:
                    raise ValueError(f"quote age outside 0..90s ({age:.2f}s)")
                if not (0 < q.bid <= q.ask and np.isfinite(q.ask)):
                    raise ValueError("invalid or crossed quote")
                return {
                    "at": event.isoformat(),
                    "observed": observed.isoformat(),
                    "age_seconds": age,
                    "bid": q.bid,
                    "ask": q.ask,
                    "source": "MT5 XAUUSD",
                    "server_zone": self.zone.key,
                }
        raise ValueError("no advancing market quote")

    def minutes(self, slot):
        rows = self.mt.copy_rates_from_pos("XAUUSD", self.mt.TIMEFRAME_M1, 0, 7200)
        if rows is None or not len(rows):
            raise ValueError("broker minute history unavailable")
        d = pd.DataFrame(rows)
        wall = pd.to_datetime(d.pop("time"), unit="s")
        d.index = wall.dt.tz_localize(
            self.zone.key, ambiguous="NaT", nonexistent="NaT"
        ).dt.tz_convert("UTC")
        frame, _ = clean(d.loc[d.index.notna() & (d.index < slot)])
        return frame

    def ticks(self, start, end):
        def server_time(ms):
            return (
                datetime.fromtimestamp(ms / 1000, UTC)
                .astimezone(self.zone)
                .replace(tzinfo=UTC)
            )

        rows = self.mt.copy_ticks_range(
            "XAUUSD", server_time(start), server_time(end), self.mt.COPY_TICKS_ALL
        )
        if rows is None or not len(rows):
            raise ValueError("tick history unavailable")
        clock = pd.to_datetime(rows["time_msc"], unit="ms").tz_localize(
            self.zone.key, ambiguous="NaT", nonexistent="NaT"
        )
        ms = clock.tz_convert("UTC").as_unit("ns").asi8 // 1_000_000
        bid, ask = rows["bid"], rows["ask"]
        if (
            clock.hasnans
            or np.any(np.diff(ms) < 0)
            or np.any((bid <= 0) | (ask < bid))
            or not np.isfinite([bid, ask]).all()
        ):
            raise ValueError("invalid broker tick path")
        return ms, bid, ask
