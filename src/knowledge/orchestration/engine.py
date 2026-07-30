from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from knowledge.evidence.evidence import Evidence
from knowledge.evidence.collection import EvidenceCollection
from knowledge.evidence.weighting import EvidenceWeighter, WeightedAggregate
from knowledge.causal.relation import CausalRelation
from knowledge.integrity.lineage import LineageRelationType
from knowledge.cbi.adapter import CbiEvidenceAdapter
from knowledge.cai.adapter import CaiEvidenceAdapter
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
    cbi_evidence: EvidenceCollection = field(default_factory=EvidenceCollection)
    cai_evidence: EvidenceCollection = field(default_factory=EvidenceCollection)
    cfi_evidence: EvidenceCollection = field(default_factory=EvidenceCollection)
    regime_evidence: EvidenceCollection = field(default_factory=EvidenceCollection)
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
            report.cbi_evidence = self._run_cbi(ctx)
            report.cai_evidence = self._run_cai(ctx)
            report.cfi_evidence = self._run_cfi(ctx)
            report.regime_evidence = self._run_regime(ctx)

            collections = {}
            if report.economic_evidence:
                collections["economic"] = report.economic_evidence
            if report.temporal_evidence:
                collections["temporal"] = report.temporal_evidence
            if report.causal_evidence:
                collections["causal"] = report.causal_evidence
            if report.core_evidence:
                collections["core"] = report.core_evidence
            if report.cbi_evidence:
                collections["cbi"] = report.cbi_evidence
            if report.cai_evidence:
                collections["cai"] = report.cai_evidence
            if report.cfi_evidence:
                collections["cfi"] = report.cfi_evidence
            if report.regime_evidence:
                collections["regime"] = report.regime_evidence

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
                institutional_context=ctx.institutional_context,
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
                    new_meta = dict(ev.metadata)
                    new_meta["_source_layer"] = "economic"
                    object.__setattr__(ev, "metadata", new_meta)
                    items.append(ev)
        return EvidenceCollection(items)

    def _run_temporal(self, ctx: OrchestrationContext) -> EvidenceCollection:
        if ctx.temporal_adapter is None or ctx.temporal_indexer is None:
            return EvidenceCollection()
        items = ctx.temporal_adapter.indexer_to_evidence(ctx.temporal_indexer)
        for ev in items:
            new_meta = dict(ev.metadata)
            new_meta["_source_layer"] = "temporal"
            object.__setattr__(ev, "metadata", new_meta)
        return EvidenceCollection(items)

    def _run_causal(self, ctx: OrchestrationContext) -> EvidenceCollection:
        if ctx.causal_graph is None:
            return EvidenceCollection()
        items = [_causal_relation_to_evidence(r) for r in ctx.causal_graph.all_relations()]
        for ev in items:
            new_meta = dict(ev.metadata)
            new_meta["_source_layer"] = "causal"
            object.__setattr__(ev, "metadata", new_meta)
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
                new_meta = dict(ev.metadata)
                new_meta["_source_layer"] = "core"
                object.__setattr__(ev, "metadata", new_meta)
            all_items.extend(coll)
        return EvidenceCollection(all_items)

    def _run_cbi(self, ctx: OrchestrationContext) -> EvidenceCollection:
        if ctx.cbi_adapter is None:
            return EvidenceCollection()
        items: list[Evidence] = []
        if ctx.cbi_bias_scores is not None:
            for pbs in ctx.cbi_bias_scores:
                ev = ctx.cbi_adapter.policy_bias_to_evidence(pbs)
                new_meta = dict(ev.metadata)
                new_meta["_source_layer"] = "cbi"
                object.__setattr__(ev, "metadata", new_meta)
                items.append(ev)
        if ctx.cbi_guidance_records is not None:
            for fgr in ctx.cbi_guidance_records:
                ev = ctx.cbi_adapter.forward_guidance_to_evidence(fgr)
                new_meta = dict(ev.metadata)
                new_meta["_source_layer"] = "cbi"
                object.__setattr__(ev, "metadata", new_meta)
                items.append(ev)
        if ctx.cbi_rate_paths is not None:
            for rpp in ctx.cbi_rate_paths:
                ev = ctx.cbi_adapter.rate_path_to_evidence(rpp)
                new_meta = dict(ev.metadata)
                new_meta["_source_layer"] = "cbi"
                object.__setattr__(ev, "metadata", new_meta)
                items.append(ev)
        return EvidenceCollection(items)

    def _run_cai(self, ctx: OrchestrationContext) -> EvidenceCollection:
        if ctx.cai_adapter is None:
            return EvidenceCollection()
        items: list[Evidence] = []
        if ctx.cai_correlations is not None:
            for corr in ctx.cai_correlations:
                ev = ctx.cai_adapter.cross_asset_correlation_to_evidence(corr)
                new_meta = dict(ev.metadata)
                new_meta["_source_layer"] = "cai"
                object.__setattr__(ev, "metadata", new_meta)
                items.append(ev)
        if ctx.cai_spreads is not None:
            for spread in ctx.cai_spreads:
                ev = ctx.cai_adapter.spread_analysis_to_evidence(spread)
                new_meta = dict(ev.metadata)
                new_meta["_source_layer"] = "cai"
                object.__setattr__(ev, "metadata", new_meta)
                items.append(ev)
        if ctx.cai_volatilities is not None:
            for vol in ctx.cai_volatilities:
                ev = ctx.cai_adapter.volatility_regime_to_evidence(vol)
                new_meta = dict(ev.metadata)
                new_meta["_source_layer"] = "cai"
                object.__setattr__(ev, "metadata", new_meta)
                items.append(ev)
        return EvidenceCollection(items)

    def _run_cfi(self, ctx: OrchestrationContext) -> EvidenceCollection:
        if ctx.cfi_adapter is None:
            return EvidenceCollection()
        items: list[Evidence] = []
        if ctx.cfi_etf_flows is not None:
            for flow in ctx.cfi_etf_flows:
                ev = ctx.cfi_adapter.etf_flow_to_evidence(flow)
                new_meta = dict(ev.metadata)
                new_meta["_source_layer"] = "cfi"
                object.__setattr__(ev, "metadata", new_meta)
                items.append(ev)
        if ctx.cfi_cb_reserve_reports is not None:
            for report in ctx.cfi_cb_reserve_reports:
                ev = ctx.cfi_adapter.cb_reserve_flow_to_evidence(report)
                new_meta = dict(ev.metadata)
                new_meta["_source_layer"] = "cfi"
                object.__setattr__(ev, "metadata", new_meta)
                items.append(ev)
        if ctx.cfi_positioning_dashboards is not None:
            for dash in ctx.cfi_positioning_dashboards:
                ev = ctx.cfi_adapter.positioning_to_evidence(dash)
                new_meta = dict(ev.metadata)
                new_meta["_source_layer"] = "cfi"
                object.__setattr__(ev, "metadata", new_meta)
                items.append(ev)
        return EvidenceCollection(items)

    def _run_regime(self, ctx: OrchestrationContext) -> EvidenceCollection:
        if ctx.regime_evidence is not None:
            items = list(ctx.regime_evidence)
            for ev in items:
                new_meta = dict(ev.metadata)
                new_meta["_source_layer"] = "regime"
                object.__setattr__(ev, "metadata", new_meta)
            return EvidenceCollection(items)
        if ctx.composite_score_builder is None or ctx.regime_detector is None:
            return EvidenceCollection()
        try:
            scores = ctx.composite_score_builder.build()
            if scores.empty:
                return EvidenceCollection()
            detector = ctx.regime_detector.fit(scores)
            regime_data = detector.get_regime_data()
            regimes = regime_data["macro_regime"].unique()
            items = [
                Evidence(
                    evidence_id=f"regime_{r}",
                    source_node_id=f"macro_regime_{r}",
                    event_type="REGIME",
                    condition={"macro_regime": r},
                    horizon_days=90,
                    sample_count=int((regime_data["macro_regime"] == r).sum()),
                    average_return_pct=0.0,
                    confidence=0.7,
                    bias=self._regime_to_bias(r),
                    explanation=f"Macro regime detected: {r}",
                    metadata={
                        "macro_regime": r,
                        "regime_count": int((regime_data["macro_regime"] == r).sum()),
                    },
                )
                for r in regimes
            ]
            for ev in items:
                new_meta = dict(ev.metadata)
                new_meta["_source_layer"] = "regime"
                object.__setattr__(ev, "metadata", new_meta)
            return EvidenceCollection(items)
        except Exception:
            return EvidenceCollection()

    @staticmethod
    def _regime_to_bias(regime: str) -> str:
        if regime in ("CONTRACTION",):
            return "bearish"
        if regime in ("EXPANSION", "RECOVERY"):
            return "bullish"
        return "neutral"

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
