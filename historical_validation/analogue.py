"""Historical Validation Run 001 -- Step 3 single-case historical replay.

Validation-only adapter wiring ONE cohort case through the EXISTING
production components, with no production modifications:

    ValidationCase
        -> ValidationSnapshot                      (Step 2, as-of safe)
        -> historical SituationQuery               (built ONLY from snapshot)
        -> as-of filtered episode corpus           (in memory, event_date < D)
        -> HistoricalSituationRetriever            (existing, unmodified)
        -> build_historical_adjudication           (existing, unmodified)
        -> ThesisBuilder._build_historical_assessment (existing, unmodified)

No-lookahead rules enforced here:

* the episode corpus is rebuilt IN MEMORY strictly restricted to
  ``event_date < evaluation_date``; the globally persisted episode index is
  never consulted and nothing is written anywhere;
* the evaluated episode itself is never retrievable as its own analogue;
* the query carries ONLY snapshot values -- ``current_context_trends()``,
  today's regime diagnosis, and every other present-day enricher are never
  invoked;
* future gold outcomes stay confined to ``evaluation_only_outcomes``.

Reuse-only: similarity scoring, aggregation, adjudication and assessment
semantics are entirely the existing production implementations.  This module
adds serialization and guards only.
"""

from __future__ import annotations

from typing import Any

from .spec import TRACE_ID

DEFAULT_TOP_K = 3

AGGREGATE_SCOPE = "top_k"

_HONEST_METHODS = ("exact", "contextual", "broadened", "weak")


def asof_episode_corpus(evaluation_date, lessons_path) -> tuple[Any, tuple[str, ...]]:
    """Build an in-memory as-of episode index restricted to event_date < D.

    Reuses the existing ``build_lesson_episode_index`` projection over a
    strictly filtered view of the read-only lesson artifact.  Nothing is
    loaded from or written to any persisted index location.
    """
    import pandas as pd

    from knowledge.temporal.lesson_index import build_lesson_episode_index

    from .cases import load_lessons

    cutoff = evaluation_date.isoformat()
    rows = [row for row in load_lessons(lessons_path) if row["event_date"] < cutoff]
    indexer = build_lesson_episode_index(pd.DataFrame(rows))
    return indexer, tuple(row["lesson_id"] for row in rows)


def snapshot_query(snapshot):
    """Build the historical SituationQuery from ValidationSnapshot fields ONLY."""
    from knowledge.reasoning.retrieval import SituationQuery

    condition = {
        "cpi_pressure": snapshot.cpi_pressure,
        "us10y_trend": snapshot.us10y_trend,
        "dxy_trend": snapshot.dxy_trend,
    }
    institutional_context: dict[str, str] = {}
    if snapshot.institutional_regime:
        institutional_context["regime"] = str(snapshot.institutional_regime)
    return SituationQuery(
        event_type="CPI",
        condition=condition,
        institutional_context=institutional_context,
    )


def _verify_no_lookahead(snapshot, indexer, match_ids: tuple[str, ...]) -> dict[str, bool]:
    states = indexer._ensure_sorted()
    corpus_ids = {s.state_id for s in states}
    cutoff = snapshot.evaluation_date.isoformat()
    return {
        "snapshot_assertions_passed": True,  # build/assert happens before this point
        "corpus_strictly_before_evaluation": all(s.date < cutoff for s in states),
        "current_episode_excluded_from_corpus": snapshot.lesson_id not in corpus_ids,
        "matches_within_eligible_corpus": set(match_ids).issubset(corpus_ids),
        "current_episode_not_retrieved": snapshot.lesson_id not in set(match_ids),
        "future_outcomes_evaluation_only": all(
            item.get("evaluation_only") is True
            for item in snapshot.evaluation_only_outcomes
        ),
    }


class _ReasoningStub:
    """Minimal stand-in exposing only ``metadata`` for the existing
    ThesisBuilder assessment projection."""

    def __init__(self, metadata: dict[str, Any]) -> None:
        self.metadata = metadata


