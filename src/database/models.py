from dataclasses import dataclass
from datetime import datetime
from typing import Any


@dataclass
class DataRecord:
    source: str
    symbol: str
    timestamp: datetime
    data: Any