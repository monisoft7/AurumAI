from __future__ import annotations

import logging
from typing import Any

import numpy as np
import pandas as pd

from connectors.dxy_fetcher import DXYFetcher
from connectors.fred_client import (
    FRED_DAILY_SERIES_MAX_AGE_DAYS,
    FredClient,
)
from pre_market.contracts import OvernightPriceChange

LOG = logging.getLogger(__name__)

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

    The yield freshness policy is enforced at this data boundary by
    default: ``max_age_days`` defaults to
    ``FRED_DAILY_SERIES_MAX_AGE_DAYS`` (7) for the FRED daily series
    (DFII10, DGS10, T5YIE), so a cached observation older than the
    threshold triggers a live refresh with a stale-cache fallback on
    network failure. Pass ``max_age_days=None`` explicitly to restore
    the legacy cache-only behavior (no freshness checks, no refresh).
    """

    def __init__(
        self,
        fred_client: FredClient | None = None,
        lookback_days: int = 10,
        max_age_days: int | None = FRED_DAILY_SERIES_MAX_AGE_DAYS,
    ) -> None:
        self._fred = fred_client or FredClient()
        self._lookback_days = lookback_days
        self._max_age_days = max_age_days

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
                series = self._fred.get_series(
                    series_id, use_cache=True, max_age_days=self._max_age_days
                )
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
                        persistence_days=self._compute_persistence_days(series),
                    ))
            except Exception:
                pass

        self._log_freshness()
        return results

    def _log_freshness(self) -> None:
        report = getattr(self._fred, "freshness_report", lambda: {})()
        for series_id in OVERNIGHT_FRED_SERIES.values():
            record = report.get(series_id)
            if record is None:
                continue
            status = record.get("status")
            if status == "fallback_stale":
                LOG.warning(
                    "FRED %s refresh failed; using stale cached data "
                    "(cache_last_date=%s age_days=%s error=%s)",
                    series_id, record.get("cache_last_date"),
                    record.get("cache_age_days"), record.get("error"),
                )
            elif status == "refreshed":
                LOG.info(
                    "FRED %s refreshed (cache_last_date=%s age_days=%s "
                    "refreshed_last_date=%s)",
                    series_id, record.get("cache_last_date"),
                    record.get("cache_age_days"),
                    record.get("refreshed_last_date"),
                )

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
            persistence_days=self._compute_persistence_days(close),
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

    @staticmethod
    def _compute_persistence_days(series: pd.Series) -> float:
        """Consecutive same-direction daily returns ending at the last bar."""
        returns = series.pct_change().dropna()
        if len(returns) < 1 or abs(returns.iloc[-1]) < 1e-12:
            return 0.0
        last_sign = 1.0 if returns.iloc[-1] > 0 else -1.0
        days = 0
        for ret in reversed(returns.tolist()):
            if abs(ret) < 1e-12:
                break
            if (1.0 if ret > 0 else -1.0) != last_sign:
                break
            days += 1
        return float(days)

    def fetch_all(self, session: str = "APAC") -> dict[str, Any]:
        overnight_changes = self.fetch_overnight_changes(session=session)
        report = getattr(self._fred, "freshness_report", lambda: {})()
        yield_freshness = {
            series_id: report[series_id]
            for series_id in OVERNIGHT_FRED_SERIES.values()
            if series_id in report
        }
        return {
            "overnight_changes": overnight_changes,
            "yield_freshness": yield_freshness,
        }
