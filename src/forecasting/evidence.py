from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from knowledge._compat import FrozenDict, freeze_dict

if TYPE_CHECKING:
    from forecasting.confidence import ForecastConfidence
    from forecasting.context import ForecastContext
    from forecasting.knowledge import ForecastPackage
    from forecasting.provenance import ForecastProvenance

_EVIDENCE_NAMESPACE = uuid.UUID("6e8d3e9a-1b2c-4f5a-9e7d-8f6a5b4c3d2e")


@dataclass(frozen=True)
class ForecastEvidence:
    evidence_id: str
    evidence_strength: float
    evidence_sources: tuple[str, ...]
    supporting_context: dict[str, Any]
    confidence_snapshot: dict[str, float]
    provenance_snapshot: dict[str, Any]
    metadata: dict[str, Any]

    def __post_init__(self) -> None:
        object.__setattr__(self, "supporting_context", freeze_dict(self.supporting_context))
        object.__setattr__(self, "confidence_snapshot", freeze_dict(self.confidence_snapshot))
        object.__setattr__(self, "provenance_snapshot", freeze_dict(self.provenance_snapshot))
        object.__setattr__(self, "metadata", freeze_dict(self.metadata))

    def to_dict(self) -> dict[str, Any]:
        return {
            "evidence_id": self.evidence_id,
            "evidence_strength": self.evidence_strength,
            "evidence_sources": list(self.evidence_sources),
            "supporting_context": dict(self.supporting_context),
            "confidence_snapshot": dict(self.confidence_snapshot),
            "provenance_snapshot": dict(self.provenance_snapshot),
            "metadata": dict(self.metadata),
        }


class ForecastEvidenceBuilder:

    def build(
        self,
        package: "ForecastPackage",
        context: "ForecastContext",
        confidence: "ForecastConfidence",
        provenance: "ForecastProvenance",
    ) -> ForecastEvidence:
        evidence_id = self._compute_evidence_id(provenance)
        evidence_strength = confidence.overall
        evidence_sources = tuple(sorted(package.results.keys()))
        supporting_context = self._build_supporting_context(context)
        confidence_snapshot = confidence.to_dict()
        provenance_snapshot = provenance.to_dict()
        metadata = self._build_metadata(package)

        return ForecastEvidence(
            evidence_id=evidence_id,
            evidence_strength=evidence_strength,
            evidence_sources=evidence_sources,
            supporting_context=supporting_context,
            confidence_snapshot=confidence_snapshot,
            provenance_snapshot=provenance_snapshot,
            metadata=metadata,
        )

    @staticmethod
    def _compute_evidence_id(provenance: "ForecastProvenance") -> str:
        seed = f"{provenance.data_hash}:{provenance.model_version}"
        return str(uuid.uuid5(_EVIDENCE_NAMESPACE, seed))

    @staticmethod
    def _build_supporting_context(context: "ForecastContext") -> dict[str, Any]:
        return {
            "current_regime": context.current_regime,
            "regime_confidence": context.regime_confidence,
            "news_mood": context.news_mood,
            "news_confidence": context.news_confidence,
            "fomc_mood": context.fomc_mood,
            "fomc_confidence": context.fomc_confidence,
            "num_recent_events": len(context.recent_events),
            "data_date_range": list(context.data_date_range),
        }

    @staticmethod
    def _build_metadata(package: "ForecastPackage") -> dict[str, Any]:
        num_points = 0
        for result in package.results.values():
            num_points += len(result.points)
        return {
            "target_variable": package.target_variable,
            "horizon": package.horizon,
            "num_models": len(package.results),
            "num_forecast_points": num_points,
            "model_spec_count": len(package.model_specs),
        }
