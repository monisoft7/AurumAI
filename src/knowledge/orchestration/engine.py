from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from knowledge.evidence.evidence import Evidence
from knowledge.evidence.collection import EvidenceCollection
from knowledge.evidence.weighting import EvidenceWeighter, WeightedAggregate
from knowledge.causal.relation import CausalRelation
from knowledge.integrity.lineage import LineageRelationType
from knowledge.orchestration.context import OrchestrationContext
from knowledge.orchestration.aggregator import EvidenceAggregator
from knowledge.orchestration.policy import LayerPolicy, evaluate_policies
from knowledge.reasoning.cross_event import CrossEventAnalyzer
from knowledge.reasoning.retrieval import SituationQuery


@dataclass
class OrchestrationReport:
    economic_evidence: EvidenceCollection = field(default_factory=EvidenceCollection)
    temporal_evidence: EvidenceCollection = field(default_factory=EvidenceCollection)
    causal_evidence: EvidenceCollection = field(default_factory=EvidenceCollection)
    core_evidence: EvidenceCollection = field(default_factory=EvidenceCollection)
    aggregation: Any = None
    weighted_aggregate: WeightedAggregate | None = None
    chain: Any = None
    decision: Any = None
    cross_event_result: Any = None
    historical_matches: list[Any] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    timing_ms: dict[str, float] = field(default_factory=dict)


def _causal_relation_to_evidence(r: CausalRelation) -> Evidence:
    return Evidence(
        evidence_id=f"causal_{r.relation_id}",
        source_node_id=f"causal_{r.source_id}_{r.target_id}",
        event_type="CAUSAL",
        condition={"relation_type": r.relation_type, "direction": r.direction},
        horizon_days=r.temporal_lag,
        sample_count=len(r.evidence_ids),
        average_return_pct=0.0,
        confidence=r.confidence,
        bias="neutral",
        explanation=r.explanation,
        metadata={
            "causal_relation_id": r.relation_id,
            "source_id": r.source_id,
            "target_id": r.target_id,
            "relation_type": r.relation_type,
            "strength": r.strength,
            "direction": r.direction,
        },
    )


