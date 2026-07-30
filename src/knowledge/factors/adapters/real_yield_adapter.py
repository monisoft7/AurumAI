from __future__ import annotations

from datetime import datetime, timezone

import pandas as pd

from knowledge.factors.contracts import (
    BIAS_BEARISH,
    BIAS_BULLISH,
    BIAS_NEUTRAL,
    DIRECTION_FALLING,
    DIRECTION_RISING,
    DIRECTION_STABLE,
    DIRECTION_UNKNOWN,
    MECHANISM_OPPORTUNITY_COST,
    QUALITY_HIGH,
    QUALITY_LOW,
    QUALITY_MODERATE,
    QUALITY_STALE,
    FactorSignal,
)
from knowledge.integrity.provenance import Provenance


class RealYieldAdapter:
    """Transforms raw DFII10 FRED data into a canonical FactorSignal.

    This is the reference adapter implementation — every other Gold Factor
    adapter should follow this pattern:

    1. Accept a pd.Series (indexed by date) as primary input.
    2. Compute z-score and percentile over a trailing window.
    3. Map direction (rising/falling/stable/unknown).
    4. Map to gold influence bias and strength (inverse relationship).
    5. Assess data quality from recency.
    6. Return a frozen FactorSignal dataclass.
    """

    FACTOR_ID = "real_yield_10y"
    _THRESHOLD_BPS = 2.0
    _WINDOW_DEFAULT = 1260

    @classmethod
    def to_factor_signal(
        cls,
        series: pd.Series,
        observation_date: str | None = None,
        z_score_window: int = _WINDOW_DEFAULT,
    ) -> FactorSignal:
        if len(series) == 0:
            return cls._empty_signal(observation_date)

        obs_ts, value = cls._resolve_observation(series, observation_date)
        relevant = series[series.index <= obs_ts]
        if len(relevant) == 0:
            relevant = series

        window_data = cls._window(relevant, z_score_window)
        z_score, percentile = cls._compute_z(window_data, value)
        direction = cls._determine_direction(relevant)
        bias, strength = cls._compute_gold_influence(z_score)
        data_quality = cls._assess_data_quality(obs_ts)
        confidence = cls._compute_confidence(data_quality, len(window_data))

        return FactorSignal(
            factor_id=cls.FACTOR_ID,
            observation_date=obs_ts.strftime("%Y-%m-%d"),
            value=round(value, 4),
            z_score=round(z_score, 4),
            percentile=round(percentile, 4),
            direction=direction,
            influence_bias=bias,
            influence_strength=round(strength, 4),
            mechanism=MECHANISM_OPPORTUNITY_COST,
            data_quality=data_quality,
            confidence=round(confidence, 4),
            provenance=cls._make_provenance(),
        )

    # ── Internal helpers ──────────────────────────────────────────────

    @classmethod
    def _empty_signal(cls, observation_date: str | None) -> FactorSignal:
        return FactorSignal(
            factor_id=cls.FACTOR_ID,
            observation_date=observation_date or "",
            value=0.0,
            z_score=0.0,
            percentile=0.5,
            direction=DIRECTION_UNKNOWN,
            influence_bias=BIAS_NEUTRAL,
            influence_strength=0.0,
            mechanism=MECHANISM_OPPORTUNITY_COST,
            data_quality=QUALITY_STALE,
            confidence=0.0,
        )

    @staticmethod
    def _resolve_observation(
        series: pd.Series, observation_date: str | None,
    ) -> tuple[pd.Timestamp, float]:
        if observation_date is not None:
            obs_ts = pd.Timestamp(observation_date)
        else:
            obs_ts = series.index[-1]
        value = float(series[series.index <= obs_ts].iloc[-1])
        return obs_ts, value

    @staticmethod
    def _window(series: pd.Series, window: int) -> pd.Series:
        if len(series) <= window:
            return series
        return series.iloc[-window:]

    @staticmethod
    def _compute_z(
        window_data: pd.Series, value: float,
    ) -> tuple[float, float]:
        if len(window_data) < 30:
            return 0.0, 0.5
        mean = float(window_data.mean())
        std = float(window_data.std())
        if std <= 0:
            return 0.0, 0.5
        z_score = (value - mean) / std
        percentile = float((window_data <= value).sum() / len(window_data))
        return z_score, percentile

    @classmethod
    def _determine_direction(
        cls, series: pd.Series,
    ) -> str:
        values = series.dropna()
        if len(values) < 2:
            return DIRECTION_UNKNOWN
        diff = float(values.iloc[-1]) - float(values.iloc[-2])
        if diff > cls._THRESHOLD_BPS / 100.0:
            return DIRECTION_RISING
        if diff < -cls._THRESHOLD_BPS / 100.0:
            return DIRECTION_FALLING
        return DIRECTION_STABLE

    @staticmethod
    def _compute_gold_influence(
        z_score: float,
    ) -> tuple[str, float]:
        if z_score > 0.5:
            bias = BIAS_BEARISH
        elif z_score < -0.5:
            bias = BIAS_BULLISH
        else:
            bias = BIAS_NEUTRAL
        strength = -max(-1.0, min(1.0, z_score / 2.0))
        return bias, strength

    @staticmethod
    def _assess_data_quality(obs_ts: pd.Timestamp) -> str:
        now = pd.Timestamp.now(tz=obs_ts.tz) if obs_ts.tz is not None else pd.Timestamp.now()
        days_since = (now - obs_ts).days
        if days_since <= 2:
            return QUALITY_HIGH
        if days_since <= 7:
            return QUALITY_MODERATE
        if days_since <= 30:
            return QUALITY_LOW
        return QUALITY_STALE

    @staticmethod
    def _compute_confidence(quality: str, n_obs: int) -> float:
        base = {
            QUALITY_HIGH: 0.85,
            QUALITY_MODERATE: 0.70,
            QUALITY_LOW: 0.50,
            QUALITY_STALE: 0.30,
        }.get(quality, 0.30)
        if n_obs < 30:
            base *= 0.5
        return base

    @staticmethod
    def _make_provenance() -> Provenance:
        return Provenance(
            created_at=datetime.now(timezone.utc).isoformat(),
            created_by="real_yield_adapter.v1",
            entity_version="1.0.0",
        )
