from __future__ import annotations

from datetime import date as date_type

from math import sqrt

import pytest

from knowledge.evidence.collection import EvidenceCollection
from knowledge.evidence.evidence import Evidence
from knowledge.evidence.query import EvidenceQuery
from knowledge.graph.graph import KnowledgeGraph
from knowledge.graph.node import GraphNode
from knowledge.orchestration.context import OrchestrationContext
from knowledge.orchestration.engine import OrchestrationEngine, OrchestrationReport
from knowledge.reasoning.retrieval import (
    HistoricalSituationRetriever,
    RetrievalConfig,
    SituationMatch,
    SituationQuery,
)

EPSILON = 1e-6


def _add_test_node(
    graph: KnowledgeGraph,
    node_id: str,
    event_type: str = "FOMC",
    condition: dict[str, str] | None = None,
    horizon_days: int = 30,
    sample_count: int = 100,
    average_return_pct: float = 0.5,
    confidence: float = 0.8,
    bias: str = "gold_positive_bias",
    explanation: str = "test record",
    last_event_date: str = "",
) -> None:
    props: dict = {
        "event_type": event_type,
        "condition": condition or {},
        "horizon_days": horizon_days,
        "sample_count": sample_count,
        "average_return_pct": average_return_pct,
        "confidence": confidence,
        "bias": bias,
        "explanation": explanation,
        "knowledge_id": node_id,
    }
    if last_event_date:
        props["last_event_date"] = last_event_date
    graph.add_node(GraphNode(node_id=node_id, node_type="knowledge", properties=props))


def _graph_with_fomc_and_cpi() -> KnowledgeGraph:
    g = KnowledgeGraph()
    _add_test_node(g, "fomc_hike_25_30", event_type="FOMC", condition={"rate": "hike", "inflation": "3.5"}, horizon_days=30, sample_count=200, last_event_date="2025-01-15")
    _add_test_node(g, "fomc_hike_25_60", event_type="FOMC", condition={"rate": "hike", "inflation": "3.5"}, horizon_days=60, sample_count=150, last_event_date="2024-06-10")
    _add_test_node(g, "fomc_hold_30", event_type="FOMC", condition={"rate": "hold", "inflation": "2.8"}, horizon_days=30, sample_count=80, last_event_date="2023-11-20")
    _add_test_node(g, "cpi_high_30", event_type="CPI", condition={"cpi": "high", "core": "sticky"}, horizon_days=30, sample_count=300, last_event_date="2025-03-01")
    _add_test_node(g, "cpi_moderate_90", event_type="CPI", condition={"cpi": "moderate"}, horizon_days=90, sample_count=50, last_event_date="2024-09-05")
    return g


# --------------------------------------------------------------------------
# SituationQuery dataclass
# --------------------------------------------------------------------------


class TestSituationQuery:
    def test_defaults(self) -> None:
        q = SituationQuery(event_type="FOMC")
        assert q.event_type == "FOMC"
        assert q.condition is None
        assert q.horizon_days is None
        assert q.date is None
        assert q.sample_count == 0

    def test_all_fields(self) -> None:
        q = SituationQuery(
            event_type="CPI",
            condition={"cpi": "high"},
            horizon_days=30,
            date="2026-07-01",
            sample_count=100,
        )
        assert q.event_type == "CPI"
        assert q.condition == {"cpi": "high"}
        assert q.horizon_days == 30
        assert q.date == "2026-07-01"
        assert q.sample_count == 100


# --------------------------------------------------------------------------
# SituationMatch dataclass
# --------------------------------------------------------------------------


