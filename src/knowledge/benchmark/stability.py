from __future__ import annotations

from knowledge.benchmark.base import Benchmark, BenchmarkResult
from knowledge.evidence.collection import EvidenceCollection
from knowledge.evidence.evidence import Evidence
from knowledge.evidence.weighting import EvidenceWeighter
from knowledge.reasoning.cross_event import CrossEventAnalyzer
from knowledge.reasoning.engine import ReasoningEngine
from knowledge.reasoning.context import ReasoningContext
from knowledge.decision.engine import DecisionEngine
from knowledge.decision.context import DecisionContext


def _make_collection(
    conf_suffix: float = 0.0,
) -> EvidenceCollection:
    return EvidenceCollection([
        Evidence(
            evidence_id=f"cpi_a{conf_suffix}",
            source_node_id="s1",
            event_type="CPI",
            condition={},
            horizon_days=20,
            sample_count=100,
            average_return_pct=1.5,
            confidence=min(0.9, 0.7 + conf_suffix),
            bias="gold_positive_bias",
            explanation="test",
        ),
        Evidence(
            evidence_id=f"nfp_b{conf_suffix}",
            source_node_id="s2",
            event_type="NFP",
            condition={},
            horizon_days=30,
            sample_count=200,
            average_return_pct=0.8,
            confidence=min(0.9, 0.65 + conf_suffix),
            bias="gold_positive_bias",
            explanation="test",
        ),
    ])


class StabilityBenchmark(Benchmark):
    def __init__(self) -> None:
        super().__init__("stability")

    def run(self) -> BenchmarkResult:
        variations = [-0.1, 0.0, 0.1, 0.2]
        engine = ReasoningEngine()
        dc_engine = DecisionEngine()
        weighter = EvidenceWeighter()
        analyzer = CrossEventAnalyzer()

        decisions: list[str] = []
        consensuses: list[str] = []
        confidences: list[float] = []

        for v in variations:
            coll = _make_collection(conf_suffix=v)
            rctx = ReasoningContext(event_type="CPI")
            chain = engine.reason(coll, rctx)
            dctx = DecisionContext(event_type="CPI", query="test")
            dec = dc_engine.decide(chain, context=dctx)
            decisions.append(dec.decision_type)

            ce = analyzer.analyze(coll)
            consensuses.append(ce.overall_consensus)
            confidences.append(ce.consensus_confidence)

        dominant_decision = max(set(decisions), key=decisions.count)
        decision_stability = (
            decisions.count(dominant_decision) / len(decisions)
            if decisions
            else 0.0
        )

        dominant_consensus = max(set(consensuses), key=consensuses.count)
        consensus_stability = (
            consensuses.count(dominant_consensus) / len(consensuses)
            if consensuses
            else 0.0
        )

        conf_range = max(confidences) - min(confidences) if confidences else 0.0
        conf_stability = max(0.0, 1.0 - conf_range)

        return self._result(
            metrics=[
                self._metric(
                    "decision_stability",
                    decision_stability,
                    "ratio",
                    "Fraction of variations producing the same decision type vs dominant",
                ),
                self._metric(
                    "consensus_stability",
                    consensus_stability,
                    "ratio",
                    "Fraction of variations producing the same consensus vs dominant",
                ),
                self._metric(
                    "confidence_stability",
                    conf_stability,
                    "score",
                    "1.0 - range of confidence values across variations",
                ),
            ],
            thresholds={
                "decision_stability": (0.5, "gte"),
                "consensus_stability": (0.5, "gte"),
            },
        )
