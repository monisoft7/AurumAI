from __future__ import annotations

from typing import Any

from knowledge.evidence.evidence import Evidence
from knowledge.evidence.collection import EvidenceCollection
from knowledge.graph.graph import KnowledgeGraph


class EvidenceQuery:
    def __init__(self, graph: KnowledgeGraph):
        self._graph = graph

    def by_event_type(self, event_type: str) -> EvidenceCollection:
        return self.search(event_type=event_type)

    def by_condition(self, condition: dict[str, str]) -> EvidenceCollection:
        items: list[Evidence] = []
        for node_id in self._graph._graph.nodes:
            node = self._graph.get_node(node_id)
            if node is None:
                continue
            props = node.properties
            node_condition = props.get("condition")
            if isinstance(node_condition, dict) and all(
                node_condition.get(k) == v for k, v in condition.items()
            ):
                evidence = self._node_to_evidence(node)
                if evidence is not None:
                    items.append(evidence)
        return EvidenceCollection(items)

    def by_horizon(self, horizon_days: int) -> EvidenceCollection:
        return self.search(horizon_days=horizon_days)

    def by_node_id(self, node_id: str) -> Evidence | None:
        node = self._graph.get_node(node_id)
        if node is None:
            return None
        return self._node_to_evidence(node)

    def related(
        self, evidence_id: str, relation_type: str | None = None
    ) -> EvidenceCollection:
        node = self._graph.get_node(evidence_id)
        if node is None:
            return EvidenceCollection()
        neighbors = self._graph.get_neighbors(evidence_id, relation_type)
        items: list[Evidence] = []
        for neighbor in neighbors:
            evidence = self._node_to_evidence(neighbor)
            if evidence is not None:
                items.append(evidence)
        return EvidenceCollection(items)

    def all(self) -> EvidenceCollection:
        items: list[Evidence] = []
        for node_id in self._graph._graph.nodes:
            node = self._graph.get_node(node_id)
            if node is None:
                continue
            evidence = self._node_to_evidence(node)
            if evidence is not None:
                items.append(evidence)
        return EvidenceCollection(items)

    def search(self, **kwargs: Any) -> EvidenceCollection:
        items: list[Evidence] = []
        for node_id in self._graph._graph.nodes:
            node = self._graph.get_node(node_id)
            if node is None:
                continue
            props = node.properties
            if all(props.get(k) == v for k, v in kwargs.items()):
                evidence = self._node_to_evidence(node)
                if evidence is not None:
                    items.append(evidence)
        return EvidenceCollection(items)

    def _node_to_evidence(self, node: Any) -> Evidence | None:
        props = node.properties
        evidence_id = props.get("knowledge_id") or node.node_id
        event_type = props.get("event_type", "")
        if not event_type:
            return None
        condition = props.get("condition", {})
        if not isinstance(condition, dict):
            condition = {}
        return Evidence(
            evidence_id=evidence_id,
            source_node_id=node.node_id,
            event_type=event_type,
            condition=condition,
            horizon_days=props.get("horizon_days", 0),
            sample_count=props.get("sample_count", 0),
            average_return_pct=props.get("average_return_pct", 0.0),
            confidence=props.get("confidence", 0.0),
            bias=props.get("bias", ""),
            explanation=props.get("explanation", ""),
            metadata=dict(props),
        )
