from __future__ import annotations

from pathlib import Path

import pytest

from knowledge.evidence.evidence import Evidence
from knowledge.evidence.collection import EvidenceCollection
from knowledge.economics.regime import EconomicRegime
from knowledge.economics.state import EconomicState

from knowledge.economics.adapter import EconomicEvidenceAdapter
from knowledge.temporal.state import TemporalState
from knowledge.temporal.indexer import TemporalIndexer
from knowledge.temporal.context import TimeContext
from knowledge.temporal.adapter import TemporalEvidenceAdapter
from knowledge.causal.relation import (
    CausalRelation,
    RELATION_CAUSATION,
    DIRECTION_SOURCE_TO_TARGET,
)
from knowledge.causal.graph import CausalGraph
from knowledge.causal.analyzer import CausalAnalyzer
from knowledge.graph.graph import KnowledgeGraph
from knowledge.graph.node import GraphNode
from knowledge.evidence.query import EvidenceQuery
from knowledge.reasoning.engine import ReasoningEngine
from knowledge.decision.engine import DecisionEngine
from knowledge.decision.context import DecisionContext
from knowledge.integrity.lineage import LineageRegistry, LineageRelationType

from knowledge.orchestration.context import OrchestrationContext
from knowledge.orchestration.aggregator import EvidenceAggregator, AggregationResult
from knowledge.orchestration.engine import OrchestrationEngine, OrchestrationReport
from knowledge.orchestration.policy import LayerPolicy, evaluate_policies


# ── EvidenceAggregator ──────────────────────────────────────────────────────

def test_aggregator_merge_single_layer() -> None:
    agg = EvidenceAggregator()
    coll = EvidenceCollection([
        Evidence(
            evidence_id="ev_1", source_node_id="n1", event_type="ECONOMIC",
            condition={}, horizon_days=0, sample_count=1,
            average_return_pct=0.0, confidence=0.8, bias="bullish",
            explanation="ok",
        ),
    ])
    result = agg.merge({"economic": coll})
    assert isinstance(result, AggregationResult)
    assert len(result.collection) == 1
    assert result.layer_counts == {"economic": 1}


def test_aggregator_merge_multiple_layers() -> None:
    agg = EvidenceAggregator()
    econ = EvidenceCollection([
        Evidence(
            evidence_id="ev_1", source_node_id="n1", event_type="ECONOMIC",
            condition={}, horizon_days=0, sample_count=1,
            average_return_pct=0.0, confidence=0.8, bias="bullish",
            explanation="econ",
        ),
    ])
    temporal = EvidenceCollection([
        Evidence(
            evidence_id="ev_2", source_node_id="n2", event_type="TEMPORAL",
            condition={}, horizon_days=0, sample_count=1,
            average_return_pct=0.0, confidence=0.9, bias="bearish",
            explanation="temporal",
        ),
    ])
    result = agg.merge({"economic": econ, "temporal": temporal})
    assert len(result.collection) == 2
    assert result.layer_counts == {"economic": 1, "temporal": 1}


def test_aggregator_deduplicates_by_id() -> None:
    agg = EvidenceAggregator()
    coll = EvidenceCollection([
        Evidence(
            evidence_id="ev_1", source_node_id="n1", event_type="ECONOMIC",
            condition={}, horizon_days=0, sample_count=1,
            average_return_pct=0.0, confidence=0.8, bias="bullish",
            explanation="same",
        ),
    ])
    result = agg.merge({"economic": coll, "temporal": coll})
    assert len(result.collection) == 1


def test_aggregator_conflict_detection() -> None:
    agg = EvidenceAggregator()
    econ = EvidenceCollection([
        Evidence(
            evidence_id="ev_1", source_node_id="n1", event_type="ECONOMIC",
            condition={}, horizon_days=0, sample_count=1,
            average_return_pct=0.0, confidence=0.8, bias="bullish",
            explanation="econ", metadata={},
        ),
    ])
    temporal = EvidenceCollection([
        Evidence(
            evidence_id="ev_1", source_node_id="n1", event_type="TEMPORAL",
            condition={}, horizon_days=0, sample_count=1,
            average_return_pct=0.0, confidence=0.8, bias="bearish",
            explanation="temporal", metadata={},
        ),
    ])
    result = agg.merge({"economic": econ, "temporal": temporal})
    assert len(result.conflicts) == 1
    assert result.conflicts[0]["existing_bias"] == "bullish"
    assert result.conflicts[0]["incoming_bias"] == "bearish"


# ── OrchestrationEngine ─────────────────────────────────────────────────────

def make_kg_with_node(**overrides: str) -> KnowledgeGraph:
    props: dict = {
        "knowledge_id": "kr_1", "event_type": "CPI", "asset": "GOLD",
        "condition": {}, "horizon_days": 20, "sample_count": 10,
        "average_return_pct": 1.0, "confidence": 0.7, "bias": "bullish",
        "explanation": "test",
    }
    props.update(overrides)
    kg = KnowledgeGraph()
    kg.add_node(GraphNode(node_id="kr_1", node_type="knowledge_record", properties=props))
    return kg


