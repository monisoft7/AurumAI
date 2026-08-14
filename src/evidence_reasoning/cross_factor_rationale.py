"""Trace 016-B: explanation-only cross-factor rationale (Real Yield x DXY).

Combines the existing deterministic adapters (RealYieldAdapter, DXYAdapter)
with the existing institutional rule (gold_rule_001) into a single rationalefor
the thesis explanation chain.  Mirrors the Correction 008-B pattern exactly:

- the rationale is carried in ``reasoning.metadata["factor_rationale"]`` and
  composed into the final thesis ``explanation`` suffix by ThesisBuilder (W8)
  and recomposed by ThesisUpdater (W10);
- it is numerically inert: it feeds no score, weight, confidence, consensus,
  or decision value;
- it degrades to ``None`` (chunk omitted) when either input file is missing
  or unreadable, keeping outputs byte-identical to before.

Freshness honesty: each FactorSignal carries the adapter's own deterministic
``data_quality`` recency label (high/moderate/low/stale).  This module invents
no freshness policy - it only surfaces those existing labels.  A stale input
is never presented as a current observation: the per-factor ``status`` marks
it explicitly and the rationale carries a ``freshness_note`` naming the stale
observation dates.  DXY refresh is deliberately out of scope for this
correction (separate targeted correction); stale DXY is surfaced, not hidden.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from knowledge.factors.adapters.dxy_adapter import DXYAdapter
from knowledge.factors.adapters.real_yield_adapter import RealYieldAdapter
from knowledge.factors.contracts import QUALITY_STALE, FactorSignal
from knowledge.reasoning.rules.gold_rule_001 import apply as _apply_gold_rule_001

_REPO_ROOT = Path(__file__).resolve().parents[2]

DEFAULT_REAL_YIELD_PATH = _REPO_ROOT / "data" / "economic" / "DFII10.csv"
DEFAULT_DXY_PATH = _REPO_ROOT / "data" / "context" / "dxy" / "dxy.csv"


def build_cross_factor_rationale(
    real_yield_path: str | Path | None = None,
    dxy_path: str | Path | None = None,
) -> dict[str, Any] | None:
    """Build the deterministic gold_rule_001 cross-factor rationale.

    Loads DFII10 and DXY series from the given paths (defaulting to the
    production data files), converts them with the existing adapters, and
    applies the existing ``gold_rule_001.apply`` rule unchanged.

    Returns:
        A frozen-safe dict with the assessment fields and per-factor
        freshness status, or ``None`` when either input is unavailable so the
        caller omits the chunk entirely (byte-identical baseline).

    Determinism: identical input files always produce an identical dict.
    """
    ry_path = Path(real_yield_path) if real_yield_path else DEFAULT_REAL_YIELD_PATH
    dx_path = Path(dxy_path) if dxy_path else DEFAULT_DXY_PATH

    if not ry_path.is_file() or not dx_path.is_file():
        return None

    try:
        real_yield = RealYieldAdapter.to_factor_signal(_load_series(ry_path))
        dxy = DXYAdapter.to_factor_signal(_load_series(dx_path))
    except Exception:
        return None

    assessment = _apply_gold_rule_001(real_yield, dxy)

    factors = [_factor_entry(real_yield), _factor_entry(dxy)]
    stale = [f for f in factors if f["status"] == "stale"]

    rationale: dict[str, Any] = {
        "rule_id": assessment.rule_id,
        "observation_date": assessment.observation_date,
        "composite_bias": assessment.composite_bias,
        "composite_strength": assessment.composite_strength,
        "composite_confidence": assessment.composite_confidence,
        "signal_dispersion": assessment.signal_dispersion,
        "status": "stale" if stale else "ok",
        "factors": factors,
        "explanation": assessment.explanation,
    }
    if stale:
        stale_parts = [
            f"{f['factor_id']} last observed {f['observation_date']} "
            f"(data_quality={f['data_quality']}) is stale - not a current observation"
            for f in stale
        ]
        rationale["freshness_note"] = (
            "; ".join(stale_parts)
            + ". The composite assessment includes these non-current inputs."
        )
    return rationale


def _load_series(path: Path) -> pd.Series:
    df = pd.read_csv(path)
    return pd.Series(
        df["Value"].astype(float).values, index=pd.to_datetime(df["Date"])
    ).sort_index()


def _factor_status(signal: FactorSignal) -> str:
    if signal.data_quality == QUALITY_STALE:
        return "stale"
    return "current"


def _factor_entry(signal: FactorSignal) -> dict[str, Any]:
    return {
        "factor_id": signal.factor_id,
        "observation_date": signal.observation_date,
        "value": signal.value,
        "z_score": signal.z_score,
        "percentile": signal.percentile,
        "direction": signal.direction,
        "influence_bias": signal.influence_bias,
        "influence_strength": signal.influence_strength,
        "confidence": signal.confidence,
        "data_quality": signal.data_quality,
        "status": _factor_status(signal),
    }