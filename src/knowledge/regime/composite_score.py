from __future__ import annotations

from pathlib import Path

import pandas as pd


class CompositeScoreBuilder:
    """Produces a monthly composite_score DataFrame from raw economic CSVs.

    Reads 5 monthly indicators (CPI, PPI, PMI, UNRATE, PAYEMS) from
    *data_dir*, transforms each into a z-score, and averages them into
    a single ``composite_score`` per month.
    """

    _INDICATORS: dict[str, str] = {
        "CPI": "CPIAUCSL.csv",
        "PPI": "PPIACO.csv",
        "PMI": "PMI.csv",
        "UNRATE": "UNRATE.csv",
        "PAYEMS": "PAYEMS.csv",
    }

    def __init__(self, data_dir: str | Path = "data/economic/") -> None:
        self._data_dir = Path(data_dir)

    def build(self) -> pd.DataFrame:
        z_scores: list[pd.Series] = []
        common_index: pd.DatetimeIndex | None = None

        for name, filename in self._INDICATORS.items():
            series = self._load_and_transform(name, filename)
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

    def _load_and_transform(
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

        if name in ("CPI", "PPI", "PAYEMS"):
            # Year-over-year percent change
            series = df.set_index("Date")["Value"]
            series = series.pct_change(12).dropna() * 100.0
        elif name == "UNRATE":
            # Invert so higher z-score = stronger economy
            series = df.set_index("Date")["Value"] * -1.0
        elif name == "PMI":
            # Already an index; center at 50 (neutral)
            series = df.set_index("Date")["Value"] - 50.0
        else:
            series = df.set_index("Date")["Value"]

        return series

    @staticmethod
    def _z_score(series: pd.Series) -> pd.Series:
        std = series.std()
        if std < 1e-12:
            return series * 0.0
        return (series - series.mean()) / std
