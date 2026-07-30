from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from connectors.dxy_fetcher import DXYFetcher
from connectors.fred_client import FredClient
from pre_market.contracts import OvernightPriceChange

OVERNIGHT_TICKERS: dict[str, dict[str, Any]] = {
    "XAU/USD": {"source": "yfinance", "ticker": "GC=F"},
    "DXY": {"source": "yfinance", "ticker": "DX-Y.NYB"},
    "S&P 500 Futures": {"source": "yfinance", "ticker": "ES=F"},
    "Brent Crude": {"source": "yfinance", "ticker": "BZ=F"},
    "EUR/USD": {"source": "yfinance", "ticker": "EURUSD=X"},
    "USD/JPY": {"source": "yfinance", "ticker": "USDJPY=X"},
}

OVERNIGHT_FRED_SERIES: dict[str, str] = {
    "US10Y Real Yield": "DFII10",
    "US10Y Nominal Yield": "DGS10",
    "Breakeven Inflation": "T5YIE",
}


class OvernightDataFetcher:
    """Batch fetcher for overnight market data across APAC/European sessions.

    Uses yfinance for price instruments and FRED for yield series.
    Returns empty lists on failure rather than raising.
    """

    def __init__(
        self,
        fred_client: FredClient | None = None,
        lookback_days: int = 5,
    ) -> None:
        self._fred = fred_client or FredClient()
        self._lookback_days = lookback_days

    def fetch_overnight_changes(
        self,
        session: str = "APAC",
    ) -> list[OvernightPriceChange]:
        results: list[OvernightPriceChange] = []

        for name, info in OVERNIGHT_TICKERS.items():
            try:
                change = self._fetch_yfinance_change(name, info["ticker"], session)
                if change is not None:
                    results.append(change)
            except Exception:
                pass

        for name, series_id in OVERNIGHT_FRED_SERIES.items():
            try:
                series = self._fred.get_series(series_id, use_cache=True)
                if isinstance(series, pd.Series) and len(series) >= 2:
                    prev = float(series.iloc[-2])
                    curr = float(series.iloc[-1])
                    if abs(prev) > 1e-12:
                        pct = (curr - prev) / abs(prev) * 100.0
                    else:
                        pct = 0.0
                    sigma = self._compute_sigma(series, prev, curr)
                    results.append(OvernightPriceChange(
                        instrument=name,
                        previous_close=round(prev, 4),
                        current_price=round(curr, 4),
                        change_pct=round(pct, 4),
                        change_sigma=round(sigma, 4),
                        session=session,
                    ))
            except Exception:
                pass

        return results

    def _fetch_yfinance_change(
        self,
        name: str,
        ticker: str,
        session: str,
    ) -> OvernightPriceChange | None:
        import yfinance as yf

        data = yf.download(ticker, period=f"{self._lookback_days}d", progress=False, auto_adjust=True)
        if data.empty:
            return None
        close = data["Close"].squeeze().dropna()
        if len(close) < 2:
            return None
        prev = float(close.iloc[-2])
        curr = float(close.iloc[-1])
        if abs(prev) > 1e-12:
            pct = (curr - prev) / abs(prev) * 100.0
        else:
            pct = 0.0
        sigma = self._compute_sigma(close, prev, curr)
        return OvernightPriceChange(
            instrument=name,
            previous_close=round(prev, 4),
            current_price=round(curr, 4),
            change_pct=round(pct, 4),
            change_sigma=round(sigma, 4),
            session=session,
        )

    @staticmethod
    def _compute_sigma(series: pd.Series, prev: float, curr: float) -> float:
        if len(series) < 5:
            return 0.0
        returns = series.pct_change().dropna()
        if len(returns) < 4 or returns.std() < 1e-12:
            return 0.0
        single_return = (curr - prev) / abs(prev) if abs(prev) > 1e-12 else 0.0
        return float(single_return / returns.std())

    def fetch_all(self, session: str = "APAC") -> dict[str, Any]:
        return {
            "overnight_changes": self.fetch_overnight_changes(session=session),
        }
