from pathlib import Path

import pandas as pd

from knowledge.events.base import MacroEvent


class CPIEvent(MacroEvent):
    """Lesson-building logic for Consumer Price Index releases."""

    event_type = "CPI"
    lesson_version = "cpi_gold_v1"
    condition_columns = ["cpi_pressure"]
    knowledge_version = "cpi_gold_summary_v1"

    def load_and_extract(self, path: Path) -> pd.DataFrame:
        df = pd.read_csv(path)
        required = {"Date", "Value"}
        missing = required.difference(df.columns)
        if missing:
            missing_text = ", ".join(sorted(missing))
            raise ValueError(f"{path} is missing required columns: {missing_text}")

        df = df.copy()
        df["Date"] = pd.to_datetime(df["Date"], errors="raise")
        df["Value"] = pd.to_numeric(df["Value"], errors="raise")
        df = df.sort_values("Date").drop_duplicates("Date", keep="last")
        df["previous_value"] = df["Value"].shift(1)
        df["cpi_change_pct"] = (
            (df["Value"] - df["previous_value"]) / df["previous_value"]
        ) * 100.0
        return df.dropna(subset=["previous_value", "cpi_change_pct"])

    def build_lesson_fields(
        self, event_row: pd.Series, anchor_date: str
    ) -> dict[str, object]:
        return {
            "cpi_value": round(float(event_row["Value"]), 6),
            "previous_cpi_value": round(float(event_row["previous_value"]), 6),
            "cpi_change_pct": round(float(event_row["cpi_change_pct"]), 6),
            "cpi_pressure": self._cpi_pressure(float(event_row["cpi_change_pct"])),
        }

    def lesson_text(self, lesson: dict[str, object]) -> str:
        horizon = int(lesson["primary_horizon_days"])
        direction = lesson[f"gold_direction_{horizon}d"]
        move = lesson[f"gold_return_{horizon}d_pct"]
        cpi_change = lesson["cpi_change_pct"]
        return (
            f"After CPI changed by {cpi_change}% on {lesson['event_date']}, "
            f"gold moved {move}% over {horizon} trading days "
            f"({direction})."
        )

    @staticmethod
    def _cpi_pressure(cpi_change_pct: float) -> str:
        if cpi_change_pct > 0:
            return "inflation_pressure_up"
        if cpi_change_pct < 0:
            return "inflation_pressure_down"
        return "inflation_pressure_flat"
