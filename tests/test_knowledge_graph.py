import json
from pathlib import Path

import pytest

from knowledge.graph.node import GraphNode
from knowledge.graph.relation import (
    GraphRelation,
    RELATION_SAME_EVENT_TYPE,
    RELATION_SAME_CONDITION,
    RELATION_SAME_HORIZON,
)
from knowledge.graph.graph import KnowledgeGraph
from knowledge.graph.builder import GraphBuilder
from knowledge.graph.repository import GraphRepository


# ── GraphNode ──────────────────────────────────────────────────────────────

def test_graph_node_creation() -> None:
    node = GraphNode(node_id="n1", node_type="knowledge_record", properties={"a": 1})
    assert node.node_id == "n1"
    assert node.node_type == "knowledge_record"
    assert node.properties == {"a": 1}


def test_graph_node_frozen() -> None:
    node = GraphNode(node_id="n1", node_type="t")
    with pytest.raises(Exception):
        node.node_id = "n2"  # type: ignore[misc]


def test_graph_node_default_properties() -> None:
    node = GraphNode(node_id="n1", node_type="t")
    assert node.properties == {}


# ── GraphRelation ──────────────────────────────────────────────────────────

def test_graph_relation_creation() -> None:
    rel = GraphRelation(source_id="a", target_id="b", relation_type="same_x")
    assert rel.source_id == "a"
    assert rel.target_id == "b"
    assert rel.relation_type == "same_x"


def test_graph_relation_constants() -> None:
    assert RELATION_SAME_EVENT_TYPE == "same_event_type"
    assert RELATION_SAME_CONDITION == "same_condition"
    assert RELATION_SAME_HORIZON == "same_horizon"


# ── KnowledgeGraph ─────────────────────────────────────────────────────────

def test_empty_graph() -> None:
    g = KnowledgeGraph()
    assert g.node_count == 0
    assert g.relation_count == 0


def test_add_and_get_node() -> None:
    g = KnowledgeGraph()
    node = GraphNode(node_id="a", node_type="t", properties={"k": "v"})
    g.add_node(node)
    assert g.node_count == 1
    assert g.has_node("a")
    retrieved = g.get_node("a")
    assert retrieved is not None
    assert retrieved.node_id == "a"
    assert retrieved.node_type == "t"
    assert retrieved.properties == {"k": "v"}


def test_get_node_missing() -> None:
    g = KnowledgeGraph()
    assert g.get_node("nonexistent") is None


def test_get_neighbors_missing_node() -> None:
    g = KnowledgeGraph()
    assert g.get_neighbors("nonexistent") == []


def test_add_relation_and_count() -> None:
    g = KnowledgeGraph()
    g.add_node(GraphNode(node_id="a", node_type="t"))
    g.add_node(GraphNode(node_id="b", node_type="t"))
    g.add_relation(GraphRelation(source_id="a", target_id="b", relation_type="same_x"))
    assert g.relation_count == 1


def test_get_neighbors_symmetric() -> None:
    g = KnowledgeGraph()
    g.add_node(GraphNode(node_id="a", node_type="t"))
    g.add_node(GraphNode(node_id="b", node_type="t"))
    g.add_relation(GraphRelation(source_id="a", target_id="b", relation_type="same_x"))
    neighbors_of_a = g.get_neighbors("a")
    neighbors_of_b = g.get_neighbors("b")
    assert len(neighbors_of_a) == 1
    assert neighbors_of_a[0].node_id == "b"
    assert len(neighbors_of_b) == 1
    assert neighbors_of_b[0].node_id == "a"


def test_get_neighbors_filtered_by_type() -> None:
    g = KnowledgeGraph()
    g.add_node(GraphNode(node_id="a", node_type="t"))
    g.add_node(GraphNode(node_id="b", node_type="t"))
    g.add_node(GraphNode(node_id="c", node_type="t"))
    g.add_relation(GraphRelation(source_id="a", target_id="b", relation_type="same_x"))
    g.add_relation(GraphRelation(source_id="a", target_id="c", relation_type="same_y"))
    assert len(g.get_neighbors("a", "same_x")) == 1
    assert g.get_neighbors("a", "same_x")[0].node_id == "b"
    assert len(g.get_neighbors("a", "same_y")) == 1
    assert g.get_neighbors("a", "same_y")[0].node_id == "c"
    assert len(g.get_neighbors("a", "nonexistent")) == 0


