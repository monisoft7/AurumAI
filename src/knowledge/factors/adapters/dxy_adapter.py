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
    MECHANISM_CURRENCY_SUBSTITUTION,
    QUALITY_HIGH,
    QUALITY_LOW,
    QUALITY_MODERATE,
    QUALITY_STALE,
    FactorSignal,
)
from knowledge.factors.factor_config import FactorConfig
from knowledge.integrity.provenance import Provenance


class DXYAdapter:
    """Transforms raw DXY data into a canonical FactorSignal.

    This is the second reference Gold Factor adapter, following the
    exact same architecture as RealYieldAdapter:

    1. Accept a pd.Series (indexed by date) as primary input.
    2. Compute z-score and percentile over a trailing window.
    3. Map direction (rising/falling/stable/unknown).
    4. Map to gold influence bias and strength (inverse relationship:
       stronger USD → bearish gold).
    5. Assess data quality from recency.
    6. Apply RegimeAdjustment hook (identity for now).
    7. Return a frozen FactorSignal dataclass.

    Unlike RealYieldAdapter, all thresholds are driven by a FactorConfig
    instance rather than hardcoded class constants. This establishes
    the configurable pattern for every future Gold Factor.
    """

    CONFIG = FactorConfig(
        factor_id="us_dollar_index",
        name="US Dollar Index (DXY)",
        direction_threshold=0.20,
        z_score_window=1260,
        min_samples=30,
        influence_bias_threshold=0.5,
        influence_strength_scalar=2.0,
    )

    @classmethod
    def to_factor_signal(
        cls,
        series: pd.Series,
        observation_date: str | None = None,
        config: FactorConfig | None = None,
    ) -> FactorSignal:
        cfg = config or cls.CONFIG

        if len(series) == 0:
            return cls._empty_signal(cfg, observation_date)

        obs_ts, value = cls._resolve_observation(series, observation_date)
        relevant = series[series.index <= obs_ts]
        if len(relevant) == 0:
            relevant = series

        window_data = cls._window(relevant, cfg.z_score_window)
        z_score, percentile = cls._compute_z(window_data, value, cfg.min_samples)
        direction = cls._determine_direction(relevant, cfg.direction_threshold)
        bias, strength = cls._compute_gold_influence(
            z_score, cfg.influence_bias_threshold, cfg.influence_strength_scalar,
        )
        data_quality = cls._assess_data_quality(obs_ts, cfg)
        confidence = cls._compute_confidence(data_quality, len(window_data), cfg)

        return FactorSignal(
            factor_id=cfg.factor_id,
            observation_date=obs_ts.strftime("%Y-%m-%d"),
            value=round(value, 4),
            z_score=round(z_score, 4),
            percentile=round(percentile, 4),
            direction=direction,
            influence_bias=bias,
            influence_strength=round(strength, 4),
            mechanism=MECHANISM_CURRENCY_SUBSTITUTION,
            data_quality=data_quality,
            confidence=round(confidence, 4),
            provenance=cls._make_provenance(),
        )

    @classmethod
    def regime_adjust(
        cls,
        bias: str,
        strength: float,
        regime: str | None = None,
        config: FactorConfig | None = None,
    ) -> tuple[str, float]:
        """Apply regime-aware adjustment to gold influence.

        Identity implementation: returns bias and strength unchanged.
        Future implementations can override to adjust influence based
        on macro regime context (e.g., amplify in risk-off regimes
        where USD and gold both attract safe-haven flows, or invert
        in regimes where the dollar-gold correlation breaks down).
        """
        return bias, strength

    # ── Internal helpers ──────────────────────────────────────────────

    @classmethod
    def _empty_signal(
        cls, config: FactorConfig, observation_date: str | None,
    ) -> FactorSignal:
        return FactorSignal(
            factor_id=config.factor_id,
            observation_date=observation_date or "",
            value=0.0,
            z_score=0.0,
            percentile=0.5,
            direction=DIRECTION_UNKNOWN,
            influence_bias=BIAS_NEUTRAL,
            influence_strength=0.0,
            mechanism=MECHANISM_CURRENCY_SUBSTITUTION,
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
        window_data: pd.Series, value: float, min_samples: int,
    ) -> tuple[float, float]:
        if len(window_data) < min_samples:
            return 0.0, 0.5
        mean = float(window_data.mean())
        std = float(window_data.std())
        if std <= 0:
            return 0.0, 0.5
        z_score = (value - mean) / std
        percentile = float((window_data <= value).sum() / len(window_data))
        return z_score, percentile

    @staticmethod
    def _determine_direction(series: pd.Series, threshold: float) -> str:
        values = series.dropna()
        if len(values) < 2:
            return DIRECTION_UNKNOWN
        diff = float(values.iloc[-1]) - float(values.iloc[-2])
        if diff > threshold:
            return DIRECTION_RISING
        if diff < -threshold:
            return DIRECTION_FALLING
        return DIRECTION_STABLE

    @staticmethod
    def _compute_gold_influence(
        z_score: float, bias_threshold: float, scalar: float,
    ) -> tuple[str, float]:
        if z_score > bias_threshold:
            bias = BIAS_BEARISH
        elif z_score < -bias_threshold:
            bias = BIAS_BULLISH
        else:
            bias = BIAS_NEUTRAL
        strength = -max(-1.0, min(1.0, z_score / scalar))
        return bias, strength

    @staticmethod
    def _assess_data_quality(obs_ts: pd.Timestamp, config: FactorConfig) -> str:
        now = pd.Timestamp.now(tz=obs_ts.tz) if obs_ts.tz is not None else pd.Timestamp.now()
        days_since = (now - obs_ts).days
        if days_since <= config.quality_high_days:
            return QUALITY_HIGH
        if days_since <= config.quality_moderate_days:
            return QUALITY_MODERATE
        if days_since <= config.quality_low_days:
            return QUALITY_LOW
        return QUALITY_STALE

    @staticmethod
    def _compute_confidence(quality: str, n_obs: int, config: FactorConfig) -> float:
        base = {
            QUALITY_HIGH: config.confidence_high,
            QUALITY_MODERATE: config.confidence_moderate,
            QUALITY_LOW: config.confidence_low,
            QUALITY_STALE: config.confidence_stale,
        }.get(quality, config.confidence_stale)
        if n_obs < config.min_samples:
            base *= 0.5
        return base

    @staticmethod
    def _make_provenance() -> Provenance:
        return Provenance(
            created_at=datetime.now(timezone.utc).isoformat(),
            created_by="dxy_adapter.v1",
            entity_version="1.0.0",
        )
