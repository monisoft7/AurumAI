from __future__ import annotations

import pytest

from knowledge.evidence.evidence import Evidence
from knowledge.evidence.collection import EvidenceCollection
from knowledge.orchestration.context import OrchestrationContext
from knowledge.orchestration.aggregator import EvidenceAggregator, AggregationResult
from knowledge.orchestration.engine import OrchestrationEngine, OrchestrationReport
from knowledge.cai.contracts import (
    CrossAssetCorrelation,
    SpreadAnalysis,
    VolatilityRegime,
    EQUITIES,
    FIXED_INCOME,
    COMMODITIES,
    CORRELATION_POSITIVE,
    CORRELATION_NEGATIVE,
    CORRELATION_DECOUPLING,
    SPREAD_NARROWING,
    SPREAD_WIDENING,
    SPREAD_STABLE,
    SPREAD_INVERSION,
    VOL_LOW,
    VOL_MODERATE,
    VOL_ELEVATED,
    VOL_HIGH,
    VOL_EXTREME,
)
from knowledge.cai.adapter import CaiEvidenceAdapter
from knowledge.integrity.provenance import Provenance
from knowledge.integrity.lineage import LineageRegistry
from knowledge.graph.graph import KnowledgeGraph
from knowledge.graph.node import GraphNode
from knowledge.evidence.query import EvidenceQuery
from knowledge.reasoning.engine import ReasoningEngine
from knowledge.decision.engine import DecisionEngine


# ── CAI Layer Activation ───────────────────────────────────────────────────


def test_engine_cai_layer_no_adapter() -> None:
    engine = OrchestrationEngine()
    ctx = OrchestrationContext()
    report = engine.analyze(ctx)
    assert len(report.cai_evidence) == 0


def test_engine_cai_layer_adapter_no_data() -> None:
    engine = OrchestrationEngine()
    ctx = OrchestrationContext(cai_adapter=CaiEvidenceAdapter())
    report = engine.analyze(ctx)
    assert len(report.cai_evidence) == 0


def test_engine_cai_correlations() -> None:
    engine = OrchestrationEngine()
    corr = CrossAssetCorrelation(
        asset_class_a=EQUITIES,
        asset_class_b=FIXED_INCOME,
        correlation_coefficient=-0.65,
        lookback_periods=252,
        trend_direction=CORRELATION_NEGATIVE,
        confidence=0.85,
        valid_from="2026-07-27T00:00:00Z",
        valid_until="2026-10-27T00:00:00Z",
    )
    ctx = OrchestrationContext(
        cai_correlations=[corr],
        cai_adapter=CaiEvidenceAdapter(),
    )
    report = engine.analyze(ctx)
    assert len(report.cai_evidence) == 1
    ev = report.cai_evidence[0]
    assert ev.event_type == "CAI_CORRELATION"
    assert ev.confidence == 0.85
    assert ev.bias == "bearish"
    assert ev.metadata["_source_layer"] == "cai"


def test_engine_cai_spreads() -> None:
    engine = OrchestrationEngine()
    spread = SpreadAnalysis(
        instrument_a="US10Y",
        instrument_b="US2Y",
        current_spread=0.45,
        historical_mean=1.20,
        standard_deviation=0.50,
        z_score=-1.50,
        trend=SPREAD_NARROWING,
        confidence=0.78,
        valid_from="2026-07-27T00:00:00Z",
        valid_until="2026-10-27T00:00:00Z",
    )
    ctx = OrchestrationContext(
        cai_spreads=[spread],
        cai_adapter=CaiEvidenceAdapter(),
    )
    report = engine.analyze(ctx)
    assert len(report.cai_evidence) == 1
    ev = report.cai_evidence[0]
    assert ev.event_type == "CAI_SPREAD"
    assert ev.confidence == 0.78
    assert ev.bias == "bullish"
    assert ev.metadata["_source_layer"] == "cai"


def test_engine_cai_volatilities() -> None:
    engine = OrchestrationEngine()
    vol = VolatilityRegime(
        asset_class=EQUITIES,
        current_state=VOL_ELEVATED,
        previous_state=VOL_MODERATE,
        regime_persistence=0.72,
        mean_reversion_half_life_days=14.0,
        tail_risk_index=0.65,
        confidence=0.82,
        valid_from="2026-07-27T00:00:00Z",
        valid_until="2026-10-27T00:00:00Z",
    )
    ctx = OrchestrationContext(
        cai_volatilities=[vol],
        cai_adapter=CaiEvidenceAdapter(),
    )
    report = engine.analyze(ctx)
    assert len(report.cai_evidence) == 1
    ev = report.cai_evidence[0]
    assert ev.event_type == "CAI_VOLATILITY"
    assert ev.confidence == 0.82
    assert ev.bias == "bearish"
    assert ev.metadata["_source_layer"] == "cai"


