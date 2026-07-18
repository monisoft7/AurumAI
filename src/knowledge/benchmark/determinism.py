from __future__ import annotations

from knowledge.benchmark.base import Benchmark, BenchmarkResult
from knowledge.evidence.collection import EvidenceCollection
from knowledge.evidence.evidence import Evidence
from knowledge.evidence.weighting import EvidenceWeighter
from knowledge.reasoning.cross_event import CrossEventAnalyzer
from knowledge.reasoning.engine import ReasoningEngine
from knowledge.reasoning.step import STEP_AGGREGATION, STEP_CONCLUSION
from knowledge.decision.engine import DecisionEngine
from knowledge.decision.context import DecisionContext
from knowledge.reasoning.context import ReasoningContext


def _make_collection() -> EvidenceCollection:
    return EvidenceCollection([
        Evidence(
            evidence_id="d1",
            source_node_id="s1",
            event_type="CPI",
            condition={},
            horizon_days=20,
            sample_count=100,
            average_return_pct=1.5,
            confidence=0.8,
            bias="gold_positive_bias",
            explanation="test",
        ),
        Evidence(
            evidence_id="d2",
            source_node_id="s2",
            event_type="NFP",
            condition={},
            horizon_days=30,
            sample_count=200,
            average_return_pct=0.8,
            confidence=0.7,
            bias="gold_positive_bias",
            explanation="test",
        ),
    ])


class DeterminismBenchmark(Benchmark):
    def __init__(self) -> None:
        super().__init__("determinism")

    def run(self) -> BenchmarkResult:
        coll = _make_collection()

        w1 = EvidenceWeighter().weigh(coll)
        w2 = EvidenceWeighter().weigh(coll)
        weighting_deterministic = (
            w1.weighted_avg_return == w2.weighted_avg_return
            and w1.weighted_avg_confidence == w2.weighted_avg_confidence
            and w1.effective_sample_size == w2.effective_sample_size
        )

        ce1 = CrossEventAnalyzer().analyze(coll)
        ce2 = CrossEventAnalyzer().analyze(coll)
        cross_event_deterministic = (
            ce1.overall_consensus == ce2.overall_consensus
            and ce1.consensus_confidence == ce2.consensus_confidence
            and len(ce1.conflicts) == len(ce2.conflicts)
        )

        engine = ReasoningEngine()
        rctx = ReasoningContext(event_type="CPI")
        dc_engine = DecisionEngine()

        chain1 = engine.reason(coll, rctx)
        chain2 = engine.reason(coll, rctx)
        chain1_d = dc_engine.decide(chain1)
        chain2_d = dc_engine.decide(chain2)

        def _extract_avg_return(c):
            for s in reversed(c.steps):
                if s.step_type in (STEP_AGGREGATION, STEP_CONCLUSION):
                    val = s.details.get("avg_return_pct") or s.details.get("average_return_pct")
                    if val is not None:
                        return val
            return 0.0

        reasoning_deterministic = (
            chain1.overall_confidence == chain2.overall_confidence
            and _extract_avg_return(chain1) == _extract_avg_return(chain2)
            and chain1_d.decision_type == chain2_d.decision_type
            and chain1_d.confidence == chain2_d.confidence
        )

        all_deterministic = (
            weighting_deterministic
            and cross_event_deterministic
            and reasoning_deterministic
        )

        return self._result(
            metrics=[
                self._metric(
                    "determinism_score",
                    1.0 if all_deterministic else 0.0,
                    "binary",
                    "All components produce identical outputs across repeat runs",
                ),
                self._metric(
                    "weighting_deterministic",
                    1.0 if weighting_deterministic else 0.0,
                    "binary",
                    "EvidenceWeighter produces identical results on re-run",
                ),
                self._metric(
                    "cross_event_deterministic",
                    1.0 if cross_event_deterministic else 0.0,
                    "binary",
                    "CrossEventAnalyzer produces identical results on re-run",
                ),
                self._metric(
                    "reasoning_deterministic",
                    1.0 if reasoning_deterministic else 0.0,
                    "binary",
                    "ReasoningEngine produces identical results on re-run",
                ),
            ],
            thresholds={
                "determinism_score": (1.0, "gte"),
            },
        )
