from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd


@dataclass(frozen=True)
class ReleaseRecord:
    reference_period: str
    release_date: str
    release_time: str
    timezone: str = "US/Eastern"

    @property
    def release_timestamp_et(self) -> str:
        return f"{self.release_date}T{self.release_time}:00"

    def to_dict(self) -> dict[str, Any]:
        return {
            "reference_period": self.reference_period,
            "release_date": self.release_date,
            "release_time": self.release_time,
            "timezone": self.timezone,
            "release_timestamp": self.release_timestamp_et,
        }


class ReleaseCalendar:
    def __init__(self, records: dict[str, ReleaseRecord]) -> None:
        if not records:
            raise ValueError("ReleaseCalendar must have at least one record")
        self._records = dict(records)

    @classmethod
    def from_csv(cls, path: str | Path) -> ReleaseCalendar:
        df = pd.read_csv(path)
        required = {"reference_period", "release_date", "release_time"}
        missing = required.difference(df.columns)
        # Also accept a combined release_timestamp column
        if missing and "release_timestamp" in df.columns:
            colset = set(df.columns)
            if "reference_period" not in colset:
                raise ValueError(
                    "Release calendar CSV with release_timestamp must "
                    "also have reference_period"
                )
        elif missing:
            raise ValueError(
                f"Release calendar CSV missing columns: {missing}"
            )
        records: dict[str, ReleaseRecord] = {}
        for _, row in df.iterrows():
            ref = str(row["reference_period"])
            if "release_timestamp" in df.columns:
                ts = str(row["release_timestamp"])
                date_part, time_part = ts.split(" ", 1)
                if time_part.endswith(":00"):
                    time_part = time_part[:-3]
                records[ref] = ReleaseRecord(
                    reference_period=ref,
                    release_date=date_part,
                    release_time=time_part,
                    timezone=str(row.get("release_timezone", "US/Eastern")),
                )
            else:
                records[ref] = ReleaseRecord(
                    reference_period=ref,
                    release_date=str(row["release_date"]),
                    release_time=str(row["release_time"]),
                    timezone=str(row.get("timezone", "US/Eastern")),
                )
        return cls(records)

    @property
    def records(self) -> tuple[ReleaseRecord, ...]:
        return tuple(self._records.values())

    def get(self, reference_period: str) -> ReleaseRecord | None:
        return self._records.get(reference_period)

    def __len__(self) -> int:
        return len(self._records)

    def __contains__(self, reference_period: str) -> bool:
        return reference_period in self._records

    def to_dict(self) -> dict[str, Any]:
        return {
            "records": {k: v.to_dict() for k, v in self._records.items()},
            "count": len(self._records),
        }
