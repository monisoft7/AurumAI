"""Audit the historical bid-minute approximation on the preregistered April 2023 tick sample."""

import json
import zipfile
import numpy as np
import pandas as pd
from .data import EST, PROTOCOL, acquire, minute_data, digest
from .strategies import Market
from .ticks import settle


def audit():
    path = acquire(2023, 4)
    with (
        zipfile.ZipFile(path) as z,
        z.open(next(n for n in z.namelist() if n.lower().endswith(".csv"))) as f,
    ):
        ticks = pd.read_csv(f, names=["at", "bid", "ask", "volume"])
    times = (
        pd.DatetimeIndex(pd.to_datetime(ticks["at"], format="%Y%m%d %H%M%S%f"))
        .tz_localize(EST)
        .asi8
        // 1_000_000
    )
    bids = ticks.bid.to_numpy()
    asks = ticks.ask.to_numpy()
    if (
        np.any(np.diff(times) < 0)
        or not np.isfinite([bids, asks]).all()
        or np.any((asks < bids) | (bids <= 0))
    ):
        raise ValueError("invalid tick data")
    minutes, _ = minute_data(acquire(2023))
    m = Market(minutes.loc["2023-03-29":"2023-05-01"])
    results = {}
    for spec in json.loads(PROTOCOL.read_bytes())["hypotheses"]:
        family = spec["id"]
        pairs = []
        known = 0
        count = 0
        busy = pd.Timestamp("2023-04-03", tz="UTC")
        for t, plan in m.signals(family):
            if t < busy or t >= pd.Timestamp("2023-04-29", tz="UTC"):
                continue
            status, r, n, filled = m.outcome(t, plan)
            busy = t + pd.Timedelta(minutes=n)
            if family == "pullback_replication" and plan.regime != "trend":
                continue
            ms = int(t.value // 1_000_000)
            actual = settle(times, bids, asks, ms, plan, ms + 5 * 3600000 + 300001)
            count += 1
            known += actual["status"] == status
            if r is not None and actual["net_r"] is not None:
                pairs.append((r, actual["net_r"]))
        results[family] = {
            "orders": count,
            "matching_status": known,
            "both_closed": len(pairs),
            "paired_mean_r_bid_model_and_ticks": np.mean(pairs, axis=0)
            .round(5)
            .tolist()
            if pairs
            else None,
        }
    return {
        "tick_sha256": digest(path),
        "ticks": len(times),
        "spread_quantiles_50_95": np.quantile(asks - bids, [0.5, 0.95])
        .round(4)
        .tolist(),
        "comparison": results,
    }


if __name__ == "__main__":
    print(json.dumps(audit(), indent=2))
