"""Read-only M5 adapter. Unknown source clock is a hard data gate."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd
import numpy as np


@dataclass(frozen=True)
class ClockEvidence:
    source_timezone: str  # Verified IANA zone, e.g. Europe/Helsinki, or UTC.
    timestamp_basis: str  # 'open' or 'close', established from source export.
    evidence_reference: str  # Auditable export specification or paired clock log.

    def __post_init__(self) -> None:
        if not self.source_timezone or not self.evidence_reference.strip():
            raise ValueError("DATA_REQUIRED: timestamp timezone evidence missing")
        if self.timestamp_basis not in {"open", "close"}:
            raise ValueError("DATA_REQUIRED: bar timestamp basis missing")
        ZoneInfo(self.source_timezone)


def _utc(local: datetime, zone: ZoneInfo) -> datetime:
    one = local.replace(tzinfo=zone, fold=0)
    two = local.replace(tzinfo=zone, fold=1)
    if one.utcoffset() != two.utcoffset():
        raise ValueError(f"ambiguous DST timestamp: {local}")
    utc = one.astimezone(timezone.utc)
    if utc.astimezone(zone).replace(tzinfo=None) != local:
        raise ValueError(f"nonexistent DST timestamp: {local}")
    return utc


def read_m5(path: Path, clock: ClockEvidence | None) -> pd.DataFrame:
    """Load OHLCV and convert spread_points once (point=0.01 USD/oz)."""
    if clock is None:
        raise ValueError("DATA_REQUIRED: source timezone and bar basis unproven")
    frame = pd.read_csv(path)
    expected = ["timestamp", "open", "high", "low", "close", "volume", "spread_points"]
    if list(frame.columns) != expected:
        raise ValueError("unexpected Gold Hedge M5 schema")
    if frame.empty or frame.isna().any().any():
        raise ValueError("missing M5 values")
    stamp = pd.to_datetime(frame.timestamp, errors="raise")
    if stamp.dt.tz is not None or not stamp.is_monotonic_increasing or stamp.duplicated().any():
        raise ValueError("expected ordered unique naive source timestamps")
    if ((stamp.dt.minute % 5 != 0) | (stamp.dt.second != 0)).any():
        raise ValueError("unaligned M5 timestamp")
    numeric = ["open", "high", "low", "close", "volume", "spread_points"]
    numbers = frame[numeric].apply(pd.to_numeric, errors="coerce")
    if not np.isfinite(numbers.to_numpy(dtype=float)).all():
        raise ValueError("non-numeric M5 values")
    frame[numeric] = numbers
    if ((frame[["open", "high", "low", "close"]] <= 0).any(axis=1)
            | (frame.high < frame[["open", "close", "low"]].max(axis=1))
            | (frame.low > frame[["open", "close", "high"]].min(axis=1))
            | (frame.volume < 0) | (frame.spread_points < 0)).any():
        raise ValueError("invalid M5 OHLCV or spread")
    zone = ZoneInfo(clock.source_timezone)
    close_times = [_utc(value.to_pydatetime(), zone) +
                   (timedelta(minutes=5) if clock.timestamp_basis == "open" else timedelta())
                   for value in stamp]
    result = frame.drop(columns=["timestamp", "spread_points"]).copy()
    result["spread"] = frame.spread_points.astype(float) * 0.01
    result.index = pd.DatetimeIndex(close_times, name="available_at")
    if not result.index.is_monotonic_increasing or not result.index.is_unique:
        raise ValueError("converted UTC timestamps are not ordered unique")
    return result


def aggregate_complete(m5: pd.DataFrame, timeframe: str) -> pd.DataFrame:
    """Aggregate only contiguous, complete UTC groups; never forward fill."""
    size = {"M15": 3, "H1": 12}.get(timeframe)
    if size is None:
        raise ValueError("timeframe must be M15 or H1")
    if not isinstance(m5.index, pd.DatetimeIndex) or m5.index.tz is None:
        raise ValueError("M5 UTC close timestamps required")
    if not m5.index.is_monotonic_increasing or not m5.index.is_unique:
        raise ValueError("unordered or duplicate M5 timestamps")
    duration = f"{5 * size}min"
    records = []
    for end, group in m5.groupby(m5.index.ceil(duration), sort=True):
        if len(group) != size:
            continue
        expected = pd.date_range(end=end, periods=size, freq="5min", tz="UTC")
        if not group.index.equals(expected):
            continue
        records.append((end, float(group.open.iloc[0]), float(group.high.max()),
                        float(group.low.min()), float(group.close.iloc[-1]),
                        float(group.volume.sum()), float(group.spread.iloc[-1])))
    return pd.DataFrame(records, columns=["available_at", "open", "high", "low", "close", "volume", "spread"]).set_index("available_at")


class GoldHedgeProvider:
    def __init__(self, path: Path, clock: ClockEvidence | None):
        m5 = read_m5(path, clock)
        self.frames = {tf: aggregate_complete(m5, tf) for tf in ("M15", "H1")}

    def completed(self, timeframe: str, as_of: datetime) -> pd.DataFrame:
        if as_of.tzinfo is None:
            raise ValueError("as_of must be timezone-aware")
        return self.frames[timeframe].loc[:as_of.astimezone(timezone.utc)].copy()
