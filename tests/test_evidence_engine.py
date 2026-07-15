import json
from pathlib import Path

import pytest

from knowledge.graph.graph import KnowledgeGraph
from knowledge.graph.node import GraphNode
from knowledge.graph.relation import GraphRelation
from knowledge.graph.builder import GraphBuilder
from knowledge.evidence.evidence import Evidence
from knowledge.evidence.collection import EvidenceCollection
from knowledge.evidence.query import EvidenceQuery
from knowledge.evidence.ranker import EvidenceRanker
from knowledge.evidence.repository import EvidenceRepository


# ── Fixtures ────────────────────────────────────────────────────────────────

def make_graph() -> KnowledgeGraph:
    records = [
        {
            "knowledge_id": "CPI_GOLD_inflation_pressure_up_5D",
            "event_type": "CPI",
            "asset": "GOLD",
            "condition": {"cpi_pressure": "inflation_pressure_up"},
            "horizon_days": 5,
            "sample_count": 50,
            "average_return_pct": 1.5,
            "confidence": 0.85,
            "bias": "gold_positive_bias",
            "explanation": "CPI up → gold up over 5 days.",
        },
        {
            "knowledge_id": "CPI_GOLD_inflation_pressure_up_20D",
            "event_type": "CPI",
            "asset": "GOLD",
            "condition": {"cpi_pressure": "inflation_pressure_up"},
            "horizon_days": 20,
            "sample_count": 50,
            "average_return_pct": 2.0,
            "confidence": 0.75,
            "bias": "gold_positive_bias",
            "explanation": "CPI up → gold up over 20 days.",
        },
        {
            "knowledge_id": "CPI_GOLD_inflation_pressure_down_5D",
            "event_type": "CPI",
            "asset": "GOLD",
            "condition": {"cpi_pressure": "inflation_pressure_down"},
            "horizon_days": 5,
            "sample_count": 30,
            "average_return_pct": -1.2,
            "confidence": 0.60,
            "bias": "gold_negative_bias",
            "explanation": "CPI down → gold down over 5 days.",
        },
        {
            "knowledge_id": "NFP_GOLD_surprise_positive_5D",
            "event_type": "NFP",
            "asset": "GOLD",
            "condition": {"nfp_surprise": "positive"},
            "horizon_days": 5,
            "sample_count": 20,
            "average_return_pct": 0.8,
            "confidence": 0.45,
            "bias": "mixed_or_context_dependent",
            "explanation": "NFP positive surprise → gold mixed.",
        },
    ]
    return GraphBuilder().build(records)


# ── Evidence ────────────────────────────────────────────────────────────────

def test_evidence_creation() -> None:
    ev = Evidence(
        evidence_id="e1",
        source_node_id="n1",
        event_type="CPI",
        condition={"cpi_pressure": "up"},
        horizon_days=5,
        sample_count=50,
        average_return_pct=1.5,
        confidence=0.85,
        bias="gold_positive_bias",
        explanation="CPI up → gold up.",
        metadata={"extra": "value"},
    )
    assert ev.evidence_id == "e1"
    assert ev.event_type == "CPI"
    assert ev.confidence == 0.85
    assert ev.metadata["extra"] == "value"


def test_evidence_default_metadata() -> None:
    ev = Evidence(
        evidence_id="e1",
        source_node_id="n1",
        event_type="CPI",
        condition={},
        horizon_days=0,
        sample_count=0,
        average_return_pct=0.0,
        confidence=0.0,
        bias="",
        explanation="",
    )
    assert ev.metadata == {}


# ── EvidenceCollection ─────────────────────────────────────────────────────

def test_collection_empty() -> None:
    col = EvidenceCollection()
    assert len(col) == 0


def test_collection_len_and_iter() -> None:
    ev = Evidence(
        evidence_id="e1", source_node_id="n1", event_type="CPI",
        condition={}, horizon_days=0, sample_count=0,
        average_return_pct=0.0, confidence=0.0, bias="", explanation="",
    )
    col = EvidenceCollection([ev])
    assert len(col) == 1
    assert list(col) == [ev]


def test_collection_getitem() -> None:
    ev1 = Evidence(
        evidence_id="e1", source_node_id="n1", event_type="CPI",
        condition={}, horizon_days=0, sample_count=0,
        average_return_pct=0.0, confidence=0.0, bias="", explanation="",
    )
    ev2 = Evidence(
        evidence_id="e2", source_node_id="n2", event_type="NFP",
        condition={}, horizon_days=0, sample_count=0,
        average_return_pct=0.0, confidence=0.0, bias="", explanation="",
    )
    col = EvidenceCollection([ev1, ev2])
    assert col[0].evidence_id == "e1"
    assert col[1].evidence_id == "e2"


