import pandas as pd
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


DEFAULT_HORIZONS = (1, 5, 20)


@dataclass(frozen=True)
class LessonBuilderConfig:
    cpi_path: Path = Path("data/economic/CPIAUCSL.csv")
    gold_path: Path = Path("data/history/gold/gold.csv")
    output_path: Path = Path("data/lessons/cpi_gold_lessons.csv")
    horizons: tuple[int, ...] = DEFAULT_HORIZONS
    min_abs_move_pct: float = 0.10


class LessonBuilder:
    """Build deterministic macro-to-market lessons from local history."""

    def __init__(self, config: LessonBuilderConfig | None = None):
        self.config = config or LessonBuilderConfig()

    def build(self) -> pd.DataFrame:
        cpi = self._load_cpi(self.config.cpi_path)
        gold = self._load_gold(self.config.gold_path)
        lessons = self._build_cpi_gold_lessons(cpi, gold, self.config.horizons)
        return pd.DataFrame(lessons)

    def build_and_save(self) -> pd.DataFrame:
        lessons = self.build()
        self.config.output_path.parent.mkdir(parents=True, exist_ok=True)
        lessons.to_csv(self.config.output_path, index=False)
        return lessons

    def _load_cpi(self, path: Path) -> pd.DataFrame:
        df = pd.read_csv(path)
        required = {"Date", "Value"}
        self._require_columns(df, required, path)

        df = df.copy()
        df["Date"] = pd.to_datetime(df["Date"], errors="raise")
        df["Value"] = pd.to_numeric(df["Value"], errors="raise")
        df = df.sort_values("Date").drop_duplicates("Date", keep="last")
        df["previous_value"] = df["Value"].shift(1)
        df["cpi_change_pct"] = (
            (df["Value"] - df["previous_value"]) / df["previous_value"]
        ) * 100.0
        return df.dropna(subset=["previous_value", "cpi_change_pct"])

    def _load_gold(self, path: Path) -> pd.DataFrame:
        df = pd.read_csv(path)
        required = {"Date", "Close"}
        self._require_columns(df, required, path)

        df = df.copy()
        df["Date"] = pd.to_datetime(df["Date"], errors="raise")
        df["Close"] = pd.to_numeric(df["Close"], errors="raise")
        df = df.sort_values("Date").drop_duplicates("Date", keep="last")
        return df.reset_index(drop=True)

    def _build_cpi_gold_lessons(
        self,
        cpi: pd.DataFrame,
        gold: pd.DataFrame,
        horizons: Iterable[int],
    ) -> list[dict[str, object]]:
        lessons: list[dict[str, object]] = []
        gold_dates = gold["Date"]
        first_gold_date = gold_dates.iloc[0]

        for _, row in cpi.iterrows():
            if row["Date"] < first_gold_date:
                continue

            anchor_index = self._first_gold_index_on_or_after(gold_dates, row["Date"])
            if anchor_index is None:
                continue

            max_horizon = max(horizons)
            if anchor_index + max_horizon >= len(gold):
                continue

            anchor = gold.iloc[anchor_index]
            lesson = self._base_lesson(row, anchor)

            for horizon in horizons:
                future = gold.iloc[anchor_index + horizon]
                return_pct = self._pct_return(anchor["Close"], future["Close"])
                lesson[f"gold_close_t_plus_{horizon}d"] = round(float(future["Close"]), 6)
                lesson[f"gold_return_{horizon}d_pct"] = round(return_pct, 6)
                lesson[f"gold_direction_{horizon}d"] = self._direction(return_pct)

            lesson["primary_horizon_days"] = self._primary_horizon(lesson, horizons)
            lesson["lesson_text"] = self._lesson_text(lesson)
            lessons.append(lesson)

        return lessons

    def _base_lesson(self, cpi_row: pd.Series, anchor_row: pd.Series) -> dict[str, object]:
        event_date = cpi_row["Date"].date().isoformat()
        anchor_date = anchor_row["Date"].date().isoformat()
        cpi_change_pct = float(cpi_row["cpi_change_pct"])

        return {
            "lesson_id": f"CPI_GOLD_{event_date}",
            "lesson_version": "cpi_gold_v1",
            "event_type": "CPI",
            "event_date": event_date,
            "anchor_gold_date": anchor_date,
            "alignment_method": "first_gold_session_on_or_after_event_date",
            "cpi_value": round(float(cpi_row["Value"]), 6),
            "previous_cpi_value": round(float(cpi_row["previous_value"]), 6),
            "cpi_change_pct": round(cpi_change_pct, 6),
            "cpi_pressure": self._cpi_pressure(cpi_change_pct),
            "gold_close_at_event": round(float(anchor_row["Close"]), 6),
        }

    def _first_gold_index_on_or_after(
        self,
        gold_dates: pd.Series,
        event_date: pd.Timestamp,
    ) -> int | None:
        positions = gold_dates.searchsorted(event_date, side="left")
        if positions >= len(gold_dates):
            return None
        return int(positions)

    def _primary_horizon(self, lesson: dict[str, object], horizons: Iterable[int]) -> int:
        return max(
            horizons,
            key=lambda horizon: abs(float(lesson[f"gold_return_{horizon}d_pct"])),
        )

    def _lesson_text(self, lesson: dict[str, object]) -> str:
        horizon = int(lesson["primary_horizon_days"])
        direction = lesson[f"gold_direction_{horizon}d"]
        move = lesson[f"gold_return_{horizon}d_pct"]
        cpi_change = lesson["cpi_change_pct"]
        return (
            f"After CPI changed by {cpi_change}% on {lesson['event_date']}, "
            f"gold moved {move}% over {horizon} trading days "
            f"({direction})."
        )

    def _cpi_pressure(self, cpi_change_pct: float) -> str:
        if cpi_change_pct > 0:
            return "inflation_pressure_up"
        if cpi_change_pct < 0:
            return "inflation_pressure_down"
        return "inflation_pressure_flat"

    def _direction(self, return_pct: float) -> str:
        if return_pct > self.config.min_abs_move_pct:
            return "UP"
        if return_pct < -self.config.min_abs_move_pct:
            return "DOWN"
        return "FLAT"

    def _pct_return(self, start: float, end: float) -> float:
        if start == 0:
            raise ValueError("Cannot calculate return from a zero start price.")
        return ((float(end) - float(start)) / float(start)) * 100.0

    def _require_columns(self, df: pd.DataFrame, required: set[str], path: Path) -> None:
        missing = required.difference(df.columns)
        if missing:
            missing_text = ", ".join(sorted(missing))
            raise ValueError(f"{path} is missing required columns: {missing_text}")


if __name__ == "__main__":

    output = LessonBuilder().build_and_save()
    print(output.head())
    print()
    print("Lessons:", len(output))
