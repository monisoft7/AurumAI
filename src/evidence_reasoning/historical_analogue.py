"""Correction 025-B: explanation-only historical gold analogue for the W-path.

Connects the existing lesson episode index (Correction 025) to the current
production EvidenceReasoner boundary:

    lesson artifact -> episode index -> LessonEpisodeQuery
    -> HistoricalSituationRetriever -> historical matches
    -> EvidenceReasoning.metadata["historical_analogue"] -> Thesis explanation

The analogue is strictly explanatory.  It feeds no weight, confidence,
counter-evidence, composite, risk/reward, or decision value.  The payload is
assembled from existing retrieved fields and the existing
``EvidenceCollection.aggregate()`` utility only; no new statistic is
invented.

Current configuration comes from existing W-path semantics only:

- ``cpi_pressure`` from the active event/knowledge path
  (``reasoning_condition``), validated exactly like ``_evidence_collection``;
- ``us10y_trend`` / ``dxy_trend`` from the current factor observations,
  classified with the existing lesson-context enrichers (same thresholds and
  lookback semantics as the lesson artifact);
- ``regime`` from the current institutional regime (canonical six-state code).

Degradation: a missing/unreadable episode index, an invalid CPI condition, or
zero passing matches returns ``None`` and the pipeline continues unchanged --
no fabricated analogue is ever produced.
"""

from __future__ import annotations

from datetime import date as date_type
from pathlib import Path
from typing import Any

import pandas as pd

from knowledge.context.dxy import DXYContextConfig, DXYContextEnricher
from knowledge.context.yields import YieldContextConfig, YieldContextEnricher
from knowledge.evidence.collection import EvidenceCollection
from knowledge.evidence.evidence import Evidence
from knowledge.reasoning.retrieval import (
    HistoricalSituationRetriever,
    SituationMatch,
    SituationQuery,
)
from knowledge.temporal.indexer import TemporalIndexer
from knowledge.temporal.lesson_index import (
    LessonEpisodeQuery,
    load_lesson_episode_index,
)

_REPO_ROOT = Path(__file__).resolve().parents[2]

DEFAULT_EPISODES_INDEX_PATH = _REPO_ROOT / "data" / "state" / "lesson_episodes.json"
DEFAULT_REAL_YIELD_PATH = _REPO_ROOT / "data" / "economic" / "DFII10.csv"
DEFAULT_DXY_PATH = _REPO_ROOT / "data" / "context" / "dxy" / "dxy.csv"

VALID_CPI_PRESSURE: tuple[str, ...] = (
    "inflation_pressure_up",
    "inflation_pressure_down",
)
VALID_YIELD_TRENDS: tuple[str, ...] = (
    "yields_rising",
    "yields_falling",
    "yields_flat",
)
VALID_DXY_TRENDS: tuple[str, ...] = (
    "dxy_rising",
    "dxy_falling",
    "dxy_flat",
)

GOLD_OUTCOME_FIELDS: tuple[str, ...] = (
    "gold_return_1d_pct",
    "gold_return_5d_pct",
    "gold_return_20d_pct",
    "gold_direction_1d",
    "gold_direction_5d",
    "gold_direction_20d",
    "gold_close_at_event",
    "anchor_gold_date",
)


def current_context_trends(
    real_yield_path: str | Path | None = None,
    dxy_path: str | Path | None = None,
    lookback_days: int = 30,
    as_of_date: str | None = None,
) -> dict[str, str]:
    """Classify the current Real Yield and DXY trend states.

    Reuses the existing lesson-context enrichers (the same deterministic
    classification and lookback semantics that produced the lesson artifact's
    condition columns) at ``as_of_date`` (default: today).  Only the three
    lesson vocabulary values are accepted; missing/unreadable inputs are
    omitted, never fabricated.
    """
    as_of = as_of_date or date_type.today().isoformat()
    trends: dict[str, str] = {}

    yield_path = Path(real_yield_path) if real_yield_path else DEFAULT_REAL_YIELD_PATH
    dxy_path = Path(dxy_path) if dxy_path else DEFAULT_DXY_PATH

    if yield_path.is_file():
        try:
            config = YieldContextConfig(
                yield_path=yield_path, lookback_days=lookback_days
            )
            framed = YieldContextEnricher(config).enrich(
                pd.DataFrame([{"event_date": as_of}])
            )
            trend = str(framed.iloc[0]["us10y_trend"])
            if trend in VALID_YIELD_TRENDS:
                trends["us10y_trend"] = trend
        except Exception:
            pass

    if dxy_path.is_file():
        try:
            config = DXYContextConfig(dxy_path=dxy_path, lookback_days=lookback_days)
            framed = DXYContextEnricher(config).enrich(
                pd.DataFrame([{"event_date": as_of}])
            )
            trend = str(framed.iloc[0]["dxy_trend"])
            if trend in VALID_DXY_TRENDS:
                trends["dxy_trend"] = trend
        except Exception:
            pass

    return trends