def run_step3(
    case,
    *,
    config=None,
    snapshot=None,
    candidate_direction: str = "neutral",
    top_k: int = DEFAULT_TOP_K,
) -> dict[str, Any]:
    """Run the full Step-3 flow for ONE validation case (read-only)."""
    from evidence_reasoning.historical_adjudication import (
        build_historical_adjudication,
    )
    from evidence_reasoning.historical_analogue import _match_entry_honest
    from knowledge.evidence.collection import EvidenceCollection
    from knowledge.reasoning.retrieval import HistoricalSituationRetriever
    from knowledge.reasoning.retrieval import SituationQuery
    from knowledge.temporal.lesson_index import LessonEpisodeQuery
    from thesis_construction.builder import ThesisBuilder

    from .snapshot import SnapshotConfig, build_snapshot

    cfg = config or SnapshotConfig()
    snap = snapshot if snapshot is not None else build_snapshot(case, cfg)
    snap.assert_no_lookahead()

    indexer, eligible_ids = asof_episode_corpus(snap.evaluation_date, cfg.lessons_path)

    base_query = snapshot_query(snap)
    surface = LessonEpisodeQuery(indexer)
    retriever = HistoricalSituationRetriever()

    effective_query = base_query
    matches = retriever.retrieve(base_query, surface)
    context_relaxed: Any = False
    if not matches and base_query.institutional_context:
        # Mirror of the existing production fallback: retry with the regime
        # dimension relaxed (empty institutional_context => neutral 0.5).
        effective_query = SituationQuery(
            event_type=base_query.event_type,
            condition=dict(base_query.condition),
            institutional_context={},
        )
        matches = retriever.retrieve(effective_query, surface)
        context_relaxed = ["regime"]

    state_by_id = {s.state_id: s for s in indexer._ensure_sorted()}
    honesty_regime = (
        None if context_relaxed else snap.institutional_regime or None
    )
    selected = matches[:top_k]
    entries = [
        _match_entry_honest(m, state_by_id, honesty_regime) for m in selected
    ]
    aggregate = (
        EvidenceCollection([m.evidence for m in selected]).aggregate()
        if selected
        else {}
    )

    query_block = {
        "event_type": effective_query.event_type,
        "condition": dict(effective_query.condition),
        "institutional_context": dict(effective_query.institutional_context),
    }

    adjudication_payload = {"matches": entries, "query": query_block}
    adjudication = build_historical_adjudication(adjudication_payload)

    assessment = None
    if adjudication is not None:
        reasoning = _ReasoningStub({"historical_adjudication": adjudication})
        assessment = ThesisBuilder._build_historical_assessment(
            reasoning, candidate_direction
        )

    match_ids = tuple(entry["lesson_id"] for entry in entries)

    return {
        "lesson_id": snap.lesson_id,
        "evaluation_date": snap.evaluation_date,
        "snapshot_summary": {
            "cpi_pressure": snap.cpi_pressure,
            "us10y_trend": snap.us10y_trend,
            "us10y_observation_date": snap.us10y_observation_date,
            "dxy_trend": snap.dxy_trend,
            "dxy_observation_date": snap.dxy_observation_date,
            "institutional_regime": snap.institutional_regime,
            "regime_source_max_date": snap.regime_source_max_date,
            "knowledge_cutoff": snap.knowledge_cutoff,
            "analogue_cutoff": snap.analogue_cutoff,
        },
        "query": query_block,
        "eligible_episode_count": len(eligible_ids),
        "eligible_episode_ids": tuple(eligible_ids),
        "analogue_match_ids": match_ids,
        "retrieval_method_per_match": {
            entry["lesson_id"]: entry["similarity"]["retrieval_method"]
            for entry in entries
        },
        "context_relaxed": context_relaxed,
        "similarity_breakdown": {
            entry["lesson_id"]: entry["similarity"] for entry in entries
        },
        "aggregate_scope": AGGREGATE_SCOPE,
        "aggregate": aggregate,
        "historical_adjudication": adjudication,
        "candidate_historical_assessment": assessment,
        "provenance": {
            "trace_id": TRACE_ID,
            "lessons_artifact": cfg.lessons_path.name,
            "episode_corpus_source": (
                "in-memory as-of filter of the existing lesson artifact "
                "(event_date < evaluation_date); global episode index "
                "unused, nothing persisted"
            ),
            "reused_components": (
                "HistoricalSituationRetriever; build_historical_adjudication; "
                "ThesisBuilder._build_historical_assessment"
            ),
            "candidate_direction": candidate_direction,
            "match_provenance": {
                entry["lesson_id"]: dict(entry.get("provenance") or {})
                for entry in entries
            },
        },
        "no_lookahead_verification": _verify_no_lookahead(snap, indexer, match_ids),
    }
