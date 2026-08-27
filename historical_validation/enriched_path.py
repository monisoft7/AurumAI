"""Correction 047-B -- smoke-case revalidation over the enriched corpus.

Validation-only runner that re-executes the three Run 001 smoke cases
through the SAME pure historical inference path (``pure_path``), with the
single boundary difference mandated by Correction 047-A: the in-memory
as-of episode corpus and its query surface are the ENRICHED ones
(``enriched_corpus.asof_enriched_episode_corpus`` +
``enriched_query_surface``), so each episode's condition carries the FULL
Correction-029 configuration and the unchanged retriever's temporal
criterion can engage.

Nothing here modifies production artifacts, the retriever, weights,
thresholds, top_k or scoring; nothing is persisted.  The PRE-047-A side of
every comparison is produced by the UNMODIFIED Run 001 path
(``pure_path.build_analogue_payload``) executed against the same read-only
artifacts in the same process.
"""

from __future__ import annotations

from typing import Any

ENRICHED_TRACE_ID = "047-B"

DEFAULT_TOP_K = 3

AGGREGATE_SCOPE = "top_k"


def build_enriched_analogue_payload(
    snapshot,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Retrieve analogues for ONE snapshot over the enriched episode corpus.

    Mirrors ``pure_path.build_analogue_payload`` verbatim -- identical query
    construction, retriever, fallback, top_k selection, honest-entry
    projection and aggregation -- with exactly ONE difference: the corpus is
    the Correction-047-A enriched as-of corpus and its query surface.
    """
    from evidence_reasoning.historical_analogue import _match_entry_honest
    from knowledge.evidence.collection import EvidenceCollection
    from knowledge.reasoning.retrieval import (
        HistoricalSituationRetriever,
        SituationQuery,
    )

    from .analogue import snapshot_query
    from .enriched_corpus import (
        asof_enriched_episode_corpus,
        enriched_query_surface,
    )
    from .snapshot import SnapshotConfig

    indexer, eligible_ids, _trends = asof_enriched_episode_corpus(
        snapshot.evaluation_date, SnapshotConfig().lessons_path
    )

    base_query = snapshot_query(snapshot)
    surface = enriched_query_surface(indexer)
    retriever = HistoricalSituationRetriever()

    effective_query = base_query
    matches = retriever.retrieve(base_query, surface)
    context_relaxed: Any = False
    if not matches and base_query.institutional_context:
        effective_query = SituationQuery(
            event_type=base_query.event_type,
            condition=dict(base_query.condition),
            institutional_context={},
        )
        matches = retriever.retrieve(effective_query, surface)
        context_relaxed = ["regime"]

    state_by_id = {s.state_id: s for s in indexer._ensure_sorted()}
    honesty_regime = (
        None if context_relaxed else snapshot.institutional_regime or None
    )
    selected = matches[:DEFAULT_TOP_K]
    entries = [
        _match_entry_honest(m, state_by_id, honesty_regime)
        for m in selected
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
    payload = {
        "primary_query": query_block,
        "effective_query": query_block,
        "context_relaxed": context_relaxed,
        "match_count": len(entries),
        "matches": entries,
        "aggregate": aggregate,
        "top_k": DEFAULT_TOP_K,
        "aggregate_scope": AGGREGATE_SCOPE,
        "query": query_block,
    }
    info: dict[str, Any] = {
        "match_ids": [e["lesson_id"] for e in entries],
        "retrieval_methods": {
            e["lesson_id"]: e["similarity"]["retrieval_method"]
            for e in entries
        },
        "context_relaxed": context_relaxed,
        "eligible_episode_count": len(eligible_ids),
        "raw_match_count": len(matches),
        "condition_exact_match_count": sum(
            1 for m in matches if m.evidence.condition == dict(effective_query.condition)
        ),
        "raw_overall_similarities": [
            m.overall_similarity for m in matches
        ],
        "similarity_breakdown": {
            e["lesson_id"]: e["similarity"] for e in entries
        },
    }
    return payload, info


# ---------------------------------------------------------------------------
# Pure variant execution over the enriched corpus
# ---------------------------------------------------------------------------


def run_enriched_variant(
    case,
    *,
    history_enabled: bool,
    run_label: str = "a",
    config=None,
    snapshot=None,
) -> dict[str, Any]:
    """Run the pure validation chain once for ONE variant, enriched corpus.

    Read-only; identical guards, W5 empty-collection boundary, inference
    chain and result extraction as ``pure_path.run_pure_variant``.
    """
    from .pure_path import (
        UPSTREAM_EVIDENCE_DEPENDENCY,
        _extract_comparison,
        _run_inference_chain,
        today_guard,
        verify_no_lookahead,
        verify_payload_lookahead,
    )
    from .snapshot import SnapshotConfig, build_snapshot

    snap = snapshot if snapshot is not None else build_snapshot(case, config or SnapshotConfig())
    snap.assert_no_lookahead()
    nl_checks = verify_no_lookahead(snap)

    with today_guard():
        payload = None
        payload_info: dict[str, Any] = {
            "match_ids": [],
            "retrieval_methods": {},
            "context_relaxed": False,
            "eligible_episode_count": None,
        }
        if history_enabled:
            payload, payload_info = build_enriched_analogue_payload(snap)

        from evidence_collection.contracts import EvidenceCollection

        collection = EvidenceCollection(
            collection_id="ec_hv_pure",
            assessment_id="hv_pure_boundary",
            timestamp="validation-only",
            regime=snap.institutional_regime or "",
            items=(),
        )

        outputs = _run_inference_chain(collection, snap.institutional_regime, payload)

    payload_checks = verify_payload_lookahead(case, payload)

    result = _extract_comparison(outputs, history_enabled, snap, payload_info)
    result["no_lookahead_checks"] = nl_checks
    result["payload_lookahead_checks"] = payload_checks
    result["eligible_episode_count"] = payload_info["eligible_episode_count"]
    result["upstream_evidence_dependency"] = UPSTREAM_EVIDENCE_DEPENDENCY
    return result


# ---------------------------------------------------------------------------
# PRE (Run 001 baseline) vs POST (047-A enriched) retrieval-layer record
# ---------------------------------------------------------------------------


def _adjudicate(payload):
    from evidence_reasoning.historical_adjudication import (
        build_historical_adjudication,
    )

    return build_historical_adjudication(
        {"matches": payload.get("matches") or [], "query": payload.get("query") or {}}
    )


def _assess(adjudication):
    if adjudication is None:
        return None
    from thesis_construction.builder import ThesisBuilder

    from .analogue import _ReasoningStub

    stub = _ReasoningStub({"historical_adjudication": adjudication})
    return ThesisBuilder._build_historical_assessment(stub, "neutral")


def _side_block(payload: dict[str, Any], info: dict[str, Any]) -> dict[str, Any]:
    from collections import Counter

    from .pure_path import _serialize

    adjudication = _adjudicate(payload)
    horizons = (adjudication or {}).get("horizon_results") or {}
    return {
        "query_configuration": payload["primary_query"],
        "eligible_episode_count": info["eligible_episode_count"],
        "match_count": payload["match_count"],
        "match_ids": list(info["match_ids"]),
        "retrieval_method_distribution": dict(
            Counter(info["retrieval_methods"].values())
        ),
        "context_relaxed": info["context_relaxed"],
        "aggregate_scope": payload["aggregate_scope"],
        "overall_similarity_by_match": {
            entry["lesson_id"]: entry["similarity"]["overall_similarity"]
            for entry in payload["matches"]
        },
        "similarity_breakdown": dict(info.get("similarity_breakdown") or {}),
        "condition_exact_match_count": info.get("condition_exact_match_count"),
        "raw_match_count": info.get("raw_match_count"),
        "raw_overall_similarities": list(info.get("raw_overall_similarities") or ()),
        "match_honesty": [
            {
                "lesson_id": entry["lesson_id"],
                "retrieval_method": entry["similarity"]["retrieval_method"],
                "condition_similarity": entry["similarity"]["condition_similarity"],
                "historical_condition": dict(entry["historical_condition"]),
                "historical_regime": dict(entry["historical_regime"]),
            }
            for entry in payload["matches"]
        ],
        "adjudication_horizons": {
            key: {
                "status": block.get("status"),
                "direction_summary": block.get("direction_summary"),
                "returns_pct": block.get("returns_pct"),
                "directions": block.get("directions"),
            }
            for key, block in horizons.items()
        },
        "candidate_historical_assessment_neutral": _serialize(_assess(adjudication)),
        "actual_gold_outcomes_attached": {
            entry["lesson_id"]: entry["gold_outcome"]
            for entry in payload["matches"]
        },
        "adjudication_serialized": _serialize(adjudication),
    }


def retrieval_layer_record(case, *, snapshot=None) -> dict[str, Any]:
    """PRE vs POST record restricted to the retrieval/history layer.

    POST runs through the enriched corpus; PRE re-runs the UNMODIFIED Run
    001 analogue builder against the same snapshot and artifacts.
    """
    from .pure_path import build_analogue_payload as run001_analogue_payload
    from .snapshot import SnapshotConfig, build_snapshot

    snap = snapshot if snapshot is not None else build_snapshot(case, SnapshotConfig())

    pre_payload, pre_info = run001_analogue_payload(snap)
    post_payload, post_info = build_enriched_analogue_payload(snap)

    pre_block = _side_block(pre_payload, pre_info)
    post_block = _side_block(post_payload, post_info)

    pre_sims = sorted(pre_block["overall_similarity_by_match"].values(), reverse=True)
    post_sims = sorted(post_block["overall_similarity_by_match"].values(), reverse=True)

    deltas = {
        "cohort_changed_ordered": pre_block["match_ids"] != post_block["match_ids"],
        "cohort_changed_set": set(pre_block["match_ids"]) != set(post_block["match_ids"]),
        "similarity_differentiated": (
            len(set(post_sims)) > len(set(pre_sims))
            or (len(post_sims) > 1 and post_sims[0] > post_sims[-1])
        ),
        "post_similarity_spread": (post_sims[0] - post_sims[-1]) if post_sims else 0.0,
        "pre_similarity_spread": (pre_sims[0] - pre_sims[-1]) if pre_sims else 0.0,
        "retrieval_became_exact_or_contextual": any(
            label in {"exact", "contextual"}
            for label in post_block["retrieval_method_distribution"]
        ),
        "pre_all_broadened": set(pre_block["retrieval_method_distribution"]) <= {"broadened"},
        "adjudication_changed": (
            pre_block["adjudication_serialized"]
            != post_block["adjudication_serialized"]
        ),
    }

    return {
        "lesson_id": snap.lesson_id,
        "evaluation_date": snap.evaluation_date.isoformat(),
        "snapshot_summary": {
            "cpi_pressure": snap.cpi_pressure,
            "us10y_trend": snap.us10y_trend,
            "dxy_trend": snap.dxy_trend,
            "institutional_regime": snap.institutional_regime,
            "analogue_cutoff": snap.analogue_cutoff.isoformat()
            if snap.analogue_cutoff
            else None,
        },
        "episode_trends_asof_safe": verify_episode_trends_asof(snap.evaluation_date),
        "pre_run001_baseline": pre_block,
        "post_047a_enriched": post_block,
        "deltas": deltas,
    }


def verify_episode_trends_asof(evaluation_date) -> bool:
    """Recompute every enriched episode's trends strictly as-of its own date.

    For EVERY episode with event_date < evaluation_date, the stored
    us10y_trend / dxy_trend must equal a fresh Correction-029 fold computed
    ONLY from observations <= that episode's event_date.
    """
    import pandas as pd

    from knowledge.context.trend_state import trend_state_at

    from .enriched_corpus import asof_enriched_frame
    from .snapshot import SnapshotConfig

    cfg = SnapshotConfig()
    df = asof_enriched_frame(evaluation_date, cfg.lessons_path)

    def series(path):
        s = pd.read_csv(path)
        s["Date"] = pd.to_datetime(s["Date"])
        s["Value"] = pd.to_numeric(s["Value"], errors="coerce")
        return s.dropna(subset=["Date", "Value"]).sort_values("Date")

    yld = series(cfg.dfii10_path)
    dxy = series(cfg.dxy_path)

    yield_to_label = {
        "flat": "yields_flat",
        "rising": "yields_rising",
        "falling": "yields_falling",
    }
    dxy_to_label = {
        "flat": "dxy_flat",
        "rising": "dxy_rising",
        "falling": "dxy_falling",
    }

    for _, row in df.iterrows():
        ep = pd.Timestamp(row["event_date"])
        ys = yld[yld["Date"] <= ep]
        ds = dxy[dxy["Date"] <= ep]
        expected_us10y = yield_to_label[
            trend_state_at(
                ys["Date"],
                ys["Value"].astype(float) * 100.0,
                ep,
                cfg.yield_lookback_days,
                cfg.yield_flat_change_bps,
            )
        ]
        expected_dxy = dxy_to_label[
            trend_state_at(
                ds["Date"],
                ds["Value"].astype(float),
                ep,
                cfg.dxy_lookback_days,
                cfg.dxy_flat_change,
            )
        ]
        if row["us10y_trend"] != expected_us10y:
            return False
        if row["dxy_trend"] != expected_dxy:
            return False
        if ep.date() >= evaluation_date:
            return False
    return True
