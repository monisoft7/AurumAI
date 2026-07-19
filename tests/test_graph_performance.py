from __future__ import annotations

import itertools
import time
from typing import Any

import pytest

from knowledge.graph.builder import GraphBuilder
from knowledge.graph.relation import (
    RELATION_SAME_EVENT_TYPE,
    RELATION_SAME_CONDITION,
    RELATION_SAME_HORIZON,
)

# ═════════════════════════════════════════════════════════════════════════════
# Helpers
# ═════════════════════════════════════════════════════════════════════════════

_EVENT_TYPES = [
    "CPI", "NFP", "PPI", "GDP", "PMI", "FOMC",
    "UNEMP", "RETAIL", "INDPRO", "HOUSING",
    "DURABLES", "FEDBAL", "CONFIDX", "SENTIX",
    "TRADE", "INVENTORY", "CONSTR", "MANUF",
    "SERVICES", "COMPOSITE",
]
_CONDITIONS = [
    {"pressure": "high"},
    {"pressure": "low"},
    {"surprise": "positive"},
    {"surprise": "negative"},
    {"trend": "up"},
    {"trend": "down"},
]


def _make_record(
    knowledge_id: str,
    event_type: str,
    condition: dict[str, str],
    horizon_days: int,
) -> dict[str, Any]:
    return {
        "knowledge_id": knowledge_id,
        "event_type": event_type,
        "condition": condition,
        "horizon_days": horizon_days,
    }


