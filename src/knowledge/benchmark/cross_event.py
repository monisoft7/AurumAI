from __future__ import annotations

from knowledge.benchmark.base import Benchmark, BenchmarkResult
from knowledge.evidence.collection import EvidenceCollection
from knowledge.evidence.evidence import Evidence
from knowledge.reasoning.cross_event import CrossEventAnalyzer


def _ev(
    event_type: str,
    bias: str = "gold_positive_bias",
    confidence: float = 0.7,
    eid: str = "",
) -> Evidence:
    return Evidence(
        evidence_id=eid or f"{event_type}_{bias}",
        source_node_id=f"{event_type}_node",
        event_type=event_type,
        condition={},
        horizon_days=20,
        sample_count=50,
        average_return_pct=0.5,
        confidence=confidence,
        bias=bias,
        explanation="",
    )


class CrossEventBenchmark(Benchmark):
    def __init__(self) -> None:
        super().__init__("cross_event")
        self._analyzer = CrossEventAnalyzer()

    def run(self) -> BenchmarkResult:
        scenarios: list[tuple[str, EvidenceCollection, str, int]] = [
            (
                "both_positive_agreement",
                EvidenceCollection([
                    _ev("CPI", "gold_positive_bias", 0.8, "cpi_1"),
                    _ev("CPI", "gold_positive_bias", 0.7, "cpi_2"),
                    _ev("NFP", "gold_positive_bias", 0.9, "nfp_1"),
                    _ev("NFP", "gold_positive_bias", 0.75, "nfp_2"),
                ]),
                "agreement",
                1,
            ),
            (
                "positive_vs_negative_conflict",
                EvidenceCollection([
                    _ev("CPI", "gold_positive_bias", 0.8, "cpi_1"),
                    _ev("CPI", "gold_positive_bias", 0.7, "cpi_2"),
                    _ev("DXY", "gold_negative_bias", 0.75, "dxy_1"),
                    _ev("DXY", "gold_negative_bias", 0.65, "dxy_2"),
                ]),
                "conflict",
                1,
            ),
            (
                "single_type_insufficient",
                EvidenceCollection([
                    _ev("CPI", "gold_positive_bias", 0.7, "cpi_1"),
                ]),
                "insufficient",
                0,
            ),
            (
                "empty_insufficient",
                EvidenceCollection([]),
                "insufficient",
                0,
            ),
            (
                "mixed_signals",
                EvidenceCollection([
                    _ev("CPI", "gold_positive_bias", 0.7, "cpi_1"),
                    _ev("NFP", "mixed_or_context_dependent", 0.5, "nfp_1"),
                ]),
                "mixed",
                0,
            ),
        ]

        correct = 0
        total = len(scenarios)
        total_conflicts_detected = 0
        total_conflicts_expected = 0

        for name, coll, expected_consensus, expected_conflicts in scenarios:
            result = self._analyzer.analyze(coll)
            if result.overall_consensus == expected_consensus:
                correct += 1
            if expected_conflicts > 0:
                total_conflicts_expected += expected_conflicts
                if len(result.conflicts) >= expected_conflicts:
                    total_conflicts_detected += expected_conflicts

        consensus_accuracy = correct / total if total > 0 else 0.0
        conflict_detection = (
            total_conflicts_detected / total_conflicts_expected
            if total_conflicts_expected > 0
            else 1.0
        )

        return self._result(
            metrics=[
                self._metric(
                    "consensus_accuracy",
                    consensus_accuracy,
                    "ratio",
                    "Fraction of scenarios where detected consensus matches expected",
                ),
                self._metric(
                    "conflict_detection_rate",
                    conflict_detection,
                    "ratio",
                    "Fraction of expected conflicts correctly detected",
                ),
                self._metric(
                    "num_scenarios",
                    float(total),
                    "count",
                    "Total cross-event scenarios evaluated",
                ),
                self._metric(
                    "num_correct",
                    float(correct),
                    "count",
                    "Scenarios with correct consensus label",
                ),
            ],
            thresholds={
                "consensus_accuracy": (0.8, "gte"),
            },
        )
