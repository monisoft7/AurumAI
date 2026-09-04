from __future__ import annotations

import os
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd
from dotenv import load_dotenv
from fredapi import Fred

load_dotenv()

FRED_DAILY_SERIES_MAX_AGE_DAYS = 7


class FredClient:
    """Base FRED API client for fetching US economic data series.

    Wraps fredapi, reads FRED_API_KEY from .env, and provides
    common data-fetching utilities with local CSV caching.
    """

    _DEFAULT_CACHE_DIR = Path("data/economic")

    def __init__(
        self,
        api_key: str | None = None,
        cache_dir: str | Path | None = None,
    ) -> None:
        api_key = api_key if api_key is not None else os.getenv("FRED_API_KEY")
        self._fred = Fred(api_key=api_key) if api_key else None
        self._cache_dir = (
            Path(cache_dir) if cache_dir else self._DEFAULT_CACHE_DIR
        )
        self._freshness: dict[str, dict[str, Any]] = {}

    def get_series(
        self,
        series_id: str,
        observation_start: str | None = None,
        observation_end: str | None = None,
        use_cache: bool = True,
        max_age_days: int | None = None,
    ) -> pd.Series:
        cache_path = self._cache_dir / f"{series_id}.csv"
        cached: pd.Series | None = None
        if use_cache and cache_path.exists():
            cached = self._read_cached_series(cache_path)
            if observation_start:
                cached = cached[cached.index >= observation_start]
            if observation_end:
                cached = cached[cached.index <= observation_end]

        if cached is not None and len(cached) > 0:
            if max_age_days is None:
                return cached
            last_date = pd.Timestamp(cached.index[-1]).normalize()
            age_days = (pd.Timestamp.now().normalize() - last_date).days
            if age_days <= max_age_days:
                self._record_freshness(series_id, "fresh", last_date, age_days)
                return cached
            try:
                fresh = self._fetch_and_cache(
                    series_id, cache_path,
                    observation_start=observation_start,
                    observation_end=observation_end,
                )
                self._record_freshness(
                    series_id, "refreshed", last_date, age_days,
                    refreshed_last_date=(
                        pd.Timestamp(fresh.index[-1]).normalize()
                        if len(fresh) > 0 else None
                    ),
                )
                return fresh
            except Exception as exc:
                self._record_freshness(
                    series_id, "fallback_stale", last_date, age_days,
                    error=str(exc),
                )
                return cached

        return self._fetch_and_cache(
            series_id, cache_path,
            observation_start=observation_start,
            observation_end=observation_end,
        )

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

    def _fetch_and_cache(
        self,
        series_id: str,
        cache_path: Path,
        observation_start: str | None = None,
        observation_end: str | None = None,
    ) -> pd.Series:
        if self._fred is None:
            raise RuntimeError(
                f"FRED_API_KEY is required to fetch {series_id} live; "
                "configure the key or use an available CSV cache."
            )
        raw: pd.Series = self._fred.get_series(
            series_id,
            observation_start=observation_start,
            observation_end=observation_end,
        )
        raw = raw.dropna()

        self._cache_dir.mkdir(parents=True, exist_ok=True)
        df = pd.DataFrame({"Date": raw.index, "Value": raw.values})
        df.to_csv(cache_path, index=False)

        return raw

    def get_dataframe(
        self,
        series_dict: dict[str, str],
        observation_start: str | None = None,
        observation_end: str | None = None,
        use_cache: bool = True,
    ) -> pd.DataFrame:
        frames: list[pd.Series] = []
        for name, series_id in series_dict.items():
            s = self.get_series(
                series_id,
                observation_start=observation_start,
                observation_end=observation_end,
                use_cache=use_cache,
            )
            frames.append(s.rename(name))

        result = pd.concat(frames, axis=1)
        return result

    @property
    def api_key(self) -> str | None:
        return self._fred.api_key if self._fred is not None else None

    def clear_cache(self, series_id: str | None = None) -> None:
        if series_id:
            path = self._cache_dir / f"{series_id}.csv"
            if path.exists():
                path.unlink()
        else:
            import shutil
            if self._cache_dir.exists():
                shutil.rmtree(self._cache_dir)
                self._cache_dir.mkdir(parents=True, exist_ok=True)


class EconomicDataFetcher:
    """High-level fetcher for CompositeScoreBuilder indicators via FRED."""

    _INDICATORS: dict[str, str] = {
        "CPI": "CPIAUCSL",
        "PPI": "PPIACO",
        "PMI": "PMI",
        "UNRATE": "UNRATE",
        "PAYEMS": "PAYEMS",
        "FEDFUNDS": "FEDFUNDS",
        "DGS10": "DGS10",
        "DFF": "DFF",
        "GDP": "GDP",
    }

    def __init__(self, fred_client: FredClient | None = None) -> None:
        self._client = fred_client or FredClient()

    def get_series(
        self, name: str, **kwargs: Any
    ) -> pd.Series:
        series_id = self._INDICATORS.get(name)
        if series_id is None:
            msg = f"Unknown indicator '{name}'. Valid: {list(self._INDICATORS)}"
            raise ValueError(msg)
        return self._client.get_series(series_id, **kwargs)

    def get_all_indicators(
        self, **kwargs: Any
    ) -> dict[str, pd.Series]:
        return {
            name: self._client.get_series(series_id, **kwargs)
            for name, series_id in self._INDICATORS.items()
        }

    def refresh_cache(self) -> None:
        for series_id in self._INDICATORS.values():
            self._client.clear_cache(series_id)
            self._client.get_series(series_id, use_cache=False)
