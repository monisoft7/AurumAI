"""Trace 045-C -- Historical signal replay into the pure W-path (READ-ONLY).

For ONE historical case, injects the Trace-045-B reconstructed
SignalAssessment into W5 via the EXISTING pure production collector, then
runs the existing W6-W13 chain:

    ValidationCase -> ValidationSnapshot
      -> historical PreMarketBriefing / SignalAssessment   (Trace 045-B)
      -> in-memory as-of knowledge graph                   (eligible <= D)
      -> EvidenceCollector.collect()                       (existing W5)
      -> _run_inference_chain (W6..W13)                    (existing engines)

FULL vs NO_HISTORY share an IDENTICAL briefing/SignalAssessment/evidence
collection; only the historical analogue payload at W6 differs.

Writes: none.
"""

from __future__ import annotations

from typing import Any

from .spec import TRACE_ID

TRACE_045_C = "045-C"

# Production default when no regime-diagnosis confidence is available.
REGIME_WEIGHT_DEFAULT = 0.8


def asof_knowledge_graph(snapshot, cfg):
    """In-memory KnowledgeGraph restricted to records eligible at D.

    Records come from the deterministic as-of derivation over the canonical
    lesson artifact (``snapshot.asof_eligible_knowledge_records``), so the
    graph reflects exactly what a real-time system could have known at D;
    the persisted convenience aggregate is not consulted.
    """
    from knowledge.graph.builder import GraphBuilder

    from .snapshot import eligible_asof_knowledge_records

    records = eligible_asof_knowledge_records(snapshot, cfg)
    graph = GraphBuilder().build(records)
    return graph, len(records)


def run_replay_variant(
    case,
    *,
    history_enabled: bool,
    run_label: str = "a",
    config=None,
    snapshot=None,
) -> dict[str, Any]:
    """Run briefing->W4/W5->W6-W13 once for ONE variant.  Read-only."""
    from evidence_collection.collector import EvidenceCollector

    from .briefing import assemble_historical_signal
    from .pure_path import (
        _extract_comparison,
        build_analogue_payload,
        today_guard,
        verify_no_lookahead,
        verify_payload_lookahead,
        _run_inference_chain,
    )
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
        }
        if history_enabled:
            payload, payload_info = build_analogue_payload(snap)

        # Trace 045-B boundary: identical for FULL and NO_HISTORY.
        briefing, signal_assessment, _built = assemble_historical_signal(
            case, snap, config=cfg
        )

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
    result["trace_sub_id"] = TRACE_045_C
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
        "items": [
            {
                "instrument": e.condition.get("instrument"),
                "event_type": e.event_type,
                "bias": e.bias,
                "composite_weight": e.composite_weight,
            }
            for e in collection.items
        ],
    }
    return result


run_variant = run_replay_variant
