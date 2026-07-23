import json
from pathlib import Path

import pytest

from knowledge.evidence.evidence import Evidence
from knowledge.evidence.collection import EvidenceCollection
from knowledge.evidence.weighting import EvidenceWeighter
from knowledge.reasoning.context import ReasoningContext
from knowledge.reasoning.step import (
    ReasoningStep,
    STEP_EVIDENCE_REVIEW,
    STEP_COMPARISON,
    STEP_AGGREGATION,
    STEP_CONCLUSION,
)
from knowledge.reasoning.chain import ReasoningChain
from knowledge.reasoning.engine import ReasoningEngine
from knowledge.reasoning.repository import ReasoningRepository


# ── Fixtures ────────────────────────────────────────────────────────────────

def cpi_evidence() -> EvidenceCollection:
    return EvidenceCollection([
        Evidence(
            evidence_id="CPI_GOLD_up_5D",
            source_node_id="n1",
            event_type="CPI",
            condition={"cpi_pressure": "up"},
            horizon_days=5,
            sample_count=50,
            average_return_pct=1.5,
            confidence=0.85,
            bias="gold_positive_bias",
            explanation="CPI up → gold up over 5 days.",
        ),
        Evidence(
            evidence_id="CPI_GOLD_up_20D",
            source_node_id="n2",
            event_type="CPI",
            condition={"cpi_pressure": "up"},
            horizon_days=20,
            sample_count=50,
            average_return_pct=2.0,
            confidence=0.75,
            bias="gold_positive_bias",
            explanation="CPI up → gold up over 20 days.",
        ),
        Evidence(
            evidence_id="CPI_GOLD_down_5D",
            source_node_id="n3",
            event_type="CPI",
            condition={"cpi_pressure": "down"},
            horizon_days=5,
            sample_count=30,
            average_return_pct=-1.2,
            confidence=0.60,
            bias="gold_negative_bias",
            explanation="CPI down → gold down over 5 days.",
        ),
    ])


def single_evidence() -> EvidenceCollection:
    return EvidenceCollection([
        Evidence(
            evidence_id="CPI_GOLD_up_5D",
            source_node_id="n1",
            event_type="CPI",
            condition={"cpi_pressure": "up"},
            horizon_days=5,
            sample_count=50,
            average_return_pct=1.5,
            confidence=0.85,
            bias="gold_positive_bias",
            explanation="CPI up → gold up over 5 days.",
        ),
    ])


def mixed_event_evidence() -> EvidenceCollection:
    return EvidenceCollection([
        Evidence(
            evidence_id="CPI_GOLD_up_5D",
            source_node_id="n1",
            event_type="CPI",
            condition={"cpi_pressure": "up"},
            horizon_days=5,
            sample_count=50,
            average_return_pct=1.5,
            confidence=0.85,
            bias="gold_positive_bias",
            explanation="CPI up → gold up over 5 days.",
        ),
        Evidence(
            evidence_id="NFP_GOLD_positive_5D",
            source_node_id="n2",
            event_type="NFP",
            condition={"nfp_surprise": "positive"},
            horizon_days=5,
            sample_count=20,
            average_return_pct=0.8,
            confidence=0.45,
            bias="mixed_or_context_dependent",
            explanation="NFP positive → gold mixed.",
        ),
    ])


# ── ReasoningContext ────────────────────────────────────────────────────────

def test_context_creation() -> None:
    ctx = ReasoningContext(event_type="CPI", condition={"x": "y"}, horizon_days=5)
    assert ctx.event_type == "CPI"
    assert ctx.condition == {"x": "y"}
    assert ctx.horizon_days == 5


def test_context_defaults() -> None:
    ctx = ReasoningContext(event_type="CPI")
    assert ctx.condition is None
    assert ctx.horizon_days is None
    assert ctx.metadata == {}


# ── ReasoningStep ──────────────────────────────────────────────────────────

def test_step_creation() -> None:
    step = ReasoningStep(
        step_id="s1",
        step_type=STEP_EVIDENCE_REVIEW,
        conclusion="test conclusion",
        confidence=0.85,
        supporting_evidence_ids=("e1", "e2"),
    )
    assert step.step_id == "s1"
    assert step.step_type == STEP_EVIDENCE_REVIEW
    assert step.conclusion == "test conclusion"
    assert step.supporting_evidence_ids == ("e1", "e2")


def test_step_type_constants() -> None:
    assert STEP_EVIDENCE_REVIEW == "evidence_review"
    assert STEP_COMPARISON == "comparison"
    assert STEP_AGGREGATION == "aggregation"
    assert STEP_CONCLUSION == "conclusion"


# ── ReasoningChain ─────────────────────────────────────────────────────────