def build_situation_query(
    cpi_condition: dict[str, Any] | None,
    trends: dict[str, str] | None = None,
    regime: str | None = None,
) -> SituationQuery | None:
    """Build the SituationQuery from the existing current configuration.

    Returns None when the CPI pressure is missing or invalid -- the CPI
    condition is the anchor of the current configuration, exactly as in
    ``_evidence_collection``.  Trend and regime values are included only when
    present and recognized.
    """
    condition: dict[str, str] = {}
    if isinstance(cpi_condition, dict):
        pressure = cpi_condition.get("cpi_pressure")
        if pressure in VALID_CPI_PRESSURE:
            condition["cpi_pressure"] = str(pressure)
    if not condition:
        return None

    for key in ("us10y_trend", "dxy_trend"):
        value = (trends or {}).get(key)
        if value:
            condition[key] = str(value)

    institutional_context: dict[str, str] = {}
    if regime:
        institutional_context["regime"] = str(regime)

    return SituationQuery(
        event_type="CPI",
        condition=condition,
        institutional_context=institutional_context,
    )


def build_historical_analogue(
    *,
    cpi_condition: dict[str, Any] | None = None,
    regime: str | None = None,
    real_yield_path: str | Path | None = None,
    dxy_path: str | Path | None = None,
    lookback_days: int = 30,
    as_of_date: str | None = None,
    trends: dict[str, str] | None = None,
    episodes_index_path: str | Path | None = None,
    top_k: int = 3,
) -> dict[str, Any] | None:
    """Retrieve comparable CPI episodes and assemble the analogue payload.

    Two-stage retrieval:

    Stage 1: query with regime intact.
        If useful results exist, return them unchanged (existing exact behavior).

    Stage 2: if Stage 1 produces no useful result, OR every exact-condition
        candidate is rejected solely because institutional_context mismatches,
        retry without institutional_context (regime relaxed).

    Returns None (omitted, pipeline continues unchanged) when the episode
    index is missing/unreadable, the current CPI condition is invalid, or no
    match passes the existing retriever similarity floor even after fallback.

    Deterministic: same lesson artifact + same current configuration always
    yield the same matches, order, and content.

    When regime is relaxed, ``context_relaxed`` is set to ``["regime"]``
    and each returned match is honestly classified (not labeled "exact"
    when the regime differs).
    """
    index_path = (
        Path(episodes_index_path) if episodes_index_path else DEFAULT_EPISODES_INDEX_PATH
    )
    if not index_path.is_file():
        return None
    try:
        indexer: TemporalIndexer = load_lesson_episode_index(index_path)
        query_surface = LessonEpisodeQuery(indexer)
    except Exception:
        return None

    current_trends = (
        trends
        if trends is not None
        else current_context_trends(
            real_yield_path=real_yield_path,
            dxy_path=dxy_path,
            lookback_days=lookback_days,
            as_of_date=as_of_date,
        )
    )
    base_query = build_situation_query(cpi_condition, current_trends, regime)

    # ── Stage 1: query with regime intact ────────────────────────────────
    if base_query is not None and base_query.institutional_context:
        matches = HistoricalSituationRetriever().retrieve(base_query, query_surface)
        if matches:
            state_by_id = {
                s.state_id: s for s in indexer._ensure_sorted()
            }
            entries = [_match_entry_honest(m, state_by_id, regime) for m in matches[:top_k]]
            aggregate = EvidenceCollection([m.evidence for m in matches[:top_k]]).aggregate()

            return {
                "primary_query": {
                    "event_type": base_query.event_type,
                    "condition": dict(base_query.condition),
                    "institutional_context": dict(base_query.institutional_context),
                },
                "effective_query": {
                    "event_type": base_query.event_type,
                    "condition": dict(base_query.condition),
                    "institutional_context": dict(base_query.institutional_context),
                },
                "context_relaxed": False,
                "match_count": len(matches),
                "matches": entries,
                "aggregate": aggregate,
                "top_k": top_k,
                "aggregate_scope": "top_k",
                # Backward compatibility
                "query": {
                    "event_type": base_query.event_type,
                    "condition": dict(base_query.condition),
                    "institutional_context": dict(base_query.institutional_context),
                },
            }

    # ── Stage 2: fallback without institutional_context ──────────────────
    # Retry without institutional_context (regime relaxed).
    # empty institutional_context => neutral 0.5 context similarity.
    fallback_query = build_situation_query(cpi_condition, current_trends, None)

    matches = HistoricalSituationRetriever().retrieve(fallback_query, query_surface)
    if not matches:
        return None

    state_by_id = {
        s.state_id: s for s in indexer._ensure_sorted()
    }
    entries = [_match_entry_honest(m, state_by_id, regime) for m in matches[:top_k]]
    aggregate = EvidenceCollection([m.evidence for m in matches[:top_k]]).aggregate()

    return {
        "primary_query": (
            {
                "event_type": base_query.event_type,
                "condition": dict(base_query.condition),
                "institutional_context": dict(base_query.institutional_context),
            }
            if base_query
            else {
                "event_type": fallback_query.event_type,
                "condition": dict(fallback_query.condition),
                "institutional_context": {},
            }
        ),
        "effective_query": {
            "event_type": fallback_query.event_type,
            "condition": dict(fallback_query.condition),
            "institutional_context": {},
        },
        "context_relaxed": ["regime"],
        "match_count": len(matches),
        "matches": entries,
        "aggregate": aggregate,
        "top_k": top_k,
        "aggregate_scope": "top_k",
        # Backward compatibility
        "query": {
            "event_type": fallback_query.event_type,
            "condition": dict(fallback_query.condition),
            "institutional_context": {},
        },
    }


