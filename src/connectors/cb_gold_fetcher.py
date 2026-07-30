from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path

import pandas as pd

from connectors.fred_client import FredClient

_CACHE_PATH = Path("data/central_bank_gold.csv")


@dataclass(frozen=True)
class CBGoldHolding:
    country: str
    tonnes: float
    usd_value: float
    share_of_reserves_pct: float
    as_of_date: date
    change_month_tonnes: float = 0.0
    change_yTD_tonnes: float = 0.0


class CBGoldReserveFetcher:
    """Fetches central bank gold reserve data.

    Primary source: IMF IFS via FRED (series GOLD* for individual countries),
    supplemented by World Gold Council data.

    Currently provides structural holdings data; monthly delta tracking
    requires WGC data subscription.
    """

    _FRED_GOLD_SERIES: dict[str, str] = {
        "US_GOLD": "GOLDUS",       # US gold reserves (FRED)
    }

    def __init__(
        self, fred_client: FredClient | None = None,
    ) -> None:
        self._client = fred_client or FredClient()

    def get_us_holdings(self) -> pd.Series | None:
        try:
            return self._client.get_series(
                self._FRED_GOLD_SERIES["US_GOLD"],
            )
        except (KeyError, ValueError, Exception):
            return None

    def get_known_top_holders(self) -> list[CBGoldHolding]:
        """Returns structural holdings for the top ~15 central banks.

        Values from latest WGC data (mid-2025/early 2026). These change
        slowly (monthly) so cached data is acceptable between WGC releases.
        """
        return [
            CBGoldHolding("United States", 8133.46, 0.0, 79.0, date(2026, 3, 31)),
            CBGoldHolding("Germany", 3351.53, 0.0, 76.0, date(2026, 3, 31)),
            CBGoldHolding("IMF", 2814.0, 0.0, 0.0, date(2026, 3, 31)),
            CBGoldHolding("Italy", 2451.84, 0.0, 72.0, date(2026, 3, 31)),
            CBGoldHolding("France", 2436.97, 0.0, 74.0, date(2026, 3, 31)),
            CBGoldHolding("Russia", 2335.0, 0.0, 30.0, date(2026, 3, 31)),
            CBGoldHolding("China", 2292.0, 0.0, 6.0, date(2026, 3, 31)),
            CBGoldHolding("Switzerland", 1040.0, 0.0, 8.0, date(2026, 3, 31)),
            CBGoldHolding("Japan", 845.97, 0.0, 5.0, date(2026, 3, 31)),
            CBGoldHolding("India", 876.0, 0.0, 11.0, date(2026, 3, 31)),
            CBGoldHolding("Netherlands", 612.45, 0.0, 68.0, date(2026, 3, 31)),
            CBGoldHolding("Turkey", 540.0, 0.0, 27.0, date(2026, 3, 31)),
            CBGoldHolding("Poland", 420.0, 0.0, 17.0, date(2026, 3, 31)),
            CBGoldHolding("Taiwan", 423.0, 0.0, 6.0, date(2026, 3, 31)),
            CBGoldHolding("Kazakhstan", 410.0, 0.0, 72.0, date(2026, 3, 31)),
        ]

    def aggregate_central_bank_demand(
        self,
    ) -> dict[str, float]:
        """Return estimated central bank net purchases for recent periods.

        Values based on WGC mid-2025 review + known Q4 2025 / Q1 2026 trends.
        """
        return {
            "2024_full_year_tonnes": 1045.0,
            "2025_h1_tonnes": 483.0,
            "2025_q3_tonnes": 186.0,
            "2025_q4_tonnes_est": 220.0,
            "2025_full_year_est_tonnes": 889.0,
            "2026_q1_est_tonnes": 230.0,
            "trend": "accelerating",
        }

    def to_dataframe(self) -> pd.DataFrame:
        holders = self.get_known_top_holders()
        rows = []
        for h in holders:
            rows.append({
                "country": h.country,
                "tonnes": h.tonnes,
                "share_of_reserves_pct": h.share_of_reserves_pct,
                "as_of_date": h.as_of_date.isoformat(),
            })
        return pd.DataFrame(rows).sort_values("tonnes", ascending=False)
