import json
from pathlib import Path

from knowledge.pipeline.result import PipelineResult
from knowledge.graph.graph import KnowledgeGraph
from knowledge.evidence.collection import EvidenceCollection
from knowledge.reasoning.chain import ReasoningChain
from knowledge.decision.decision import Decision


class PipelineRepository:
    def save(self, result: PipelineResult, path: Path) -> None:
        stages_data = []
        for stage in result.stages:
            output = stage.output
            serialized = self._serialize_output(output)
            stages_data.append({
                "name": stage.name,
                "output_type": type(output).__name__,
                "output": serialized,
                "duration_ms": round(stage.duration_ms, 2),
                "references": stage.references,
            })

        payload = {
            "context": {
                "event_type": result.context.event.event_type,
                "event_data_path": str(result.context.event_data_path),
                "gold_path": str(result.context.gold_path),
                "output_dir": str(result.context.output_dir),
                "knowledge_prefix": result.context.knowledge_prefix,
                "condition_columns": list(result.context.condition_columns),
                "horizons": list(result.context.horizons),
                "query": result.context.query,
                "reasoning_condition": result.context.reasoning_condition,
                "reasoning_horizon": result.context.reasoning_horizon,
                "min_evidence_count": result.context.min_evidence_count,
                "yield_data_path": (
                    None if result.context.yield_data_path is None
                    else str(result.context.yield_data_path)
                ),
                "yield_context_lookback_days": result.context.yield_context_lookback_days,
                "context_comparison_baseline_path": (
                    None if result.context.context_comparison_baseline_path is None
                    else str(result.context.context_comparison_baseline_path)
                ),
                "context_comparison_output_path": (
                    None if result.context.context_comparison_output_path is None
                    else str(result.context.context_comparison_output_path)
                ),
                "context_comparison_base_columns": (
                    None if result.context.context_comparison_base_columns is None
                    else list(result.context.context_comparison_base_columns)
                ),
                "context_comparison_context_columns": (
                    None if result.context.context_comparison_context_columns is None
                    else list(result.context.context_comparison_context_columns)
                ),
            },
            "stages": stages_data,
        }
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, indent=2))

    def _serialize_output(self, output: object) -> dict | list | str | None:
        if isinstance(output, dict):
            return {k: self._serialize_value(v) for k, v in output.items()}
        if isinstance(output, KnowledgeGraph):
            nodes = []
            for nid, data in output._graph.nodes(data=True):
                nodes.append({
                    "node_id": nid,
                    "node_type": data.get("node_type", ""),
                    "properties": data.get("properties", {}),
                })
            rels = []
            for u, v, data in output._graph.edges(data=True):
                rels.append({
                    "source_id": u,
                    "target_id": v,
                    "relation_type": data.get("relation_type", ""),
                    "properties": data.get("properties", {}),
                })
            return {"node_count": output.node_count, "relation_count": output.relation_count, "nodes": nodes, "relations": rels}
        if isinstance(output, EvidenceCollection):
            return {
                "evidence_count": len(output),
                "evidence_ids": [e.evidence_id for e in output],
            }
        if isinstance(output, ReasoningChain):
            return {
                "chain_id": output.chain_id,
                "final_conclusion": output.final_conclusion,
                "overall_confidence": output.overall_confidence,
                "step_count": len(output.steps),
            }
        if isinstance(output, Decision):
            return {
                "decision_id": output.decision_id,
                "decision_type": output.decision_type,
                "confidence": output.confidence,
                "reasoning_chain_id": output.reasoning_chain_id,
                "explanation": output.explanation,
            }
        return None

    def _serialize_value(self, value: object) -> object:
        if isinstance(value, Path):
            return str(value)
        if hasattr(value, "to_dict"):
            return value.to_dict()
        if hasattr(value, "to_csv"):
            return str(type(value))
        return value
