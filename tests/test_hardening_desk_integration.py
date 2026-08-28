"""Final Hardening — Group F: desk integration & canonical facts (D-07/D-09).

- The Technical Research Desk becomes a research-layer component: its
  confirmation / contradiction / structure context rides on every candidate
  thesis as NON-SCORING metadata (no vote, no weight, no confidence change).
- Every run aggregates desk facts into ONE run-scoped CanonicalFactRegistry
  and surfaces cross-producer convergence (e.g. technical close ==
  reference-price close) in the finalize payload.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


from knowledge.facts.builders import technical_fact_references  # noqa: E402

_TECH_FACTS = technical_fact_references(
    {
        "assessment_id": "tech_test1234",
        "as_of": "2026-08-24",
        "timeframe": "D1",
        "trend_direction": "bullish",
        "momentum_direction": "bullish",
        "structure_state": "uptrend",
        "volatility_state": "normal",
        "technical_confidence": 0.72,
        "supporting_indicators": ("trend_ema_stack_adx=bullish", "structure=uptrend"),
        "conflicting_indicators": ("rsi_extremes=overbought",),
        "metadata": {
            "structure": {"bos_flag": "bullish_bos"},
            "indicator_snapshot": {"close": "2050.1", "atr_14": "25.0"},
        },
    }
)

TECHNICAL_PAYLOAD = {
    "assessment_id": "tech_test1234",
    "as_of": "2026-08-24",
    "timeframe": "D1",
    "trend_direction": "bullish",
    "momentum_direction": "bullish",
    "structure_state": "uptrend",
    "volatility_state": "normal",
    "technical_confidence": 0.72,
    "supporting_indicators": ("trend_ema_stack_adx=bullish", "structure=uptrend"),
    "conflicting_indicators": ("rsi_extremes=overbought",),
    "metadata": {
        "structure": {"bos_flag": "bullish_bos"},
        "indicator_snapshot": {"close": "2050.1", "atr_14": "25.0"},
    },
    "fact_references": {
        "status": "ok",
        "facts": _TECH_FACTS["facts"],
    },
}


def _results_with_technical():
    return {"technical_research": TECHNICAL_PAYLOAD}


def test_technical_context_extracted():
    from orchestration.stages import _technical_research_context

    context = _technical_research_context(TECHNICAL_PAYLOAD)
    assert context is not None
    assert context["trend_direction"] == "bullish"
    assert context["structure_state"] == "uptrend"
    assert context["bos_flag"] == "bullish_bos"
    assert any("structure" in s for s in context["supporting_indicators"])

    assert _technical_research_context({"error": "x"}) is None
    assert _technical_research_context(None) is None


def test_thesis_metadata_carries_technical_research_without_scoring():
    """The desk context must ride as metadata and change NO scoring input."""
    from evidence_collection.contracts import Evidence, EvidenceCollection
    from counter_evidence.assessor import CounterEvidenceAssessor
    from evidence_reasoning.reasoner import EvidenceReasoner
    from thesis_construction.constructor import ThesisConstructor
    from orchestration.stages import _technical_research_context

    def _evidence(eid, bias):
        return Evidence(
            evidence_id=eid,
            source_kr_id="KR-1",
            source_kr_node_id="KR-1",
            event_type="REAL_YIELD",
            condition={"instrument": "XAU/USD"},
            bias=bias,
            base_confidence=0.8,
            regime_weight=0.8,
            composite_weight=0.64,
            explanation="e",
            regime="NORMAL_GROWTH",
            source_label="overnight_price",
            temporal_recency=0.9,
            metadata={"instrument": "XAU/USD", "classification": "Signal"},
        )

    collection = EvidenceCollection(
        collection_id="ec_f",
        assessment_id="sa_f",
        timestamp="2026-08-24T00:00:00",
        regime="NORMAL_GROWTH",
        items=(_evidence("e1", "bullish"), _evidence("e2", "bullish")),
        total_classified=2,
        signals_count=2,
    )
    reasoning = EvidenceReasoner().reason(collection, regime="NORMAL_GROWTH")
    assessment = CounterEvidenceAssessor().assess(reasoning)

    without = ThesisConstructor().construct(reasoning, assessment)
    with_ctx = ThesisConstructor().construct(
        reasoning,
        assessment,
        technical_context=_technical_research_context(TECHNICAL_PAYLOAD),
    )

    base_plain = without.theses[0]
    base_ctx = with_ctx.theses[0]
    # metadata carries the desk context
    ctx = base_ctx.metadata.get("technical_research")
    assert isinstance(ctx, dict)
    assert ctx["trend_direction"] == "bullish"
    assert "technical_research" not in base_plain.metadata
    # scoring inputs are byte-identical -- context is not a vote
    assert base_ctx.institutional_support == base_plain.institutional_support
    assert base_ctx.confidence_inputs == base_plain.confidence_inputs
    assert base_ctx.economic_mechanism == base_plain.economic_mechanism


def test_finalize_surfaces_canonical_fact_registry_with_convergence():
    from orchestration.stages import _canonical_fact_registry_summary
    from trade_recommendation.recommender import RecommendationEngine
    from tests.test_hardening_real_risk_execution import _buy_decision

    rec = RecommendationEngine().recommend(
        _buy_decision(),
        reference_price=2050.1,
        reference_provenance={
            "status": "resolved_from_gold_data",
            "value": 2050.1,
            "bar_date": "2026-08-24T00:00:00",
            "source_data_hash": "deadbeef",
            "method": "last_valid_close",
        },
    )
    summary = _canonical_fact_registry_summary(
        {"technical_research": TECHNICAL_PAYLOAD, "trade_recommendation": rec}
    )
    assert summary["status"] == "ok"
    assert set(summary["sources"]) == {"reference_price", "technical_research"}
    assert summary["summary"]["primitive_count"] >= 1
    assert summary["lineage_edges"] >= 1
    # cross-desk convergence on the SAME close primitive
    convergence = summary["cross_producer_convergence"]
    assert convergence, "technical close and reference price must converge"
    entry = next(c for c in convergence if c["agreement"])
    assert set(entry["producers"]) == {"reference_price", "technical_research"}


def test_finalize_registry_degrades_gracefully_without_inputs():
    from orchestration.stages import _canonical_fact_registry_summary

    summary = _canonical_fact_registry_summary({})
    assert summary["status"] == "ok"
    assert summary["sources"] == []
    assert summary["cross_producer_convergence"] == []
