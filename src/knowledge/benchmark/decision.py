from __future__ import annotations

from knowledge.benchmark.base import Benchmark, BenchmarkResult
from knowledge.decision.context import DecisionContext
from knowledge.decision.engine import DecisionEngine
from knowledge.reasoning.chain import ReasoningChain
from knowledge.reasoning.context import ReasoningContext
from knowledge.reasoning.step import ReasoningStep, STEP_CONCLUSION


def _make_chain(
    chain_id: str,
    overall_conf: float,
    final_conclusion: str = "positive directional bias",
    avg_return_pct: float = 0.0,
) -> ReasoningChain:
    return ReasoningChain(
        chain_id=chain_id,
        context=ReasoningContext(event_type="CPI"),
        steps=(
            ReasoningStep(
                step_id=f"{chain_id}_s1",
                step_type=STEP_CONCLUSION,
                conclusion=final_conclusion,
                confidence=overall_conf,
                supporting_evidence_ids=("ev_1",),
                details={"avg_return_pct": avg_return_pct},
            ),
        ),
        final_conclusion=final_conclusion,
        overall_confidence=overall_conf,
        evidence_count=1,
    )


def _same_chain() -> bool:
    engine = DecisionEngine()
    chain_a = _make_chain("chain_same_1", 0.8, avg_return_pct=2.0)
    chain_b = _make_chain("chain_same_2", 0.8, avg_return_pct=2.0)
    dctx = DecisionContext(event_type="CPI", query="test")
    da = engine.decide(chain_a, context=dctx)
    db = engine.decide(chain_b, context=dctx)
    return (
        da.decision_type == db.decision_type
        and abs(da.confidence - db.confidence) < 0.01
    )


def _different_chains() -> bool:
    engine = DecisionEngine()
    chain_pos = _make_chain("chain_pos", 0.9, "positive directional bias", avg_return_pct=2.5)
    chain_neg = _make_chain("chain_neg", 0.8, "negative directional bias", avg_return_pct=-2.0)
    dctx = DecisionContext(event_type="CPI", query="test")
    dp = engine.decide(chain_pos, context=dctx)
    dn = engine.decide(chain_neg, context=dctx)
    return dp.decision_type != dn.decision_type


def _stability_under_perturbation() -> float:
    engine = DecisionEngine()
    base = _make_chain("base", 0.8, "positive directional bias", avg_return_pct=2.0)
    dctx = DecisionContext(event_type="CPI", query="test")
    base_d = engine.decide(base, context=dctx)

    variations = [
        ("positive directional bias", 0.75, 2.0),
        ("positive directional bias", 0.85, 1.5),
        ("positive directional bias", 0.6, 0.5),
    ]
    stable_count = sum(
        1
        for concl, conf, ret in variations
        if engine.decide(
            _make_chain("pert", conf, concl, avg_return_pct=ret), context=dctx
        ).decision_type
        == base_d.decision_type
    )

    return stable_count / len(variations) if variations else 0.0


def _no_chain() -> bool:
    engine = DecisionEngine()
    empty = ReasoningChain(
        chain_id="empty",
        context=ReasoningContext(event_type="CPI"),
        steps=(),
        final_conclusion="",
        overall_confidence=0.0,
        evidence_count=0,
    )
    d = engine.decide(empty)
    return d is not None


class DecisionBenchmark(Benchmark):
    def __init__(self) -> None:
        super().__init__("decision")

    def run(self) -> BenchmarkResult:
        same = _same_chain()
        diff = _different_chains()
        stab = _stability_under_perturbation()
        no = _no_chain()

        tests_passed = sum([same, diff, no])
        tests_total = 3

        return self._result(
            metrics=[
                self._metric(
                    "decision_consistency",
                    1.0 if same else 0.0,
                    "binary",
                    "Identical inputs produce identical decision types",
                ),
                self._metric(
                    "decision_discrimination",
                    1.0 if diff else 0.0,
                    "binary",
                    "Different inputs produce different decision types",
                ),
                self._metric(
                    "decision_stability",
                    stab,
                    "ratio",
                    "Fraction of perturbed inputs that preserve decision type",
                ),
                self._metric(
                    "decision_accuracy",
                    tests_passed / tests_total if tests_total > 0 else 0.0,
                    "ratio",
                    "Fraction of decision property tests passed",
                ),
            ],
            thresholds={
                "decision_consistency": (1.0, "gte"),
                "decision_stability": (0.5, "gte"),
                "decision_accuracy": (0.66, "gte"),
            },
        )