def test_chain_creation() -> None:
    ctx = ReasoningContext(event_type="CPI")
    step = ReasoningStep(
        step_id="s1", step_type=STEP_EVIDENCE_REVIEW, conclusion="c",
        confidence=0.8, supporting_evidence_ids=("e1",),
    )
    chain = ReasoningChain(
        chain_id="reason_CPI",
        context=ctx,
        steps=(step,),
        final_conclusion="final",
        overall_confidence=0.8,
        evidence_count=1,
    )
    assert chain.chain_id == "reason_CPI"
    assert len(chain.steps) == 1
    assert chain.final_conclusion == "final"


# ── ReasoningEngine — Basic ────────────────────────────────────────────────

def test_engine_empty_evidence() -> None:
    engine = ReasoningEngine()
    ctx = ReasoningContext(event_type="CPI")
    chain = engine.reason(EvidenceCollection(), ctx)
    assert chain.chain_id == "reason_CPI"
    assert chain.evidence_count == 0
    assert len(chain.steps) == 0
    assert chain.overall_confidence == 0.0
    assert chain.final_conclusion == "No evidence to reason from."


def test_engine_single_evidence() -> None:
    engine = ReasoningEngine()
    ctx = ReasoningContext(event_type="CPI")
    chain = engine.reason(single_evidence(), ctx)
    assert chain.evidence_count == 1
    assert len(chain.steps) == 3  # review + aggregation + conclusion
    assert chain.steps[0].step_type == STEP_EVIDENCE_REVIEW
    assert chain.steps[1].step_type == STEP_AGGREGATION
    assert chain.steps[2].step_type == STEP_CONCLUSION
    assert chain.overall_confidence == 0.85
    assert "positive" in chain.final_conclusion


def test_engine_multiple_evidence() -> None:
    engine = ReasoningEngine()
    ctx = ReasoningContext(event_type="CPI")
    chain = engine.reason(cpi_evidence(), ctx)
    assert chain.evidence_count == 3
    assert len(chain.steps) == 6  # 3 reviews + 1 comparison + 1 aggregation + 1 conclusion

    # First three steps should be evidence reviews
    for i in range(3):
        assert chain.steps[i].step_type == STEP_EVIDENCE_REVIEW
    assert chain.steps[3].step_type == STEP_COMPARISON
    assert chain.steps[4].step_type == STEP_AGGREGATION
    assert chain.steps[5].step_type == STEP_CONCLUSION


def test_engine_chain_id() -> None:
    engine = ReasoningEngine()
    ctx = ReasoningContext(event_type="CPI", condition={"cpi_pressure": "up"}, horizon_days=5)
    chain = engine.reason(cpi_evidence(), ctx)
    assert chain.chain_id == "reason_CPI_up_5"


# ── ReasoningEngine — Step Content ─────────────────────────────────────────

def test_evidence_review_step_content() -> None:
    engine = ReasoningEngine()
    chain = engine.reason(single_evidence(), ReasoningContext(event_type="CPI"))
    step = chain.steps[0]
    assert step.step_type == STEP_EVIDENCE_REVIEW
    assert "CPI" in step.conclusion
    assert "1.500" in step.conclusion
    assert "5 days" in step.conclusion
    assert "0.850" in step.conclusion
    assert step.supporting_evidence_ids == ("CPI_GOLD_up_5D",)
    assert step.details["event_type"] == "CPI"
    assert step.details["average_return_pct"] == 1.5


def test_comparison_step_detects_opposite_directions() -> None:
    engine = ReasoningEngine()
    chain = engine.reason(cpi_evidence(), ReasoningContext(event_type="CPI"))
    comp = chain.steps[3]
    assert comp.step_type == STEP_COMPARISON
    assert "Comparing conditions within CPI" in comp.conclusion
    assert "positive" in comp.conclusion
    assert "negative" in comp.conclusion


def test_comparison_step_single_event_type_no_duplicate() -> None:
    engine = ReasoningEngine()
    chain = engine.reason(single_evidence(), ReasoningContext(event_type="CPI"))
    # No comparison step when only one event_type with single evidence
    types = [s.step_type for s in chain.steps]
    assert STEP_COMPARISON not in types


def test_aggregation_step_content() -> None:
    engine = ReasoningEngine()
    chain = engine.reason(cpi_evidence(), ReasoningContext(event_type="CPI"))
    agg = chain.steps[4]
    assert agg.step_type == STEP_AGGREGATION
    assert "3 evidence items" in agg.conclusion
    assert len(agg.supporting_evidence_ids) == 3
    assert agg.details["count"] == 3


