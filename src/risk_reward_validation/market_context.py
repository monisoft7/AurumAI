"""Run-003 repair (Phase 6): as-of market context for risk/reward validation.

W12's legacy metrics were deterministic functions of the scenario conviction
proxy -- no market quantity entered the module.  This builder supplies the
missing, as-of-safe market quantities from the repository's own gold OHLCV
history:

* ``reference_price``     last valid close at or before ``as_of``;
* ``atr_abs`` / ``atr_pct``  ATR(14) over the as-of slice (reuses the
  existing technical-desk machinery: validated frame preparation,
  deterministic as-of slicing and the pandas-ta-classic engine -- the same
  implementation the W14 level anchoring already uses);
* ``realized_vol_daily``  population standard deviation of daily log
  returns over the trailing ``VOL_LOOKBACK`` observations;
* ``semivol_up_daily`` / ``semivol_down_daily``  root-mean-square of the
  positive / negative deviations from zero of the same daily log returns
  (semi-deviation around zero -- a market-derived favorable/adverse
  asymmetry measure; both sides use the SAME estimator so the treatment is
  direction-symmetric).

Availability is explicit: when the required history is missing or the
quantities are not strictly positive, ``available`` is False and the
validator keeps its legacy conviction-derived basis with an explicit
``risk_basis`` label -- no volatility number is ever invented.

Deterministic: pure functions of the CSV slice; no wall clock, no network.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

# Trailing observation window for realized / semi-deviations.  Chosen a
# priori (RiskMetrics-style short window, stable for daily gold data with
# >= VOL_MIN_OBS observations); never fitted to outcomes.
VOL_LOOKBACK = 60
VOL_MIN_OBS = 30

# ATR-14 requires the same 30-bar minimum as the existing W14 level anchor.
ATR_MIN_BARS = 30


@dataclass(frozen=True)
class MarketContext:
    """As-of market quantities for one instrument, strictly ``<= as_of``."""

    available: bool
    as_of: str
    asset: str = "XAU/USD"
    reference_price: float | None = None
    atr_abs: float | None = None
    atr_pct: float | None = None
    realized_vol_daily: float | None = None
    semivol_up_daily: float | None = None
    semivol_down_daily: float | None = None
    bars_used: int = 0
    vol_observations: int = 0
    provenance: dict[str, Any] = field(default_factory=dict)

    def describe(self) -> dict[str, Any]:
        """Serialization-safe summary carried in validation metadata."""
        return {
            "available": self.available,
            "as_of": self.as_of,
            "asset": self.asset,
            "reference_price": self.reference_price,
            "atr_abs": self.atr_abs,
            "atr_pct": self.atr_pct,
            "realized_vol_daily": self.realized_vol_daily,
            "semivol_up_daily": self.semivol_up_daily,
            "semivol_down_daily": self.semivol_down_daily,
            "bars_used": self.bars_used,
            "vol_observations": self.vol_observations,
        }


def _unavailable(as_of: str, reason: str, extra: dict[str, Any] | None = None) -> MarketContext:
    provenance: dict[str, Any] = {"status": "unavailable", "reason": reason, "as_of": str(as_of)}
    if extra:
        provenance.update(extra)
    return MarketContext(available=False, as_of=str(as_of), provenance=provenance)


def build_market_context(
    gold_path: str | None,
    as_of: str | None,
    *,
    asset: str = "XAU/USD",
) -> MarketContext:
    """Build the as-of market context from the repository gold OHLCV CSV.

    Reuses the existing ``TechnicalResearchDesk._prepare_frame`` /
    ``_slice_as_of`` machinery (deterministic, validated, as-of safe) and
    the existing ``PandasTaClassicEngine`` ATR-14 -- identical to the
    machinery ``orchestration.stages._resolve_atr_context`` uses for W14
    level anchoring, so no second technical implementation exists.
    """
    import datetime

    import numpy as np
    import pandas as pd

    effective_as_of = str(as_of or datetime.date.today().isoformat())
    if not gold_path:
        return _unavailable(effective_as_of, "no gold_path")

    try:
        from technical.desk import TechnicalResearchDesk
        from technical.engine import PandasTaClassicEngine

        frame = TechnicalResearchDesk._prepare_frame(pd.read_csv(gold_path))
        sliced = TechnicalResearchDesk._slice_as_of(frame, effective_as_of)
        n_bars = int(len(sliced))
        if n_bars < max(ATR_MIN_BARS, VOL_MIN_OBS + 1):
            return _unavailable(
                effective_as_of,
                (
                    f"insufficient history: {n_bars} bars available, "
                    f"{max(ATR_MIN_BARS, VOL_MIN_OBS + 1)} required"
                ),
                {"bars_used": n_bars},
            )

        closes = sliced["close"].to_numpy(dtype=float)
        reference_price = float(closes[-1])
        if not math.isfinite(reference_price) or reference_price <= 0.0:
            return _unavailable(
                effective_as_of, "reference close not finite/positive",
                {"bars_used": n_bars},
            )

        indicators = PandasTaClassicEngine().compute(sliced)
        atr_value = indicators["atr_14"].iloc[-1]
        atr_abs: float | None = None
        if atr_value is not None:
            atr_candidate = float(atr_value)
            if math.isfinite(atr_candidate) and atr_candidate > 0.0:
                atr_abs = atr_candidate
        if atr_abs is None:
            return _unavailable(
                effective_as_of, "atr_14 not finite on the as-of slice",
                {"bars_used": n_bars},
            )

        log_returns = np.diff(np.log(closes))
        tail = log_returns[-VOL_LOOKBACK:]
        tail = tail[np.isfinite(tail)]
        if len(tail) < VOL_MIN_OBS:
            return _unavailable(
                effective_as_of,
                f"insufficient return observations for volatility: {len(tail)} available, "
                f"{VOL_MIN_OBS} required",
                {"bars_used": n_bars, "vol_observations": int(len(tail))},
            )

        realized = float(np.sqrt(np.mean(np.square(tail))))
        up_devs = tail[tail > 0.0]
        down_devs = tail[tail < 0.0]
        semivol_up = (
            float(np.sqrt(np.mean(np.square(up_devs)))) if len(up_devs) else 0.0
        )
        semivol_down = (
            float(np.sqrt(np.mean(np.square(down_devs)))) if len(down_devs) else 0.0
        )
        if realized <= 0.0 or semivol_up <= 0.0 or semivol_down <= 0.0:
            return _unavailable(
                effective_as_of,
                "degenerate volatility estimate (zero dispersion on one side)",
                {
                    "bars_used": n_bars,
                    "vol_observations": int(len(tail)),
                    "realized_vol_daily": realized,
                    "semivol_up_daily": semivol_up,
                    "semivol_down_daily": semivol_down,
                },
            )

        atr_pct = atr_abs / reference_price
        provenance = {
            "status": "ok",
            "source": str(gold_path),
            "as_of": effective_as_of,
            "bar_date": str(sliced.index[-1].date()),
            "bars_used": n_bars,
            "vol_observations": int(len(tail)),
            "engine": "pandas_ta_classic:atr_14",
            "atr_source_machinery": (
                "TechnicalResearchDesk._prepare_frame/_slice_as_of "
                "(shared with W14 level anchoring)"
            ),
            "vol_estimator": (
                f"population std / zero-mean semi-deviations of daily log "
                f"returns, trailing {VOL_LOOKBACK} observations "
                f"(min {VOL_MIN_OBS})"
            ),
        }
        return MarketContext(
            available=True,
            as_of=effective_as_of,
            asset=asset,
            reference_price=round(reference_price, 6),
            atr_abs=round(atr_abs, 6),
            atr_pct=round(atr_pct, 8),
            realized_vol_daily=round(realized, 8),
            semivol_up_daily=round(semivol_up, 8),
            semivol_down_daily=round(semivol_down, 8),
            bars_used=n_bars,
            vol_observations=int(len(tail)),
            provenance=provenance,
        )
    except Exception as exc:
        return _unavailable(
            effective_as_of, f"{type(exc).__name__}: {exc}"
        )
