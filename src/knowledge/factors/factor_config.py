from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class FactorConfig:
    """Frozen configuration for a gold factor adapter.

    Every configurable threshold lives here. Each factor adapter
    defines its own FactorConfig instance with factor-specific defaults.
    This replaces hardcoded class constants with an explicit, shareable
    configuration object.

    Fields (groups):
        identity: factor_id, name
        signal computation: direction_threshold, z_score_window, min_samples
        gold influence: influence_bias_threshold, influence_strength_scalar
        confidence: confidence_high, _moderate, _low, _stale
        data quality recency: quality_high_days, _moderate_days, _low_days
    """
    factor_id: str
    name: str = ""
    direction_threshold: float = 2.0
    z_score_window: int = 1260
    min_samples: int = 30
    influence_bias_threshold: float = 0.5
    influence_strength_scalar: float = 2.0
    confidence_high: float = 0.85
    confidence_moderate: float = 0.70
    confidence_low: float = 0.50
    confidence_stale: float = 0.30
    quality_high_days: int = 2
    quality_moderate_days: int = 7
    quality_low_days: int = 30