def test_get_relations_all() -> None:
    g = KnowledgeGraph()
    g.add_node(GraphNode(node_id="a", node_type="t"))
    g.add_node(GraphNode(node_id="b", node_type="t"))
    g.add_node(GraphNode(node_id="c", node_type="t"))
    g.add_relation(GraphRelation(source_id="a", target_id="b", relation_type="same_x"))
    g.add_relation(GraphRelation(source_id="b", target_id="c", relation_type="same_y"))
    rels = g.get_relations()
    assert len(rels) == 2


def test_get_relations_filtered() -> None:
    g = KnowledgeGraph()
    g.add_node(GraphNode(node_id="a", node_type="t"))
    g.add_node(GraphNode(node_id="b", node_type="t"))
    g.add_node(GraphNode(node_id="c", node_type="t"))
    g.add_relation(GraphRelation(source_id="a", target_id="b", relation_type="same_x"))
    g.add_relation(GraphRelation(source_id="a", target_id="c", relation_type="same_x"))
    rels = g.get_relations(source_id="a", relation_type="same_x")
    assert len(rels) == 2
    rels = g.get_relations(target_id="b")
    assert len(rels) == 1
    assert rels[0].source_id == "a"
    assert rels[0].target_id == "b"


# ── GraphBuilder ───────────────────────────────────────────────────────────

def test_builder_empty_records() -> None:
    graph = GraphBuilder().build([])
    assert graph.node_count == 0
    assert graph.relation_count == 0


def test_builder_single_record_no_edges() -> None:
    records = [
        {
            "knowledge_id": "CPI_GOLD_inflation_pressure_up_20D",
            "event_type": "CPI",
            "asset": "GOLD",
            "condition": {"cpi_pressure": "inflation_pressure_up"},
            "horizon_days": 20,
        },
    ]
    graph = GraphBuilder().build(records)
    assert graph.node_count == 1
    assert graph.relation_count == 0


def test_builder_creates_same_event_type_edges() -> None:
    records = [
        {
            "knowledge_id": "id1",
            "event_type": "CPI",
            "condition": {"cpi_pressure": "up"},
            "horizon_days": 5,
        },
        {
            "knowledge_id": "id2",
            "event_type": "CPI",
            "condition": {"cpi_pressure": "down"},
            "horizon_days": 20,
        },
    ]
    graph = GraphBuilder().build(records)
    assert graph.node_count == 2
    rels = graph.get_relations(relation_type=RELATION_SAME_EVENT_TYPE)
    assert len(rels) == 1
    assert rels[0].source_id == "id1"
    assert rels[0].target_id == "id2"


def test_builder_creates_same_condition_edges() -> None:
    records = [
        {
            "knowledge_id": "id1",
            "event_type": "CPI",
            "condition": {"cpi_pressure": "up"},
            "horizon_days": 5,
        },
        {
            "knowledge_id": "id2",
            "event_type": "CPI",
            "condition": {"cpi_pressure": "up"},
            "horizon_days": 20,
        },
    ]
    graph = GraphBuilder().build(records)
    rels = graph.get_relations(relation_type=RELATION_SAME_CONDITION)
    assert len(rels) == 1
    assert rels[0].source_id == "id1"
    assert rels[0].target_id == "id2"


def test_builder_creates_same_horizon_edges() -> None:
    records = [
        {
            "knowledge_id": "id1",
            "event_type": "CPI",
            "condition": {"cpi_pressure": "up"},
            "horizon_days": 20,
        },
        {
            "knowledge_id": "id2",
            "event_type": "NFP",
            "condition": {"nfp_surprise": "positive"},
            "horizon_days": 20,
        },
    ]
    graph = GraphBuilder().build(records)
    rels = graph.get_relations(relation_type=RELATION_SAME_HORIZON)
    assert len(rels) == 1
    assert rels[0].source_id == "id1"
    assert rels[0].target_id == "id2"


def test_builder_multiple_edges_between_same_pair() -> None:
    records = [
        {
            "knowledge_id": "id1",
            "event_type": "CPI",
            "condition": {"x": "a"},
            "horizon_days": 5,
        },
        {
            "knowledge_id": "id2",
            "event_type": "CPI",
            "condition": {"x": "a"},
            "horizon_days": 5,
        },
    ]
    graph = GraphBuilder().build(records)
    # Shares all three dimensions: same_event_type, same_condition, same_horizon
    assert graph.relation_count == 3


