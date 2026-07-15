import json
from pathlib import Path
from typing import Any

from knowledge.causal.relation import CausalRelation
from knowledge.causal.hypothesis import CausalHypothesis
from knowledge.causal.evidence import CausalEvidence
from knowledge.causal.graph import CausalGraph


class CausalRepository:
    def save_graph(self, graph: CausalGraph, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        payload: dict[str, Any] = {
            "relations": [
                {
                    "relation_id": r.relation_id,
                    "source_id": r.source_id,
                    "target_id": r.target_id,
                    "relation_type": r.relation_type,
                    "strength": r.strength,
                    "confidence": r.confidence,
                    "direction": r.direction,
                    "evidence_ids": list(r.evidence_ids),
                    "temporal_lag": r.temporal_lag,
                    "explanation": r.explanation,
                    "metadata": r.metadata,
                }
                for r in graph.all_relations()
            ],
            "hypotheses": [
                {
                    "hypothesis_id": h.hypothesis_id,
                    "name": h.name,
                    "description": h.description,
                    "cause_node_id": h.cause_node_id,
                    "effect_node_id": h.effect_node_id,
                    "direction": h.direction,
                    "status": h.status,
                    "supporting_evidence_ids": list(h.supporting_evidence_ids),
                    "contradicting_evidence_ids": list(h.contradicting_evidence_ids),
                    "confidence": h.confidence,
                    "created_at": h.created_at,
                    "metadata": h.metadata,
                }
                for h in graph.all_hypotheses()
            ],
            "causal_evidence": [
                {
                    "causal_evidence_id": ce.causal_evidence_id,
                    "hypothesis_id": ce.hypothesis_id,
                    "evidence_id": ce.evidence_id,
                    "role": ce.role,
                    "strength": ce.strength,
                    "explanation": ce.explanation,
                    "metadata": ce.metadata,
                }
                for ce in graph.all_causal_evidence()
            ],
        }
        path.write_text(json.dumps(payload, indent=2))

    def load_graph(self, path: Path) -> CausalGraph:
        payload = json.loads(path.read_text())
        graph = CausalGraph()

        for r in payload.get("relations", []):
            graph.add_relation(CausalRelation(
                relation_id=r["relation_id"],
                source_id=r.get("source_id", ""),
                target_id=r.get("target_id", ""),
                relation_type=r.get("relation_type", "correlation"),
                strength=r.get("strength", 0.0),
                confidence=r.get("confidence", 0.0),
                direction=r.get("direction", "unknown"),
                evidence_ids=tuple(r.get("evidence_ids", [])),
                temporal_lag=r.get("temporal_lag", 0),
                explanation=r.get("explanation", ""),
                metadata=r.get("metadata", {}),
            ))

        for h in payload.get("hypotheses", []):
            graph.add_hypothesis(CausalHypothesis(
                hypothesis_id=h["hypothesis_id"],
                name=h.get("name", ""),
                description=h.get("description", ""),
                cause_node_id=h.get("cause_node_id", ""),
                effect_node_id=h.get("effect_node_id", ""),
                direction=h.get("direction", "cause_to_effect"),
                status=h.get("status", "proposed"),
                supporting_evidence_ids=tuple(h.get("supporting_evidence_ids", [])),
                contradicting_evidence_ids=tuple(h.get("contradicting_evidence_ids", [])),
                confidence=h.get("confidence", 0.0),
                created_at=h.get("created_at", ""),
                metadata=h.get("metadata", {}),
            ))

        for ce in payload.get("causal_evidence", []):
            graph.add_causal_evidence(CausalEvidence(
                causal_evidence_id=ce["causal_evidence_id"],
                hypothesis_id=ce.get("hypothesis_id", ""),
                evidence_id=ce.get("evidence_id", ""),
                role=ce.get("role", "contextual"),
                strength=ce.get("strength", 0.0),
                explanation=ce.get("explanation", ""),
                metadata=ce.get("metadata", {}),
            ))

        return graph
