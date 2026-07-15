import networkx as nx

from knowledge.graph.node import GraphNode
from knowledge.graph.relation import GraphRelation


class KnowledgeGraph:
    def __init__(self) -> None:
        self._graph = nx.MultiDiGraph()

    def add_node(self, node: GraphNode) -> None:
        self._graph.add_node(
            node.node_id, node_type=node.node_type, properties=node.properties
        )

    def add_relation(self, relation: GraphRelation) -> None:
        self._graph.add_edge(
            relation.source_id,
            relation.target_id,
            relation_type=relation.relation_type,
            properties=relation.properties,
        )

    def get_node(self, node_id: str) -> GraphNode | None:
        if node_id not in self._graph:
            return None
        data = self._graph.nodes[node_id]
        return GraphNode(
            node_id=node_id,
            node_type=data.get("node_type", ""),
            properties=data.get("properties", {}),
        )

    def get_neighbors(
        self, node_id: str, relation_type: str | None = None
    ) -> list[GraphNode]:
        if node_id not in self._graph:
            return []
        neighbors: list[GraphNode] = []
        seen: set[str] = set()
        for neighbor_id in self._graph.successors(node_id):
            if neighbor_id in seen:
                continue
            seen.add(neighbor_id)
            if relation_type:
                if self._has_relation(node_id, neighbor_id, relation_type):
                    neighbors.append(self.get_node(neighbor_id))
            else:
                neighbors.append(self.get_node(neighbor_id))
        for neighbor_id in self._graph.predecessors(node_id):
            if neighbor_id in seen:
                continue
            seen.add(neighbor_id)
            if relation_type:
                if self._has_relation(neighbor_id, node_id, relation_type):
                    neighbors.append(self.get_node(neighbor_id))
            else:
                neighbors.append(self.get_node(neighbor_id))
        return neighbors

    def _has_relation(self, u: str, v: str, relation_type: str) -> bool:
        edge_data = self._graph.get_edge_data(u, v)
        if edge_data is None:
            return False
        return any(
            data.get("relation_type") == relation_type
            for data in edge_data.values()
        )
        return neighbors

    def get_relations(
        self,
        source_id: str | None = None,
        target_id: str | None = None,
        relation_type: str | None = None,
    ) -> list[GraphRelation]:
        results: list[GraphRelation] = []
        for u, v, data in self._graph.edges(data=True):
            if source_id is not None and u != source_id:
                continue
            if target_id is not None and v != target_id:
                continue
            if relation_type is not None and data.get("relation_type") != relation_type:
                continue
            results.append(
                GraphRelation(
                    source_id=u,
                    target_id=v,
                    relation_type=data.get("relation_type", ""),
                    properties=data.get("properties", {}),
                )
            )
        return results

    def has_node(self, node_id: str) -> bool:
        return self._graph.has_node(node_id)

    @property
    def node_count(self) -> int:
        return int(self._graph.number_of_nodes())

    @property
    def relation_count(self) -> int:
        return int(self._graph.number_of_edges())
