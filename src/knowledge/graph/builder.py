from collections import defaultdict
from typing import Any

from knowledge.graph.graph import KnowledgeGraph
from knowledge.graph.node import GraphNode
from knowledge.graph.relation import (
    GraphRelation,
    RELATION_SAME_EVENT_TYPE,
    RELATION_SAME_CONDITION,
    RELATION_SAME_HORIZON,
)
from knowledge.integrity.knowledge_record import KnowledgeRecord


def _as_dict(record: dict[str, Any] | KnowledgeRecord) -> dict[str, Any]:
    if isinstance(record, KnowledgeRecord):
        return record.to_dict()
    return record


def _condition_key(cond: dict[str, Any]) -> tuple[tuple[str, Any], ...]:
    """Convert a condition dict to a hashable, deterministic key."""
    return tuple(sorted(cond.items()))


def _complete_subgraph(
    graph: KnowledgeGraph,
    node_ids: list[str],
    relation_type: str,
) -> None:
    """Add a relation between every unordered pair of node_ids."""
    m = len(node_ids)
    for i in range(m):
        for j in range(i + 1, m):
            graph.add_relation(GraphRelation(
                source_id=node_ids[i], target_id=node_ids[j],
                relation_type=relation_type,
            ))


class GraphBuilder:
    def build(self, records: list[dict[str, Any] | KnowledgeRecord]) -> KnowledgeGraph:
        graph = KnowledgeGraph()
        if not records:
            return graph

        dicts = [_as_dict(r) for r in records]

        # 1. Add all nodes
        for rec in dicts:
            node = GraphNode(
                node_id=rec["knowledge_id"],
                node_type="knowledge_record",
                properties=dict(rec),
            )
            graph.add_node(node)

        # 2. Group by each dimension and build complete subgraphs per group.
        #    This replaces the O(n²) pairwise comparison with O(n) grouping
        #    plus O(k²) per group where k << n in typical data.

        # 2a. Group by event_type
        by_event_type: dict[str, list[str]] = defaultdict(list)
        for rec in dicts:
            et = rec.get("event_type")
            if et is not None:
                by_event_type[et].append(rec["knowledge_id"])
        for group in by_event_type.values():
            _complete_subgraph(graph, group, RELATION_SAME_EVENT_TYPE)

        # 2b. Group by condition (dict → hashable tuple key)
        by_condition: dict[tuple[tuple[str, Any], ...], list[str]] = defaultdict(list)
        for rec in dicts:
            cond = rec.get("condition")
            if cond is not None:
                by_condition[_condition_key(cond)].append(rec["knowledge_id"])
        for group in by_condition.values():
            _complete_subgraph(graph, group, RELATION_SAME_CONDITION)

        # 2c. Group by horizon_days
        by_horizon: dict[str | int, list[str]] = defaultdict(list)
        for rec in dicts:
            hd = rec.get("horizon_days")
            if hd is not None:
                by_horizon[hd].append(rec["knowledge_id"])
        for group in by_horizon.values():
            _complete_subgraph(graph, group, RELATION_SAME_HORIZON)

        return graph
