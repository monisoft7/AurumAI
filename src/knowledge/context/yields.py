from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd


@dataclass(frozen=True)
class YieldContextConfig:
    yield_path: Path
    lookback_days: int = 30
    low_yield_threshold: float = 2.0
    high_yield_threshold: float = 4.0
    flat_change_bps: float = 10.0


class YieldContextEnricher:
    """Attach US 10Y yield context to event lessons.

    Yield level is classified from the latest available value on or before the
    event date. Yield trend compares that value with the latest available value
    on or before `event_date - lookback_days`, expressed in basis points.
    """

    def __init__(self, config: YieldContextConfig):
        self.config = config

    def enrich(self, lessons: pd.DataFrame) -> pd.DataFrame:
        self._require_columns(lessons, {"event_date"}, Path("<lessons>"))
        yields = self._load_yields(self.config.yield_path)

        enriched = lessons.copy()
        enriched["event_date"] = pd.to_datetime(enriched["event_date"], errors="raise")

        context_rows = [
            self._context_for_date(event_date, yields)
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

    def _load_yields(self, path: Path) -> pd.DataFrame:
        df = pd.read_csv(path)
        self._require_columns(df, {"Date", "Value"}, path)
        df = df.copy()
        df["Date"] = pd.to_datetime(df["Date"], errors="raise")
        df["Value"] = pd.to_numeric(df["Value"], errors="raise")
        df = df.sort_values("Date").drop_duplicates("Date", keep="last")
        df = df.dropna(subset=["Value"])
        if df.empty:
            raise ValueError(f"{path} contains no yield observations.")
        return df.reset_index(drop=True)

    def _context_for_date(
        self,
        event_date: pd.Timestamp,
        yields: pd.DataFrame,
    ) -> dict[str, object]:
        current = self._latest_on_or_before(yields, event_date)
        lookback_date = event_date - pd.Timedelta(days=self.config.lookback_days)
        previous = self._latest_on_or_before(yields, lookback_date)

        if current is None:
            return {
                "us10y_value_at_event": None,
                "us10y_value_lookback": None,
                "us10y_change_bps": None,
                "us10y_level": "missing_yield_context",
                "us10y_trend": "missing_yield_context",
            }

        current_value = float(current["Value"])
        if previous is None:
            previous_value = None
            change_bps = None
            trend = "missing_yield_lookback"
        else:
            previous_value = float(previous["Value"])
            change_bps = round((current_value - previous_value) * 100.0, 6)
            trend = self._trend(change_bps)

        return {
            "us10y_value_at_event": round(current_value, 6),
            "us10y_value_lookback": (
                None if previous_value is None else round(previous_value, 6)
            ),
            "us10y_change_bps": change_bps,
            "us10y_level": self._level(current_value),
            "us10y_trend": trend,
        }

    def _latest_on_or_before(
        self,
        yields: pd.DataFrame,
        date: pd.Timestamp,
    ) -> pd.Series | None:
        positions = yields["Date"].searchsorted(date, side="right")
        if positions <= 0:
            return None
        return yields.iloc[int(positions) - 1]

    def _level(self, value: float) -> str:
        if value < self.config.low_yield_threshold:
            return "low_yield_regime"
        if value > self.config.high_yield_threshold:
            return "high_yield_regime"
        return "normal_yield_regime"

    def _trend(self, change_bps: float) -> str:
        if change_bps > self.config.flat_change_bps:
            return "yields_rising"
        if change_bps < -self.config.flat_change_bps:
            return "yields_falling"
        return "yields_flat"

    def _require_columns(self, df: pd.DataFrame, required: set[str], path: Path) -> None:
        missing = required.difference(df.columns)
        if missing:
            missing_text = ", ".join(sorted(missing))
            raise ValueError(f"{path} is missing required columns: {missing_text}")
