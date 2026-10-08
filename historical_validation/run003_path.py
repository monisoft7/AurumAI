"""Run-003 -- repaired-chain historical replay variant (READ-ONLY).

Composes the EXISTING corrected machinery (Correction-047-C enriched replay)
with the Run-003 institutional repairs:

    ValidationCase -> ValidationSnapshot
      -> historical PreMarketBriefing / SignalAssessment   (Trace 045-B)
      -> TechnicalResearchDesk as-of D on repository gold OHLCV  (Phase 9)
      -> as-of knowledge graph + EvidenceCollector          (W4/W5,
         technical reading enters the dedicated TECHNICAL channel)
      -> Correction-047-A enriched historical analogue corpus
      -> HistoricalSituationRetriever -> adjudication       (W6 memory,
         one bounded HISTORICAL_MEMORY evidence item)
      -> W6/W7/W8/W10/W9/W12/W13                            (existing
         engines with the Run-003 discriminability / confidence / regime
         / market-RR repairs)

Variant flags (all recorded in the result):
  history_enabled   -- FULL memory vs NO_HISTORY ablation (Phase 8/10)
  technical_enabled -- TechnicalResearchDesk evidence on/off (Phase 9)

Market risk/reward context (Phase 6) is built as-of D from the repository
gold OHLCV history in every variant; its availability is explicit and its
as-of safety is asserted.

No-lookahead contract additions:
  * the desk assessment is computed exclusively from bars <= D
    (the desk's own as-of slice; verified here via assessment.as_of == D);
  * the market context is built strictly from observations <= D
    (verified via context.as_of == D and its provenance status).

Writes: none.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .spec import TRACE_ID

TRACE_RUN003 = "run003"

_REPO_ROOT = Path(__file__).resolve().parents[1]
GOLD_CSV_PATH = _REPO_ROOT / "data" / "history" / "gold" / "gold.csv"


def build_technical_assessment_asof(
    evaluation_date,
    gold_path: Path | None = None,
):
    """Run the EXISTING TechnicalResearchDesk as-of D (Phase 9).

    The desk performs its own deterministic as-of slice before any indicator
    computation and returns an explicitly degraded assessment when history
    is insufficient -- nothing is fabricated here either way.  ``created_at``
    is pinned to the evaluation date for replay determinism.
    """
    from technical.desk import TechnicalResearchDesk

    import pandas as pd

    path = Path(gold_path) if gold_path else GOLD_CSV_PATH
    d_iso = evaluation_date.isoformat()
    frame = pd.read_csv(path)
    assessment = TechnicalResearchDesk().assess(
        frame,
        as_of=d_iso,
        timeframe="D1",
        asset="XAU/USD",
        created_at=f"{d_iso}T00:00:00+00:00",
    )
    return assessment


def verify_technical_asof(assessment, evaluation_date) -> dict[str, bool]:
    """As-of safety checks for the desk assessment (fail-closed)."""
    d_iso = evaluation_date.isoformat()
    return {
        "assessment_present": assessment is not None,
        "as_of_eq_D": bool(assessment) and str(assessment.as_of) == d_iso,
        "bars_used_positive": bool(assessment)
        and int((assessment.metadata or {}).get("bars_used", 0)) > 0,
        "source_data_hash_present": bool(assessment)
        and bool(str(assessment.source_data_hash or "")),
    }


def run_run003_variant(
    case,
    *,
    history_enabled: bool,
    technical_enabled: bool,
    run_label: str = "a",
    config=None,
    snapshot=None,
    gold_path: Path | None = None,
) -> dict[str, Any]:
    """Run briefing->W4/W5(+technical)->enriched-memory->W6-W13(market RR)."""
    from evidence_collection.collector import EvidenceCollector
    from risk_reward_validation.market_context import build_market_context

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

    # Phase 6: as-of market context (identical across variants; built once
    # per case outside the variant branch so RR differences can only come
    # from the memory/technical ablations, never from the market inputs).
    market_context = build_market_context(str(gold_path or GOLD_CSV_PATH), snap.evaluation_date.isoformat())
    market_asof_checks = {
        "context_as_of_eq_D": market_context.as_of == snap.evaluation_date.isoformat(),
        "availability_explicit": isinstance(market_context.available, bool),
        "provenance_present": bool(market_context.provenance),
    }

    technical_assessment = None
    technical_checks: dict[str, bool] = {"technical_enabled": technical_enabled}
    if technical_enabled:
        technical_assessment = build_technical_assessment_asof(
            snap.evaluation_date, gold_path=gold_path
        )
        technical_checks.update(verify_technical_asof(technical_assessment, snap.evaluation_date))

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
            technical_assessment=technical_assessment,
        )
        outputs = _run_inference_chain(
            collection, snap.institutional_regime, payload,
            market_context=market_context,
        )

    payload_checks = verify_payload_lookahead(case, payload)

    result = _extract_comparison(outputs, history_enabled, snap, payload_info)
    result["no_lookahead_checks"] = nl_checks
    result["payload_lookahead_checks"] = payload_checks
    result["briefing_asof_checks"] = briefing_asof_checks
    result["market_context_checks"] = market_asof_checks
    result["market_context_summary"] = market_context.describe()
    result["market_context_available"] = market_context.available
    result["technical_checks"] = technical_checks
    result["technical_enabled"] = technical_enabled
    result["trace_sub_id"] = TRACE_RUN003
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
    technical_summary = None
    if technical_assessment is not None:
        technical_summary = {
            "assessment_id": technical_assessment.assessment_id,
            "as_of": technical_assessment.as_of,
            "trend_direction": technical_assessment.trend_direction,
            "momentum_direction": technical_assessment.momentum_direction,
            "structure_state": technical_assessment.structure_state,
            "technical_confidence": technical_assessment.technical_confidence,
            "bars_used": (technical_assessment.metadata or {}).get("bars_used"),
            "notes": (technical_assessment.metadata or {}).get("notes"),
        }
    result["technical_summary"] = technical_summary
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
        "canonical_fact_ids": sorted(
            {
                e.metadata.get("canonical_fact_id")
                for e in collection.items
                if e.metadata.get("canonical_fact_id")
            }
        ),
        "technical_desk": dict(collection.metadata.get("technical_desk", {})),
    }
    result["analogue_similarity_breakdown"] = dict(
        payload_info.get("similarity_breakdown") or {}
    )
    result["condition_exact_match_count"] = payload_info.get(
        "condition_exact_match_count"
    )
    result["eligible_episode_count"] = payload_info.get("eligible_episode_count")
    result["provenance"] = {
        "trace_id": TRACE_ID,
        "sub_trace_id": TRACE_RUN003,
        "gold_csv": str(gold_path or GOLD_CSV_PATH),
        "technical_desk_integration": (
            "existing TechnicalResearchDesk assessed as-of D; directional "
            "readings projected onto one TECHNICAL-channel Evidence item via "
            "evidence_collection.desk_evidence.build_technical_evidence"
        ),
        "memory_integration": (
            "existing analogue adjudication projected onto one bounded "
            "HISTORICAL_MEMORY Evidence item via "
            "evidence_collection.desk_evidence.build_memory_evidence"
        ),
        "market_rr_integration": (
            "risk_reward_validation.market_context.build_market_context "
            "as-of D threaded into the existing W12 validator"
        ),
    }
    return result
