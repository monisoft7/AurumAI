from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from knowledge.evidence.evidence import Evidence
from knowledge.evidence.collection import EvidenceCollection


@dataclass(frozen=True)
class WeightConfig:
    confidence_exponent: float = 2.0
    sample_baseline: int = 100
    provenance_bonus: float = 0.3
    consistency_bonus: float = 0.2
    recency_days: int = 365
    combine_method: str = "geometric"


_BIAS_POSITIVE = "gold_positive_bias"
_BIAS_NEGATIVE = "gold_negative_bias"
_BIAS_MIXED = "mixed_or_context_dependent"


@dataclass(frozen=True)
class WeightFactors:
    evidence_id: str
    confidence_factor: float
    sample_factor: float
    provenance_factor: float
    consistency_factor: float
    recency_factor: float
    composite_weight: float


@dataclass(frozen=True)
class WeightedAggregate:
    weighted_avg_return: float
    weighted_avg_confidence: float
    effective_sample_size: float
    total_raw_weight: float
    item_count: int
    weight_factors: tuple[WeightFactors, ...] = field(default_factory=tuple)
    attribution: dict[str, float] = field(default_factory=dict)


class EvidenceWeighter:
    def __init__(self, config: WeightConfig | None = None):
        self._config = config or WeightConfig()

    def weigh(
        self,
        collection: EvidenceCollection,
        as_of: datetime | None = None,
    ) -> WeightedAggregate:
        items = list(collection)
        if not items:
            return WeightedAggregate(
                weighted_avg_return=0.0,
                weighted_avg_confidence=0.0,
                effective_sample_size=0.0,
                total_raw_weight=0.0,
                item_count=0,
            )

        majority_map = self._compute_majority_bias(items)
        factors = [
            self._compute_factors(ev, majority_map, as_of=as_of) for ev in items
        ]

        total_w = sum(f.composite_weight for f in factors)

        attribution: dict[str, float] = {}
        if total_w > 0.0:
            for ev, f in zip(items, factors):
                et = ev.event_type
                attribution[et] = attribution.get(et, 0.0) + (f.composite_weight / total_w)

        if total_w == 0.0:
            return WeightedAggregate(
                weighted_avg_return=0.0,
                weighted_avg_confidence=0.0,
                effective_sample_size=0.0,
                total_raw_weight=0.0,
                item_count=len(items),
                weight_factors=tuple(factors),
                attribution=attribution,
            )

        w_ret = (
            sum(f.composite_weight * ev.average_return_pct for ev, f in zip(items, factors))
            / total_w
        )
        w_conf = (
            sum(f.composite_weight * ev.confidence for ev, f in zip(items, factors))
            / total_w
        )
        w_sq = sum(f.composite_weight ** 2 for f in factors)
        ess = (total_w * total_w) / w_sq if w_sq > 0 else 0.0

        return WeightedAggregate(
            weighted_avg_return=round(w_ret, 6),
            weighted_avg_confidence=round(w_conf, 6),
            effective_sample_size=round(ess, 2),
            total_raw_weight=round(total_w, 6),
            item_count=len(items),
            weight_factors=tuple(factors),
            attribution=attribution,
        )

    def _compute_majority_bias(
        self, items: list[Evidence]
    ) -> dict[str, str]:
        by_type: dict[str, list[str]] = {}
        for ev in items:
            by_type.setdefault(ev.event_type, []).append(ev.bias)
        majority: dict[str, str] = {}
        for et, biases in by_type.items():
            pos = sum(1 for b in biases if b == _BIAS_POSITIVE)
            neg = sum(1 for b in biases if b == _BIAS_NEGATIVE)
            if pos > neg:
                majority[et] = _BIAS_POSITIVE
            elif neg > pos:
                majority[et] = _BIAS_NEGATIVE
            else:
                majority[et] = _BIAS_MIXED
        return majority

    def _compute_factors(
        self,
        ev: Evidence,
        majority_map: dict[str, str],
        as_of: datetime | None = None,
    ) -> WeightFactors:
        cf = self._confidence_factor(ev.confidence)
        sf = self._sample_factor(ev.sample_count)
        pf = self._provenance_factor(ev.provenance is not None)
        cosf = self._consistency_factor(ev.bias, ev.event_type, majority_map)
        rf = self._recency_factor(ev, as_of=as_of)

        if self._config.combine_method == "arithmetic":
            composite = (cf + sf + pf + cosf + rf) / 5.0
        else:
            composite = (cf * sf * pf * cosf * rf) ** (1.0 / 5.0)

        return WeightFactors(
            evidence_id=ev.evidence_id,
            confidence_factor=round(cf, 6),
            sample_factor=round(sf, 6),
            provenance_factor=round(pf, 6),
            consistency_factor=round(cosf, 6),
            recency_factor=round(rf, 6),
            composite_weight=round(composite, 6),
        )

    def _confidence_factor(self, confidence: float) -> float:
        return min(max(confidence, 0.0), 1.0) ** self._config.confidence_exponent

    def _sample_factor(self, sample_count: int) -> float:
        if sample_count <= 0:
            return 0.0
        return min(sample_count / self._config.sample_baseline, 1.0)

    def _provenance_factor(self, has_provenance: bool) -> float:
        base = 1.0 if has_provenance else 0.0
        return min(base + self._config.provenance_bonus, 1.0)

    def _consistency_factor(
        self, bias: str, event_type: str, majority_map: dict[str, str]
    ) -> float:
        maj = majority_map.get(event_type, _BIAS_MIXED)
        if maj == _BIAS_MIXED:
            return 0.5 + self._config.consistency_bonus / 2.0
        if bias == maj:
            return 1.0
        return 1.0 - self._config.consistency_bonus

    def _recency_factor(
        self,
        ev: Evidence,
        as_of: datetime | None = None,
    ) -> float:
        prov = ev.provenance
        if prov is None or not prov.created_at:
            return 0.5
        try:
            dt = datetime.fromisoformat(prov.created_at)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            now = as_of if as_of is not None else datetime.now(timezone.utc)
            age_days = (now - dt).total_seconds() / 86400.0
            if age_days <= 0:
                return 1.0
            decay = max(1.0 - age_days / self._config.recency_days, 0.1)
            return decay
        except (ValueError, TypeError):
            return 0.5