def test_engine_cai_all_three_contract_types() -> None:
    engine = OrchestrationEngine()
    corr = CrossAssetCorrelation(
        asset_class_a=EQUITIES,
        asset_class_b=COMMODITIES,
        correlation_coefficient=0.40,
        trend_direction=CORRELATION_POSITIVE,
        confidence=0.75,
        valid_from="2026-07-27T00:00:00Z",
        valid_until="2026-10-27T00:00:00Z",
    )
    spread = SpreadAnalysis(
        instrument_a="GOLD",
        instrument_b="SILVER",
        current_spread=82.0,
        historical_mean=75.0,
        standard_deviation=8.0,
        z_score=0.875,
        trend=SPREAD_WIDENING,
        confidence=0.70,
        valid_from="2026-07-27T00:00:00Z",
        valid_until="2026-10-27T00:00:00Z",
    )
    vol = VolatilityRegime(
        asset_class=COMMODITIES,
        current_state=VOL_LOW,
        previous_state=VOL_MODERATE,
        regime_persistence=0.88,
        confidence=0.90,
        valid_from="2026-07-27T00:00:00Z",
        valid_until="2026-10-27T00:00:00Z",
    )
    ctx = OrchestrationContext(
        cai_correlations=[corr],
        cai_spreads=[spread],
        cai_volatilities=[vol],
        cai_adapter=CaiEvidenceAdapter(),
    )
    report = engine.analyze(ctx)
    assert len(report.cai_evidence) == 3
    event_types = {ev.event_type for ev in report.cai_evidence}
    assert event_types == {"CAI_CORRELATION", "CAI_SPREAD", "CAI_VOLATILITY"}
    for ev in report.cai_evidence:
        assert ev.metadata["_source_layer"] == "cai"


# ── Aggregation Integration ───────────────────────────────────────────────


def test_cai_evidence_merges_via_aggregator() -> None:
    adapter = CaiEvidenceAdapter()
    corr = CrossAssetCorrelation(
        asset_class_a=EQUITIES,
        asset_class_b=FIXED_INCOME,
        correlation_coefficient=-0.65,
        trend_direction=CORRELATION_NEGATIVE,
        confidence=0.85,
        valid_from="2026-07-27T00:00:00Z",
        valid_until="2026-10-27T00:00:00Z",
    )
    ev = adapter.cross_asset_correlation_to_evidence(corr)

    event_evidence = [
        Evidence(
            evidence_id="event_001",
            source_node_id="event_source",
            event_type="CPI",
            condition={"asset": "XAU/USD"},
            horizon_days=5,
            sample_count=100,
            average_return_pct=0.5,
            confidence=0.6,
            bias="bullish",
            explanation="CPI came in hot.",
        ),
    ]

    agg = EvidenceAggregator()
    result = agg.merge({
        "event": EvidenceCollection(event_evidence),
        "cai": EvidenceCollection([ev]),
    })
    assert len(result.collection) == 2
    assert result.layer_counts["cai"] == 1
    assert result.layer_counts["event"] == 1


def test_cai_evidence_conflict_detection() -> None:
    adapter = CaiEvidenceAdapter()
    corr = CrossAssetCorrelation(
        asset_class_a=EQUITIES,
        asset_class_b=FIXED_INCOME,
        correlation_coefficient=-0.65,
        trend_direction=CORRELATION_NEGATIVE,
        confidence=0.85,
        valid_from="2026-07-27T00:00:00Z",
        valid_until="2026-10-27T00:00:00Z",
    )
    ev = adapter.cross_asset_correlation_to_evidence(corr)

    conflicting = Evidence(
        evidence_id=f"cai_corr_{EQUITIES}_{FIXED_INCOME}",
        source_node_id=f"cai_{EQUITIES}_{FIXED_INCOME}",
        event_type="CAI_CORRELATION",
        condition={"asset_a": EQUITIES, "asset_b": FIXED_INCOME, "trend": "negative"},
        horizon_days=0,
        sample_count=1,
        average_return_pct=0.0,
        confidence=0.85,
        bias="bullish",
        explanation="Conflicting bias for same evidence_id.",
    )

    agg = EvidenceAggregator()
    result = agg.merge({
        "cai_v1": EvidenceCollection([ev]),
        "cai_v2": EvidenceCollection([conflicting]),
    })
    assert len(result.conflicts) >= 1


