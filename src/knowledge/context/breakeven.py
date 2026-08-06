from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd


@dataclass(frozen=True)
class BreakevenContextConfig:
    breakeven_path: Path
    lookback_days: int = 30
    low_breakeven_threshold: float = 1.5
    high_breakeven_threshold: float = 3.0
    flat_change: float = 0.1


class BreakevenContextEnricher:
    """Attach 5-Year Breakeven Inflation (T5YIE) context to event lessons.

    Breakeven level is classified from the latest available value on or before
    the event date. Breakeven trend compares that value with the latest
    available value on or before `event_date - lookback_days`, expressed in
    percentage points.
    """

    def __init__(self, config: BreakevenContextConfig):
        self.config = config

    def enrich(self, lessons: pd.DataFrame) -> pd.DataFrame:
        self._require_columns(lessons, {"event_date"}, Path("<lessons>"))
        breakeven = self._load_breakeven(self.config.breakeven_path)

        enriched = lessons.copy()
        enriched["event_date"] = pd.to_datetime(enriched["event_date"], errors="raise")

        context_rows = [
            self._context_for_date(event_date, breakeven)
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

    def _load_breakeven(self, path: Path) -> pd.DataFrame:
        df = pd.read_csv(path)
        self._require_columns(df, {"Date", "Value"}, path)
        df = df.copy()
        df["Date"] = pd.to_datetime(df["Date"], errors="raise")
        df["Value"] = pd.to_numeric(df["Value"], errors="raise")
        df = df.sort_values("Date").drop_duplicates("Date", keep="last")
        df = df.dropna(subset=["Value"])
        if df.empty:
            raise ValueError(f"{path} contains no breakeven observations.")
        return df.reset_index(drop=True)

    def _context_for_date(
        self,
        event_date: pd.Timestamp,
        breakeven: pd.DataFrame,
    ) -> dict[str, object]:
        current = self._latest_on_or_before(breakeven, event_date)
        lookback_date = event_date - pd.Timedelta(days=self.config.lookback_days)
        previous = self._latest_on_or_before(breakeven, lookback_date)

        if current is None:
            return {
                "t5yie_value_at_event": None,
                "t5yie_value_lookback": None,
                "t5yie_change": None,
                "t5yie_level": "missing_breakeven_context",
                "t5yie_trend": "missing_breakeven_context",
            }

        current_value = float(current["Value"])
        if previous is None:
            previous_value = None
            change = None
            trend = "missing_breakeven_lookback"
        else:
            previous_value = float(previous["Value"])
            change = round(current_value - previous_value, 6)
            trend = self._trend(change)

        return {
            "t5yie_value_at_event": round(current_value, 6),
            "t5yie_value_lookback": (
                None if previous_value is None else round(previous_value, 6)
            ),
            "t5yie_change": change,
            "t5yie_level": self._level(current_value),
            "t5yie_trend": trend,
        }

    def _latest_on_or_before(
        self,
        breakeven: pd.DataFrame,
        date: pd.Timestamp,
    ) -> pd.Series | None:
        positions = breakeven["Date"].searchsorted(date, side="right")
        if positions <= 0:
            return None
        return breakeven.iloc[int(positions) - 1]

    def _level(self, value: float) -> str:
        if value < self.config.low_breakeven_threshold:
            return "low_breakeven_regime"
        if value > self.config.high_breakeven_threshold:
            return "high_breakeven_regime"
        return "normal_breakeven_regime"

    def _trend(self, change: float) -> str:
        if change > self.config.flat_change:
            return "breakeven_rising"
        if change < -self.config.flat_change:
            return "breakeven_falling"
        return "breakeven_flat"

    def _require_columns(self, df: pd.DataFrame, required: set[str], path: Path) -> None:
        missing = required.difference(df.columns)
        if missing:
            missing_text = ", ".join(sorted(missing))
            raise ValueError(f"{path} is missing required columns: {missing_text}")