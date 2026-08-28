from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pandas as pd

if TYPE_CHECKING:
    from connectors.fred_client import EconomicDataFetcher

SYNTHETIC_INDEX_FILENAME = "synthetic_data_index.json"


def load_synthetic_exclusions(data_dir: str | Path) -> dict[str, dict[str, Any]]:
    """Load the synthetic-data index for *data_dir* (Final Hardening, D-03).

    ``synthetic_data_index.json`` lists CSV files in that directory that are
    machine-generated placeholders (rng-seeded) rather than observed market /
    macro data.  Synthetic files must never masquerade as institutional
    input: callers exclude them from every live computation.  A missing
    index means "no known synthetic files" and is not an error.
    """
    index_path = Path(data_dir) / SYNTHETIC_INDEX_FILENAME
    if not index_path.is_file():
        return {}
    try:
        payload = json.loads(index_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    files = payload.get("files")
    if not isinstance(files, dict):
        return {}
    return {str(k): v for k, v in files.items() if isinstance(v, dict)}


class CompositeScoreBuilder:
    """Produces a monthly composite_score DataFrame from raw economic CSVs
    or live FRED API data.

    Reads 5 monthly indicators (CPI, PPI, PMI, UNRATE, PAYEMS),
    transforms each into a z-score, and averages them into
    a single ``composite_score`` per month.

    Final Hardening (D-03): files listed in ``synthetic_data_index.json``
    are excluded from the CSV path -- synthetic placeholders never feed the
    institutional regime path.  Use :meth:`build_with_provenance` to obtain
    the exclusion report alongside the frame.
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
        return self.build_with_provenance()[0]

    def build_with_provenance(self) -> tuple[pd.DataFrame, dict[str, Any]]:
        """Return (composite frame, provenance report).

        The provenance report records which indicators were included and
        which were excluded as synthetic placeholders (D-03).
        """
        if self._fred_fetcher is not None:
            return self._build_from_fred(), {
                "source": "fred",
                "excluded_indicators": [],
            }
        frame, excluded = self._build_from_csv_with_exclusions()
        return frame, {
            "source": "csv",
            "excluded_indicators": excluded,
        }

    def _build_from_csv(self) -> pd.DataFrame:
        return self._build_from_csv_with_exclusions()[0]

    def _build_from_csv_with_exclusions(
        self,
    ) -> tuple[pd.DataFrame, list[dict[str, Any]]]:
        synthetic = load_synthetic_exclusions(self._data_dir)
        z_scores: list[pd.Series] = []
        common_index: pd.DatetimeIndex | None = None
        excluded: list[dict[str, Any]] = []

        for name, filename in self._INDICATORS.items():
            if filename in synthetic:
                excluded.append(
                    {
                        "indicator": name,
                        "file": filename,
                        "reason": "synthetic_placeholder",
                        "detail": synthetic[filename],
                    }
                )
                continue
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
            return (
                pd.DataFrame(columns=["Date", "composite_score"]),
                excluded,
            )

        aligned = [z.reindex(common_index) for z in z_scores]
        composite = pd.concat(aligned, axis=1).mean(axis=1, skipna=True)
        composite = composite.dropna()

        return (
            pd.DataFrame({
                "Date": composite.index,
                "composite_score": composite.values.round(6),
            }).reset_index(drop=True),
            excluded,
        )

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