def test_engine_analyze_no_layers() -> None:
    engine = OrchestrationEngine()
    ctx = OrchestrationContext()
    report = engine.analyze(ctx)
    assert isinstance(report, OrchestrationReport)
    assert len(report.economic_evidence) == 0
    assert len(report.temporal_evidence) == 0
    assert len(report.causal_evidence) == 0
    assert len(report.core_evidence) == 0
    assert report.chain is None
    assert report.decision is None


def test_engine_economic_layer() -> None:
    engine = OrchestrationEngine()
    states = [
        EconomicState(
            state_id="st_1", date="2026-01-01",
            indicators={"cpi_yoy_pct": 6.0},
            regime_ids=("HIGH_INFLATION",),
        ),
    ]
    adapter = EconomicEvidenceAdapter()
    ctx = OrchestrationContext(
        economic_states=states,
        economic_adapter=adapter,
    )
    report = engine.analyze(ctx)
    assert len(report.economic_evidence) > 0


def test_engine_temporal_layer() -> None:
    engine = OrchestrationEngine()
    indexer = TemporalIndexer(context=TimeContext(frequency="daily"))
    indexer.index(TemporalState(
        state_id="ts_1", date="2026-01-01", source_type="evidence", source_id="ev_1",
    ))
    adapter = TemporalEvidenceAdapter()
    ctx = OrchestrationContext(
        temporal_indexer=indexer,
        temporal_adapter=adapter,
    )
    report = engine.analyze(ctx)
    assert len(report.temporal_evidence) == 1


def test_engine_causal_layer() -> None:
    engine = OrchestrationEngine()
    graph = CausalGraph()
    graph.add_relation(CausalRelation(
        relation_id="cr_1", source_id="src_1", target_id="tgt_1",
        relation_type=RELATION_CAUSATION, strength=0.8, confidence=0.9,
        direction=DIRECTION_SOURCE_TO_TARGET, explanation="causal link",
    ))
    ctx = OrchestrationContext(causal_graph=graph)
    report = engine.analyze(ctx)
    assert len(report.causal_evidence) == 1
    ev = report.causal_evidence[0]
    assert ev.event_type == "CAUSAL"
    assert ev.confidence == 0.9


def test_engine_core_layer() -> None:
    engine = OrchestrationEngine()
    kg = make_kg_with_node()
    query = EvidenceQuery(kg)
    ctx = OrchestrationContext(evidence_query=query)
    report = engine.analyze(ctx)
    assert len(report.core_evidence) > 0


def test_engine_full_pipeline_with_decision() -> None:
    engine = OrchestrationEngine()
    kg = make_kg_with_node()
    query = EvidenceQuery(kg)
    reasoning = ReasoningEngine()
    decision = DecisionEngine()

    ctx = OrchestrationContext(
        event_type="CPI",
        evidence_query=query,
        reasoning_engine=reasoning,
        decision_engine=decision,
    )
    report = engine.analyze(ctx)
    assert len(report.core_evidence) > 0
    assert report.chain is not None
    assert report.decision is not None
    assert report.decision.decision_type is not None


def test_engine_aggregation_includes_all_layers() -> None:
    engine = OrchestrationEngine()

    graph = CausalGraph()
    graph.add_relation(CausalRelation(
        relation_id="cr_1", source_id="s1", target_id="s2",
        relation_type=RELATION_CAUSATION, strength=0.8, confidence=0.9,
        direction=DIRECTION_SOURCE_TO_TARGET, explanation="c",
    ))

    indexer = TemporalIndexer(context=TimeContext(frequency="daily"))
    indexer.index(TemporalState(
        state_id="ts_1", date="2026-01-01", source_type="evidence", source_id="ev_1",
    ))

    states = [
        EconomicState(
            state_id="st_1", date="2026-01-01",
            indicators={"cpi_yoy_pct": 6.0},
            regime_ids=("HIGH_INFLATION",),
        ),
    ]

    kg = make_kg_with_node()
    query = EvidenceQuery(kg)
    reasoning = ReasoningEngine()
    decision = DecisionEngine()

    ctx = OrchestrationContext(
        event_type="CPI",
        economic_states=states,
        economic_adapter=EconomicEvidenceAdapter(),
        temporal_indexer=indexer,
        temporal_adapter=TemporalEvidenceAdapter(),
        causal_graph=graph,
        evidence_query=query,
        reasoning_engine=reasoning,
        decision_engine=decision,
    )
    report = engine.analyze(ctx)
    assert len(report.economic_evidence) > 0
    assert len(report.temporal_evidence) > 0
    assert len(report.causal_evidence) > 0
    assert len(report.core_evidence) > 0
    assert report.aggregation is not None
    total = (
        report.aggregation.layer_counts.get("economic", 0)
        + report.aggregation.layer_counts.get("temporal", 0)
        + report.aggregation.layer_counts.get("causal", 0)
        + report.aggregation.layer_counts.get("core", 0)
    )
    assert total == len(report.aggregation.collection)
    assert report.chain is not None
    assert report.decision is not None


