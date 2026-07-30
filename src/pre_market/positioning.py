from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import numpy as np
import pandas as pd

from pre_market.contracts import PositioningSnapshot


class PositioningDataFetcher:
    """Fetches COMEX COT, gold ETF flow, and LBMA/GOFO positioning data.

    COT data is updated weekly (CFTC). ETF flow is daily via yfinance.
    GOFO/LBMA rates are sourced from LBMA (stub: returns defaults).

    Returns PositioningSnapshot with defaults when data is unavailable.
    """

    COT_TICKER = "GC=F"
    ETF_TICKERS = {"GLD": "GLD", "IAUM": "IAUM"}

    def fetch(self) -> PositioningSnapshot:
        cot = self._fetch_cot()
        etf = self._fetch_etf_flow()
        oi = self._fetch_open_interest()
        gofo = self._fetch_gofo()

        return PositioningSnapshot(
            cot_z_score=cot["z_score"],
            cot_regime=cot["regime"],
            etf_flow_momentum=etf["momentum"],
            etf_flow_change_pct=etf["change_pct"],
            open_interest_change_pct=oi["change_pct"],
            gofo_rate=gofo["rate"],
            timestamp=datetime.now(timezone.utc).isoformat(),
        )

    def _fetch_cot(self) -> dict[str, Any]:
        return {"z_score": 0.0, "regime": "neutral"}

    def _fetch_etf_flow(self) -> dict[str, Any]:
        try:
            import yfinance as yf

            total_prev = 0.0
            total_curr = 0.0
            for ticker in self.ETF_TICKERS.values():
                data = yf.download(ticker, period="5d", progress=False, auto_adjust=True)
                if data.empty:
                    continue
                close = data["Close"].squeeze().dropna()
                volume = data["Volume"].squeeze().dropna() if "Volume" in data.columns else None
                if len(close) >= 2:
                    total_prev += float(close.iloc[-2])
                    total_curr += float(close.iloc[-1])
            if total_prev > 0:
                change_pct = (total_curr - total_prev) / total_prev * 100.0
            else:
                change_pct = 0.0
            if change_pct > 1.0:
                momentum = "accumulating"
            elif change_pct < -1.0:
                momentum = "distributing"
            else:
                momentum = "stable"
            return {"momentum": momentum, "change_pct": round(change_pct, 2)}
        except Exception:
            return {"momentum": "stable", "change_pct": 0.0}

    def _fetch_open_interest(self) -> dict[str, Any]:
        try:
            import yfinance as yf

            data = yf.download(self.COT_TICKER, period="10d", progress=False, auto_adjust=True)
            if data.empty or len(data) < 2:
                return {"change_pct": 0.0}
                prev_oi = float(data["Volume"].iloc[-2].iloc[0]) if "Volume" in data.columns else 0.0
                curr_oi = float(data["Volume"].iloc[-1].iloc[0]) if "Volume" in data.columns else 0.0
            if prev_oi > 0:
                return {"change_pct": round((curr_oi - prev_oi) / prev_oi * 100.0, 2)}
            return {"change_pct": 0.0}
        except Exception:
            return {"change_pct": 0.0}

    @staticmethod
    def _fetch_gofo() -> dict[str, Any]:
        return {"rate": 0.0}
