from __future__ import annotations

import numpy as np
import pandas as pd

TREND_FLAT = "flat"
TREND_RISING = "rising"
TREND_FALLING = "falling"


def derive_trend_states(
    dates: pd.Series,
    values: pd.Series,
    lookback_days: int,
    threshold: float,
) -> list[str]:
    """Chronological prefix fold of the trend state machine (Correction 029).

    Deterministic and stateless: the state after each observation depends only
    on the observations up to and including it, never on a persisted value.

    State transitions on the raw measure
    ``change(i) = value(i) - value(latest_on_or_before(i - lookback_days))``:

        flat:   change >  +threshold -> rising
                change <  -threshold -> falling
                otherwise            -> flat
        rising: change <= 0.0        -> flat
                change >  0.0        -> rising
        falling: change >= 0.0       -> flat
                change <  0.0        -> falling

    No direct rising <-> falling transition.  Threshold equality stays flat;
    the release boundary is the zero crossing.
    """
    dates = pd.Series(dates).reset_index(drop=True)
    values = np.asarray(values, dtype=float)

    states: list[str] = []
    state = TREND_FLAT
    for i in range(len(dates)):
        anchor = dates.iloc[i] - pd.Timedelta(days=lookback_days)
        positions = dates.searchsorted(anchor, side="right")
        if positions > 0:
            change = round(
                float(values[i]) - float(values[int(positions) - 1]), 6
            )
            state = _transition(state, change, threshold)
        states.append(state)
    return states


def trend_state_at(
    dates: pd.Series,
    values: pd.Series,
    as_of: pd.Timestamp,
    lookback_days: int,
    threshold: float,
) -> str:
    """Trend state at ``as_of``: the fold over observations on or before it.

    Uses only observations <= as_of (no lookahead), so an old as-of date is
    independent of the current date and of any later observations.
    """
    dates = pd.Series(dates).reset_index(drop=True)
    values = np.asarray(values, dtype=float)
    positions = dates.searchsorted(pd.Timestamp(as_of), side="right")
    if positions <= 0:
        return TREND_FLAT
    states = derive_trend_states(
        dates.iloc[: int(positions)],
        values[: int(positions)],
        lookback_days,
        threshold,
    )
    return states[-1]


def _transition(state: str, change: float, threshold: float) -> str:
    if state == TREND_RISING:
        if change <= 0.0:
            return TREND_FLAT
        return TREND_RISING
    if state == TREND_FALLING:
        if change >= 0.0:
            return TREND_FLAT
        return TREND_FALLING
    if change > threshold:
        return TREND_RISING
    if change < -threshold:
        return TREND_FALLING
    return TREND_FLAT