def _generate_records(count: int) -> list[dict[str, Any]]:
    """Generate deterministic records cycling through test dimensions."""
    records: list[dict[str, Any]] = []
    for i in range(count):
        et = _EVENT_TYPES[i % len(_EVENT_TYPES)]
        cond = _CONDITIONS[(i // len(_EVENT_TYPES)) % len(_CONDITIONS)]
        hd = 5 * (1 + (i % 5))
        records.append(_make_record(f"rec_{i:05d}", et, cond, hd))
    return records


def _expected_complete_graph_edges(group_sizes: list[int]) -> int:
    """Sum of k*(k-1)/2 for each group of size k."""
    return sum(k * (k - 1) // 2 for k in group_sizes)


def _count_by(graph: Any, relation_type: str) -> int:
    return len(graph.get_relations(relation_type=relation_type))


# ═════════════════════════════════════════════════════════════════════════════
# Determinism & Correctness
# ═════════════════════════════════════════════════════════════════════════════

class TestGraphBuilderDeterminism:
    def test_deterministic_output(self) -> None:
        """Same input must produce identical graph."""
        records = _generate_records(100)
        g1 = GraphBuilder().build(records)
        g2 = GraphBuilder().build(records)
        assert g1.node_count == g2.node_count
        assert g1.relation_count == g2.relation_count
        ids_1 = {r.source_id for r in g1.get_relations()}
        ids_2 = {r.source_id for r in g2.get_relations()}
        assert ids_1 == ids_2

    def test_empty_records(self) -> None:
        graph = GraphBuilder().build([])
        assert graph.node_count == 0
        assert graph.relation_count == 0

    def test_single_record(self) -> None:
        records = [_make_record("r1", "CPI", {"p": "h"}, 5)]
        graph = GraphBuilder().build(records)
        assert graph.node_count == 1
        assert graph.relation_count == 0


class TestGraphBuilderEdgeCounts:
    """Verify edge counts match expected formulas for controlled data."""

    def test_all_share_event_type(self) -> None:
        records = [_make_record(f"r{i}", "CPI", {"p": str(i)}, i) for i in range(10)]
        graph = GraphBuilder().build(records)
        # 10 same event_type nodes => 10*9/2 = 45 edges
        assert _count_by(graph, RELATION_SAME_EVENT_TYPE) == 45
        # No shared condition or horizon
        assert _count_by(graph, RELATION_SAME_CONDITION) == 0
        assert _count_by(graph, RELATION_SAME_HORIZON) == 0

    def test_all_share_condition(self) -> None:
        records = [_make_record(f"r{i}", f"ET{i}", {"p": "same"}, i) for i in range(10)]
        graph = GraphBuilder().build(records)
        assert _count_by(graph, RELATION_SAME_CONDITION) == 45
        assert _count_by(graph, RELATION_SAME_EVENT_TYPE) == 0
        assert _count_by(graph, RELATION_SAME_HORIZON) == 0

    def test_all_share_horizon(self) -> None:
        records = [_make_record(f"r{i}", f"ET{i}", {"p": str(i)}, 5) for i in range(10)]
        graph = GraphBuilder().build(records)
        assert _count_by(graph, RELATION_SAME_HORIZON) == 45
        assert _count_by(graph, RELATION_SAME_EVENT_TYPE) == 0
        assert _count_by(graph, RELATION_SAME_CONDITION) == 0

    def test_two_groups_per_dimension(self) -> None:
        """5 CPI + 5 NFP, 5 condA + 5 condB, 5 hd5 + 5 hd10."""
        records = [
            _make_record(f"r{i}", "CPI" if i < 5 else "NFP",
                         {"c": "a"} if i < 5 else {"c": "b"},
                         5 if i < 5 else 10)
            for i in range(10)
        ]
        graph = GraphBuilder().build(records)
        # event_type: CPI group 5 => 10, NFP group 5 => 10 => 20 total
        assert _count_by(graph, RELATION_SAME_EVENT_TYPE) == 20
        # condition: 5 each => 20 total
        assert _count_by(graph, RELATION_SAME_CONDITION) == 20
        # horizon: 5 each => 20 total
        assert _count_by(graph, RELATION_SAME_HORIZON) == 20
        assert graph.relation_count == 60

    def test_no_shared_dimensions(self) -> None:
        """Every record unique across all 3 dimensions => 0 edges."""
        records = [_make_record(f"r{i}", f"ET{i}", {"p": str(i)}, i) for i in range(20)]
        graph = GraphBuilder().build(records)
        assert graph.relation_count == 0

    def test_three_groups_event_type(self) -> None:
        records = [
            _make_record(f"r{i}", et, {"p": str(i)}, i)
            for et in ["CPI", "NFP", "PPI"]
            for i in range(4)
        ]
        graph = GraphBuilder().build(records)
        # 3 groups of 4 => 3 * (4*3/2) = 3 * 6 = 18
        assert _count_by(graph, RELATION_SAME_EVENT_TYPE) == 18

    def test_dimension_independence(self) -> None:
        """Edges for each dimension are generated independently."""
        # 6 records: 2 event_types × 3 conditions, all same horizon
        records = [
            _make_record(f"r{i}", et, cond, 5)
            for i, (et, cond) in enumerate(
                itertools.product(["CPI", "NFP"], [{"c": "a"}, {"c": "b"}, {"c": "c"}])
            )
        ]
        graph = GraphBuilder().build(records)
        # event_type: 2 groups of 3 => 2 * 3 = 6
        assert _count_by(graph, RELATION_SAME_EVENT_TYPE) == 6
        # condition: 3 groups of 2 => 3 * 1 = 3
        assert _count_by(graph, RELATION_SAME_CONDITION) == 3
        # horizon: 1 group of 6 => 15
        assert _count_by(graph, RELATION_SAME_HORIZON) == 15
        assert graph.relation_count == 24


class TestGraphBuilderRecordTypes:
    def test_knowledge_record_input(self) -> None:
        from knowledge.integrity.knowledge_record import KnowledgeRecord

        kr = KnowledgeRecord(
            knowledge_id="kr1", event_type="CPI", asset="GOLD",
            condition={"p": "h"}, horizon_days=5, sample_count=10,
            positive_return_rate_pct=60.0, negative_return_rate_pct=40.0,
            up_direction_rate_pct=50.0, down_direction_rate_pct=30.0,
            flat_direction_rate_pct=20.0, average_return_pct=1.5,
            median_return_pct=1.0, min_return_pct=-2.0, max_return_pct=5.0,
            first_event_date="2026-01-01", last_event_date="2026-06-01",
            bias="bullish", confidence=0.8, explanation="test",
        )
        graph = GraphBuilder().build([kr])
        assert graph.node_count == 1
        node = graph.get_node("kr1")
        assert node is not None
        assert node.properties["event_type"] == "CPI"

    def test_mixed_dict_and_kr(self) -> None:
        from knowledge.integrity.knowledge_record import KnowledgeRecord

        kr = KnowledgeRecord(
            knowledge_id="kr1", event_type="CPI", asset="GOLD",
            condition={"p": "h"}, horizon_days=5, sample_count=10,
            positive_return_rate_pct=0.0, negative_return_rate_pct=0.0,
            up_direction_rate_pct=0.0, down_direction_rate_pct=0.0,
            flat_direction_rate_pct=0.0, average_return_pct=0.0,
            median_return_pct=0.0, min_return_pct=0.0, max_return_pct=0.0,
            first_event_date="", last_event_date="",
            bias="neutral", confidence=0.0, explanation="",
        )
        d = {"knowledge_id": "d1", "event_type": "CPI", "condition": {"p": "h"}, "horizon_days": 5}
        graph = GraphBuilder().build([kr, d])
        assert graph.node_count == 2
        # Both share event_type and condition and horizon => 3 edges
        assert graph.relation_count == 3


# ═════════════════════════════════════════════════════════════════════════════
# Benchmark (informational, not time-sensitive assertions)
# ═════════════════════════════════════════════════════════════════════════════

class TestGraphBuilderBenchmark:
    """Measure build time for increasing record counts.

    The total edge count depends on how many records share each dimension.
    Dense data (all records share a dimension) produces O(n²) edges —
    this is inherent to the output, not the algorithm. The optimization
    improves the constant factor and the average case (sparse/diverse data).
    """

    @pytest.mark.parametrize("count", [100, 1_000, 10_000])
    def test_diverse_data(self, count: int, capsys: pytest.CaptureFixture) -> None:
        """Diverse data: many unique event_types & conditions."""
        records = [
            _make_record(
                f"r{i:05d}",
                _EVENT_TYPES[i % 20],              # 20 event types
                {"p": str(i // 20), "q": str(i % 5)},  # many unique conditions
                (i % 20) + 1,                       # 20 horizon values
            )
            for i in range(count)
        ]
        builder = GraphBuilder()
        t0 = time.perf_counter()
        graph = builder.build(records)
        elapsed = time.perf_counter() - t0
        with capsys.disabled():
            print(f"\n  GraphBuilder({count:>6,} diverse): {elapsed*1000:>8.1f} ms  "
                  f"| nodes={graph.node_count}  edges={graph.relation_count}")
        assert graph.node_count == count
        # Bound is generous — timing is for human reference.
        # Edge count is output-bound (complete subgraphs), not algorithm-bound.
        max_sec = {100: 2.0, 1_000: 5.0, 10_000: 60.0}[count]
        assert elapsed < max_sec, f"{count} diverse records took {elapsed:.1f}s (limit {max_sec}s)"

    def test_dense_1k(self, capsys: pytest.CaptureFixture) -> None:
        """Dense 1k: few groups — output-bound case for reference."""
        records = _generate_records(1000)
        builder = GraphBuilder()
        t0 = time.perf_counter()
        graph = builder.build(records)
        elapsed = time.perf_counter() - t0
        with capsys.disabled():
            print(f"\n  GraphBuilder(1,000 dense): {elapsed*1000:>8.1f} ms  "
                  f"| nodes={graph.node_count}  edges={graph.relation_count}")
        assert graph.node_count == 1000
        assert elapsed < 10.0, f"Dense 1k took {elapsed:.1f}s (limit 10s)"
