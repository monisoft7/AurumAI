from knowledge.cai.contracts import (
    CrossAssetCorrelation,
    CORRELATION_POSITIVE,
    CORRELATION_NEGATIVE,
    CORRELATION_DIVERGING,
    CORRELATION_CONVERGING,
    CORRELATION_DECOUPLING,
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
