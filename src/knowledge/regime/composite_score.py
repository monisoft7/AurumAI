from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import pandas as pd

if TYPE_CHECKING:
    from connectors.fred_client import EconomicDataFetcher


class CompositeScoreBuilder:
    """Produces a monthly composite_score DataFrame from raw economic CSVs
    or live FRED API data.

    Reads 5 monthly indicators (CPI, PPI, PMI, UNRATE, PAYEMS),
    transforms each into a z-score, and averages them into
    a single ``composite_score`` per month.
    """

    _INDICATORS: dict[str, str] = {
        "CPI": "CPIAUCSL.csv",
        "PPI": "PPIACO.csv",
        "PMI": "PMI.csv",
        "UNRATE": "UNRATE.csv",
        "PAYEMS": "PAYEMS.csv",
    }

    _FRED_INDICATORS: dict[str, str] = {
        "CPI": "CPIAUCSL",
        "PPI": "PPIACO",
        "PMI": "PMI",
        "UNRATE": "UNRATE",
        "PAYEMS": "PAYEMS",
    }

    def __init__(
        self,
        data_dir: str | Path = "data/economic/",
        fred_fetcher: EconomicDataFetcher | None = None,
    ) -> None:
        self._data_dir = Path(data_dir)
        self._fred_fetcher = fred_fetcher

    def build(self) -> pd.DataFrame:
        if self._fred_fetcher is not None:
            return self._build_from_fred()
        return self._build_from_csv()

    def _build_from_csv(self) -> pd.DataFrame:
        z_scores: list[pd.Series] = []
        common_index: pd.DatetimeIndex | None = None

        for name, filename in self._INDICATORS.items():
            series = self._load_and_transform_csv(name, filename)
            if series is None:
                continue
            z = self._z_score(series)
            if common_index is None:
                common_index = z.index
            else:
                common_index = common_index.union(z.index)
            z_scores.append(z.rename(name))

        if not z_scores or common_index is None:
            return pd.DataFrame(columns=["Date", "composite_score"])

        aligned = [z.reindex(common_index) for z in z_scores]
        composite = pd.concat(aligned, axis=1).mean(axis=1, skipna=True)
        composite = composite.dropna()

        return pd.DataFrame({
            "Date": composite.index,
            "composite_score": composite.values.round(6),
        }).reset_index(drop=True)

    def _build_from_fred(self) -> pd.DataFrame:
        z_scores: list[pd.Series] = []
        common_index: pd.DatetimeIndex | None = None

        for name in self._FRED_INDICATORS:
            series = self._load_and_transform_fred(name)
            if series is None:
                continue
            z = self._z_score(series)
            if common_index is None:
                common_index = z.index
            else:
                common_index = common_index.union(z.index)
            z_scores.append(z.rename(name))

        if not z_scores or common_index is None:
            return pd.DataFrame(columns=["Date", "composite_score"])

        aligned = [z.reindex(common_index) for z in z_scores]
        composite = pd.concat(aligned, axis=1).mean(axis=1, skipna=True)
        composite = composite.dropna()

        return pd.DataFrame({
            "Date": composite.index,
            "composite_score": composite.values.round(6),
        }).reset_index(drop=True)

    def _load_and_transform_csv(
        self, name: str, filename: str,
    ) -> pd.Series | None:
        path = self._data_dir / filename
        if not path.exists():
            return None
        df = pd.read_csv(path, parse_dates=["Date"])
        df = df.dropna(subset=["Date", "Value"]).sort_values("Date")
        df["Value"] = pd.to_numeric(df["Value"], errors="coerce")

        if df["Value"].isna().all():
            return None

        return self._transform_series(name, df.set_index("Date")["Value"])

    def _load_and_transform_fred(self, name: str) -> pd.Series | None:
        if self._fred_fetcher is None:
            return None
        try:
            raw = self._fred_fetcher.get_series(name)
        except (KeyError, ValueError, Exception):
            return None
        if raw.empty or raw.isna().all():
            return None
        return self._transform_series(name, raw)

    @staticmethod
    def _transform_series(name: str, series: pd.Series) -> pd.Series:
        series = pd.to_numeric(series, errors="coerce").dropna()
        if name in ("CPI", "PPI", "PAYEMS"):
            result = series.pct_change(12).dropna() * 100.0
        elif name == "UNRATE":
            result = series * -1.0
        elif name == "PMI":
            result = series - 50.0
        else:
            result = series
        return result

    @staticmethod
    def _z_score(series: pd.Series) -> pd.Series:
        std = series.std()
        if std < 1e-12:
            return series * 0.0
        return (series - series.mean()) / std
