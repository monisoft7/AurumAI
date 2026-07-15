from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass(slots=True)
class Lesson:

    event_id: str
    event_type: str
    event_date: datetime

    event_value: float
    event_surprise: Optional[float]

    gold_before: float
    gold_1d: float
    gold_3d: float
    gold_7d: float
    gold_30d: float

    return_1d: float
    return_3d: float
    return_7d: float
    return_30d: float

    trend: str
    volatility: float

    source: str
    confidence: float