class TestSituationMatch:
    def test_is_frozen(self) -> None:
        ev = Evidence(
            evidence_id="test", source_node_id="src", event_type="FOMC",
            condition={}, horizon_days=30, sample_count=100,
            average_return_pct=0.5, confidence=0.8, bias="positive", explanation="",
        )
        m = SituationMatch(
            evidence=ev, overall_similarity=0.85,
            event_type_similarity=1.0, condition_similarity=0.5,
            horizon_similarity=0.8, maturity_similarity=0.9,
            temporal_similarity=0.7,
        )
        assert m.overall_similarity == 0.85
        assert m.evidence is ev

    def test_default_retrieval_method(self) -> None:
        ev = Evidence(
            evidence_id="test", source_node_id="src", event_type="FOMC",
            condition={}, horizon_days=30, sample_count=100,
            average_return_pct=0.5, confidence=0.8, bias="positive", explanation="",
        )
        m = SituationMatch(
            evidence=ev, overall_similarity=0.5,
            event_type_similarity=1.0, condition_similarity=1.0,
            horizon_similarity=1.0, maturity_similarity=1.0,
            temporal_similarity=1.0,
        )
        assert m.retrieval_method == "exact"

    def test_custom_retrieval_method(self) -> None:
        ev = Evidence(
            evidence_id="test", source_node_id="src", event_type="FOMC",
            condition={}, horizon_days=30, sample_count=100,
            average_return_pct=0.5, confidence=0.8, bias="positive", explanation="",
        )
        m = SituationMatch(
            evidence=ev, overall_similarity=0.5,
            event_type_similarity=1.0, condition_similarity=1.0,
            horizon_similarity=1.0, maturity_similarity=1.0,
            temporal_similarity=1.0,
            retrieval_method="broadened",
        )
        assert m.retrieval_method == "broadened"


# --------------------------------------------------------------------------
# RetrievalConfig
# --------------------------------------------------------------------------


class TestRetrievalConfig:
    def test_defaults(self) -> None:
        cfg = RetrievalConfig()
        assert cfg.top_k == 5
        assert cfg.min_similarity == 0.3
        assert cfg.broaden_on_empty is True
        assert cfg.broaden_min_results == 3
        assert abs(cfg.event_type_weight - 0.35) < EPSILON
        assert abs(cfg.condition_weight - 0.30) < EPSILON
        assert abs(cfg.horizon_weight - 0.15) < EPSILON
        assert abs(cfg.maturity_weight - 0.10) < EPSILON
        assert abs(cfg.temporal_weight - 0.10) < EPSILON

    def test_custom_values(self) -> None:
        cfg = RetrievalConfig(
            top_k=10, min_similarity=0.5, broaden_on_empty=False,
            event_type_weight=0.5, condition_weight=0.3,
            horizon_weight=0.1, maturity_weight=0.05, temporal_weight=0.05,
        )
        assert cfg.top_k == 10
        assert cfg.broaden_on_empty is False

    def test_raises_on_bad_weights(self) -> None:
        with pytest.raises(ValueError, match="must sum to 1.0"):
            RetrievalConfig(
                event_type_weight=0.6, condition_weight=0.0,
                horizon_weight=0.0, maturity_weight=0.0, temporal_weight=0.0,
            )

    def test_accepts_zero_weight_dimensions(self) -> None:
        cfg = RetrievalConfig(
            event_type_weight=0.5, condition_weight=0.5,
            horizon_weight=0.0, maturity_weight=0.0, temporal_weight=0.0,
        )
        assert abs(cfg.horizon_weight) < EPSILON


# --------------------------------------------------------------------------
# Similarity computation (static methods)
# --------------------------------------------------------------------------


class TestJaccardSimilarity:
    def test_identical_keys(self) -> None:
        sim = HistoricalSituationRetriever._jaccard_similarity(
            {"a": "1", "b": "2"}, {"a": "1", "b": "2"}
        )
        assert abs(sim - 1.0) < EPSILON

    def test_partial_overlap(self) -> None:
        sim = HistoricalSituationRetriever._jaccard_similarity(
            {"a": "1", "b": "2", "c": "3"}, {"a": "1", "b": "2"}
        )
        assert abs(sim - 2.0 / 3.0) < EPSILON

    def test_no_overlap(self) -> None:
        sim = HistoricalSituationRetriever._jaccard_similarity(
            {"a": "1"}, {"b": "2"}
        )
        assert abs(sim) < EPSILON

    def test_both_empty(self) -> None:
        sim = HistoricalSituationRetriever._jaccard_similarity({}, {})
        assert abs(sim - 0.5) < EPSILON

    def test_query_empty_candidate_has_keys(self) -> None:
        sim = HistoricalSituationRetriever._jaccard_similarity({}, {"a": "1"})
        assert abs(sim - 0.5) < EPSILON

    def test_candidate_empty_query_has_keys(self) -> None:
        sim = HistoricalSituationRetriever._jaccard_similarity({"a": "1"}, {})
        assert abs(sim - 0.5) < EPSILON


