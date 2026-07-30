from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any

import pandas as pd
from dotenv import load_dotenv
from fredapi import Fred

load_dotenv()


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
        self._fred = Fred(api_key=api_key) if api_key is not None else Fred()
        self._cache_dir = (
            Path(cache_dir) if cache_dir else self._DEFAULT_CACHE_DIR
        )

    def get_series(
        self,
        series_id: str,
        observation_start: str | None = None,
        observation_end: str | None = None,
        use_cache: bool = True,
    ) -> pd.Series:
        cache_path = self._cache_dir / f"{series_id}.csv"
        if use_cache and cache_path.exists():
            df = pd.read_csv(
                cache_path, parse_dates=["Date"]
            )
            df = df.dropna(subset=["Date", "Value"]).sort_values("Date")
            series = df.set_index("Date")["Value"]
            series = pd.to_numeric(series, errors="coerce")
            if observation_start:
                series = series[series.index >= observation_start]
            if observation_end:
                series = series[series.index <= observation_end]
            return series

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
        return self._fred.api_key

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