def test_cai_evidence_reaches_aggregation_in_full_pipeline() -> None:
    engine = OrchestrationEngine()
    corr = CrossAssetCorrelation(
        asset_class_a=EQUITIES,
        asset_class_b=FIXED_INCOME,
        correlation_coefficient=-0.65,
        trend_direction=CORRELATION_NEGATIVE,
        confidence=0.85,
        valid_from="2026-07-27T00:00:00Z",
        valid_until="2026-10-27T00:00:00Z",
    )
    spread = SpreadAnalysis(
        instrument_a="US10Y",
        instrument_b="US2Y",
        current_spread=0.45,
        historical_mean=1.20,
        standard_deviation=0.50,
        z_score=-1.50,
        trend=SPREAD_NARROWING,
        confidence=0.78,
        valid_from="2026-07-27T00:00:00Z",
        valid_until="2026-10-27T00:00:00Z",
    )
    ctx = OrchestrationContext(
        cai_correlations=[corr],
        cai_spreads=[spread],
        cai_adapter=CaiEvidenceAdapter(),
    )
    report = engine.analyze(ctx)
    assert report.aggregation is not None
    assert report.aggregation.layer_counts.get("cai", 0) == 2
    assert len(report.aggregation.collection) == 2


# ── Full Pipeline with Reasoning + Decision ────────────────────────────────


def test_cai_full_pipeline_with_decision() -> None:
    engine = OrchestrationEngine()
    kg = KnowledgeGraph()
    kg.add_node(GraphNode(
        node_id="kr_1",
        node_type="knowledge_record",
        properties={
            "knowledge_id": "kr_1", "event_type": "CPI", "asset": "GOLD",
            "condition": {}, "horizon_days": 20, "sample_count": 10,
            "average_return_pct": 1.0, "confidence": 0.7, "bias": "bullish",
            "explanation": "test",
        },
    ))
    query = EvidenceQuery(kg)
    reasoning = ReasoningEngine()
    decision = DecisionEngine()

    vol = VolatilityRegime(
        asset_class=EQUITIES,
        current_state=VOL_HIGH,
        previous_state=VOL_ELEVATED,
        regime_persistence=0.80,
        confidence=0.88,
        valid_from="2026-07-27T00:00:00Z",
        valid_until="2026-10-27T00:00:00Z",
    )

    ctx = OrchestrationContext(
        event_type="CPI",
        evidence_query=query,
        reasoning_engine=reasoning,
        decision_engine=decision,
        cai_volatilities=[vol],
        cai_adapter=CaiEvidenceAdapter(),
    )
    report = engine.analyze(ctx)
    assert len(report.cai_evidence) == 1
    assert len(report.core_evidence) > 0
    assert report.chain is not None
    assert report.decision is not None
    assert report.aggregation.layer_counts.get("cai", 0) == 1
    assert report.aggregation.layer_counts.get("core", 0) > 0
    total = sum(report.aggregation.layer_counts.values())
    assert total == len(report.aggregation.collection)


# ── Lineage Integration ───────────────────────────────────────────────────


def test_cai_lineage_recording() -> None:
    reg = LineageRegistry()
    engine = OrchestrationEngine()
    kg = KnowledgeGraph()
    kg.add_node(GraphNode(
        node_id="kr_1",
        node_type="knowledge_record",
        properties={
            "knowledge_id": "kr_1", "event_type": "CPI", "asset": "GOLD",
            "condition": {}, "horizon_days": 20, "sample_count": 10,
            "average_return_pct": 1.0, "confidence": 0.7, "bias": "bullish",
            "explanation": "test",
        },
    ))
    query = EvidenceQuery(kg)
    reasoning = ReasoningEngine()
    decision = DecisionEngine()

    corr = CrossAssetCorrelation(
        asset_class_a=EQUITIES,
        asset_class_b=COMMODITIES,
        correlation_coefficient=0.55,
        trend_direction=CORRELATION_POSITIVE,
        confidence=0.80,
        valid_from="2026-07-27T00:00:00Z",
        valid_until="2026-10-27T00:00:00Z",
    )
    ctx = OrchestrationContext(
        event_type="CPI",
        evidence_query=query,
        reasoning_engine=reasoning,
        decision_engine=decision,
        lineage_registry=reg,
        cai_correlations=[corr],
        cai_adapter=CaiEvidenceAdapter(),
    )
    report = engine.analyze(ctx)
    assert report.decision is not None
    records = reg.all_records()
    assert len(records) > 0
    layer_sources = [r.source_id for r in records if r.source_id.startswith("layer:")]
    assert "layer:cai" in layer_sources