def _match_entry_honest(
    match: SituationMatch,
    state_by_id: dict[str, Any],
    regime: str | None,
) -> dict[str, Any]:
    """Convert a SituationMatch to a payload dict with honest retrieval_method.

    Rules (per-match, not per-call):
      - exact:   all required configuration dimensions match
      - contextual: configuration dimensions match but institutional regime differs
      - broadened: one or more requested condition keys are relaxed/mismatched
      - weak:    partial low-dimension similarity if existing semantics require it
    """
    ev: Evidence = match.evidence
    state = state_by_id.get(ev.evidence_id)

    # Determine if this match's configuration matches the original query regime
    match_regime = dict(ev.metadata.get("institutional_context", {}))
    regime_matches = (regime is not None) and (match_regime.get("regime") == regime)

    gold_outcome: dict[str, Any] = {
        "average_return_pct": ev.average_return_pct,
        "horizon_days": ev.horizon_days,
    }
    if state is not None:
        for key in GOLD_OUTCOME_FIELDS:
            value = state.metadata.get(key)
            if value is not None:
                gold_outcome[key] = value

    # Honestly classify retrieval_method based on what actually matches
    if match.retrieval_method == "exact" and not regime_matches:
        # Regime-mismatched exact-condition: label as contextual, not exact
        retrieved_method = "contextual"
    elif match.retrieval_method == "broadened":
        retrieved_method = "broadened"
    else:
        # "exact" with matching regime, or any other case
        retrieved_method = match.retrieval_method

    entry: dict[str, Any] = {
        "lesson_id": ev.evidence_id,
        "event_date": state.date if state is not None else None,
        "gold_outcome": gold_outcome,
        "historical_condition": {
            key: ev.condition[key]
            for key in ("cpi_pressure", "us10y_trend", "dxy_trend")
            if key in ev.condition
        },
        "historical_regime": match_regime,
        "provenance": {
            key: ev.metadata[key]
            for key in ("source_artifact_path", "source_artifact_sha256")
            if key in ev.metadata
        },
        "similarity": {
            "overall_similarity": match.overall_similarity,
            "event_type_similarity": match.event_type_similarity,
            "condition_similarity": match.condition_similarity,
            "horizon_similarity": match.horizon_similarity,
            "maturity_similarity": match.maturity_similarity,
            "temporal_similarity": match.temporal_similarity,
            "institutional_context_similarity": match.institutional_context_similarity,
            "retrieval_method": retrieved_method,
        },
    }
    return entry