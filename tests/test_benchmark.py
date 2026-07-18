"""Institutional Reasoning Benchmark — official acceptance gate.

Every capability added to AurumAI must not degrade these metrics below threshold.
"""

from __future__ import annotations

import json

import pytest

from knowledge.benchmark import (
    BenchmarkReport,
    BenchmarkResult,
    BenchmarkSuite,
    CrossEventBenchmark,
    DecisionBenchmark,
    DeterminismBenchmark,
    ReasoningBenchmark,
    RetrievalBenchmark,
    StabilityBenchmark,
    WeightingBenchmark,
)


@pytest.fixture(scope="module")
def suite() -> BenchmarkSuite:
    s = BenchmarkSuite(name="aurumai-institutional")
    s.add(ReasoningBenchmark())
    s.add(RetrievalBenchmark())
    s.add(CrossEventBenchmark())
    s.add(WeightingBenchmark())
    s.add(DecisionBenchmark())
    s.add(DeterminismBenchmark())
    s.add(StabilityBenchmark())
    return s


@pytest.fixture(scope="module")
def report(suite: BenchmarkSuite) -> BenchmarkReport:
    return suite.run()


# ---------------------------------------------------------------------------
# Suite-level checks
# ---------------------------------------------------------------------------


class TestBenchmarkSuite:
    def test_all_benchmarks_report(self, report: BenchmarkReport) -> None:
        assert len(report.results) == 7

    def test_report_serializable(self, report: BenchmarkReport) -> None:
        d = report.to_dict()
        json_str = json.dumps(d, indent=2)
        assert len(json_str) > 0
        parsed = json.loads(json_str)
        assert parsed["suite_name"] == "aurumai-institutional"

    def test_all_benchmarks_pass(self, report: BenchmarkReport) -> None:
        failing = [r for r in report.results if not r.passed]
        if failing:
            msg_parts = []
            for f in failing:
                failed_metrics = [
                    m for m in f.metrics
                    if m.value <= 0
                ]
                msg_parts.append(
                    f"{f.benchmark_name}: {f.num_passed}/{f.num_passed + f.num_failed} passed"
                )
            pytest.fail("; ".join(msg_parts))


# ---------------------------------------------------------------------------
# Per-benchmark result checks
# ---------------------------------------------------------------------------


def _find(report: BenchmarkReport, name: str) -> BenchmarkResult:
    for r in report.results:
        if r.benchmark_name == name:
            return r
    raise AssertionError(f"Benchmark '{name}' not found in report")


class TestReasoningMetrics:
    def test_reasoning_accuracy(self, report: BenchmarkReport) -> None:
        r = _find(report, "reasoning")
        m = next(m for m in r.metrics if m.name == "reasoning_accuracy")
        assert m.value >= 0.8, f"reasoning_accuracy={m.value} < 0.8"

    def test_num_scenarios(self, report: BenchmarkReport) -> None:
        r = _find(report, "reasoning")
        m = next(m for m in r.metrics if m.name == "num_scenarios")
        assert m.value >= 5

    def test_confidence_calibration_reported(self, report: BenchmarkReport) -> None:
        r = _find(report, "reasoning")
        m = next(m for m in r.metrics if m.name == "confidence_calibration")
        assert m.value >= 0.0


class TestRetrievalMetrics:
    def test_precision_at_1(self, report: BenchmarkReport) -> None:
        r = _find(report, "retrieval")
        m = next(m for m in r.metrics if m.name == "precision_at_1")
        assert m.value >= 0.9, f"precision_at_1={m.value} < 0.9"

    def test_retrieval_accuracy(self, report: BenchmarkReport) -> None:
        r = _find(report, "retrieval")
        m = next(m for m in r.metrics if m.name == "retrieval_accuracy")
        assert m.value >= 0.75, f"retrieval_accuracy={m.value} < 0.75"


class TestCrossEventMetrics:
    def test_consensus_accuracy(self, report: BenchmarkReport) -> None:
        r = _find(report, "cross_event")
        m = next(m for m in r.metrics if m.name == "consensus_accuracy")
        assert m.value >= 0.8, f"consensus_accuracy={m.value} < 0.8"

    def test_conflict_detection(self, report: BenchmarkReport) -> None:
        r = _find(report, "cross_event")
        m = next(m for m in r.metrics if m.name == "conflict_detection_rate")
        assert m.value >= 0.5, f"conflict_detection_rate={m.value} < 0.5"


class TestWeightingMetrics:
    def test_quality_weighting(self, report: BenchmarkReport) -> None:
        r = _find(report, "weighting")
        m = next(m for m in r.metrics if m.name == "quality_weighting_accuracy")
        assert m.value >= 1.0, f"quality_weighting_accuracy={m.value} < 1.0"

    def test_sample_size_sensitivity(self, report: BenchmarkReport) -> None:
        r = _find(report, "weighting")
        m = next(m for m in r.metrics if m.name == "sample_size_sensitivity")
        assert m.value >= 1.0, f"sample_size_sensitivity={m.value} < 1.0"


class TestDecisionMetrics:
    def test_decision_consistency(self, report: BenchmarkReport) -> None:
        r = _find(report, "decision")
        m = next(m for m in r.metrics if m.name == "decision_consistency")
        assert m.value >= 1.0, f"decision_consistency={m.value} < 1.0"

    def test_decision_stability(self, report: BenchmarkReport) -> None:
        r = _find(report, "decision")
        m = next(m for m in r.metrics if m.name == "decision_stability")
        assert m.value >= 0.5, f"decision_stability={m.value} < 0.5"

    def test_decision_accuracy(self, report: BenchmarkReport) -> None:
        r = _find(report, "decision")
        m = next(m for m in r.metrics if m.name == "decision_accuracy")
        assert m.value >= 0.66, f"decision_accuracy={m.value} < 0.66"


class TestDeterminismMetrics:
    def test_determinism_score(self, report: BenchmarkReport) -> None:
        r = _find(report, "determinism")
        m = next(m for m in r.metrics if m.name == "determinism_score")
        assert m.value >= 1.0, f"determinism_score={m.value} < 1.0"


class TestStabilityMetrics:
    def test_decision_stability(self, report: BenchmarkReport) -> None:
        r = _find(report, "stability")
        m = next(m for m in r.metrics if m.name == "decision_stability")
        assert m.value >= 0.5, f"stability_decision_stability={m.value} < 0.5"

    def test_consensus_stability(self, report: BenchmarkReport) -> None:
        r = _find(report, "stability")
        m = next(m for m in r.metrics if m.name == "consensus_stability")
        assert m.value >= 0.5, f"consensus_stability={m.value} < 0.5"