# ── Source Layer Tagging ───────────────────────────────────────────────────


def test_cai_source_layer_tag_correlation() -> None:
    engine = OrchestrationEngine()
    corr = CrossAssetCorrelation(
        asset_class_a=EQUITIES,
        asset_class_b=FIXED_INCOME,
        correlation_coefficient=-0.65,
        trend_direction=CORRELATION_NEGATIVE,
        confidence=0.85,
        valid_from="2026-07-27T00:00:00Z",
        valid_until="2026-10-27T00:00:00Z",
    )
    ctx = OrchestrationContext(
        cai_correlations=[corr],
        cai_adapter=CaiEvidenceAdapter(),
    )
    report = engine.analyze(ctx)
    for ev in report.cai_evidence:
        assert ev.metadata["_source_layer"] == "cai"


def test_cai_source_layer_tag_spread() -> None:
    engine = OrchestrationEngine()
    spread = SpreadAnalysis(
        instrument_a="US10Y",
        instrument_b="DE10Y",
        current_spread=1.80,
        historical_mean=1.50,
        standard_deviation=0.30,
        z_score=1.00,
        trend=SPREAD_WIDENING,
        confidence=0.72,
        valid_from="2026-07-27T00:00:00Z",
        valid_until="2026-10-27T00:00:00Z",
    )
    ctx = OrchestrationContext(
        cai_spreads=[spread],
        cai_adapter=CaiEvidenceAdapter(),
    )
    report = engine.analyze(ctx)
    for ev in report.cai_evidence:
        assert ev.metadata["_source_layer"] == "cai"


def test_cai_source_layer_tag_volatility() -> None:
    engine = OrchestrationEngine()
    vol = VolatilityRegime(
        asset_class=COMMODITIES,
        current_state=VOL_EXTREME,
        previous_state=VOL_HIGH,
        regime_persistence=0.95,
        confidence=0.92,
        valid_from="2026-07-27T00:00:00Z",
        valid_until="2026-10-27T00:00:00Z",
    )
    ctx = OrchestrationContext(
        cai_volatilities=[vol],
        cai_adapter=CaiEvidenceAdapter(),
    )
    report = engine.analyze(ctx)
    for ev in report.cai_evidence:
        assert ev.metadata["_source_layer"] == "cai"


# ── Multiple Objects per Type ──────────────────────────────────────────────


def test_engine_cai_multiple_correlations() -> None:
    engine = OrchestrationEngine()
    corrs = [
        CrossAssetCorrelation(
            asset_class_a=EQUITIES, asset_class_b=FIXED_INCOME,
            correlation_coefficient=-0.65, trend_direction=CORRELATION_NEGATIVE,
            confidence=0.85,
            valid_from="2026-07-27T00:00:00Z", valid_until="2026-10-27T00:00:00Z",
        ),
        CrossAssetCorrelation(
            asset_class_a=EQUITIES, asset_class_b=COMMODITIES,
            correlation_coefficient=0.40, trend_direction=CORRELATION_POSITIVE,
            confidence=0.70,
            valid_from="2026-07-27T00:00:00Z", valid_until="2026-10-27T00:00:00Z",
        ),
        CrossAssetCorrelation(
            asset_class_a=COMMODITIES, asset_class_b=FIXED_INCOME,
            correlation_coefficient=-0.30, trend_direction=CORRELATION_DECOUPLING,
            confidence=0.60,
            valid_from="2026-07-27T00:00:00Z", valid_until="2026-10-27T00:00:00Z",
        ),
    ]
    ctx = OrchestrationContext(
        cai_correlations=corrs,
        cai_adapter=CaiEvidenceAdapter(),
    )
    report = engine.analyze(ctx)
    assert len(report.cai_evidence) == 3
    assert all(ev.event_type == "CAI_CORRELATION" for ev in report.cai_evidence)


def test_engine_cai_multiple_volatility_regimes() -> None:
    engine = OrchestrationEngine()
    vols = [
        VolatilityRegime(
            asset_class=EQUITIES, current_state=VOL_ELEVATED,
            previous_state=VOL_MODERATE, regime_persistence=0.72,
            confidence=0.82,
            valid_from="2026-07-27T00:00:00Z", valid_until="2026-10-27T00:00:00Z",
        ),
        VolatilityRegime(
            asset_class=COMMODITIES, current_state=VOL_LOW,
            previous_state=VOL_LOW, regime_persistence=0.95,
            confidence=0.90,
            valid_from="2026-07-27T00:00:00Z", valid_until="2026-10-27T00:00:00Z",
        ),
    ]
    ctx = OrchestrationContext(
        cai_volatilities=vols,
        cai_adapter=CaiEvidenceAdapter(),
    )
    report = engine.analyze(ctx)
    assert len(report.cai_evidence) == 2
    biases = {ev.bias for ev in report.cai_evidence}
    assert "bearish" in biases
    assert "bullish" in biases