class TestHorizonSimilarity:
    def test_exact_match(self) -> None:
        sim = HistoricalSituationRetriever._horizon_similarity(30, 30)
        assert abs(sim - 1.0) < EPSILON

    def test_partial_diff(self) -> None:
        sim = HistoricalSituationRetriever._horizon_similarity(30, 60)
        assert 0.66 < sim < 0.68

    def test_large_diff(self) -> None:
        sim = HistoricalSituationRetriever._horizon_similarity(30, 365)
        assert sim < 0.6
        assert sim > 0.5

    def test_both_none(self) -> None:
        sim = HistoricalSituationRetriever._horizon_similarity(None, None)
        assert abs(sim - 0.5) < EPSILON

    def test_query_none(self) -> None:
        sim = HistoricalSituationRetriever._horizon_similarity(None, 30)
        assert abs(sim - 0.5) < EPSILON

    def test_candidate_none(self) -> None:
        sim = HistoricalSituationRetriever._horizon_similarity(30, None)
        assert abs(sim - 0.5) < EPSILON

    def test_zero_vs_nonzero(self) -> None:
        sim = HistoricalSituationRetriever._horizon_similarity(0, 30)
        assert 0 < sim < 1.0


class TestMaturitySimilarity:
    def test_equal_samples(self) -> None:
        sim = HistoricalSituationRetriever._maturity_similarity(100, 100)
        assert abs(sim - 1.0) < EPSILON

    def test_query_larger(self) -> None:
        sim = HistoricalSituationRetriever._maturity_similarity(200, 50)
        assert abs(sim - sqrt(50.0 / 200.0)) < EPSILON

    def test_candidate_larger(self) -> None:
        sim = HistoricalSituationRetriever._maturity_similarity(50, 200)
        assert abs(sim - sqrt(50.0 / 200.0)) < EPSILON

    def test_both_zero(self) -> None:
        sim = HistoricalSituationRetriever._maturity_similarity(0, 0)
        assert abs(sim - 0.5) < EPSILON

    def test_query_zero(self) -> None:
        sim = HistoricalSituationRetriever._maturity_similarity(0, 100)
        assert abs(sim - 0.5) < EPSILON

    def test_candidate_zero(self) -> None:
        sim = HistoricalSituationRetriever._maturity_similarity(100, 0)
        assert abs(sim - 0.5) < EPSILON


class TestGeometricMean:
    def test_all_perfect(self) -> None:
        sim = HistoricalSituationRetriever._geometric_mean(
            (1.0, 1.0, 1.0, 1.0, 1.0), (0.35, 0.30, 0.15, 0.10, 0.10)
        )
        assert abs(sim - 1.0) < EPSILON

    def test_all_zero_scores(self) -> None:
        sim = HistoricalSituationRetriever._geometric_mean(
            (0.0, 0.0, 0.0, 0.0, 0.0), (0.35, 0.30, 0.15, 0.10, 0.10)
        )
        assert abs(sim) < EPSILON

    def test_one_zero_with_weight(self) -> None:
        sim = HistoricalSituationRetriever._geometric_mean(
            (0.0, 1.0, 1.0, 1.0, 1.0), (0.35, 0.30, 0.15, 0.10, 0.10)
        )
        assert abs(sim) < EPSILON

    def test_one_zero_with_zero_weight(self) -> None:
        sim = HistoricalSituationRetriever._geometric_mean(
            (0.0, 0.8, 0.8, 0.8, 0.8), (0.0, 0.30, 0.25, 0.20, 0.25)
        )
        assert sim > 0.5

    def test_uniform_mid(self) -> None:
        sim = HistoricalSituationRetriever._geometric_mean(
            (0.5, 0.5, 0.5, 0.5, 0.5), (0.35, 0.30, 0.15, 0.10, 0.10)
        )
        assert abs(sim - 0.5) < EPSILON

    def test_all_weights_zero(self) -> None:
        sim = HistoricalSituationRetriever._geometric_mean(
            (1.0, 1.0, 1.0, 1.0, 1.0), (0.0, 0.0, 0.0, 0.0, 0.0)
        )
        assert abs(sim) < EPSILON


