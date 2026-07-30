from __future__ import annotations

from datetime import date

import pandas as pd

from connectors.fred_client import FredClient


class RealYieldFetcher:
    """Fetches US 10-Year Real Yield (DFII10) from FRED.

    Wraps FredClient with DFII10-specific logic: observation window,
    latest-value convenience, and error handling. Returns empty series
    on failure rather than raising.
    """

    SERIES_ID = "DFII10"

    def __init__(self, fred_client: FredClient | None = None) -> None:
        self._client = fred_client or FredClient()

    def fetch(
        self,
        observation_start: str | None = None,
        observation_end: str | None = None,
        use_cache: bool = True,
    ) -> pd.Series:
        try:
            series = self._client.get_series(
                self.SERIES_ID,
                observation_start=observation_start,
                observation_end=observation_end,
                use_cache=use_cache,
            )
            if isinstance(series, pd.Series) and len(series) > 0:
                return series.dropna()
            return pd.Series(dtype="float64")
        except Exception:
            return pd.Series(dtype="float64")

    def fetch_latest(
        self,
        use_cache: bool = True,
    ) -> tuple[pd.Timestamp | None, float | None]:
        series = self.fetch(use_cache=use_cache)
        if len(series) == 0:
            return None, None
        return series.index[-1], float(series.iloc[-1])

    def fetch_window(
        self,
        window_observations: int = 1260,
        use_cache: bool = True,
    ) -> pd.Series:
        if window_observations <= 0:
            return pd.Series(dtype="float64")
        series = self.fetch(use_cache=use_cache)
        if len(series) == 0:
            return series
        return series.iloc[-window_observations:]
