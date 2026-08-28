from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from pre_market.contracts import PositioningSnapshot


class PositioningDataFetcher:
    """Fetches COMEX COT, gold ETF flow, and LBMA/GOFO positioning data.

    COT data is updated weekly (CFTC). ETF flow is daily via yfinance.
    GOFO/LBMA rates are sourced from LBMA (no data source wired yet).

    Final Hardening (D-11): every feed carries an explicit availability
    state in ``PositioningSnapshot.availability``.  A failed fetch is never
    serialized as a "stable"/0.0 measurement; neutral-looking numeric
    defaults on unavailable feeds are placeholders, flagged as such.
    """

    COT_TICKER = "GC=F"
    ETF_TICKERS = {"GLD": "GLD", "IAUM": "IAUM"}
    _DEFAULT_OI_STATE_FILE = Path("data/economic/gold_oi_state.json")

    def __init__(self, oi_state_file: str | Path | None = None) -> None:
        self._oi_state_file = (
            Path(oi_state_file) if oi_state_file else self._DEFAULT_OI_STATE_FILE
        )

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
            availability={
                "cot": cot["status"],
                "etf_flow": etf["status"],
                "open_interest": oi["status"],
                "gofo": gofo["status"],
            },
        )

    def _fetch_cot(self) -> dict[str, Any]:
        # No CFTC COT data source is wired; report unavailable instead of a
        # fake neutral z-score (Final Hardening D-11).
        return {
            "z_score": 0.0,
            "regime": "unavailable",
            "status": "unavailable_no_data_source",
        }

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
                return {
                    "momentum": "unknown",
                    "change_pct": 0.0,
                    "status": "unavailable_fetch_failed",
                }
            if change_pct > 1.0:
                momentum = "accumulating"
            elif change_pct < -1.0:
                momentum = "distributing"
            else:
                momentum = "stable"
            return {
                "momentum": momentum,
                "change_pct": round(change_pct, 2),
                "status": "available",
            }
        except Exception:
            return {
                "momentum": "unknown",
                "change_pct": 0.0,
                "status": "unavailable_fetch_failed",
            }

    def _fetch_open_interest(self) -> dict[str, Any]:
        """Real COMEX gold open interest via the existing yfinance quote field.

        Uses the current ``openInterest`` level from ``Ticker("GC=F").get_info()``
        (no new provider/connector) and computes the day-over-day percentage
        change against the last previously observed level, persisted in a small
        state file (fred-client cache pattern). Traded ``Volume`` is never used
        as a substitute for open interest.

        Final Hardening (D-11): unavailability is explicit.  When the level
        cannot be fetched the status is ``unavailable_fetch_failed``; when no
        previous state exists the change is 0.0 but the status
        ``unavailable_no_previous_state`` makes clear the 0.0 is not an
        observed flat day.  A valid previous state is never overwritten by a
        failure.
        """
        current_oi = self._fetch_current_oi()
        if current_oi is None:
            return {"change_pct": 0.0, "status": "unavailable_fetch_failed"}

        previous_oi = self._load_previous_oi()
        if previous_oi is not None:
            change_pct = round((current_oi - previous_oi) / previous_oi * 100.0, 2)
            status = "available"
        else:
            change_pct = 0.0
            status = "unavailable_no_previous_state"

        self._persist_oi_level(current_oi, datetime.now(timezone.utc).isoformat())
        return {"change_pct": change_pct, "status": status}

    def _fetch_current_oi(self) -> float | None:
        try:
            import yfinance as yf

            info = yf.Ticker(self.COT_TICKER).get_info()
            raw = info.get("openInterest")
            if raw is None or not isinstance(raw, (int, float)):
                return None
            level = float(raw)
            if not math.isfinite(level) or level <= 0.0:
                return None
            return level
        except Exception:
            return None

    def _load_previous_oi(self) -> float | None:
        try:
            if not self._oi_state_file.exists():
                return None
            raw = json.loads(self._oi_state_file.read_text(encoding="utf-8"))
            value = raw.get("open_interest")
            if value is None:
                return None
            level = float(value)
            if not math.isfinite(level) or level <= 0.0:
                return None
            return level
        except Exception:
            return None

    def _persist_oi_level(self, level: float, timestamp: str) -> None:
        try:
            self._oi_state_file.parent.mkdir(parents=True, exist_ok=True)
            self._oi_state_file.write_text(
                json.dumps(
                    {"timestamp": timestamp, "open_interest": round(level, 2)},
                    indent=2,
                ),
                encoding="utf-8",
            )
        except Exception:
            pass

    @staticmethod
    def _fetch_gofo() -> dict[str, Any]:
        # No GOFO/LBMA data source is wired; report unavailable instead of a
        # fake zero rate (Final Hardening D-11).
        return {"rate": 0.0, "status": "unavailable_no_data_source"}