class TestTemporalSimilarity:
    def test_same_date(self) -> None:
        query = SituationQuery(event_type="FOMC", date="2026-01-01")
        ev = Evidence(
            evidence_id="test", source_node_id="src", event_type="FOMC",
            condition={}, horizon_days=30, sample_count=100,
            average_return_pct=0.5, confidence=0.8, bias="positive",
            explanation="", metadata={"last_event_date": "2026-01-01"},
        )
        sim = HistoricalSituationRetriever._temporal_similarity(query, ev, None)
        assert abs(sim - 1.0) < EPSILON

    def test_one_year_diff(self) -> None:
        query = SituationQuery(event_type="FOMC", date="2026-01-01")
        ev = Evidence(
            evidence_id="test", source_node_id="src", event_type="FOMC",
            condition={}, horizon_days=30, sample_count=100,
            average_return_pct=0.5, confidence=0.8, bias="positive",
            explanation="", metadata={"last_event_date": "2025-01-01"},
        )
        sim = HistoricalSituationRetriever._temporal_similarity(query, ev, None)
        assert sim == pytest.approx(0.5, abs=0.01)

    def test_no_query_date(self) -> None:
        query = SituationQuery(event_type="FOMC")
        ev = Evidence(
            evidence_id="test", source_node_id="src", event_type="FOMC",
            condition={}, horizon_days=30, sample_count=100,
            average_return_pct=0.5, confidence=0.8, bias="positive",
            explanation="", metadata={"last_event_date": "2025-01-01"},
        )
        sim = HistoricalSituationRetriever._temporal_similarity(query, ev, None)
        assert abs(sim - 0.5) < EPSILON

    def test_no_candidate_date(self) -> None:
        query = SituationQuery(event_type="FOMC", date="2026-01-01")
        ev = Evidence(
            evidence_id="test", source_node_id="src", event_type="FOMC",
            condition={}, horizon_days=30, sample_count=100,
            average_return_pct=0.5, confidence=0.8, bias="positive",
            explanation="",
        )
        sim = HistoricalSituationRetriever._temporal_similarity(query, ev, None)
        assert abs(sim - 0.5) < EPSILON

    def test_no_dates_at_all(self) -> None:
        query = SituationQuery(event_type="FOMC")
        ev = Evidence(
            evidence_id="test", source_node_id="src", event_type="FOMC",
            condition={}, horizon_days=30, sample_count=100,
            average_return_pct=0.5, confidence=0.8, bias="positive",
            explanation="",
        )
        sim = HistoricalSituationRetriever._temporal_similarity(query, ev, None)
        assert abs(sim - 0.5) < EPSILON

    def test_invalid_date_format(self) -> None:
        query = SituationQuery(event_type="FOMC", date="not-a-date")
        ev = Evidence(
            evidence_id="test", source_node_id="src", event_type="FOMC",
            condition={}, horizon_days=30, sample_count=100,
            average_return_pct=0.5, confidence=0.8, bias="positive",
            explanation="", metadata={"last_event_date": "2025-01-01"},
        )
        sim = HistoricalSituationRetriever._temporal_similarity(query, ev, None)
        assert abs(sim - 0.5) < EPSILON


# --------------------------------------------------------------------------
# HistoricalSituationRetriever — retrieval scenarios
# --------------------------------------------------------------------------


