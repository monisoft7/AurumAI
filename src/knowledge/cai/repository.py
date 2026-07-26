import json
from pathlib import Path
from typing import Any

from knowledge._compat import atomic_write_json
from knowledge.integrity.provenance import (
    Provenance,
    serialize_provenance,
    deserialize_provenance,
)

from knowledge.cai.contracts import (
    CrossAssetCorrelation,
    SpreadAnalysis,
    RelativeValueAssessment,
    FlowPressure,
    VolatilityRegime,
)


class CaiRepository:
    def save_correlation(self, obj: CrossAssetCorrelation, path: Path) -> None:
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
            "asset_class_a": obj.asset_class_a,
            "asset_class_b": obj.asset_class_b,
            "correlation_coefficient": obj.correlation_coefficient,
            "lookback_periods": obj.lookback_periods,
            "trend_direction": obj.trend_direction,
            "rolling_window": obj.rolling_window,
            "regime_stability": obj.regime_stability,
        }
        atomic_write_json(path, payload)

    def load_correlation(self, path: Path) -> CrossAssetCorrelation:
        payload = json.loads(path.read_text())
        return CrossAssetCorrelation(
            confidence=payload.get("confidence", 0.0),
            valid_from=payload.get("valid_from", ""),
            valid_until=payload.get("valid_until", ""),
            time_horizon=payload.get("time_horizon", ""),
            provenance=deserialize_provenance(payload.get("provenance")),
            evidence_references=payload.get("evidence_references", []),
            cross_references=payload.get("cross_references"),
            methodology_version=payload.get("methodology_version"),
            scenario_analysis=payload.get("scenario_analysis"),
            asset_class_a=payload.get("asset_class_a", ""),
            asset_class_b=payload.get("asset_class_b", ""),
            correlation_coefficient=payload.get("correlation_coefficient", 0.0),
            lookback_periods=payload.get("lookback_periods", 0),
            trend_direction=payload.get("trend_direction", "converging"),
            rolling_window=payload.get("rolling_window", "medium"),
            regime_stability=payload.get("regime_stability", 0.0),
        )

    def save_spread(self, obj: SpreadAnalysis, path: Path) -> None:
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
            "instrument_a": obj.instrument_a,
            "instrument_b": obj.instrument_b,
            "current_spread": obj.current_spread,
            "historical_mean": obj.historical_mean,
            "standard_deviation": obj.standard_deviation,
            "z_score": obj.z_score,
            "trend": obj.trend,
            "mean_reversion_signal": obj.mean_reversion_signal,
        }
        atomic_write_json(path, payload)

    def load_spread(self, path: Path) -> SpreadAnalysis:
        payload = json.loads(path.read_text())
        return SpreadAnalysis(
            confidence=payload.get("confidence", 0.0),
            valid_from=payload.get("valid_from", ""),
            valid_until=payload.get("valid_until", ""),
            time_horizon=payload.get("time_horizon", ""),
            provenance=deserialize_provenance(payload.get("provenance")),
            evidence_references=payload.get("evidence_references", []),
            cross_references=payload.get("cross_references"),
            methodology_version=payload.get("methodology_version"),
            scenario_analysis=payload.get("scenario_analysis"),
            instrument_a=payload.get("instrument_a", ""),
            instrument_b=payload.get("instrument_b", ""),
            current_spread=payload.get("current_spread", 0.0),
            historical_mean=payload.get("historical_mean", 0.0),
            standard_deviation=payload.get("standard_deviation", 0.0),
            z_score=payload.get("z_score", 0.0),
            trend=payload.get("trend", "stable"),
            mean_reversion_signal=payload.get("mean_reversion_signal", 0.0),
        )

    def save_relative_value(self, obj: RelativeValueAssessment, path: Path) -> None:
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
            "asset_class_a": obj.asset_class_a,
            "asset_class_b": obj.asset_class_b,
            "relative_z_score": obj.relative_z_score,
            "percentile_rank": obj.percentile_rank,
            "valuation_bias": obj.valuation_bias,
            "regime_consistency": obj.regime_consistency,
            "factor_exposures": dict(obj.factor_exposures),
        }
        atomic_write_json(path, payload)

    def load_relative_value(self, path: Path) -> RelativeValueAssessment:
        payload = json.loads(path.read_text())
        return RelativeValueAssessment(
            confidence=payload.get("confidence", 0.0),
            valid_from=payload.get("valid_from", ""),
            valid_until=payload.get("valid_until", ""),
            time_horizon=payload.get("time_horizon", ""),
            provenance=deserialize_provenance(payload.get("provenance")),
            evidence_references=payload.get("evidence_references", []),
            cross_references=payload.get("cross_references"),
            methodology_version=payload.get("methodology_version"),
            scenario_analysis=payload.get("scenario_analysis"),
            asset_class_a=payload.get("asset_class_a", ""),
            asset_class_b=payload.get("asset_class_b", ""),
            relative_z_score=payload.get("relative_z_score", 0.0),
            percentile_rank=payload.get("percentile_rank", 0.0),
            valuation_bias=payload.get("valuation_bias", "neutral"),
            regime_consistency=payload.get("regime_consistency", 0.0),
            factor_exposures=payload.get("factor_exposures", {}),
        )

    def save_flow_pressure(self, obj: FlowPressure, path: Path) -> None:
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
            "asset_class": obj.asset_class,
            "direction": obj.direction,
            "intensity": obj.intensity,
            "volume_z_score": obj.volume_z_score,
            "momentum": obj.momentum,
            "concentration": obj.concentration,
            "counterparty_risk": obj.counterparty_risk,
        }
        atomic_write_json(path, payload)

    def load_flow_pressure(self, path: Path) -> FlowPressure:
        payload = json.loads(path.read_text())
        return FlowPressure(
            confidence=payload.get("confidence", 0.0),
            valid_from=payload.get("valid_from", ""),
            valid_until=payload.get("valid_until", ""),
            time_horizon=payload.get("time_horizon", ""),
            provenance=deserialize_provenance(payload.get("provenance")),
            evidence_references=payload.get("evidence_references", []),
            cross_references=payload.get("cross_references"),
            methodology_version=payload.get("methodology_version"),
            scenario_analysis=payload.get("scenario_analysis"),
            asset_class=payload.get("asset_class", ""),
            direction=payload.get("direction", "stable"),
            intensity=payload.get("intensity", 0.0),
            volume_z_score=payload.get("volume_z_score", 0.0),
            momentum=payload.get("momentum", "stable"),
            concentration=payload.get("concentration", 0.0),
            counterparty_risk=payload.get("counterparty_risk"),
        )

    def save_volatility_regime(self, obj: VolatilityRegime, path: Path) -> None:
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
            "asset_class": obj.asset_class,
            "current_state": obj.current_state,
            "previous_state": obj.previous_state,
            "regime_persistence": obj.regime_persistence,
            "mean_reversion_half_life_days": obj.mean_reversion_half_life_days,
            "tail_risk_index": obj.tail_risk_index,
            "regime_drivers": obj.regime_drivers,
        }
        atomic_write_json(path, payload)

    def load_volatility_regime(self, path: Path) -> VolatilityRegime:
        payload = json.loads(path.read_text())
        return VolatilityRegime(
            confidence=payload.get("confidence", 0.0),
            valid_from=payload.get("valid_from", ""),
            valid_until=payload.get("valid_until", ""),
            time_horizon=payload.get("time_horizon", ""),
            provenance=deserialize_provenance(payload.get("provenance")),
            evidence_references=payload.get("evidence_references", []),
            cross_references=payload.get("cross_references"),
            methodology_version=payload.get("methodology_version"),
            scenario_analysis=payload.get("scenario_analysis"),
            asset_class=payload.get("asset_class", ""),
            current_state=payload.get("current_state", "moderate"),
            previous_state=payload.get("previous_state", "moderate"),
            regime_persistence=payload.get("regime_persistence", 0.0),
            mean_reversion_half_life_days=payload.get("mean_reversion_half_life_days", 0.0),
            tail_risk_index=payload.get("tail_risk_index", 0.0),
            regime_drivers=payload.get("regime_drivers"),
        )
