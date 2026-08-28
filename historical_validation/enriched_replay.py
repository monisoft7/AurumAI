"""Correction 047-C -- enriched-corpus FULL-CHAIN revalidation (READ-ONLY).

Composes the two validated pieces over the three smoke cases:

    ValidationCase -> ValidationSnapshot
      -> Historical PreMarketBriefing / SignalAssessment   (Trace 045-B)
      -> as-of knowledge graph + EvidenceCollector          (W4/W5)
      -> Correction-047-A ENRICHED historical analogue corpus
      -> HistoricalSituationRetriever -> adjudication       (W6 memory)
      -> W8/W9/W12/W13                                      (existing engines)

Identical to ``signal_replay.run_replay_variant`` except that the analogue
payload is built over the enriched in-memory episode corpus
(``enriched_path.build_enriched_analogue_payload``).  FULL vs NO_HISTORY
share an IDENTICAL snapshot, briefing, SignalAssessment and W5 collection;
only historical memory differs.  Writes: none.
"""

from __future__ import annotations

from typing import Any

TRACE_047_C = "047-C"


def run_enriched_replay_variant(
    case,
    *,
    history_enabled: bool,
    run_label: str = "a",
    config=None,
    snapshot=None,
) -> dict[str, Any]:
    """Run briefing->W4/W5->enriched-memory->W6-W13 once.  Read-only."""
    from evidence_collection.collector import EvidenceCollector

    from .briefing import assemble_historical_signal
    from .enriched_path import build_enriched_analogue_payload
    from .pure_path import (
        _extract_comparison,
        _run_inference_chain,
        today_guard,
        verify_no_lookahead,
        verify_payload_lookahead,
    )
    from .signal_replay import REGIME_WEIGHT_DEFAULT
    from .snapshot import SnapshotConfig, build_snapshot

    cfg = config or SnapshotConfig()
    snap = snapshot if snapshot is not None else build_snapshot(case, cfg)
    snap.assert_no_lookahead()
    nl_checks = verify_no_lookahead(snap)

    with today_guard():
        payload = None
        payload_info: dict[str, Any] = {
            "match_ids": [],
            "retrieval_methods": {},
            "context_relaxed": False,
            "eligible_episode_count": None,
            "similarity_breakdown": {},
            "condition_exact_match_count": 0,
        }
        if history_enabled:
            payload, payload_info = build_enriched_analogue_payload(snap)

        briefing, signal_assessment, built = assemble_historical_signal(
            case, snap, config=cfg
        )
        d_iso = snap.evaluation_date.isoformat()
        briefing_asof_checks = {
            "all_series_max_date_le_D": all(
                dt <= d_iso for dt in built["series_max_dates"].values()
            ),
            "cpi_reference_period_eq_D": (
                built["cpi_release"]["reference_period"] == d_iso
            ),
            "regime_from_snapshot": briefing.regime == snap.institutional_regime,
            "positioning_snapshot_is_None": briefing.positioning_snapshot is None,
            "news_items_empty": len(briefing.news_items) == 0,
        }

        from .signal_replay import asof_knowledge_graph

        kg, kr_node_count = asof_knowledge_graph(snap, cfg)
        collection = EvidenceCollector(knowledge_graph=kg).collect(
            signal_assessment,
            regime_weight=REGIME_WEIGHT_DEFAULT,
            cpi_condition={"cpi_pressure": snap.cpi_pressure},
        )
        outputs = _run_inference_chain(
            collection, snap.institutional_regime, payload
        )

    payload_checks = verify_payload_lookahead(case, payload)

    result = _extract_comparison(outputs, history_enabled, snap, payload_info)
    result["no_lookahead_checks"] = nl_checks
    result["payload_lookahead_checks"] = payload_checks
    result["trace_sub_id"] = TRACE_047_C
    result["signal_assessment_summary"] = {
        "observation_count": len(signal_assessment.observations),
        "classifications": [
            {
                "instrument": o.instrument,
                "source": o.source,
                "classification": o.classification,
                "confidence": o.confidence,
            }
            for o in signal_assessment.observations
        ],
    }
    result["evidence_summary"] = {
        "item_count": len(collection.items),
        "knowledge_record_nodes": kr_node_count,
        "event_types": sorted({e.event_type for e in collection.items}),
        "biases": sorted({e.bias for e in collection.items}),
        "instruments": sorted(
            {e.condition.get("instrument") for e in collection.items if e.condition.get("instrument")}
        ),
        "composite_weights_by_event_type": {
            et: [
                round(float(e.composite_weight), 9)
                for e in collection.items
                if e.event_type == et
            ]
            for et in sorted({e.event_type for e in collection.items})
        },
    }
    result["analogue_similarity_breakdown"] = dict(
        payload_info.get("similarity_breakdown") or {}
    )
    result["condition_exact_match_count"] = payload_info.get(
        "condition_exact_match_count"
    )
    result["eligible_episode_count"] = payload_info.get("eligible_episode_count")
    result["briefing_asof_checks"] = briefing_asof_checks
    return result