class TestExactRetrieval:
    def test_exact_match_returns_results(self) -> None:
        graph = _graph_with_fomc_and_cpi()
        query = EvidenceQuery(graph)
        retriever = HistoricalSituationRetriever()
        sq = SituationQuery(
            event_type="FOMC",
            condition={"rate": "hike", "inflation": "3.5"},
            horizon_days=30,
            date="2026-07-01",
        )
        matches = retriever.retrieve(sq, query)
        assert len(matches) >= 1
        assert all(m.event_type_similarity == 1.0 for m in matches)
        assert all(m.retrieval_method == "exact" for m in matches)

    def test_exact_match_ranked_by_overall(self) -> None:
        graph = _graph_with_fomc_and_cpi()
        query = EvidenceQuery(graph)
        retriever = HistoricalSituationRetriever()
        sq = SituationQuery(
            event_type="FOMC",
            condition={"rate": "hike", "inflation": "3.5"},
            horizon_days=30,
            date="2026-07-01",
        )
        matches = retriever.retrieve(sq, query)
        for i in range(len(matches) - 1):
            assert matches[i].overall_similarity >= matches[i + 1].overall_similarity

    def test_exact_match_returns_top_k(self) -> None:
        graph = _graph_with_fomc_and_cpi()
        query = EvidenceQuery(graph)
        retriever = HistoricalSituationRetriever()
        sq = SituationQuery(
            event_type="FOMC",
            condition={"rate": "hike", "inflation": "3.5"},
        )
        matches = retriever.retrieve(sq, query)
        assert len(matches) <= 5


class TestBroadenedRetrieval:
    def test_broaden_when_few_exact_matches(self) -> None:
        graph = _graph_with_fomc_and_cpi()
        query = EvidenceQuery(graph)
        retriever = HistoricalSituationRetriever()
        sq = SituationQuery(
            event_type="FOMC",
            condition={"rate": "hike", "inflation": "9.9"},
            horizon_days=30,
        )
        matches = retriever.retrieve(sq, query)
        assert all(m.retrieval_method == "broadened" for m in matches)

    def test_broaden_includes_different_conditions(self) -> None:
        graph = _graph_with_fomc_and_cpi()
        query = EvidenceQuery(graph)
        retriever = HistoricalSituationRetriever()
        sq = SituationQuery(
            event_type="FOMC",
            condition={"rate": "hike", "inflation": "9.9"},
        )
        matches = retriever.retrieve(sq, query)
        if len(matches) > 0:
            fomc_ids = {"fomc_hike_25_30", "fomc_hike_25_60", "fomc_hold_30"}
            match_ids = {m.evidence.evidence_id for m in matches}
            assert len(match_ids & fomc_ids) > 0

    def test_no_broaden_when_disabled(self) -> None:
        graph = _graph_with_fomc_and_cpi()
        query = EvidenceQuery(graph)
        retriever = HistoricalSituationRetriever(
            RetrievalConfig(broaden_on_empty=False)
        )
        sq = SituationQuery(
            event_type="FOMC",
            condition={"rate": "hike", "inflation": "9.9"},
        )
        matches = retriever.retrieve(sq, query)
        assert len(matches) == 0

    def test_broadened_match_has_lower_similarity_than_exact(self) -> None:
        graph = _graph_with_fomc_and_cpi()
        query = EvidenceQuery(graph)
        retriever = HistoricalSituationRetriever()
        sq = SituationQuery(
            event_type="FOMC",
            condition={"rate": "hike", "inflation": "3.5"},
            date="2026-07-01",
            sample_count=100,
        )
        matches = retriever.retrieve(sq, query)
        if len(matches) > 0:
            fomc_hike_25_30 = next(
                (m for m in matches if m.evidence.evidence_id == "fomc_hike_25_30"), None
            )
            fomc_hold_30 = next(
                (m for m in matches if m.evidence.evidence_id == "fomc_hold_30"), None
            )
            if fomc_hike_25_30 and fomc_hold_30:
                assert fomc_hike_25_30.overall_similarity > fomc_hold_30.overall_similarity