def test_builder_with_real_knowledge_records() -> None:
    records = [
        {
            "knowledge_id": "CPI_GOLD_inflation_pressure_up_5D",
            "event_type": "CPI",
            "asset": "GOLD",
            "condition": {"cpi_pressure": "inflation_pressure_up"},
            "horizon_days": 5,
            "sample_count": 10,
        },
        {
            "knowledge_id": "CPI_GOLD_inflation_pressure_up_20D",
            "event_type": "CPI",
            "asset": "GOLD",
            "condition": {"cpi_pressure": "inflation_pressure_up"},
            "horizon_days": 20,
            "sample_count": 10,
        },
        {
            "knowledge_id": "CPI_GOLD_inflation_pressure_down_5D",
            "event_type": "CPI",
            "asset": "GOLD",
            "condition": {"cpi_pressure": "inflation_pressure_down"},
            "horizon_days": 5,
            "sample_count": 8,
        },
    ]
    graph = GraphBuilder().build(records)
    assert graph.node_count == 3
    # id1↔id2: same_event_type + same_condition       → 2 edges
    # id1↔id3: same_event_type + same_horizon (both 5D) → 2 edges
    # id2↔id3: same_event_type                         → 1 edge
    assert graph.relation_count == 5

    # Check node properties are preserved
    node = graph.get_node("CPI_GOLD_inflation_pressure_up_5D")
    assert node is not None
    assert node.properties["sample_count"] == 10
    assert node.node_type == "knowledge_record"

    # Check neighbors from up_5D
    neighbors = graph.get_neighbors("CPI_GOLD_inflation_pressure_up_5D")
    assert {n.node_id for n in neighbors} == {
        "CPI_GOLD_inflation_pressure_up_20D",
        "CPI_GOLD_inflation_pressure_down_5D",
    }

    # Filter neighbors by condition
    cond_neighbors = graph.get_neighbors(
        "CPI_GOLD_inflation_pressure_up_5D", RELATION_SAME_CONDITION
    )
    assert len(cond_neighbors) == 1
    assert cond_neighbors[0].node_id == "CPI_GOLD_inflation_pressure_up_20D"


# ── GraphRepository ────────────────────────────────────────────────────────

def test_repository_save_and_load_round_trip(tmp_path: Path) -> None:
    graph = KnowledgeGraph()
    graph.add_node(GraphNode(node_id="a", node_type="t", properties={"v": 1}))
    graph.add_node(GraphNode(node_id="b", node_type="t", properties={"v": 2}))
    graph.add_relation(GraphRelation(source_id="a", target_id="b", relation_type="same_x"))

    path = tmp_path / "graph.json"
    repo = GraphRepository()
    repo.save(graph, path)

    assert path.exists()
    loaded = repo.load(path)
    assert loaded.node_count == 2
    assert loaded.relation_count == 1
    assert loaded.has_node("a")
    assert loaded.has_node("b")
    node_a = loaded.get_node("a")
    assert node_a is not None
    assert node_a.properties["v"] == 1
    rels = loaded.get_relations()
    assert len(rels) == 1
    assert rels[0].relation_type == "same_x"


def test_repository_save_empty_graph(tmp_path: Path) -> None:
    graph = KnowledgeGraph()
    path = tmp_path / "empty.json"
    GraphRepository().save(graph, path)
    loaded = GraphRepository().load(path)
    assert loaded.node_count == 0
    assert loaded.relation_count == 0


def test_repository_round_trip_preserves_properties(tmp_path: Path) -> None:
    graph = KnowledgeGraph()
    graph.add_node(GraphNode(
        node_id="rec1", node_type="knowledge_record",
        properties={"sample_count": 42, "bias": "gold_positive_bias"},
    ))
    graph.add_relation(GraphRelation(
        source_id="rec1", target_id="rec2",
        relation_type="same_event_type",
        properties={"weight": 1.0},
    ))

    path = tmp_path / "props.json"
    GraphRepository().save(graph, path)
    loaded = GraphRepository().load(path)

    node = loaded.get_node("rec1")
    assert node is not None
    assert node.properties["sample_count"] == 42
    assert node.properties["bias"] == "gold_positive_bias"

    rels = loaded.get_relations()
    assert len(rels) == 1
    assert rels[0].properties["weight"] == 1.0
