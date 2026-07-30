from __future__ import annotations

import pandas as pd
import yfinance as yf


class DXYFetcher:
    """Fetches US Dollar Index (DX-Y.NYB) from Yahoo Finance.

    Uses yfinance (free, no API key required) to fetch the ICE US Dollar
    Index daily close prices. Returns empty series on failure rather than
    raising, matching the RealYieldFetcher error-handling pattern.
    """

    TICKER = "DX-Y.NYB"

    def fetch(
        self,
        period: str = "max",
        start: str | None = None,
        end: str | None = None,
    ) -> pd.Series:
        try:
            data = yf.download(
                self.TICKER,
                period=period,
                start=start,
                end=end,
                progress=False,
                auto_adjust=True,
            )
            if data.empty:
                return pd.Series(dtype="float64")
            close = data["Close"].squeeze()
            close = close.dropna()
            return close
        except Exception:
            return pd.Series(dtype="float64")

    def fetch_latest(
        self,
        period: str = "1mo",
    ) -> tuple[pd.Timestamp | None, float | None]:
        series = self.fetch(period=period)
        if len(series) == 0:
            return None, None
        return series.index[-1], float(series.iloc[-1])

    def fetch_window(
        self,
        window_observations: int = 1260,
        period: str = "max",
    ) -> pd.Series:
        if window_observations <= 0:
            return pd.Series(dtype="float64")
        series = self.fetch(period=period)
        if len(series) == 0:
            return series
        return series.iloc[-window_observations:]
