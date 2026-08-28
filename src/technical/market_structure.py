"""Minimal deterministic market-structure analysis for the research desk.

Close-based swing pivots with a symmetric confirmation window, plus the
simplest defensible structure classification (HH/HL vs LH/LL) and a
break-of-structure flag.  Deliberately no Order Blocks / FVG / liquidity
maps: those are not required by any current consumer.

All functions are pure and deterministic: identical input frames produce
identical output.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

DEFAULT_PIVOT_WINDOW = 3


@dataclass(frozen=True)
class StructureResult:
    structure_state: str | None
    bos_flag: str | None
    last_swing_high: float | None
    last_swing_low: float | None
    pivot_high_count: int
    pivot_low_count: int


def find_swing_pivots(
    close: pd.Series,
    window: int = DEFAULT_PIVOT_WINDOW,
) -> tuple[list[int], list[int]]:
    """Return indices of confirmed swing highs and swing lows.

    A bar ``i`` is a pivot high when ``close[i]`` is strictly greater than
    every close in the symmetric window around it; ties produce no pivot so
    the result is deterministic.  Confirmation needs ``window`` bars on both
    sides -- all of which lie inside the caller's as-of slice, so no future
    information beyond the assessment time is used.
    """
    values = close.to_numpy(dtype=float)
    n = len(values)
    highs: list[int] = []
    lows: list[int] = []
    for i in range(window, n - window):
        segment = values[i - window : i + window + 1]
        center = values[i]
        others = np.delete(segment, window)
        if center > others.max():
            highs.append(i)
        elif center < others.min():
            lows.append(i)
    return highs, lows


def analyze_structure(
    close: pd.Series,
    window: int = DEFAULT_PIVOT_WINDOW,
) -> StructureResult:
    """Classify trend structure from the last two confirmed swings."""
    high_idx, low_idx = find_swing_pivots(close, window)
    values = close.to_numpy(dtype=float)

    last_high = float(values[high_idx[-1]]) if high_idx else None
    last_low = float(values[low_idx[-1]]) if low_idx else None

    structure: str | None = None
    if len(high_idx) >= 2 and len(low_idx) >= 2:
        hh = values[high_idx[-1]] > values[high_idx[-2]]
        hl = values[low_idx[-1]] > values[low_idx[-2]]
        lh = values[high_idx[-1]] < values[high_idx[-2]]
        ll = values[low_idx[-1]] < values[low_idx[-2]]
        if hh and hl:
            structure = "uptrend"
        elif lh and ll:
            structure = "downtrend"
        else:
            structure = "range"

    bos: str | None = None
    if len(values) > 0 and last_high is not None and last_low is not None:
        # Only the most recent confirmed swing pair bounds the current price;
        # a close outside that band is the minimal deterministic BOS signal.
        if values[-1] > last_high:
            bos = "bullish_bos"
        elif values[-1] < last_low:
            bos = "bearish_bos"

    return StructureResult(
        structure_state=structure,
        bos_flag=bos,
        last_swing_high=last_high,
        last_swing_low=last_low,
        pivot_high_count=len(high_idx),
        pivot_low_count=len(low_idx),
    )
