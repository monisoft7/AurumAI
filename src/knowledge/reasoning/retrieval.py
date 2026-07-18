from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date as date_type
from math import exp, log, sqrt
from typing import Any

from knowledge.evidence.evidence import Evidence
from knowledge.evidence.collection import EvidenceCollection
from knowledge.evidence.query import EvidenceQuery
from knowledge.temporal.indexer import TemporalIndexer


@dataclass(frozen=True)
class SituationQuery:
    event_type: str
    condition: dict[str, str] | None = None
    horizon_days: int | None = None
    date: str | None = None
    sample_count: int = 0


@dataclass(frozen=True)
class SituationMatch:
    evidence: Evidence
    overall_similarity: float
    event_type_similarity: float
    condition_similarity: float
    horizon_similarity: float
    maturity_similarity: float
    temporal_similarity: float
    retrieval_method: str = "exact"


@dataclass
class RetrievalConfig:
    top_k: int = 5
    min_similarity: float = 0.3
    broaden_on_empty: bool = True
    broaden_min_results: int = 3
    event_type_weight: float = 0.35
    condition_weight: float = 0.30
    horizon_weight: float = 0.15
    maturity_weight: float = 0.10
    temporal_weight: float = 0.10

    def __post_init__(self) -> None:
        total = (
            self.event_type_weight
            + self.condition_weight
            + self.horizon_weight
            + self.maturity_weight
            + self.temporal_weight
        )
        if abs(total - 1.0) > 1e-6:
            raise ValueError(
                f"Retrieval weights must sum to 1.0, got {total}"
            )


class HistoricalSituationRetriever:
    def __init__(self, config: RetrievalConfig | None = None) -> None:
        self._config = config or RetrievalConfig()

    def retrieve(
        self,
        query: SituationQuery,
        evidence_query: EvidenceQuery | None,
        temporal_indexer: TemporalIndexer | None = None,
    ) -> list[SituationMatch]:
        if evidence_query is None:
            return []

        cfg = self._config

        candidates = evidence_query.matching(
            event_type=query.event_type,
            condition=query.condition,
            horizon_days=query.horizon_days,
        )

        had_exact = len(candidates) > 0

        if len(candidates) < cfg.broaden_min_results and cfg.broaden_on_empty:
            broadened = evidence_query.by_event_type(query.event_type)
            seen = set(e.evidence_id for e in candidates)
            extra = [e for e in broadened if e.evidence_id not in seen]
            if extra:
                items = list(candidates)
                items.extend(extra)
                candidates = EvidenceCollection(items)

        retrieval_method = "exact" if had_exact else "broadened"

        matches: list[SituationMatch] = []
        for evidence in candidates:
            scores = self._compute_similarities(
                query, evidence, temporal_indexer
            )
            overall = self._geometric_mean(
                scores,
                (
                    cfg.event_type_weight,
                    cfg.condition_weight,
                    cfg.horizon_weight,
                    cfg.maturity_weight,
                    cfg.temporal_weight,
                ),
            )
            if overall >= cfg.min_similarity:
                matches.append(
                    SituationMatch(
                        evidence=evidence,
                        overall_similarity=overall,
                        event_type_similarity=scores[0],
                        condition_similarity=scores[1],
                        horizon_similarity=scores[2],
                        maturity_similarity=scores[3],
                        temporal_similarity=scores[4],
                        retrieval_method=retrieval_method,
                    )
                )

        matches.sort(key=lambda m: m.overall_similarity, reverse=True)
        return matches[: cfg.top_k]

    def _compute_similarities(
        self,
        query: SituationQuery,
        evidence: Evidence,
        temporal_indexer: TemporalIndexer | None,
    ) -> tuple[float, float, float, float, float]:
        et_sim = 1.0 if query.event_type == evidence.event_type else 0.0

        cond_sim = self._jaccard_similarity(
            query.condition or {}, evidence.condition
        )

        horizon_sim = self._horizon_similarity(
            query.horizon_days, evidence.horizon_days
        )

        maturity_sim = self._maturity_similarity(
            query.sample_count, evidence.sample_count
        )

        temporal_sim = self._temporal_similarity(
            query, evidence, temporal_indexer
        )

        return et_sim, cond_sim, horizon_sim, maturity_sim, temporal_sim

    @staticmethod
    def _jaccard_similarity(
        a: dict[str, str], b: dict[str, str]
    ) -> float:
        if not a or not b:
            return 0.5
        keys_a = set(a.keys())
        keys_b = set(b.keys())
        intersection = keys_a & keys_b
        union = keys_a | keys_b
        return len(intersection) / len(union)

    @staticmethod
    def _horizon_similarity(
        q_horizon: int | None, c_horizon: int | None
    ) -> float:
        if q_horizon is None or c_horizon is None:
            return 0.5
        denominator = max(abs(q_horizon), abs(c_horizon), 1)
        return 1.0 / (1.0 + abs(q_horizon - c_horizon) / denominator)

    @staticmethod
    def _maturity_similarity(q_samples: int, c_samples: int) -> float:
        if q_samples <= 0 or c_samples <= 0:
            return 0.5
        if q_samples == c_samples:
            return 1.0
        mn = min(q_samples, c_samples)
        mx = max(q_samples, c_samples)
        return sqrt(mn / mx)

    @staticmethod
    def _temporal_similarity(
        query: SituationQuery,
        evidence: Evidence,
        temporal_indexer: TemporalIndexer | None,
    ) -> float:
        q_date = query.date
        c_date = evidence.metadata.get("last_event_date", "")

        if not q_date or not c_date:
            return 0.5

        try:
            qd = date_type.fromisoformat(q_date)
            cd = date_type.fromisoformat(c_date)
        except (ValueError, TypeError):
            return 0.5

        years_diff = abs((qd - cd).days) / 365.25
        return 1.0 / (1.0 + years_diff)

    @staticmethod
    def _geometric_mean(
        scores: tuple[float, float, float, float, float],
        weights: tuple[float, float, float, float, float],
    ) -> float:
        total_weight = sum(w for w in weights if w > 0)
        if total_weight == 0:
            return 0.0

        weighted_log_sum = 0.0
        for score, weight in zip(scores, weights):
            if weight > 0:
                if score <= 0.0:
                    return 0.0
                weighted_log_sum += weight * log(score)

        return exp(weighted_log_sum / total_weight)
