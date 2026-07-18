from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd


@dataclass(frozen=True)
class DXYContextConfig:
    dxy_path: Path
    lookback_days: int = 30
    low_dxy_threshold: float = 95.0
    high_dxy_threshold: float = 105.0
    flat_change: float = 1.0


class DXYContextEnricher:
    """Attach DXY (US Dollar Index) context to event lessons.

    DXY level is classified from the latest available value on or before the
    event date. DXY trend compares that value with the latest available value
    on or before `event_date - lookback_days`, expressed in index points.
    """

    def __init__(self, config: DXYContextConfig):
        self.config = config

    def enrich(self, lessons: pd.DataFrame) -> pd.DataFrame:
        self._require_columns(lessons, {"event_date"}, Path("<lessons>"))
        dxy = self._load_dxy(self.config.dxy_path)

        enriched = lessons.copy()
        enriched["event_date"] = pd.to_datetime(enriched["event_date"], errors="raise")

        context_rows = [
            self._context_for_date(event_date, dxy)
            for event_date in enriched["event_date"]
        ]
        context = pd.DataFrame(context_rows)
        output = pd.concat(
            [enriched.reset_index(drop=True), context.reset_index(drop=True)],
            axis=1,
        )
        output["event_date"] = output["event_date"].dt.date.astype(str)
        return output

    def enrich_csv(self, lessons_path: Path, output_path: Path | None = None) -> pd.DataFrame:
        lessons = pd.read_csv(lessons_path)
        enriched = self.enrich(lessons)
        target = output_path or lessons_path
        target.parent.mkdir(parents=True, exist_ok=True)
        enriched.to_csv(target, index=False)
        return enriched

    def _load_dxy(self, path: Path) -> pd.DataFrame:
        df = pd.read_csv(path)
        self._require_columns(df, {"Date", "Value"}, path)
        df = df.copy()
        df["Date"] = pd.to_datetime(df["Date"], errors="raise")
        df["Value"] = pd.to_numeric(df["Value"], errors="raise")
        df = df.sort_values("Date").drop_duplicates("Date", keep="last")
        df = df.dropna(subset=["Value"])
        if df.empty:
            raise ValueError(f"{path} contains no DXY observations.")
        return df.reset_index(drop=True)

    def _context_for_date(
        self,
        event_date: pd.Timestamp,
        dxy: pd.DataFrame,
    ) -> dict[str, object]:
        current = self._latest_on_or_before(dxy, event_date)
        lookback_date = event_date - pd.Timedelta(days=self.config.lookback_days)
        previous = self._latest_on_or_before(dxy, lookback_date)

        if current is None:
            return {
                "dxy_value_at_event": None,
                "dxy_value_lookback": None,
                "dxy_change": None,
                "dxy_level": "missing_dxy_context",
                "dxy_trend": "missing_dxy_context",
            }

        current_value = float(current["Value"])
        if previous is None:
            previous_value = None
            change = None
            trend = "missing_dxy_lookback"
        else:
            previous_value = float(previous["Value"])
            change = round(current_value - previous_value, 6)
            trend = self._trend(change)

        return {
            "dxy_value_at_event": round(current_value, 6),
            "dxy_value_lookback": (
                None if previous_value is None else round(previous_value, 6)
            ),
            "dxy_change": change,
            "dxy_level": self._level(current_value),
            "dxy_trend": trend,
        }

    def _latest_on_or_before(
        self,
        dxy: pd.DataFrame,
        date: pd.Timestamp,
    ) -> pd.Series | None:
        positions = dxy["Date"].searchsorted(date, side="right")
        if positions <= 0:
            return None
        return dxy.iloc[int(positions) - 1]

    def _level(self, value: float) -> str:
        if value < self.config.low_dxy_threshold:
            return "low_dxy_regime"
        if value > self.config.high_dxy_threshold:
            return "high_dxy_regime"
        return "normal_dxy_regime"

    def _trend(self, change: float) -> str:
        if change > self.config.flat_change:
            return "dxy_rising"
        if change < -self.config.flat_change:
            return "dxy_falling"
        return "dxy_flat"

    def _require_columns(self, df: pd.DataFrame, required: set[str], path: Path) -> None:
        missing = required.difference(df.columns)
        if missing:
            missing_text = ", ".join(sorted(missing))
            raise ValueError(f"{path} is missing required columns: {missing_text}")