def test_collection_filter() -> None:
    graph = make_graph()
    query = EvidenceQuery(graph)
    col = query.all()
    filtered = col.filter(event_type="CPI")
    assert len(filtered) == 3
    for ev in filtered:
        assert ev.event_type == "CPI"


def test_collection_filter_no_match() -> None:
    graph = make_graph()
    col = EvidenceQuery(graph).all()
    filtered = col.filter(event_type="GDP")
    assert len(filtered) == 0


def test_collection_top() -> None:
    graph = make_graph()
    col = EvidenceQuery(graph).all()
    assert len(col) == 4
    assert len(col.top(2)) == 2
    assert len(col.top(0)) == 0
    assert len(col.top(100)) == 4


def test_collection_aggregate() -> None:
    graph = make_graph()
    col = EvidenceQuery(graph).all()
    agg = col.aggregate()
    assert agg["count"] == 4
    assert 0.0 < agg["avg_confidence"] < 1.0
    assert agg["avg_sample_count"] > 0


def test_collection_aggregate_empty() -> None:
    col = EvidenceCollection()
    agg = col.aggregate()
    assert agg["count"] == 0
    assert agg["avg_confidence"] == 0.0


# ── EvidenceQuery ──────────────────────────────────────────────────────────

def test_query_by_event_type() -> None:
    graph = make_graph()
    col = EvidenceQuery(graph).by_event_type("CPI")
    assert len(col) == 3
    for ev in col:
        assert ev.event_type == "CPI"


def test_query_by_event_type_no_match() -> None:
    graph = make_graph()
    col = EvidenceQuery(graph).by_event_type("GDP")
    assert len(col) == 0


def test_query_by_condition() -> None:
    graph = make_graph()
    col = EvidenceQuery(graph).by_condition({"cpi_pressure": "inflation_pressure_up"})
    assert len(col) == 2
    for ev in col:
        assert ev.condition == {"cpi_pressure": "inflation_pressure_up"}


def test_query_by_horizon() -> None:
    graph = make_graph()
    col = EvidenceQuery(graph).by_horizon(5)
    assert len(col) == 3
    for ev in col:
        assert ev.horizon_days == 5


def test_query_by_node_id() -> None:
    graph = make_graph()
    ev = EvidenceQuery(graph).by_node_id("CPI_GOLD_inflation_pressure_up_5D")
    assert ev is not None
    assert ev.event_type == "CPI"
    assert ev.horizon_days == 5
    assert ev.sample_count == 50


def test_query_by_node_id_missing() -> None:
    graph = make_graph()
    ev = EvidenceQuery(graph).by_node_id("nonexistent")
    assert ev is None


def test_query_related() -> None:
    graph = make_graph()
    col = EvidenceQuery(graph).related("CPI_GOLD_inflation_pressure_up_5D")
    # Connected to up_20D, down_5D (via event_type), plus NFP_5D (via horizon)
    assert len(col) == 3
    ids = {ev.evidence_id for ev in col}
    assert "CPI_GOLD_inflation_pressure_up_20D" in ids
    assert "CPI_GOLD_inflation_pressure_down_5D" in ids
    assert "NFP_GOLD_surprise_positive_5D" in ids


def test_query_related_filtered_by_type() -> None:
    graph = make_graph()
    col = EvidenceQuery(graph).related(
        "CPI_GOLD_inflation_pressure_up_5D",
        relation_type="same_condition",
    )
    assert len(col) == 1
    assert col[0].evidence_id == "CPI_GOLD_inflation_pressure_up_20D"


def test_query_related_missing_node() -> None:
    graph = make_graph()
    col = EvidenceQuery(graph).related("nonexistent")
    assert len(col) == 0


def test_query_all() -> None:
    graph = make_graph()
    col = EvidenceQuery(graph).all()
    assert len(col) == 4


def test_query_search() -> None:
    graph = make_graph()
    col = EvidenceQuery(graph).search(event_type="NFP", horizon_days=5)
    assert len(col) == 1
    assert col[0].evidence_id == "NFP_GOLD_surprise_positive_5D"


def test_query_empty_graph() -> None:
    graph = KnowledgeGraph()
    col = EvidenceQuery(graph).all()
    assert len(col) == 0
    assert EvidenceQuery(graph).by_event_type("CPI") is not None
    assert len(EvidenceQuery(graph).by_event_type("CPI")) == 0


