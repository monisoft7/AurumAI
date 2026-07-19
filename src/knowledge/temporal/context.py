from dataclasses import dataclass, field
from typing import Any

from knowledge._compat import FrozenDict, freeze_dict

CALENDAR_CALENDAR = "calendar"
CALENDAR_BUSINESS = "business"

VALID_CALENDAR_TYPES = frozenset({CALENDAR_CALENDAR, CALENDAR_BUSINESS})

FREQUENCY_DAILY = "daily"
FREQUENCY_WEEKLY = "weekly"
FREQUENCY_MONTHLY = "monthly"
FREQUENCY_QUARTERLY = "quarterly"
FREQUENCY_ANNUAL = "annual"

VALID_FREQUENCIES = frozenset({
    FREQUENCY_DAILY,
    FREQUENCY_WEEKLY,
    FREQUENCY_MONTHLY,
    FREQUENCY_QUARTERLY,
    FREQUENCY_ANNUAL,
})


@dataclass(frozen=True)
class TimeContext:
    calendar: str = CALENDAR_CALENDAR
    timezone: str = "UTC"
    frequency: str = FREQUENCY_DAILY
    business_calendar: str | None = None
    metadata: dict[str, Any] = field(default_factory=lambda: FrozenDict())

    def __post_init__(self) -> None:
        object.__setattr__(self, "metadata", freeze_dict(self.metadata))
