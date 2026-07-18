from __future__ import annotations

from knowledge.benchmark.base import Benchmark, BenchmarkResult
from knowledge.evidence.query import EvidenceQuery
from knowledge.graph.graph import KnowledgeGraph
from knowledge.graph.node import GraphNode
from knowledge.reasoning.retrieval import (
    HistoricalSituationRetriever,
    RetrievalConfig,
    SituationQuery,
)


def _build_test_graph() -> KnowledgeGraph:
    g = KnowledgeGraph()
    nodes = [
        ("fomc_hike_25", "FOMC", {"rate": "hike", "inflation": "3.5"}, 30, 200, "2025-06-01"),
        ("fomc_hike_50", "FOMC", {"rate": "hike", "inflation": "4.2"}, 60, 150, "2024-12-01"),
        ("fomc_hold", "FOMC", {"rate": "hold", "inflation": "2.8"}, 30, 80, "2023-11-01"),
        ("cpi_high", "CPI", {"cpi": "high", "core": "sticky"}, 30, 300, "2025-03-01"),
        ("cpi_moderate", "CPI", {"cpi": "moderate"}, 90, 50, "2024-09-01"),
        ("nfp_strong", "NFP", {"jobs": "strong", "unemployment": "low"}, 20, 250, "2025-04-15"),
        ("nfp_weak", "NFP", {"jobs": "weak"}, 20, 40, "2024-07-01"),
    ]
    for node_id, event_type, condition, horizon, samples, date in nodes:
        g.add_node(
            GraphNode(
                node_id=node_id,
                node_type="knowledge",
                properties={
                    "event_type": event_type,
                    "condition": condition,
                    "horizon_days": horizon,
                    "sample_count": samples,
                    "average_return_pct": 0.5,
                    "confidence": 0.8,
                    "bias": "gold_positive_bias",
                    "explanation": f"Test record: {event_type}",
                    "knowledge_id": node_id,
                    "last_event_date": date,
                },
            )
        )
    return g


class RetrievalBenchmark(Benchmark):
    def __init__(self) -> None:
        super().__init__("retrieval")
        self._graph = _build_test_graph()
        self._query = EvidenceQuery(self._graph)
        self._retriever = HistoricalSituationRetriever()

    def _exact_match(self) -> tuple[bool, float]:
        sq = SituationQuery(
            event_type="FOMC",
            condition={"rate": "hike", "inflation": "3.5"},
            horizon_days=30,
            date="2026-01-01",
            sample_count=100,
        )
        matches = self._retriever.retrieve(sq, self._query)
        if not matches:
            return False, 0.0
        top = matches[0]
        return (
            top.evidence.evidence_id == "fomc_hike_25" and top.retrieval_method == "exact",
            1.0 / (len([m for m in matches if m.evidence.evidence_id == "fomc_hike_25"]) or 1),
        )

    def _broadened_match(self) -> tuple[bool, float]:
        sq = SituationQuery(
            event_type="FOMC",
            condition={"rate": "hike", "inflation": "9.9"},
        )
        matches = self._retriever.retrieve(sq, self._query)
        if not matches:
            return False, 0.0
        fomc_ids = {"fomc_hike_25", "fomc_hike_50", "fomc_hold"}
        found = [m for m in matches if m.evidence.evidence_id in fomc_ids]
        return len(found) > 0, len(found) / max(len(fomc_ids), 1)

    def _precision_at_k(self, k: int) -> tuple[float, float]:
        sq = SituationQuery(
            event_type="FOMC",
            condition={"rate": "hike", "inflation": "3.5"},
            date="2026-01-01",
        )
        matches = self._retriever.retrieve(sq, self._query)
        if not matches or len(matches) == 0:
            return 0.0, 0.0
        top_k = matches[:k]
        relevant = sum(
            1
            for m in top_k
            if m.evidence.event_type == "FOMC"
            and "hike" in m.evidence.condition.get("rate", "")
        )
        return relevant / k, relevant / max(len(top_k), 1)

    def _empty_query(self) -> bool:
        sq = SituationQuery(event_type="GDP")
        matches = self._retriever.retrieve(sq, self._query)
        return len(matches) == 0

    def _ranking_order(self) -> bool:
        sq = SituationQuery(
            event_type="FOMC",
            condition={"rate": "hike", "inflation": "3.5"},
            date="2026-07-01",
            sample_count=100,
        )
        matches = self._retriever.retrieve(sq, self._query)
        if len(matches) < 2:
            return False
        for i in range(len(matches) - 1):
            if matches[i].overall_similarity < matches[i + 1].overall_similarity:
                return False
        return True

    def run(self) -> BenchmarkResult:
        exact_ok, exact_mrr = self._exact_match()
        broad_ok, broad_recall = self._broadened_match()
        precision_1, _ = self._precision_at_k(1)
        precision_3, _ = self._precision_at_k(3)
        empty_ok = self._empty_query()
        ranked_ok = self._ranking_order()

        tests_passed = sum([exact_ok, broad_ok, empty_ok, ranked_ok])
        tests_total = 4

        return self._result(
            metrics=[
                self._metric(
                    "precision_at_1",
                    precision_1,
                    "ratio",
                    "Precision of top-1 retrieval result",
                ),
                self._metric(
                    "precision_at_3",
                    precision_3,
                    "ratio",
                    "Precision of top-3 retrieval results",
                ),
                self._metric(
                    "broadened_recall",
                    broad_recall,
                    "ratio",
                    "Recall of broadened retrieval for same event type",
                ),
                self._metric(
                    "exact_match_mrr",
                    exact_mrr,
                    "score",
                    "Mean reciprocal rank of exact-match retrieval",
                ),
                self._metric(
                    "retrieval_accuracy",
                    tests_passed / tests_total if tests_total > 0 else 0.0,
                    "ratio",
                    "Fraction of retrieval property tests passed",
                ),
            ],
            thresholds={
                "precision_at_1": (0.9, "gte"),
                "retrieval_accuracy": (0.75, "gte"),
            },
        )