def test_conclusion_step_references_context() -> None:
    engine = ReasoningEngine()
    ctx = ReasoningContext(event_type="CPI", condition={"cpi_pressure": "up"}, horizon_days=5)
    chain = engine.reason(cpi_evidence(), ctx)
    conc = chain.steps[5]
    assert conc.step_type == STEP_CONCLUSION
    assert "CPI" in conc.conclusion
    assert "cpi_pressure=up" in conc.conclusion
    assert "5 days" in conc.conclusion
    assert conc.details["context_event_type"] == "CPI"
    assert conc.details["context_horizon_days"] == 5


# ── ReasoningEngine — Mixed Events ─────────────────────────────────────────

def test_engine_mixed_event_types() -> None:
    engine = ReasoningEngine()
    ctx = ReasoningContext(event_type="NFP")
    chain = engine.reason(mixed_event_evidence(), ctx)
    # 2 reviews + 1 comparison (each event_type has 1 evidence, so no comparison) + 1 agg + 1 conclusion
    assert len(chain.steps) == 4
    assert chain.steps[0].step_type == STEP_EVIDENCE_REVIEW
    assert chain.steps[1].step_type == STEP_EVIDENCE_REVIEW
    assert chain.steps[2].step_type == STEP_AGGREGATION
    assert chain.steps[3].step_type == STEP_CONCLUSION


# ── ReasoningEngine — Confidence ───────────────────────────────────────────

def test_overall_confidence_is_weighted() -> None:
    engine = ReasoningEngine()
    evidence = cpi_evidence()
    chain = engine.reason(evidence, ReasoningContext(event_type="CPI"))
    wa = EvidenceWeighter().weigh(evidence)
    assert chain.overall_confidence == pytest.approx(wa.weighted_avg_confidence, rel=1e-6)
    assert chain.overall_confidence != round((0.85 + 0.75 + 0.60) / 3, 6)


# ── ReasoningRepository ────────────────────────────────────────────────────

def test_repository_save_and_load_round_trip(tmp_path: Path) -> None:
    engine = ReasoningEngine()
    ctx = ReasoningContext(event_type="CPI", condition={"cpi_pressure": "up"}, horizon_days=5)
    chain = engine.reason(cpi_evidence(), ctx)

    path = tmp_path / "reason.json"
    ReasoningRepository().save(chain, path)
    assert path.exists()

    loaded = ReasoningRepository().load(path)
    assert loaded.chain_id == chain.chain_id
    assert loaded.context.event_type == "CPI"
    assert loaded.context.condition == {"cpi_pressure": "up"}
    assert loaded.evidence_count == 3
    assert len(loaded.steps) == 6
    assert loaded.final_conclusion == chain.final_conclusion
    assert loaded.overall_confidence == chain.overall_confidence


def test_repository_preserves_step_details(tmp_path: Path) -> None:
    chain = ReasoningEngine().reason(single_evidence(), ReasoningContext(event_type="CPI"))
    path = tmp_path / "details.json"
    ReasoningRepository().save(chain, path)
    loaded = ReasoningRepository().load(path)
    assert loaded.steps[0].details["average_return_pct"] == 1.5


def test_repository_save_empty_chain(tmp_path: Path) -> None:
    ctx = ReasoningContext(event_type="CPI")
    chain = ReasoningEngine().reason(EvidenceCollection(), ctx)
    path = tmp_path / "empty.json"
    ReasoningRepository().save(chain, path)
    loaded = ReasoningRepository().load(path)
    assert loaded.evidence_count == 0
    assert len(loaded.steps) == 0


def test_repository_file_format(tmp_path: Path) -> None:
    chain = ReasoningEngine().reason(single_evidence(), ReasoningContext(event_type="CPI"))
    path = tmp_path / "format.json"
    ReasoningRepository().save(chain, path)

    raw = json.loads(path.read_text())
    assert "chain_id" in raw
    assert "context" in raw
    assert "steps" in raw
    assert "final_conclusion" in raw
    assert "overall_confidence" in raw
    assert len(raw["steps"]) == 3
    assert raw["steps"][0]["step_type"] == STEP_EVIDENCE_REVIEW


# ── Edge Cases ──────────────────────────────────────────────────────────────

def test_reasoning_with_all_positive_evidence() -> None:
    evs = EvidenceCollection([
        Evidence(
            evidence_id="e1", source_node_id="n1", event_type="CPI",
            condition={"x": "a"}, horizon_days=5, sample_count=10,
            average_return_pct=2.0, confidence=0.8, bias="positive",
            explanation="",
        ),
        Evidence(
            evidence_id="e2", source_node_id="n2", event_type="CPI",
            condition={"x": "b"}, horizon_days=5, sample_count=10,
            average_return_pct=1.0, confidence=0.7, bias="positive",
            explanation="",
        ),
    ])
    chain = ReasoningEngine().reason(evs, ReasoningContext(event_type="CPI"))
    # Comparison should note all conditions point same direction
    comp = chain.steps[2]
    assert comp.step_type == STEP_COMPARISON
    assert "same direction" in comp.conclusion


