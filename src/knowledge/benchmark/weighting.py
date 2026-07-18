from __future__ import annotations

from knowledge.benchmark.base import Benchmark, BenchmarkResult
from knowledge.evidence.collection import EvidenceCollection
from knowledge.evidence.evidence import Evidence
from knowledge.evidence.weighting import EvidenceWeighter, WeightConfig


def _ev(
    eid: str,
    confidence: float = 0.8,
    sample_count: int = 100,
    avg_return: float = 1.0,
    bias: str = "gold_positive_bias",
    event_type: str = "CPI",
) -> Evidence:
    return Evidence(
        evidence_id=eid,
        source_node_id=f"src_{eid}",
        event_type=event_type,
        condition={},
        horizon_days=30,
        sample_count=sample_count,
        average_return_pct=avg_return,
        confidence=confidence,
        bias=bias,
        explanation="test",
    )


class WeightingBenchmark(Benchmark):
    def __init__(self) -> None:
        super().__init__("weighting")
        self._weighter = EvidenceWeighter()

    def run(self) -> BenchmarkResult:
        quality_items = [
            _ev("low_q_1", confidence=0.30, sample_count=3, avg_return=0.5),
            _ev("low_q_2", confidence=0.25, sample_count=5, avg_return=0.3),
            _ev("high_q_1", confidence=0.90, sample_count=300, avg_return=-1.5),
        ]
        quality_coll = EvidenceCollection(quality_items)
        quality_result = self._weighter.weigh(quality_coll)

        high_q_weight = quality_result.weight_factors[2].composite_weight
        low_q_weights = [
            f.composite_weight for f in quality_result.weight_factors[:2]
        ]

        quality_correct = high_q_weight > max(low_q_weights)

        size_items = [
            _ev("small_1", confidence=0.7, sample_count=10),
            _ev("small_2", confidence=0.7, sample_count=15),
            _ev("large_1", confidence=0.7, sample_count=500),
            _ev("large_2", confidence=0.7, sample_count=300),
        ]
        size_coll = EvidenceCollection(size_items)
        size_result = self._weighter.weigh(size_coll)

        large_weights = [
            f.composite_weight
            for f in size_result.weight_factors
            if f.evidence_id in ("large_1", "large_2")
        ]
        small_weights = [
            f.composite_weight
            for f in size_result.weight_factors
            if f.evidence_id in ("small_1", "small_2")
        ]

        size_correct = min(large_weights) > max(small_weights)

        uniform_items = [
            _ev("u1", confidence=0.8, sample_count=100),
            _ev("u2", confidence=0.8, sample_count=100),
            _ev("u3", confidence=0.8, sample_count=100),
        ]
        uniform_coll = EvidenceCollection(uniform_items)
        uniform_result = self._weighter.weigh(uniform_coll)
        uniform_weights = [f.composite_weight for f in uniform_result.weight_factors]
        uniform_correct = (
            max(uniform_weights) - min(uniform_weights) < 0.01
        )

        single_item = EvidenceCollection([_ev("single", confidence=0.8, sample_count=100)])
        single_result = self._weighter.weigh(single_item)
        single_correct = len(single_result.weight_factors) == 1 and single_result.weighted_avg_confidence > 0

        effective_n = uniform_result.effective_sample_size
        ess_correct = effective_n > 0

        tests_passed = sum(
            [quality_correct, size_correct, uniform_correct, single_correct, ess_correct]
        )
        tests_total = 5

        return self._result(
            metrics=[
                self._metric(
                    "quality_weighting_accuracy",
                    1.0 if quality_correct else 0.0,
                    "binary",
                    "High-quality evidence ranked above low-quality evidence",
                ),
                self._metric(
                    "sample_size_sensitivity",
                    1.0 if size_correct else 0.0,
                    "binary",
                    "Larger samples correctly receive higher weights",
                ),
                self._metric(
                    "weighting_accuracy",
                    tests_passed / tests_total if tests_total > 0 else 0.0,
                    "ratio",
                    "Fraction of weighting property tests passed",
                ),
            ],
            thresholds={
                "weighting_accuracy": (0.8, "gte"),
            },
        )
