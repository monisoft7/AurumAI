import json
from pathlib import Path

from knowledge._compat import atomic_write_json

from knowledge.graph.graph import KnowledgeGraph
from knowledge.graph.node import GraphNode
from knowledge.graph.relation import GraphRelation


class GraphRepository:
    def save(self, graph: KnowledgeGraph, path: Path) -> None:
        nodes = []
        for node_id, data in graph._graph.nodes(data=True):
            nodes.append({
                "node_id": node_id,
                "node_type": data.get("node_type", ""),
                "properties": data.get("properties", {}),
            })

        relations = []
        for u, v, data in graph._graph.edges(data=True):
            relations.append({
                "source_id": u,
                "target_id": v,
                "relation_type": data.get("relation_type", ""),
                "properties": data.get("properties", {}),
            })

        payload = {"nodes": nodes, "relations": relations}
        atomic_write_json(path, payload)

    def load(self, path: Path) -> KnowledgeGraph:
        payload = json.loads(path.read_text())
        graph = KnowledgeGraph()
        for node_data in payload.get("nodes", []):
            graph.add_node(GraphNode(
                node_id=node_data["node_id"],
                node_type=node_data.get("node_type", ""),
                properties=node_data.get("properties", {}),
            ))
        for rel_data in payload.get("relations", []):
            graph.add_relation(GraphRelation(
                source_id=rel_data["source_id"],
                target_id=rel_data["target_id"],
                relation_type=rel_data.get("relation_type", ""),
                properties=rel_data.get("properties", {}),
            ))
        return graph
