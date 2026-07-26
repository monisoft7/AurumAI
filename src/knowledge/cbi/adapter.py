from knowledge.cbi.contracts import (
    PolicyBiasScore,
    RatePathProjection,
    ForwardGuidanceRecord,
    LiquidityOutlook,
    GlobalMonetaryRegime,
    DIRECTION_TIGHTENING,
    DIRECTION_EASING,
    DIRECTION_NEUTRAL,
    CLASSIFICATION_EXPANDING,
    CLASSIFICATION_STABLE,
    CLASSIFICATION_CONTRACTING,
    REGIME_SYNCHRONIZED_EASING,
    REGIME_SYNCHRONIZED_TIGHTENING,
    REGIME_DIVERGENT,
    REGIME_TRANSITION,
    REGIME_EMERGENCY,
)
from knowledge.evidence.evidence import Evidence


class CbiEvidenceAdapter:
    def policy_bias_to_evidence(self, obj: PolicyBiasScore) -> Evidence:
        bias_map = {
            DIRECTION_TIGHTENING: "bearish",
            DIRECTION_EASING: "bullish",
            DIRECTION_NEUTRAL: "neutral",
        }
        return Evidence(
            evidence_id=f"cbi_policy_{obj.central_bank}",
            source_node_id=f"cbi_{obj.central_bank}",
            event_type="CBI_POLICY",
            condition={"central_bank": obj.central_bank, "direction": obj.direction},
            horizon_days=0,
            sample_count=1,
            average_return_pct=0.0,
            confidence=obj.confidence,
            bias=bias_map.get(obj.direction, "neutral"),
            explanation=(
                f"PolicyBiasScore for {obj.central_bank}: "
                f"{obj.direction} ({obj.score})"
            ),
            provenance=obj.provenance,
            metadata={
                "object_type": "PolicyBiasScore",
                "central_bank": obj.central_bank,
                "score": obj.score,
                "direction": obj.direction,
                "score_components": dict(obj.score_components),
                "valid_from": obj.valid_from,
                "valid_until": obj.valid_until,
                "time_horizon": obj.time_horizon,
                "evidence_references": obj.evidence_references,
                "cross_references": obj.cross_references,
                "methodology_version": obj.methodology_version,
                "scenario_analysis": obj.scenario_analysis,
            },
        )

    def rate_path_to_evidence(self, obj: RatePathProjection) -> Evidence:
        return Evidence(
            evidence_id=f"cbi_rate_{obj.central_bank}",
            source_node_id=f"cbi_{obj.central_bank}",
            event_type="CBI_RATE_PATH",
            condition={"central_bank": obj.central_bank},
            horizon_days=0,
            sample_count=1,
            average_return_pct=0.0,
            confidence=obj.confidence,
            bias="neutral",
            explanation=(
                f"RatePathProjection for {obj.central_bank}: "
                f"current {obj.current_rate}bps, "
                f"{len(obj.base_path)} meeting path, "
                f"CI {obj.confidence_interval}bps"
            ),
            provenance=obj.provenance,
            metadata={
                "object_type": "RatePathProjection",
                "central_bank": obj.central_bank,
                "base_path": obj.base_path,
                "confidence_interval": obj.confidence_interval,
                "current_rate": obj.current_rate,
                "valid_from": obj.valid_from,
                "valid_until": obj.valid_until,
                "time_horizon": obj.time_horizon,
                "evidence_references": obj.evidence_references,
                "cross_references": obj.cross_references,
                "methodology_version": obj.methodology_version,
                "scenario_analysis": obj.scenario_analysis,
            },
        )

    def forward_guidance_to_evidence(self, obj: ForwardGuidanceRecord) -> Evidence:
        return Evidence(
            evidence_id=f"cbi_guidance_{obj.central_bank}",
            source_node_id=f"cbi_{obj.central_bank}",
            event_type="CBI_GUIDANCE",
            condition={"central_bank": obj.central_bank, "guidance_type": obj.guidance_type},
            horizon_days=0,
            sample_count=1,
            average_return_pct=0.0,
            confidence=obj.confidence,
            bias="neutral",
            explanation=(
                f"ForwardGuidanceRecord for {obj.central_bank}: "
                f"{obj.guidance_type} — {obj.guidance_text[:120]}"
            ),
            provenance=obj.provenance,
            metadata={
                "object_type": "ForwardGuidanceRecord",
                "central_bank": obj.central_bank,
                "guidance_type": obj.guidance_type,
                "guidance_text": obj.guidance_text,
                "credibility_score": obj.credibility_score,
                "language_delta": obj.language_delta,
                "data_quality_flags": obj.data_quality_flags,
                "valid_from": obj.valid_from,
                "valid_until": obj.valid_until,
                "time_horizon": obj.time_horizon,
                "evidence_references": obj.evidence_references,
                "cross_references": obj.cross_references,
                "methodology_version": obj.methodology_version,
                "scenario_analysis": obj.scenario_analysis,
            },
        )

    def liquidity_to_evidence(self, obj: LiquidityOutlook) -> Evidence:
        bias_map = {
            CLASSIFICATION_EXPANDING: "bullish",
            CLASSIFICATION_STABLE: "neutral",
            CLASSIFICATION_CONTRACTING: "bearish",
        }
        return Evidence(
            evidence_id="cbi_liquidity",
            source_node_id="cbi_liquidity",
            event_type="CBI_LIQUIDITY",
            condition={"classification": obj.classification, "pace": obj.pace_qualifier},
            horizon_days=0,
            sample_count=1,
            average_return_pct=0.0,
            confidence=obj.confidence,
            bias=bias_map.get(obj.classification, "neutral"),
            explanation=(
                f"LiquidityOutlook: {obj.pace_qualifier} {obj.classification}, "
                f"reserves {obj.reserve_trend}"
            ),
            provenance=obj.provenance,
            metadata={
                "object_type": "LiquidityOutlook",
                "classification": obj.classification,
                "pace_qualifier": obj.pace_qualifier,
                "g4_balance_sheet_trajectory": obj.g4_balance_sheet_trajectory,
                "reserve_trend": obj.reserve_trend,
                "money_market_stress": obj.money_market_stress,
                "fiscal_liquidity_effects": obj.fiscal_liquidity_effects,
                "valid_from": obj.valid_from,
                "valid_until": obj.valid_until,
                "time_horizon": obj.time_horizon,
                "evidence_references": obj.evidence_references,
                "cross_references": obj.cross_references,
                "methodology_version": obj.methodology_version,
                "scenario_analysis": obj.scenario_analysis,
            },
        )

    def regime_to_evidence(self, obj: GlobalMonetaryRegime) -> Evidence:
        bias_map = {
            REGIME_SYNCHRONIZED_EASING: "bullish",
            REGIME_SYNCHRONIZED_TIGHTENING: "bearish",
            REGIME_DIVERGENT: "neutral",
            REGIME_TRANSITION: "neutral",
            REGIME_EMERGENCY: "bearish",
        }
        return Evidence(
            evidence_id="cbi_global_regime",
            source_node_id="cbi_global",
            event_type="CBI_REGIME",
            condition={"regime": obj.regime},
            horizon_days=0,
            sample_count=1,
            average_return_pct=0.0,
            confidence=obj.confidence,
            bias=bias_map.get(obj.regime, "neutral"),
            explanation=(
                f"GlobalMonetaryRegime: {obj.regime} — "
                f"{obj.regime_description[:200]}"
            ),
            provenance=obj.provenance,
            metadata={
                "object_type": "GlobalMonetaryRegime",
                "regime": obj.regime,
                "regime_description": obj.regime_description,
                "aggregate_monetary_stance": obj.aggregate_monetary_stance,
                "synchronization_measure": obj.synchronization_measure,
                "transition_signals": obj.transition_signals,
                "valid_from": obj.valid_from,
                "valid_until": obj.valid_until,
                "time_horizon": obj.time_horizon,
                "evidence_references": obj.evidence_references,
                "cross_references": obj.cross_references,
                "methodology_version": obj.methodology_version,
                "scenario_analysis": obj.scenario_analysis,
            },
        )
