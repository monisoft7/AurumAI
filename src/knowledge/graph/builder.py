from knowledge.graph.graph import KnowledgeGraph
from knowledge.graph.node import GraphNode
from knowledge.graph.relation import (
    GraphRelation,
    RELATION_SAME_EVENT_TYPE,
    RELATION_SAME_CONDITION,
    RELATION_SAME_HORIZON,
)


class GraphBuilder:
    def build(self, records: list[dict]) -> KnowledgeGraph:
        graph = KnowledgeGraph()
        if not records:
            return graph

        for record in records:
            node = GraphNode(
                node_id=record["knowledge_id"],
                node_type="knowledge_record",
                properties=dict(record),
            )
            graph.add_node(node)

        n = len(records)
        for i in range(n):
            for j in range(i + 1, n):
                a = records[i]
                b = records[j]
                aid = a["knowledge_id"]
                bid = b["knowledge_id"]

                if a.get("event_type") is not None and a.get("event_type") == b.get("event_type"):
                    graph.add_relation(GraphRelation(
                        source_id=aid, target_id=bid,
                        relation_type=RELATION_SAME_EVENT_TYPE,
                    ))

                if a.get("condition") is not None and a.get("condition") == b.get("condition"):
                    graph.add_relation(GraphRelation(
                        source_id=aid, target_id=bid,
                        relation_type=RELATION_SAME_CONDITION,
                    ))

                if a.get("horizon_days") is not None and a.get("horizon_days") == b.get("horizon_days"):
                    graph.add_relation(GraphRelation(
                        source_id=aid, target_id=bid,
                        relation_type=RELATION_SAME_HORIZON,
                    ))

        return graph