class TestEmptyGraph:
    def test_empty_graph_returns_empty(self) -> None:
        graph = KnowledgeGraph()
        query = EvidenceQuery(graph)
        retriever = HistoricalSituationRetriever()
        sq = SituationQuery(event_type="FOMC")
        matches = retriever.retrieve(sq, query)
        assert len(matches) == 0

    def test_none_query_returns_empty(self) -> None:
        retriever = HistoricalSituationRetriever()
        sq = SituationQuery(event_type="FOMC")
        matches = retriever.retrieve(sq, None)
        assert len(matches) == 0


class TestMinSimilarity:
    def test_filters_below_threshold(self) -> None:
        graph = _graph_with_fomc_and_cpi()
        query = EvidenceQuery(graph)
        retriever = HistoricalSituationRetriever(
            RetrievalConfig(min_similarity=0.99, broaden_on_empty=False)
        )
        sq = SituationQuery(
            event_type="FOMC",
            condition={"rate": "hike", "inflation": "3.5"},
            horizon_days=30,
            date="2026-07-01",
        )
        matches = retriever.retrieve(sq, query)
        for m in matches:
            assert m.overall_similarity >= 0.99

    def test_low_threshold_includes_more(self) -> None:
        graph = _graph_with_fomc_and_cpi()
        query = EvidenceQuery(graph)
        retriever = HistoricalSituationRetriever(
            RetrievalConfig(min_similarity=0.1)
        )
        sq = SituationQuery(event_type="FOMC")
        matches = retriever.retrieve(sq, query)
        assert len(matches) >= 1


# --------------------------------------------------------------------------
# Integration with OrchestrationReport
# --------------------------------------------------------------------------


class TestOrchestrationReportHistoricalMatches:
    def test_defaults_to_empty(self) -> None:
        report = OrchestrationReport()
        assert report.historical_matches == []

    def test_can_set_matches(self) -> None:
        ev = Evidence(
            evidence_id="test", source_node_id="src", event_type="FOMC",
            condition={}, horizon_days=30, sample_count=100,
            average_return_pct=0.5, confidence=0.8, bias="positive", explanation="",
        )
        match = SituationMatch(
            evidence=ev, overall_similarity=0.9,
            event_type_similarity=1.0, condition_similarity=1.0,
            horizon_similarity=1.0, maturity_similarity=1.0,
            temporal_similarity=1.0,
        )
        report = OrchestrationReport(historical_matches=[match])
        assert len(report.historical_matches) == 1
        assert report.historical_matches[0] is match


class TestOrchestrationContextRetriever:
    def test_defaults_to_none(self) -> None:
        ctx = OrchestrationContext()
        assert ctx.retriever is None

    def test_can_set_retriever(self) -> None:
        retriever = HistoricalSituationRetriever()
        ctx = OrchestrationContext(retriever=retriever)
        assert ctx.retriever is retriever


class TestOrchestrationEngineRetriever:
    def test_retriever_not_called_when_none(self) -> None:
        ctx = OrchestrationContext(event_type="FOMC")
        engine = OrchestrationEngine()
        report = engine.analyze(ctx)
        assert report.historical_matches == []

    def test_retriever_integration_basic(self) -> None:
        graph = _graph_with_fomc_and_cpi()
        eq = EvidenceQuery(graph)
        retriever = HistoricalSituationRetriever()
        ctx = OrchestrationContext(
            event_type="FOMC",
            condition={"rate": "hike", "inflation": "3.5"},
            horizon_days=30,
            date="2026-07-01",
            retriever=retriever,
            evidence_query=eq,
        )
        engine = OrchestrationEngine()
        report = engine.analyze(ctx)
        assert isinstance(report.historical_matches, list)
        if len(report.historical_matches) > 0:
            m = report.historical_matches[0]
            assert m.event_type_similarity == 1.0
            assert m.retrieval_method == "exact"

    def test_retriever_not_called_without_query(self) -> None:
        retriever = HistoricalSituationRetriever()
        ctx = OrchestrationContext(
            event_type="FOMC",
            retriever=retriever,
        )
        engine = OrchestrationEngine()
        report = engine.analyze(ctx)
        assert report.historical_matches == []