class OrchestrationEngine:
    def __init__(self, aggregator: EvidenceAggregator | None = None):
        self._aggregator = aggregator or EvidenceAggregator()

    def analyze(
        self,
        ctx: OrchestrationContext,
        policies: list[LayerPolicy] | None = None,
    ) -> OrchestrationReport:
        report = OrchestrationReport()

        if policies is not None:
            active = evaluate_policies(policies, ctx)
            collections: dict[str, EvidenceCollection] = {
                f"p{i}": p.layer_fn(ctx) for i, p in enumerate(active)
            }
            collections = {k: v for k, v in collections.items() if v}
        else:
            report.economic_evidence = self._run_economic(ctx)
            report.temporal_evidence = self._run_temporal(ctx)
            report.causal_evidence = self._run_causal(ctx)
            report.core_evidence = self._run_core(ctx)

            collections = {}
            if report.economic_evidence:
                collections["economic"] = report.economic_evidence
            if report.temporal_evidence:
                collections["temporal"] = report.temporal_evidence
            if report.causal_evidence:
                collections["causal"] = report.causal_evidence
            if report.core_evidence:
                collections["core"] = report.core_evidence

        report.aggregation = self._aggregator.merge(collections)

        merged = report.aggregation.collection
        weighter = EvidenceWeighter()
        report.weighted_aggregate = weighter.weigh(merged)
        if ctx.event_types is not None and len(ctx.event_types) >= 2:
            analyzer = CrossEventAnalyzer()
            report.cross_event_result = analyzer.analyze(merged)

        if ctx.retriever is not None and ctx.evidence_query is not None:
            query = SituationQuery(
                event_type=ctx.event_type,
                condition=ctx.condition,
                horizon_days=ctx.horizon_days,
                date=ctx.date,
            )
            report.historical_matches = ctx.retriever.retrieve(
                query=query,
                evidence_query=ctx.evidence_query,
                temporal_indexer=ctx.temporal_indexer,
            )

        if ctx.reasoning_engine is not None:
            from knowledge.reasoning.context import ReasoningContext
            from knowledge.decision.context import DecisionContext

            rctx = ReasoningContext(
                event_type=ctx.event_type,
                condition=ctx.condition,
                horizon_days=ctx.horizon_days,
            )
            chain = ctx.reasoning_engine.reason(merged, rctx)
            report.chain = chain

            dctx = DecisionContext(event_type=ctx.event_type, query=ctx.query) if ctx.query else None
            decision = ctx.decision_engine.decide(chain, context=dctx) if ctx.decision_engine else None
            report.decision = decision

            if ctx.lineage_registry is not None:
                self._record_lineage(ctx, collections, chain, decision)

        return report

    def _run_economic(self, ctx: OrchestrationContext) -> EvidenceCollection:
        if ctx.economic_adapter is None:
            return EvidenceCollection()
        items: list[Evidence] = []
        if ctx.economic_states is not None:
            for state in ctx.economic_states:
                regimes = ctx.economic_adapter.regimes_at_date(state.date, ctx.economic_states)
                for regime in regimes:
                    ev = ctx.economic_adapter.regime_to_evidence(regime)
                    ev.metadata["_source_layer"] = "economic"
                    items.append(ev)
        return EvidenceCollection(items)

    def _run_temporal(self, ctx: OrchestrationContext) -> EvidenceCollection:
        if ctx.temporal_adapter is None or ctx.temporal_indexer is None:
            return EvidenceCollection()
        items = ctx.temporal_adapter.indexer_to_evidence(ctx.temporal_indexer)
        for ev in items:
            ev.metadata["_source_layer"] = "temporal"
        return EvidenceCollection(items)

    def _run_causal(self, ctx: OrchestrationContext) -> EvidenceCollection:
        if ctx.causal_graph is None:
            return EvidenceCollection()
        items = [_causal_relation_to_evidence(r) for r in ctx.causal_graph.all_relations()]
        for ev in items:
            ev.metadata["_source_layer"] = "causal"
        return EvidenceCollection(items)

    def _run_core(self, ctx: OrchestrationContext) -> EvidenceCollection:
        if ctx.evidence_query is None:
            return EvidenceCollection()
        types = ctx.event_types if ctx.event_types is not None else (ctx.event_type,)
        all_items: list[Evidence] = []
        for et in types:
            coll = ctx.evidence_query.matching(
                event_type=et,
                condition=ctx.condition,
                horizon_days=ctx.horizon_days,
            )
            for ev in coll:
                ev.metadata["_source_layer"] = "core"
            all_items.extend(coll)
        return EvidenceCollection(all_items)

    def _record_lineage(
        self,
        ctx: OrchestrationContext,
        collections: dict[str, EvidenceCollection],
        chain: Any,
        decision: Any,
    ) -> None:
        reg = ctx.lineage_registry
        if reg is None:
            return
        for layer_name, coll in collections.items():
            for ev in coll:
                reg.add(
                    source_id=f"layer:{layer_name}",
                    source_type="intelligence_layer",
                    target_id=ev.evidence_id,
                    target_type="evidence",
                    relation_type=LineageRelationType.GENERATES,
                    metadata={"layer": layer_name},
                )
        if chain is not None:
            for step in getattr(chain, "steps", ()):
                for eid in getattr(step, "supporting_evidence_ids", ()):
                    reg.add(
                        source_id=eid,
                        source_type="evidence",
                        target_id=chain.chain_id,
                        target_type="reasoning_chain",
                        relation_type=LineageRelationType.REFERENCES,
                    )
            for coll in collections.values():
                for ev in coll:
                    if ev.metadata.get("_source_layer") == "core":
                        reg.add(
                            source_id=ev.source_node_id,
                            source_type="knowledge_record",
                            target_id=ev.evidence_id,
                            target_type="evidence",
                            relation_type=LineageRelationType.REFERENCES,
                        )
        if decision is not None:
            reg.add(
                source_id=decision.reasoning_chain_id,
                source_type="reasoning_chain",
                target_id=decision.decision_id,
                target_type="decision",
                relation_type=LineageRelationType.GENERATES,
            )
