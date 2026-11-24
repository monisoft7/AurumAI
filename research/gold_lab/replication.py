"""Recheck the Phase 1 trend subgroup with its original M15 fill engine."""

import argparse
import json
from datetime import datetime, timedelta
import pandas as pd
from .data import CACHE, minute_data
from .strategies import Market, simulate
from .lab import utc, summary
from gold_shadow.strategy import evaluate


def original(year):
    market = Market(minute_data(CACHE / f"histdata-M1-{year}.zip")[0])
    lookup = {at: i for i, at in enumerate(market.m15.index)}
    signals = market.signals("pullback_replication")
    folds = []
    boundaries = (
        [utc(f"{year}-01-01"), utc(f"{year}-07-01"), utc(f"{year + 1}-01-01")]
        if year == 2024
        else [utc("2023-01-01"), utc("2024-01-01")]
    )
    for first, end in zip(boundaries, boundaries[1:]):
        busy = first + timedelta(days=1)
        rows = []
        for t, p in signals:
            if t < busy or t >= end - timedelta(days=1):
                continue
            i = lookup[t]
            result = evaluate(p, t, market.bars[i + 1 : i + 23])
            if result["observed_until"]:
                busy = datetime.fromisoformat(result["observed_until"])
            if p.regime == "trend":
                rows.append((t, result["net_r"], result["status"], result["filled"]))
        folds.extend(rows)
    return summary(folds)


def validation_volatility():
    """Descriptive only. Partition the original validation trades without altering entry rules."""
    from .data import PROTOCOL

    m = Market(minute_data(CACHE / "histdata-M1-2024.zip")[0])
    hourly_range = m.hour.high - m.hour.low
    recent = hourly_range.rolling(16).mean()
    previous = hourly_range.shift(16).rolling(120).mean()
    boundaries = [utc("2024-01-01"), utc("2024-07-01"), utc("2025-01-01")]
    result = {}
    for spec in json.loads(PROTOCOL.read_bytes())["hypotheses"]:
        family = spec["id"]
        signals = m.signals(family)
        groups = {"elevated": [], "normal_or_lower": [], "unknown": []}
        for a, b in zip(boundaries, boundaries[1:]):
            for row in simulate(m, signals, family, a, b):
                hour = row[0].floor("h")
                current, reference = recent.get(hour), previous.get(hour)
                if pd.isna(current) or pd.isna(reference):
                    label = "unknown"
                else:
                    label = "elevated" if current > reference else "normal_or_lower"
                groups[label].append(row)
        result[family] = {label: summary(rows) for label, rows in groups.items()}
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--regimes", action="store_true")
    if parser.parse_args().regimes:
        print(json.dumps(validation_volatility(), indent=2))
    else:
        for year in (2023, 2024):
            print(year, original(year))
