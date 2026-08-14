from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd
import yfinance as yf

DXY_DAILY_SERIES_MAX_AGE_DAYS = 7

_SERIES_ID = "dxy"


class DXYFetcher:
    """Fetches US Dollar Index (DX-Y.NYB) from Yahoo Finance.

    Uses yfinance (free, no API key required) to fetch the ICE US Dollar
    Index daily close prices. Returns empty series on failure rather than
    raising, matching the RealYieldFetcher error-handling pattern.

    Provides the same cache/freshness contract as ``FredClient`` for the
    ``data/context/dxy/dxy.csv`` boundary: a fresh cache is used unchanged,
    a stale cache triggers a refresh, and a failed refresh keeps the stale
    cache while reporting it as ``fallback_stale`` so stale data is never
    presented as current.
    """

    TICKER = "DX-Y.NYB"
    _DEFAULT_CACHE_PATH = Path("data/context/dxy/dxy.csv")

    def __init__(self, cache_dir: str | Path | None = None) -> None:
        if cache_dir is not None:
            self._cache_path = Path(cache_dir) / "dxy.csv"
        else:
            self._cache_path = self._DEFAULT_CACHE_PATH
        self._freshness: dict[str, dict[str, Any]] = {}

    def get_series(
        self,
        use_cache: bool = True,
        max_age_days: int | None = None,
    ) -> pd.Series:
        cache_path = self._cache_path
        cached: pd.Series | None = None
        if use_cache and cache_path.exists():
            cached = self._read_cached_series(cache_path)

        if cached is not None and len(cached) > 0:
            if max_age_days is None:
                return cached
            last_date = pd.Timestamp(cached.index[-1]).normalize()
            age_days = (pd.Timestamp.now().normalize() - last_date).days
            if age_days <= max_age_days:
                self._record_freshness(_SERIES_ID, "fresh", last_date, age_days)
                return cached
            try:
                fresh = self._fetch_and_cache(cache_path)
                self._record_freshness(
                    _SERIES_ID, "refreshed", last_date, age_days,
                    refreshed_last_date=(
                        pd.Timestamp(fresh.index[-1]).normalize()
                        if len(fresh) > 0 else None
                    ),
                )
                return fresh
            except Exception as exc:
                self._record_freshness(
                    _SERIES_ID, "fallback_stale", last_date, age_days,
                    error=str(exc),
                )
                return cached

        try:
            return self._fetch_and_cache(cache_path)
        except Exception:
            return pd.Series(dtype="float64")

    def freshness_report(self) -> dict[str, dict[str, Any]]:
        return {series_id: dict(record) for series_id, record in self._freshness.items()}

    def _record_freshness(
        self,
        series_id: str,
        status: str,
        cache_last_date: pd.Timestamp | None,
        cache_age_days: int,
        refreshed_last_date: pd.Timestamp | None = None,
        error: str | None = None,
    ) -> None:
        self._freshness[series_id] = {
            "series_id": series_id,
            "status": status,
            "cache_last_date": (
                cache_last_date.date().isoformat()
                if cache_last_date is not None else None
            ),
            "cache_age_days": cache_age_days,
            "refreshed_last_date": (
                refreshed_last_date.date().isoformat()
                if refreshed_last_date is not None else None
            ),
            "error": error,
            "checked_at": datetime.now(timezone.utc).isoformat(),
        }

    @staticmethod
    def _read_cached_series(cache_path: Path) -> pd.Series:
        df = pd.read_csv(cache_path, parse_dates=["Date"])
        df = df.dropna(subset=["Date", "Value"]).sort_values("Date")
        series = df.set_index("Date")["Value"]
        return pd.to_numeric(series, errors="coerce")

    def _fetch_and_cache(self, cache_path: Path) -> pd.Series:
        raw = self._download()
        self._cache_path.parent.mkdir(parents=True, exist_ok=True)
        df = pd.DataFrame({"Date": raw.index, "Value": raw.values})
        df.to_csv(cache_path, index=False)
        return raw

    def _download(
        self,
        period: str = "max",
        start: str | None = None,
        end: str | None = None,
    ) -> pd.Series:
        data = yf.download(
            self.TICKER,
            period=period,
            start=start,
            end=end,
            progress=False,
            auto_adjust=True,
        )
        if data is None or data.empty:
            raise ConnectionError(f"yfinance returned no {self.TICKER} data")
        close = data["Close"].squeeze()
        close = close.dropna()
        if len(close) == 0:
            raise ConnectionError(f"yfinance returned no {self.TICKER} data")
        return close

    def fetch(
        self,
        period: str = "max",
        start: str | None = None,
        end: str | None = None,
    ) -> pd.Series:
        try:
            return self._download(period=period, start=start, end=end)
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
