from __future__ import annotations

import time
from pathlib import Path

from knowledge.builders.lesson_builder import LessonBuilder, LessonBuilderConfig
from knowledge.lesson_summary import LessonSummaryAggregator, LessonSummaryConfig
from knowledge.graph.builder import GraphBuilder
from knowledge.evidence.query import EvidenceQuery
from knowledge.reasoning.engine import ReasoningEngine
from knowledge.reasoning.context import ReasoningContext
from knowledge.decision.engine import DecisionEngine
from knowledge.decision.context import DecisionContext
from knowledge.pipeline.context import PipelineContext
from knowledge.pipeline.result import PipelineResult


class InferencePipeline:
    def run(self, context: PipelineContext) -> PipelineResult:
        result = PipelineResult(context)

        self._stage_build_lessons(context, result)
        self._stage_build_knowledge(context, result)
        self._stage_build_graph(context, result)
        self._stage_query_evidence(context, result)
        self._stage_reason(context, result)
        self._stage_decide(context, result)

        return result

    def _stage_build_lessons(
        self, context: PipelineContext, result: PipelineResult
    ) -> None:
        t0 = time.perf_counter()
        lessons_path = context.output_dir / "lessons.csv"
        config = LessonBuilderConfig(
            event_data_path=context.event_data_path,
            gold_path=context.gold_path,
            output_path=lessons_path,
            horizons=context.horizons,
        )
        builder = LessonBuilder(config=config, event=context.event)
        lessons = builder.build_and_save()
        elapsed = (time.perf_counter() - t0) * 1000
        result.add_stage(
            "build_lessons",
            {"dataframe": lessons, "count": len(lessons), "path": lessons_path},
            elapsed,
            {"event_type": context.event.event_type},
        )

    def _stage_build_knowledge(
        self, context: PipelineContext, result: PipelineResult
    ) -> None:
        t0 = time.perf_counter()
        lessons_output = result._stage_output("build_lessons")
        lessons_path = lessons_output["path"]
        knowledge_path = context.output_dir / "knowledge.json"
        config = LessonSummaryConfig(
            lessons_path=lessons_path,
            output_path=knowledge_path,
            condition_columns=context.condition_columns,
            knowledge_prefix=context.knowledge_prefix,
            event_type=context.event.event_type,
            asset=context.asset,
            horizons=context.horizons,
            min_samples_for_confidence=context.min_samples_for_confidence,
        )
        aggregator = LessonSummaryAggregator(config)
        summary = aggregator.build_and_save()
        elapsed = (time.perf_counter() - t0) * 1000
        result.add_stage(
            "build_knowledge",
            summary,
            elapsed,
            {"lessons_path": str(lessons_path), "record_count": summary.get("record_count", 0)},
        )

    def _stage_build_graph(
        self, context: PipelineContext, result: PipelineResult
    ) -> None:
        t0 = time.perf_counter()
        knowledge = result._stage_output("build_knowledge")
        records = knowledge.get("records", [])
        graph = GraphBuilder().build(records)
        elapsed = (time.perf_counter() - t0) * 1000
        result.add_stage(
            "build_graph",
            graph,
            elapsed,
            {"node_count": graph.node_count, "relation_count": graph.relation_count},
        )

    def _stage_query_evidence(
        self, context: PipelineContext, result: PipelineResult
    ) -> None:
        t0 = time.perf_counter()
        graph = result._stage_output("build_graph")
        query = EvidenceQuery(graph)
        if context.reasoning_condition is not None:
            evidence = query.by_condition(context.reasoning_condition)
        else:
            evidence = query.all()
        elapsed = (time.perf_counter() - t0) * 1000
        result.add_stage(
            "query_evidence",
            evidence,
            elapsed,
            {"evidence_count": len(evidence)},
        )

    def _stage_reason(
        self, context: PipelineContext, result: PipelineResult
    ) -> None:
        t0 = time.perf_counter()
        evidence = result._stage_output("query_evidence")
        engine = ReasoningEngine()
        rctx = ReasoningContext(
            event_type=context.event.event_type,
            condition=context.reasoning_condition,
            horizon_days=context.reasoning_horizon,
        )
        chain = engine.reason(evidence, rctx)
        elapsed = (time.perf_counter() - t0) * 1000
        result.add_stage(
            "reason",
            chain,
            elapsed,
            {
                "chain_id": chain.chain_id,
                "step_count": len(chain.steps),
                "overall_confidence": chain.overall_confidence,
            },
        )

    def _stage_decide(
        self, context: PipelineContext, result: PipelineResult
    ) -> None:
        t0 = time.perf_counter()
        chain = result._stage_output("reason")
        engine = DecisionEngine()
        dctx = DecisionContext(
            event_type=context.event.event_type,
            query=context.query,
        ) if context.query else None
        decision = engine.decide(chain, context=dctx)
        elapsed = (time.perf_counter() - t0) * 1000
        result.add_stage(
            "decide",
            decision,
            elapsed,
            {
                "decision_id": decision.decision_id,
                "decision_type": decision.decision_type,
                "confidence": decision.confidence,
            },
        )