# ── Context Defaults ───────────────────────────────────────────────────────


def test_context_cai_defaults() -> None:
    ctx = OrchestrationContext()
    assert ctx.cai_correlations is None
    assert ctx.cai_spreads is None
    assert ctx.cai_volatilities is None
    assert ctx.cai_adapter is None


# ── Weighted Aggregate ─────────────────────────────────────────────────────


def test_cai_evidence_reaches_weighted_aggregate() -> None:
    engine = OrchestrationEngine()
    vol = VolatilityRegime(
        asset_class=EQUITIES,
        current_state=VOL_HIGH,
        previous_state=VOL_MODERATE,
        regime_persistence=0.80,
        confidence=0.88,
        valid_from="2026-07-27T00:00:00Z",
        valid_until="2026-10-27T00:00:00Z",
    )
    ctx = OrchestrationContext(
        cai_volatilities=[vol],
        cai_adapter=CaiEvidenceAdapter(),
    )
    report = engine.analyze(ctx)
    assert report.weighted_aggregate is not None
    assert report.weighted_aggregate.total_raw_weight > 0


# ── Provenance Passthrough ─────────────────────────────────────────────────


def test_cai_provenance_preserved_through_engine() -> None:
    engine = OrchestrationEngine()
    provenance = Provenance(
        created_at="2026-07-27T00:00:00Z",
        created_by="quant_desk",
        entity_version="1.0.0",
    )
    corr = CrossAssetCorrelation(
        asset_class_a=EQUITIES,
        asset_class_b=FIXED_INCOME,
        correlation_coefficient=-0.65,
        trend_direction=CORRELATION_NEGATIVE,
        confidence=0.85,
        valid_from="2026-07-27T00:00:00Z",
        valid_until="2026-10-27T00:00:00Z",
        provenance=provenance,
    )
    ctx = OrchestrationContext(
        cai_correlations=[corr],
        cai_adapter=CaiEvidenceAdapter(),
    )
    report = engine.analyze(ctx)
    ev = report.cai_evidence[0]
    assert ev.provenance is not None
    assert ev.provenance.created_by == "quant_desk"


# ── Bias Mapping Verification ─────────────────────────────────────────────


def test_cai_volatility_bias_mappings() -> None:
    engine = OrchestrationEngine()
    adapter = CaiEvidenceAdapter()
    expected = {
        VOL_LOW: "bullish",
        VOL_MODERATE: "neutral",
        VOL_ELEVATED: "bearish",
        VOL_HIGH: "bearish",
        VOL_EXTREME: "bearish",
    }
    for state, expected_bias in expected.items():
        vol = VolatilityRegime(
            asset_class=EQUITIES,
            current_state=state,
            previous_state=VOL_MODERATE,
            regime_persistence=0.5,
            confidence=0.7,
            valid_from="2026-07-27T00:00:00Z",
            valid_until="2026-10-27T00:00:00Z",
        )
        ctx = OrchestrationContext(
            cai_volatilities=[vol],
            cai_adapter=adapter,
        )
        report = engine.analyze(ctx)
        assert report.cai_evidence[0].bias == expected_bias, (
            f"Expected {expected_bias} for {state}"
        )


def test_cai_spread_bias_mappings() -> None:
    engine = OrchestrationEngine()
    adapter = CaiEvidenceAdapter()
    expected = {
        SPREAD_NARROWING: "bullish",
        SPREAD_WIDENING: "bearish",
        SPREAD_STABLE: "neutral",
        SPREAD_INVERSION: "bearish",
    }
    for trend, expected_bias in expected.items():
        spread = SpreadAnalysis(
            instrument_a="A",
            instrument_b="B",
            current_spread=1.0,
            historical_mean=1.0,
            standard_deviation=0.5,
            z_score=0.0,
            trend=trend,
            confidence=0.7,
            valid_from="2026-07-27T00:00:00Z",
            valid_until="2026-10-27T00:00:00Z",
        )
        ctx = OrchestrationContext(
            cai_spreads=[spread],
            cai_adapter=adapter,
        )
        report = engine.analyze(ctx)
        assert report.cai_evidence[0].bias == expected_bias, (
            f"Expected {expected_bias} for {trend}"
        )
