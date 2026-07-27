from knowledge.cai.contracts import (
    CrossAssetCorrelation,
    SpreadAnalysis,
    VolatilityRegime,
    CORRELATION_POSITIVE,
    CORRELATION_NEGATIVE,
    CORRELATION_DIVERGING,
    CORRELATION_CONVERGING,
    CORRELATION_DECOUPLING,
    SPREAD_NARROWING,
    SPREAD_WIDENING,
    SPREAD_STABLE,
    SPREAD_INVERSION,
    VOL_LOW,
    VOL_MODERATE,
    VOL_ELEVATED,
    VOL_HIGH,
    VOL_EXTREME,
)
from knowledge.evidence.evidence import Evidence


class CaiEvidenceAdapter:
    def cross_asset_correlation_to_evidence(self, obj: CrossAssetCorrelation) -> Evidence:
        bias_map = {
            CORRELATION_POSITIVE: "neutral",
            CORRELATION_NEGATIVE: "bearish",
            CORRELATION_DIVERGING: "neutral",
            CORRELATION_CONVERGING: "neutral",
            CORRELATION_DECOUPLING: "bearish",
        }
        return Evidence(
            evidence_id=f"cai_corr_{obj.asset_class_a}_{obj.asset_class_b}",
            source_node_id=f"cai_{obj.asset_class_a}_{obj.asset_class_b}",
            event_type="CAI_CORRELATION",
            condition={
                "asset_a": obj.asset_class_a,
                "asset_b": obj.asset_class_b,
                "trend": obj.trend_direction,
            },
            horizon_days=0,
            sample_count=1,
            average_return_pct=0.0,
            confidence=obj.confidence,
            bias=bias_map.get(obj.trend_direction, "neutral"),
            explanation=(
                f"CrossAssetCorrelation {obj.asset_class_a}/{obj.asset_class_b}: "
                f"r={obj.correlation_coefficient:.2f}, "
                f"trend={obj.trend_direction}"
            ),
            provenance=obj.provenance,
            metadata={
                "object_type": "CrossAssetCorrelation",
                "asset_class_a": obj.asset_class_a,
                "asset_class_b": obj.asset_class_b,
                "correlation_coefficient": obj.correlation_coefficient,
                "lookback_periods": obj.lookback_periods,
                "trend_direction": obj.trend_direction,
                "rolling_window": obj.rolling_window,
                "regime_stability": obj.regime_stability,
                "valid_from": obj.valid_from,
                "valid_until": obj.valid_until,
                "time_horizon": obj.time_horizon,
                "evidence_references": obj.evidence_references,
                "cross_references": obj.cross_references,
                "methodology_version": obj.methodology_version,
                "scenario_analysis": obj.scenario_analysis,
            },
        )

    def spread_analysis_to_evidence(self, obj: SpreadAnalysis) -> Evidence:
        bias_map = {
            SPREAD_NARROWING: "bullish",
            SPREAD_WIDENING: "bearish",
            SPREAD_STABLE: "neutral",
            SPREAD_INVERSION: "bearish",
        }
        return Evidence(
            evidence_id=f"cai_spread_{obj.instrument_a}_{obj.instrument_b}",
            source_node_id=f"cai_{obj.instrument_a}_{obj.instrument_b}",
            event_type="CAI_SPREAD",
            condition={
                "instrument_a": obj.instrument_a,
                "instrument_b": obj.instrument_b,
                "trend": obj.trend,
            },
            horizon_days=0,
            sample_count=1,
            average_return_pct=0.0,
            confidence=obj.confidence,
            bias=bias_map.get(obj.trend, "neutral"),
            explanation=(
                f"SpreadAnalysis {obj.instrument_a}/{obj.instrument_b}: "
                f"spread={obj.current_spread:.2f}, "
                f"z={obj.z_score:.2f}, "
                f"trend={obj.trend}"
            ),
            provenance=obj.provenance,
            metadata={
                "object_type": "SpreadAnalysis",
                "instrument_a": obj.instrument_a,
                "instrument_b": obj.instrument_b,
                "current_spread": obj.current_spread,
                "historical_mean": obj.historical_mean,
                "standard_deviation": obj.standard_deviation,
                "z_score": obj.z_score,
                "trend": obj.trend,
                "mean_reversion_signal": obj.mean_reversion_signal,
                "valid_from": obj.valid_from,
                "valid_until": obj.valid_until,
                "time_horizon": obj.time_horizon,
                "evidence_references": obj.evidence_references,
                "cross_references": obj.cross_references,
                "methodology_version": obj.methodology_version,
                "scenario_analysis": obj.scenario_analysis,
            },
        )

    def volatility_regime_to_evidence(self, obj: VolatilityRegime) -> Evidence:
        bias_map = {
            VOL_LOW: "bullish",
            VOL_MODERATE: "neutral",
            VOL_ELEVATED: "bearish",
            VOL_HIGH: "bearish",
            VOL_EXTREME: "bearish",
        }
        return Evidence(
            evidence_id=f"cai_vol_{obj.asset_class}",
            source_node_id=f"cai_{obj.asset_class}",
            event_type="CAI_VOLATILITY",
            condition={
                "asset_class": obj.asset_class,
                "current_state": obj.current_state,
            },
            horizon_days=0,
            sample_count=1,
            average_return_pct=0.0,
            confidence=obj.confidence,
            bias=bias_map.get(obj.current_state, "neutral"),
            explanation=(
                f"VolatilityRegime {obj.asset_class}: "
                f"{obj.current_state} (prev: {obj.previous_state}), "
                f"persistence={obj.regime_persistence:.2f}"
            ),
            provenance=obj.provenance,
            metadata={
                "object_type": "VolatilityRegime",
                "asset_class": obj.asset_class,
                "current_state": obj.current_state,
                "previous_state": obj.previous_state,
                "regime_persistence": obj.regime_persistence,
                "mean_reversion_half_life_days": obj.mean_reversion_half_life_days,
                "tail_risk_index": obj.tail_risk_index,
                "regime_drivers": obj.regime_drivers,
                "valid_from": obj.valid_from,
                "valid_until": obj.valid_until,
                "time_horizon": obj.time_horizon,
                "evidence_references": obj.evidence_references,
                "cross_references": obj.cross_references,
                "methodology_version": obj.methodology_version,
                "scenario_analysis": obj.scenario_analysis,
            },
        )
