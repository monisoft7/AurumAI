from dataclasses import dataclass, field
from typing import Any

PERIOD_QUARTER = "quarter"
PERIOD_MONTH = "month"
PERIOD_WEEK = "week"
PERIOD_YEAR = "year"
PERIOD_ROLLING = "rolling"
PERIOD_CUSTOM = "custom"

VALID_PERIOD_TYPES = frozenset({
    PERIOD_QUARTER,
    PERIOD_MONTH,
    PERIOD_WEEK,
    PERIOD_YEAR,
    PERIOD_ROLLING,
    PERIOD_CUSTOM,
})


@dataclass(frozen=True)
class TimePeriod:
    period_id: str
    start_date: str
    end_date: str
    period_type: str = PERIOD_CUSTOM
    inclusive_start: bool = True
    inclusive_end: bool = True
    label: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
