import json
from pathlib import Path
from typing import Any

from knowledge._compat import atomic_write_json
from knowledge.integrity.provenance import (
    Provenance,
    serialize_provenance,
    deserialize_provenance,
)

from knowledge.cbi.contracts import (
    PolicyBiasScore,
    RatePathProjection,
    ForwardGuidanceRecord,
    LiquidityOutlook,
    GlobalMonetaryRegime,
)


class CbiRepository:
    def save_policy_bias(self, obj: PolicyBiasScore, path: Path) -> None:
        payload: dict[str, Any] = {
            "confidence": obj.confidence,
            "valid_from": obj.valid_from,
            "valid_until": obj.valid_until,
            "time_horizon": obj.time_horizon,
            "provenance": serialize_provenance(obj.provenance),
            "evidence_references": obj.evidence_references,
            "cross_references": obj.cross_references,
            "methodology_version": obj.methodology_version,
            "scenario_analysis": obj.scenario_analysis,
            "central_bank": obj.central_bank,
            "score": obj.score,
            "direction": obj.direction,
            "score_components": dict(obj.score_components),
        }
        atomic_write_json(path, payload)

    def load_policy_bias(self, path: Path) -> PolicyBiasScore:
        payload = json.loads(path.read_text())
        return PolicyBiasScore(
            confidence=payload.get("confidence", 0.0),
            valid_from=payload.get("valid_from", ""),
            valid_until=payload.get("valid_until", ""),
            time_horizon=payload.get("time_horizon", "T0"),
            provenance=deserialize_provenance(payload.get("provenance")),
            evidence_references=payload.get("evidence_references", []),
            cross_references=payload.get("cross_references"),
            methodology_version=payload.get("methodology_version"),
            scenario_analysis=payload.get("scenario_analysis"),
            central_bank=payload.get("central_bank", ""),
            score=payload.get("score", 0),
            direction=payload.get("direction", "neutral"),
            score_components=payload.get("score_components", {}),
        )

    def save_rate_path(self, obj: RatePathProjection, path: Path) -> None:
        payload: dict[str, Any] = {
            "confidence": obj.confidence,
            "valid_from": obj.valid_from,
            "valid_until": obj.valid_until,
            "time_horizon": obj.time_horizon,
            "provenance": serialize_provenance(obj.provenance),
            "evidence_references": obj.evidence_references,
            "cross_references": obj.cross_references,
            "methodology_version": obj.methodology_version,
            "scenario_analysis": obj.scenario_analysis,
            "central_bank": obj.central_bank,
            "base_path": obj.base_path,
            "confidence_interval": obj.confidence_interval,
            "current_rate": obj.current_rate,
        }
        atomic_write_json(path, payload)

    def load_rate_path(self, path: Path) -> RatePathProjection:
        payload = json.loads(path.read_text())
        return RatePathProjection(
            confidence=payload.get("confidence", 0.0),
            valid_from=payload.get("valid_from", ""),
            valid_until=payload.get("valid_until", ""),
            time_horizon=payload.get("time_horizon", "T0"),
            provenance=deserialize_provenance(payload.get("provenance")),
            evidence_references=payload.get("evidence_references", []),
            cross_references=payload.get("cross_references"),
            methodology_version=payload.get("methodology_version"),
            scenario_analysis=payload.get("scenario_analysis"),
            central_bank=payload.get("central_bank", ""),
            base_path=payload.get("base_path", []),
            confidence_interval=payload.get("confidence_interval", 0),
            current_rate=payload.get("current_rate", 0),
        )

    def save_forward_guidance(self, obj: ForwardGuidanceRecord, path: Path) -> None:
        payload: dict[str, Any] = {
            "confidence": obj.confidence,
            "valid_from": obj.valid_from,
            "valid_until": obj.valid_until,
            "time_horizon": obj.time_horizon,
            "provenance": serialize_provenance(obj.provenance),
            "evidence_references": obj.evidence_references,
            "cross_references": obj.cross_references,
            "methodology_version": obj.methodology_version,
            "scenario_analysis": obj.scenario_analysis,
            "central_bank": obj.central_bank,
            "guidance_type": obj.guidance_type,
            "guidance_text": obj.guidance_text,
            "credibility_score": obj.credibility_score,
            "language_delta": obj.language_delta,
            "data_quality_flags": obj.data_quality_flags,
        }
        atomic_write_json(path, payload)

    def load_forward_guidance(self, path: Path) -> ForwardGuidanceRecord:
        payload = json.loads(path.read_text())
        return ForwardGuidanceRecord(
            confidence=payload.get("confidence", 0.0),
            valid_from=payload.get("valid_from", ""),
            valid_until=payload.get("valid_until", ""),
            time_horizon=payload.get("time_horizon", "T0"),
            provenance=deserialize_provenance(payload.get("provenance")),
            evidence_references=payload.get("evidence_references", []),
            cross_references=payload.get("cross_references"),
            methodology_version=payload.get("methodology_version"),
            scenario_analysis=payload.get("scenario_analysis"),
            central_bank=payload.get("central_bank", ""),
            guidance_type=payload.get("guidance_type", ""),
            guidance_text=payload.get("guidance_text", ""),
            credibility_score=payload.get("credibility_score", 0.0),
            language_delta=payload.get("language_delta", ""),
            data_quality_flags=payload.get("data_quality_flags"),
        )

    def save_liquidity_outlook(self, obj: LiquidityOutlook, path: Path) -> None:
        payload: dict[str, Any] = {
            "confidence": obj.confidence,
            "valid_from": obj.valid_from,
            "valid_until": obj.valid_until,
            "time_horizon": obj.time_horizon,
            "provenance": serialize_provenance(obj.provenance),
            "evidence_references": obj.evidence_references,
            "cross_references": obj.cross_references,
            "methodology_version": obj.methodology_version,
            "scenario_analysis": obj.scenario_analysis,
            "classification": obj.classification,
            "pace_qualifier": obj.pace_qualifier,
            "g4_balance_sheet_trajectory": obj.g4_balance_sheet_trajectory,
            "reserve_trend": obj.reserve_trend,
            "money_market_stress": obj.money_market_stress,
            "fiscal_liquidity_effects": obj.fiscal_liquidity_effects,
        }
        atomic_write_json(path, payload)

    def load_liquidity_outlook(self, path: Path) -> LiquidityOutlook:
        payload = json.loads(path.read_text())
        return LiquidityOutlook(
            confidence=payload.get("confidence", 0.0),
            valid_from=payload.get("valid_from", ""),
            valid_until=payload.get("valid_until", ""),
            time_horizon=payload.get("time_horizon", "T0"),
            provenance=deserialize_provenance(payload.get("provenance")),
            evidence_references=payload.get("evidence_references", []),
            cross_references=payload.get("cross_references"),
            methodology_version=payload.get("methodology_version"),
            scenario_analysis=payload.get("scenario_analysis"),
            classification=payload.get("classification", ""),
            pace_qualifier=payload.get("pace_qualifier", ""),
            g4_balance_sheet_trajectory=payload.get("g4_balance_sheet_trajectory", []),
            reserve_trend=payload.get("reserve_trend", ""),
            money_market_stress=payload.get("money_market_stress", []),
            fiscal_liquidity_effects=payload.get("fiscal_liquidity_effects", ""),
        )

    def save_regime(self, obj: GlobalMonetaryRegime, path: Path) -> None:
        payload: dict[str, Any] = {
            "confidence": obj.confidence,
            "valid_from": obj.valid_from,
            "valid_until": obj.valid_until,
            "time_horizon": obj.time_horizon,
            "provenance": serialize_provenance(obj.provenance),
            "evidence_references": obj.evidence_references,
            "cross_references": obj.cross_references,
            "methodology_version": obj.methodology_version,
            "scenario_analysis": obj.scenario_analysis,
            "regime": obj.regime,
            "regime_description": obj.regime_description,
            "aggregate_monetary_stance": obj.aggregate_monetary_stance,
            "synchronization_measure": obj.synchronization_measure,
            "transition_signals": obj.transition_signals,
        }
        atomic_write_json(path, payload)

    def load_regime(self, path: Path) -> GlobalMonetaryRegime:
        payload = json.loads(path.read_text())
        return GlobalMonetaryRegime(
            confidence=payload.get("confidence", 0.0),
            valid_from=payload.get("valid_from", ""),
            valid_until=payload.get("valid_until", ""),
            time_horizon=payload.get("time_horizon", "T0"),
            provenance=deserialize_provenance(payload.get("provenance")),
            evidence_references=payload.get("evidence_references", []),
            cross_references=payload.get("cross_references"),
            methodology_version=payload.get("methodology_version"),
            scenario_analysis=payload.get("scenario_analysis"),
            regime=payload.get("regime", ""),
            regime_description=payload.get("regime_description", ""),
            aggregate_monetary_stance=payload.get("aggregate_monetary_stance", 0.0),
            synchronization_measure=payload.get("synchronization_measure", 0.0),
            transition_signals=payload.get("transition_signals", []),
        )