def test_conclusion_detects_strong_direction() -> None:
    evs = EvidenceCollection([
        Evidence(
            evidence_id="e1", source_node_id="n1", event_type="CPI",
            condition={}, horizon_days=5, sample_count=100,
            average_return_pct=3.0, confidence=0.9, bias="positive",
            explanation="",
        ),
    ])
    ctx = ReasoningContext(event_type="CPI")
    chain = ReasoningEngine().reason(evs, ctx)
    assert "positive directional bias" in chain.final_conclusion


def test_conclusion_detects_negative_direction() -> None:
    evs = EvidenceCollection([
        Evidence(
            evidence_id="e1", source_node_id="n1", event_type="CPI",
            condition={}, horizon_days=5, sample_count=100,
            average_return_pct=-3.0, confidence=0.9, bias="negative",
            explanation="",
        ),
    ])
    chain = ReasoningEngine().reason(evs, ReasoningContext(event_type="CPI"))
    assert "negative directional bias" in chain.final_conclusion


def test_step_ids_are_sequential() -> None:
    chain = ReasoningEngine().reason(cpi_evidence(), ReasoningContext(event_type="CPI"))
    for i, step in enumerate(chain.steps):
        assert step.step_id == f"step_{i}"


# ── CER-002: Evidence Attribution ────────────────────────────────────────


class TestAttribution:
    """Evidence attribution by event_type through the full reasoning pipeline."""

    def test_attribution_sums_to_one(self) -> None:
        engine = ReasoningEngine()
        ctx = ReasoningContext(event_type="CPI")
        chain = engine.reason(mixed_event_evidence(), ctx)
        total = sum(chain.attribution.values())
        assert abs(total - 1.0) < 1e-6

    def test_attribution_deterministic_ordering(self) -> None:
        engine = ReasoningEngine()
        ctx = ReasoningContext(event_type="CPI")
        chain1 = engine.reason(mixed_event_evidence(), ctx)
        chain2 = engine.reason(mixed_event_evidence(), ctx)
        assert chain1.attribution == chain2.attribution

    def test_single_event_attribution(self) -> None:
        engine = ReasoningEngine()
        ctx = ReasoningContext(event_type="CPI")
        chain = engine.reason(cpi_evidence(), ctx)
        assert chain.attribution == {"CPI": 1.0}

    def test_cross_event_attribution(self) -> None:
        engine = ReasoningEngine()
        ctx = ReasoningContext(event_type="CPI")
        chain = engine.reason(mixed_event_evidence(), ctx)
        assert "CPI" in chain.attribution
        assert "NFP" in chain.attribution
        total = sum(chain.attribution.values())
        assert abs(total - 1.0) < 1e-6

    def test_zero_evidence_attribution(self) -> None:
        engine = ReasoningEngine()
        ctx = ReasoningContext(event_type="CPI")
        chain = engine.reason(EvidenceCollection(), ctx)
        assert chain.attribution == {}

    def test_attribution_in_aggregation_step_details(self) -> None:
        engine = ReasoningEngine()
        ctx = ReasoningContext(event_type="CPI")
        chain = engine.reason(mixed_event_evidence(), ctx)
        agg = [s for s in chain.steps if s.step_type == STEP_AGGREGATION][0]
        attr = agg.details.get("attribution", {})
        assert "CPI" in attr
        assert "NFP" in attr
        total = sum(attr.values())
        assert abs(total - 1.0) < 1e-6

    def test_backward_compatibility_no_attribution_breakage(self) -> None:
        engine = ReasoningEngine()
        ctx = ReasoningContext(event_type="CPI")
        chain = engine.reason(single_evidence(), ctx)
        assert chain.chain_id == "reason_CPI"
        assert chain.evidence_count == 1
        assert len(chain.steps) == 3
        assert chain.steps[0].step_type == STEP_EVIDENCE_REVIEW
        assert chain.steps[1].step_type == STEP_AGGREGATION
        assert chain.steps[2].step_type == STEP_CONCLUSION

    def test_multi_event_conclusion_contains_contribution(self) -> None:
        engine = ReasoningEngine()
        ctx = ReasoningContext(event_type="CPI")
        chain = engine.reason(mixed_event_evidence(), ctx)
        assert "Cross-event evidence contribution" in chain.final_conclusion
        assert "CPI" in chain.final_conclusion
        assert "NFP" in chain.final_conclusion

    def test_single_event_conclusion_no_contribution_block(self) -> None:
        engine = ReasoningEngine()
        ctx = ReasoningContext(event_type="CPI")
        chain = engine.reason(cpi_evidence(), ctx)
        assert "Cross-event" not in chain.final_conclusion