# ── Lineage Recording ───────────────────────────────────────────────────────

def test_engine_lineage_with_registry() -> None:
    reg = LineageRegistry()
    engine = OrchestrationEngine()

    graph = CausalGraph()
    graph.add_relation(CausalRelation(
        relation_id="cr_1", source_id="s1", target_id="s2",
        relation_type=RELATION_CAUSATION, strength=0.8, confidence=0.9,
        direction=DIRECTION_SOURCE_TO_TARGET, explanation="c",
    ))

    kg = make_kg_with_node()
    query = EvidenceQuery(kg)
    reasoning = ReasoningEngine()
    decision = DecisionEngine()

    ctx = OrchestrationContext(
        event_type="CPI",
        causal_graph=graph,
        evidence_query=query,
        reasoning_engine=reasoning,
        decision_engine=decision,
        lineage_registry=reg,
    )
    report = engine.analyze(ctx)
    assert report.decision is not None
    records = reg.all_records()
    assert len(records) > 0


# ── Policy Engine ────────────────────────────────────────────────────────────

def test_evaluate_policies_filters_by_condition() -> None:
    ctx = OrchestrationContext()
    p1 = LayerPolicy(layer_fn=lambda _: EvidenceCollection(), run_if=lambda c: False)
    p2 = LayerPolicy(layer_fn=lambda _: EvidenceCollection(), run_if=lambda c: True)
    result = evaluate_policies([p1, p2], ctx)
    assert len(result) == 1
    assert result[0] == p2


def test_evaluate_policies_sorts_by_priority() -> None:
    ctx = OrchestrationContext()
    low = LayerPolicy(layer_fn=lambda _: EvidenceCollection(), priority=10)
    high = LayerPolicy(layer_fn=lambda _: EvidenceCollection(), priority=0)
    result = evaluate_policies([low, high], ctx)
    assert result == [high, low]


def test_evaluate_policies_deterministic() -> None:
    ctx = OrchestrationContext(condition={"cpi_yoy_pct": "6.0"})
    def make_pol(threshold: str) -> LayerPolicy:
        return LayerPolicy(
            layer_fn=lambda _: EvidenceCollection(),
            run_if=lambda c: c.condition is not None and c.condition.get("cpi_yoy_pct", "") == threshold,
        )
    policies = [make_pol("6.0"), make_pol("7.0")]
    r1 = evaluate_policies(policies, ctx)
    r2 = evaluate_policies(policies, ctx)
    assert [p.run_if(ctx) for p in r1] == [p.run_if(ctx) for p in r2]


def test_engine_no_policies_default_unchanged() -> None:
    engine = OrchestrationEngine()
    ctx = OrchestrationContext()
    report = engine.analyze(ctx)
    assert len(report.economic_evidence) == 0
    assert len(report.temporal_evidence) == 0
    assert len(report.causal_evidence) == 0
    assert len(report.core_evidence) == 0
    assert report.chain is None


def test_engine_policies_skip_layers() -> None:
    engine = OrchestrationEngine()
    graph = CausalGraph()
    graph.add_relation(CausalRelation(
        relation_id="cr_1", source_id="s1", target_id="s2",
        relation_type=RELATION_CAUSATION, strength=0.8, confidence=0.9,
        direction=DIRECTION_SOURCE_TO_TARGET, explanation="c",
    ))
    ctx = OrchestrationContext(causal_graph=graph)

    policies = [
        LayerPolicy(layer_fn=engine._run_causal, run_if=lambda c: c.causal_graph is not None),
        LayerPolicy(layer_fn=engine._run_economic, run_if=lambda c: False),
    ]
    report = engine.analyze(ctx, policies=policies)
    assert report.aggregation is not None
    assert len(report.aggregation.collection) == 1


def test_engine_policies_respect_priority() -> None:
    engine = OrchestrationEngine()
    ctx = OrchestrationContext()
    order: list[str] = []

    def layer_a(_: OrchestrationContext) -> EvidenceCollection:
        order.append("a")
        return EvidenceCollection()

    def layer_b(_: OrchestrationContext) -> EvidenceCollection:
        order.append("b")
        return EvidenceCollection()

    policies = [
        LayerPolicy(layer_fn=layer_b, priority=10),
        LayerPolicy(layer_fn=layer_a, priority=0),
    ]
    engine.analyze(ctx, policies=policies)
    assert order == ["a", "b"]


# ── Context defaults ────────────────────────────────────────────────────────

def test_context_defaults() -> None:
    ctx = OrchestrationContext()
    assert ctx.event_type == "CPI"
    assert ctx.date == ""
    assert ctx.condition is None
    assert ctx.horizon_days is None
    assert ctx.economic_classifier is None
    assert ctx.temporal_indexer is None
    assert ctx.causal_graph is None
    assert ctx.evidence_query is None
    assert ctx.lineage_registry is None
