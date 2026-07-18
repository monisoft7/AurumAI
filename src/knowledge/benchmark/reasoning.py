from __future__ import annotations

from knowledge.benchmark.base import Benchmark, BenchmarkResult, Metric
from knowledge.evidence.collection import EvidenceCollection
from knowledge.evidence.evidence import Evidence
from knowledge.reasoning.context import ReasoningContext
from knowledge.reasoning.engine import ReasoningEngine
from knowledge.decision.engine import DecisionEngine
from knowledge.decision.context import DecisionContext
from knowledge.decision.decision import (
    DECISION_STRONG_POSITIVE,
    DECISION_POSITIVE,
    DECISION_NEUTRAL,
    DECISION_NEGATIVE,
    DECISION_STRONG_NEGATIVE,
    DECISION_INSUFFICIENT_EVIDENCE,
)


_SCENARIOS: list[tuple[str, list[Evidence], str, float]] = [
    (
        "all_positive_high_conf",
        [
            Evidence(
                evidence_id="r1",
                source_node_id="s1",
                event_type="FOMC",
                condition={},
                horizon_days=20,
                sample_count=100,
                average_return_pct=2.0,
                confidence=0.9,
                bias="gold_positive_bias",
                explanation="Strong positive signal",
            ),
            Evidence(
                evidence_id="r2",
                source_node_id="s2",
                event_type="FOMC",
                condition={},
                horizon_days=20,
                sample_count=150,
                average_return_pct=1.5,
                confidence=0.85,
                bias="gold_positive_bias",
                explanation="Positive signal",
            ),
        ],
        DECISION_STRONG_POSITIVE,
        0.85,
    ),
    (
        "all_negative_high_conf",
        [
            Evidence(
                evidence_id="r3",
                source_node_id="s3",
                event_type="CPI",
                condition={},
                horizon_days=20,
                sample_count=100,
                average_return_pct=-2.0,
                confidence=0.9,
                bias="gold_negative_bias",
                explanation="Strong negative signal",
            ),
            Evidence(
                evidence_id="r4",
                source_node_id="s4",
                event_type="CPI",
                condition={},
                horizon_days=20,
                sample_count=150,
                average_return_pct=-1.5,
                confidence=0.85,
                bias="gold_negative_bias",
                explanation="Negative signal",
            ),
        ],
        DECISION_STRONG_NEGATIVE,
        0.85,
    ),
    (
        "mixed_positive_negative",
        [
            Evidence(
                evidence_id="r5",
                source_node_id="s5",
                event_type="FOMC",
                condition={},
                horizon_days=20,
                sample_count=100,
                average_return_pct=2.0,
                confidence=0.9,
                bias="gold_positive_bias",
                explanation="Positive",
            ),
            Evidence(
                evidence_id="r6",
                source_node_id="s6",
                event_type="DXY",
                condition={},
                horizon_days=20,
                sample_count=100,
                average_return_pct=-2.0,
                confidence=0.9,
                bias="gold_negative_bias",
                explanation="Negative",
            ),
        ],
        DECISION_NEUTRAL,
        0.5,
    ),
    (
        "all_positive_low_conf",
        [
            Evidence(
                evidence_id="r7",
                source_node_id="s7",
                event_type="NFP",
                condition={},
                horizon_days=20,
                sample_count=5,
                average_return_pct=0.5,
                confidence=0.35,
                bias="gold_positive_bias",
                explanation="Weak positive",
            ),
        ],
        DECISION_NEUTRAL,
        0.35,
    ),
    (
        "empty_evidence",
        [],
        DECISION_INSUFFICIENT_EVIDENCE,
        0.0,
    ),
    (
        "single_positive",
        [
            Evidence(
                evidence_id="r8",
                source_node_id="s8",
                event_type="CPI",
                condition={},
                horizon_days=30,
                sample_count=50,
                average_return_pct=1.0,
                confidence=0.7,
                bias="gold_positive_bias",
                explanation="Single positive",
            ),
        ],
        DECISION_POSITIVE,
        0.7,
    ),
]


_CALIBRATION_SCENARIOS: list[tuple[str, list[Evidence], int, int]] = [
    (
        "cal_high_conf_positive",
        [
            Evidence(
                evidence_id="c1",
                source_node_id="s1",
                event_type="FOMC",
                condition={},
                horizon_days=20,
                sample_count=200,
                average_return_pct=3.0,
                confidence=0.95,
                bias="gold_positive_bias",
                explanation="",
            ),
        ],
        1,
        0,
    ),
    (
        "cal_low_conf_positive",
        [
            Evidence(
                evidence_id="c2",
                source_node_id="s2",
                event_type="FOMC",
                condition={},
                horizon_days=20,
                sample_count=3,
                average_return_pct=0.2,
                confidence=0.30,
                bias="gold_positive_bias",
                explanation="",
            ),
        ],
        1,
        0,
    ),
]


class ReasoningBenchmark(Benchmark):
    def __init__(self) -> None:
        super().__init__("reasoning")
        self._engine = ReasoningEngine()
        self._decision_engine = DecisionEngine()

    def run(self) -> BenchmarkResult:
        correct = 0
        total = len(_SCENARIOS)
        calibration_errors: list[float] = []

        for name, items, expected_dir, expected_conf in _SCENARIOS:
            coll = EvidenceCollection(items)
            rctx = ReasoningContext(
                event_type=items[0].event_type if items else "CPI",
            )
            chain = self._engine.reason(coll, rctx)

            dctx = DecisionContext(
                event_type=rctx.event_type,
                query="test",
            )
            decision = self._decision_engine.decide(chain, context=dctx)

            pred_dir = decision.decision_type if decision else "neutral"
            pred_conf = decision.confidence if decision else 0.0

            if pred_dir == expected_dir:
                correct += 1

            if expected_conf > 0:
                calibration_errors.append(abs(pred_conf - expected_conf))

        accuracy = correct / total if total > 0 else 0.0
        calibration_score = (
            1.0 - (sum(calibration_errors) / len(calibration_errors))
            if calibration_errors
            else 0.0
        )

        for name, items, _, _ in _CALIBRATION_SCENARIOS:
            coll = EvidenceCollection(items)
            rctx = ReasoningContext(
                event_type=items[0].event_type if items else "CPI",
            )
            chain = self._engine.reason(coll, rctx)
            dctx = DecisionContext(event_type=rctx.event_type, query="test")
            decision = self._decision_engine.decide(chain, context=dctx)
            conf = decision.confidence if decision else 0.0
            if items and items[0].confidence > 0.5 and conf <= 0.5:
                calibration_errors.append(0.3)
            elif items and items[0].confidence < 0.4 and conf > 0.6:
                calibration_errors.append(0.3)

        return self._result(
            metrics=[
                self._metric(
                    "reasoning_accuracy",
                    accuracy,
                    "ratio",
                    "Fraction of scenarios where decision type matches expected",
                ),
                self._metric(
                    "confidence_calibration",
                    max(0.0, 1.0 - (sum(calibration_errors) / max(len(calibration_errors), 1))),
                    "score",
                    "1.0 - average absolute confidence error across scenarios",
                ),
                self._metric(
                    "num_scenarios",
                    float(total),
                    "count",
                    "Total number of reasoning scenarios evaluated",
                ),
                self._metric(
                    "num_correct",
                    float(correct),
                    "count",
                    "Number of scenarios with correct decision type",
                ),
            ],
            thresholds={
                "reasoning_accuracy": (0.8, "gte"),
            },
        )
