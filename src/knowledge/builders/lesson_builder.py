from __future__ import annotations

import pandas as pd
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from knowledge.events.base import MacroEvent, ReleaseCalendar
from knowledge.events.cpi import CPIEvent, DEFAULT_CPI_RELEASE_CALENDAR


DEFAULT_HORIZONS = (1, 5, 20)


@dataclass(frozen=True)
class LessonBuilderConfig:
    event_data_path: Path = Path("data/economic/CPIAUCSL.csv")
    gold_path: Path = Path("data/history/gold/gold.csv")
    output_path: Path = Path("data/lessons/cpi_gold_lessons.csv")
    horizons: tuple[int, ...] = DEFAULT_HORIZONS
    min_abs_move_pct: float = 0.10
    release_calendar_path: str | None = None


class LessonBuilder:
    """Build deterministic macro-to-market lessons from local history."""

    def __init__(
        self,
        config: LessonBuilderConfig | None = None,
        event: MacroEvent | None = None,
    ):
        self.config = config or LessonBuilderConfig()
        self.event = event or CPIEvent()
        self._release_calendar: ReleaseCalendar | None = None
        cal_path = self.config.release_calendar_path
        if cal_path:
            self._release_calendar = ReleaseCalendar.from_csv(cal_path)

    def build(self) -> pd.DataFrame:
        cal = self._release_calendar
        if cal is not None:
            event_data = self.event.load_and_extract_with_calendar(
                self.config.event_data_path, cal
            )
        else:
            event_data = self.event.load_and_extract(self.config.event_data_path)
        gold = self._load_gold(self.config.gold_path)
        lessons = self._build_lessons(event_data, gold, self.config.horizons)
        return pd.DataFrame(lessons)

    def build_and_save(self) -> pd.DataFrame:
        lessons = self.build()
        self.config.output_path.parent.mkdir(parents=True, exist_ok=True)
        lessons.to_csv(self.config.output_path, index=False)
        return lessons

    def _load_gold(self, path: Path) -> pd.DataFrame:
        df = pd.read_csv(path)
        required = {"Date", "Close"}
        self._require_columns(df, required, path)

        df = df.copy()
        df["Date"] = pd.to_datetime(df["Date"], errors="raise")
        df["Close"] = pd.to_numeric(df["Close"], errors="raise")
        df = df.sort_values("Date").drop_duplicates("Date", keep="last")
        return df.reset_index(drop=True)

    def _build_lessons(
        self,
        event_data: pd.DataFrame,
        gold: pd.DataFrame,
        horizons: Iterable[int],
    ) -> list[dict[str, object]]:
        lessons: list[dict[str, object]] = []
        gold_dates = gold["Date"]
        first_gold_date = gold_dates.iloc[0]
        has_release_ts = "release_timestamp" in event_data.columns

        for _, row in event_data.iterrows():
            if has_release_ts:
                release_ts = row["release_timestamp"]
                anchor_time = pd.Timestamp(release_ts).normalize()
                if anchor_time < first_gold_date:
                    continue
                anchor_index = self._first_gold_index_on_or_after(
                    gold_dates, anchor_time
                )
                alignment_method = "first_gold_session_on_or_after_release_timestamp"
            else:
                if row["Date"] < first_gold_date:
                    continue
                anchor_index = self._first_gold_index_on_or_after(
                    gold_dates, row["Date"]
                )
                alignment_method = "first_gold_session_on_or_after_event_date"
            if anchor_index is None:
                continue

            max_horizon = max(horizons)
            if anchor_index + max_horizon >= len(gold):
                continue

            anchor = gold.iloc[anchor_index]
            event_date = row["Date"].date().isoformat()
            anchor_date = anchor["Date"].date().isoformat()

            lesson: dict[str, Any] = {
                "lesson_id": f"{self.event.event_type}_GOLD_{event_date}",
                "lesson_version": self.event.lesson_version,
                "event_type": self.event.event_type,
                "event_date": event_date,
                "anchor_gold_date": anchor_date,
                "alignment_method": alignment_method,
                "gold_close_at_event": round(float(anchor["Close"]), 6),
            }
            if has_release_ts:
                lesson["release_timestamp"] = str(release_ts)
            lesson.update(self.event.build_lesson_fields(row, anchor_date))

            for horizon in horizons:
                future = gold.iloc[anchor_index + horizon]
                return_pct = self._pct_return(anchor["Close"], future["Close"])
                lesson[f"gold_close_t_plus_{horizon}d"] = round(float(future["Close"]), 6)
                lesson[f"gold_return_{horizon}d_pct"] = round(return_pct, 6)
                lesson[f"gold_direction_{horizon}d"] = self._direction(return_pct)

            lesson["primary_horizon_days"] = self._primary_horizon(lesson, horizons)
            lesson["lesson_text"] = self.event.lesson_text(lesson)
            lessons.append(lesson)

        return lessons

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