def test_query_skips_nodes_without_event_type() -> None:
    graph = KnowledgeGraph()
    graph.add_node(GraphNode(node_id="n1", node_type="other", properties={"foo": "bar"}))
    col = EvidenceQuery(graph).all()
    assert len(col) == 0


# ── EvidenceRanker ─────────────────────────────────────────────────────────

def test_ranker_by_confidence() -> None:
    graph = make_graph()
    col = EvidenceQuery(graph).all()
    ranked = EvidenceRanker.by_confidence(col)
    assert len(ranked) == 4
    confidences = [e.confidence for e in ranked]
    assert confidences == sorted(confidences, reverse=True)


def test_ranker_by_confidence_ascending() -> None:
    graph = make_graph()
    col = EvidenceQuery(graph).all()
    ranked = EvidenceRanker.by_confidence(col, reverse=False)
    confidences = [e.confidence for e in ranked]
    assert confidences == sorted(confidences)


def test_ranker_by_sample_count() -> None:
    graph = make_graph()
    col = EvidenceQuery(graph).all()
    ranked = EvidenceRanker.by_sample_count(col)
    counts = [e.sample_count for e in ranked]
    assert counts == sorted(counts, reverse=True)


def test_ranker_by_return_magnitude() -> None:
    graph = make_graph()
    col = EvidenceQuery(graph).all()
    ranked = EvidenceRanker.by_return_magnitude(col)
    mags = [abs(e.average_return_pct) for e in ranked]
    assert mags == sorted(mags, reverse=True)


def test_ranker_combined() -> None:
    graph = make_graph()
    col = EvidenceQuery(graph).all()
    ranked = EvidenceRanker.combined(col)
    assert len(ranked) == 4
    # up_20D wins: highest return magnitude (2.0) offsets slightly lower confidence
    assert ranked[0].evidence_id == "CPI_GOLD_inflation_pressure_up_20D"


def test_ranker_empty() -> None:
    col = EvidenceCollection()
    ranked = EvidenceRanker.by_confidence(col)
    assert len(ranked) == 0
    ranked = EvidenceRanker.combined(col)
    assert len(ranked) == 0


def test_ranker_single_item() -> None:
    graph = make_graph()
    col = EvidenceQuery(graph).by_node_id("CPI_GOLD_inflation_pressure_up_5D")
    assert col is not None
    ranked = EvidenceRanker.by_confidence(EvidenceCollection([col]))
    assert len(ranked) == 1
    assert ranked[0].evidence_id == "CPI_GOLD_inflation_pressure_up_5D"


# ── EvidenceRepository ─────────────────────────────────────────────────────

def test_repository_save_and_load_round_trip(tmp_path: Path) -> None:
    graph = make_graph()
    col = EvidenceQuery(graph).all()
    path = tmp_path / "evidence.json"
    EvidenceRepository().save(col, path)
    assert path.exists()

    loaded = EvidenceRepository().load(path)
    assert len(loaded) == 4
    assert loaded[0].evidence_id == col[0].evidence_id
    assert loaded[0].confidence == col[0].confidence
    assert loaded[0].explanation == col[0].explanation


def test_repository_save_empty(tmp_path: Path) -> None:
    col = EvidenceCollection()
    path = tmp_path / "empty.json"
    EvidenceRepository().save(col, path)
    loaded = EvidenceRepository().load(path)
    assert len(loaded) == 0


def test_repository_preserves_metadata(tmp_path: Path) -> None:
    graph = make_graph()
    ev = EvidenceQuery(graph).by_node_id("CPI_GOLD_inflation_pressure_up_5D")
    assert ev is not None
    col = EvidenceCollection([ev])
    path = tmp_path / "meta.json"
    EvidenceRepository().save(col, path)

    loaded = EvidenceRepository().load(path)
    assert len(loaded) == 1
    assert loaded[0].metadata["asset"] == "GOLD"
    assert loaded[0].metadata["bias"] == "gold_positive_bias"


def test_repository_file_format(tmp_path: Path) -> None:
    graph = make_graph()
    col = EvidenceQuery(graph).all()
    path = tmp_path / "format.json"
    EvidenceRepository().save(col, path)

    raw = json.loads(path.read_text())
    assert "evidence_count" in raw
    assert raw["evidence_count"] == 4
    assert len(raw["items"]) == 4
    assert "evidence_id" in raw["items"][0]
    assert "metadata" in raw["items"][0]
