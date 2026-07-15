import json
from pathlib import Path

import pytest

from knowledge.evidence.evidence import Evidence
from knowledge.evidence.collection import EvidenceCollection
from knowledge.reasoning.context import ReasoningContext as RCtx
from knowledge.reasoning.engine import ReasoningEngine
from knowledge.reasoning.chain import ReasoningChain
from knowledge.reasoning.step import ReasoningStep, STEP_AGGREGATION, STEP_CONCLUSION
from knowledge.decision.context import DecisionContext
from knowledge.decision.decision import (
    Decision,
    DECISION_STRONG_POSITIVE,
    DECISION_POSITIVE,
    DECISION_NEUTRAL,
    DECISION_NEGATIVE,
    DECISION_STRONG_NEGATIVE,
    VALID_DECISION_TYPES,
)
from knowledge.decision.engine import DecisionEngine
from knowledge.decision.validator import DecisionValidator
from knowledge.decision.repository import DecisionRepository


# ── Helpers ─────────────────────────────────────────────────────────────────

def make_chain(avg_return: float, confidence: float, evidence_count: int = 1) -> ReasoningChain:
    ctx = RCtx(event_type="CPI")
    steps = (
        ReasoningStep(
            step_id="step_0",
            step_type=STEP_AGGREGATION,
            conclusion="aggregated",
            confidence=confidence,
            supporting_evidence_ids=("e1",),
            details={"average_return_pct": avg_return, "count": evidence_count},
        ),
        ReasoningStep(
            step_id="step_1",
            step_type=STEP_CONCLUSION,
            conclusion="concluded",
            confidence=confidence,
            supporting_evidence_ids=("e1",),
            details={"average_return_pct": avg_return},
        ),
    )
    return ReasoningChain(
        chain_id=f"reason_CPI_{avg_return}_{confidence}",
        context=ctx,
        steps=steps,
        final_conclusion="test conclusion",
        overall_confidence=confidence,
        evidence_count=evidence_count,
    )


def make_evidence(avg_return: float, confidence: float) -> EvidenceCollection:
    return EvidenceCollection([
        Evidence(
            evidence_id="e1",
            source_node_id="n1",
            event_type="CPI",
            condition={},
            horizon_days=5,
            sample_count=100,
            average_return_pct=avg_return,
            confidence=confidence,
            bias="positive" if avg_return > 0 else "negative",
            explanation="",
        ),
    ])


# ── Decision Type Constants ────────────────────────────────────────────────

def test_decision_type_values() -> None:
    assert DECISION_STRONG_POSITIVE == "STRONG_POSITIVE"
    assert DECISION_POSITIVE == "POSITIVE"
    assert DECISION_NEUTRAL == "NEUTRAL"
    assert DECISION_NEGATIVE == "NEGATIVE"
    assert DECISION_STRONG_NEGATIVE == "STRONG_NEGATIVE"
    assert len(VALID_DECISION_TYPES) == 5


# ── DecisionContext ────────────────────────────────────────────────────────

def test_decision_context_creation() -> None:
    ctx = DecisionContext(event_type="CPI", query="what is the outlook?")
    assert ctx.event_type == "CPI"
    assert ctx.query == "what is the outlook?"


def test_decision_context_defaults() -> None:
    ctx = DecisionContext(event_type="CPI")
    assert ctx.query == ""
    assert ctx.metadata == {}


# ── Decision ───────────────────────────────────────────────────────────────

def test_decision_creation() -> None:
    ctx = DecisionContext(event_type="CPI")
    d = Decision(
        decision_id="dec_reason_CPI",
        decision_type=DECISION_POSITIVE,
        confidence=0.75,
        reasoning_chain_id="reason_CPI",
        evidence_count=3,
        explanation="Evidence supports positive outlook.",
        context=ctx,
    )
    assert d.decision_id == "dec_reason_CPI"
    assert d.decision_type == DECISION_POSITIVE
    assert d.confidence == 0.75
    assert d.evidence_count == 3


# ── DecisionValidator ──────────────────────────────────────────────────────

def test_validator_valid_decision() -> None:
    ctx = DecisionContext(event_type="CPI")
    d = Decision(
        decision_id="d1",
        decision_type=DECISION_POSITIVE,
        confidence=0.75,
        reasoning_chain_id="rc1",
        evidence_count=3,
        explanation="good",
        context=ctx,
    )
    assert DecisionValidator.is_valid(d)
    assert DecisionValidator.validate(d) == {}


def test_validator_invalid_type() -> None:
    ctx = DecisionContext(event_type="CPI")
    d = Decision(
        decision_id="d1",
        decision_type="INVALID",
        confidence=0.5,
        reasoning_chain_id="rc1",
        evidence_count=1,
        explanation="test",
        context=ctx,
    )
    assert not DecisionValidator.is_valid(d)
    errors = DecisionValidator.validate(d)
    assert "decision_type" in errors


def test_validator_confidence_out_of_range() -> None:
    ctx = DecisionContext(event_type="CPI")
    d = Decision(
        decision_id="d1",
        decision_type=DECISION_POSITIVE,
        confidence=1.5,
        reasoning_chain_id="rc1",
        evidence_count=1,
        explanation="test",
        context=ctx,
    )
    errors = DecisionValidator.validate(d)
    assert "confidence" in errors


def test_validator_negative_confidence() -> None:
    ctx = DecisionContext(event_type="CPI")
    d = Decision(
        decision_id="d1",
        decision_type=DECISION_POSITIVE,
        confidence=-0.1,
        reasoning_chain_id="rc1",
        evidence_count=1,
        explanation="test",
        context=ctx,
    )
    errors = DecisionValidator.validate(d)
    assert "confidence" in errors


def test_validator_empty_chain_id() -> None:
    ctx = DecisionContext(event_type="CPI")
    d = Decision(
        decision_id="d1",
        decision_type=DECISION_POSITIVE,
        confidence=0.5,
        reasoning_chain_id="",
        evidence_count=1,
        explanation="test",
        context=ctx,
    )
    errors = DecisionValidator.validate(d)
    assert "reasoning_chain_id" in errors


def test_validator_negative_evidence_count() -> None:
    ctx = DecisionContext(event_type="CPI")
    d = Decision(
        decision_id="d1",
        decision_type=DECISION_POSITIVE,
        confidence=0.5,
        reasoning_chain_id="rc1",
        evidence_count=-1,
        explanation="test",
        context=ctx,
    )
    errors = DecisionValidator.validate(d)
    assert "evidence_count" in errors


def test_validator_empty_explanation() -> None:
    ctx = DecisionContext(event_type="CPI")
    d = Decision(
        decision_id="d1",
        decision_type=DECISION_POSITIVE,
        confidence=0.5,
        reasoning_chain_id="rc1",
        evidence_count=1,
        explanation="",
        context=ctx,
    )
    errors = DecisionValidator.validate(d)
    assert "explanation" in errors


def test_validator_multiple_errors() -> None:
    ctx = DecisionContext(event_type="CPI")
    d = Decision(
        decision_id="d1",
        decision_type="BAD",
        confidence=2.0,
        reasoning_chain_id="",
        evidence_count=-5,
        explanation="",
        context=ctx,
    )
    errors = DecisionValidator.validate(d)
    assert len(errors) >= 4


# ── DecisionEngine — Classification ────────────────────────────────────────

def test_engine_strong_positive() -> None:
    chain = make_chain(avg_return=2.0, confidence=0.8)
    d = DecisionEngine().decide(chain)
    assert d.decision_type == DECISION_STRONG_POSITIVE
    assert d.evidence_count == 1
    assert d.reasoning_chain_id == chain.chain_id


def test_engine_strong_positive_edge() -> None:
    chain = make_chain(avg_return=1.001, confidence=0.7)
    d = DecisionEngine().decide(chain)
    assert d.decision_type == DECISION_STRONG_POSITIVE


def test_engine_positive() -> None:
    chain = make_chain(avg_return=0.5, confidence=0.6)
    d = DecisionEngine().decide(chain)
    assert d.decision_type == DECISION_POSITIVE


def test_engine_positive_edge() -> None:
    chain = make_chain(avg_return=0.001, confidence=0.5)
    d = DecisionEngine().decide(chain)
    assert d.decision_type == DECISION_POSITIVE


def test_engine_neutral_low_confidence() -> None:
    chain = make_chain(avg_return=2.0, confidence=0.4)
    d = DecisionEngine().decide(chain)
    assert d.decision_type == DECISION_NEUTRAL


def test_engine_neutral_small_positive() -> None:
    chain = make_chain(avg_return=0.5, confidence=0.4)
    d = DecisionEngine().decide(chain)
    assert d.decision_type == DECISION_NEUTRAL


def test_engine_negative() -> None:
    chain = make_chain(avg_return=-0.5, confidence=0.6)
    d = DecisionEngine().decide(chain)
    assert d.decision_type == DECISION_NEGATIVE


def test_engine_negative_edge() -> None:
    chain = make_chain(avg_return=-0.001, confidence=0.5)
    d = DecisionEngine().decide(chain)
    assert d.decision_type == DECISION_NEGATIVE


def test_engine_strong_negative() -> None:
    chain = make_chain(avg_return=-2.0, confidence=0.8)
    d = DecisionEngine().decide(chain)
    assert d.decision_type == DECISION_STRONG_NEGATIVE


def test_engine_strong_negative_edge() -> None:
    chain = make_chain(avg_return=-1.001, confidence=0.7)
    d = DecisionEngine().decide(chain)
    assert d.decision_type == DECISION_STRONG_NEGATIVE


def test_engine_zero_return() -> None:
    chain = make_chain(avg_return=0.0, confidence=0.9)
    d = DecisionEngine().decide(chain)
    assert d.decision_type == DECISION_NEUTRAL


# ── DecisionEngine — Integration with ReasoningEngine ──────────────────────

def test_engine_from_full_reasoning_chain() -> None:
    evs = make_evidence(avg_return=1.5, confidence=0.85)
    rctx = RCtx(event_type="CPI")
    chain = ReasoningEngine().reason(evs, rctx)
    d = DecisionEngine().decide(chain)
    assert d.decision_type == DECISION_STRONG_POSITIVE
    assert "reason_CPI" in d.decision_id
    assert d.reasoning_chain_id == chain.chain_id


def test_engine_from_full_reasoning_chain_negative() -> None:
    evs = make_evidence(avg_return=-1.5, confidence=0.85)
    chain = ReasoningEngine().reason(evs, RCtx(event_type="CPI"))
    d = DecisionEngine().decide(chain)
    assert d.decision_type == DECISION_STRONG_NEGATIVE


def test_engine_from_full_reasoning_chain_low_conf() -> None:
    evs = make_evidence(avg_return=1.5, confidence=0.3)
    chain = ReasoningEngine().reason(evs, RCtx(event_type="CPI"))
    d = DecisionEngine().decide(chain)
    assert d.decision_type == DECISION_NEUTRAL


# ── DecisionEngine — Decision ID and Explanation ───────────────────────────

def test_engine_decision_id_format() -> None:
    chain = make_chain(avg_return=1.0, confidence=0.8)
    d = DecisionEngine().decide(chain)
    assert d.decision_id == f"dec_{chain.chain_id}"


def test_engine_explanation_references_chain() -> None:
    chain = make_chain(avg_return=2.0, confidence=0.8)
    d = DecisionEngine().decide(chain)
    assert chain.chain_id in d.explanation
    assert d.decision_type in d.explanation
    assert "evidence of 1 items" in d.explanation or "1 evidence items" in d.explanation


# ── DecisionEngine — Context Handling ─────────────────────────────────────

def test_engine_with_explicit_context() -> None:
    chain = make_chain(avg_return=1.0, confidence=0.8)
    ctx = DecisionContext(event_type="CPI", query="gold outlook")
    d = DecisionEngine().decide(chain, context=ctx)
    assert d.context.query == "gold outlook"
    assert d.context.event_type == "CPI"


def test_engine_without_context_uses_chain_context() -> None:
    chain = make_chain(avg_return=1.0, confidence=0.8)
    d = DecisionEngine().decide(chain)
    assert d.context.event_type == "CPI"


# ── DecisionEngine — Empty Chain ──────────────────────────────────────────

def test_engine_empty_chain() -> None:
    ctx_r = RCtx(event_type="CPI")
    chain = ReasoningEngine().reason(EvidenceCollection(), ctx_r)
    d = DecisionEngine().decide(chain)
    assert d.decision_type == DECISION_NEUTRAL
    assert d.evidence_count == 0
    assert d.confidence == 0.0


# ── DecisionRepository ────────────────────────────────────────────────────

def test_repository_save_and_load_round_trip(tmp_path: Path) -> None:
    chain = make_chain(avg_return=2.0, confidence=0.8)
    d = DecisionEngine().decide(chain)
    path = tmp_path / "decision.json"
    DecisionRepository().save(d, path)
    assert path.exists()

    loaded = DecisionRepository().load(path)
    assert loaded.decision_id == d.decision_id
    assert loaded.decision_type == d.decision_type
    assert loaded.confidence == d.confidence
    assert loaded.reasoning_chain_id == d.reasoning_chain_id
    assert loaded.evidence_count == d.evidence_count
    assert loaded.explanation == d.explanation
    assert loaded.context.event_type == "CPI"


def test_repository_preserves_context(tmp_path: Path) -> None:
    chain = make_chain(avg_return=1.0, confidence=0.7)
    ctx = DecisionContext(event_type="NFP", query="labor market")
    d = DecisionEngine().decide(chain, context=ctx)
    path = tmp_path / "ctx.json"
    DecisionRepository().save(d, path)
    loaded = DecisionRepository().load(path)
    assert loaded.context.event_type == "NFP"
    assert loaded.context.query == "labor market"


def test_repository_file_format(tmp_path: Path) -> None:
    chain = make_chain(avg_return=2.0, confidence=0.8)
    d = DecisionEngine().decide(chain)
    path = tmp_path / "format.json"
    DecisionRepository().save(d, path)

    raw = json.loads(path.read_text())
    assert raw["decision_id"] == d.decision_id
    assert raw["decision_type"] == DECISION_STRONG_POSITIVE
    assert "context" in raw
    assert "event_type" in raw["context"]


def test_repository_preserves_metadata(tmp_path: Path) -> None:
    chain = make_chain(avg_return=2.0, confidence=0.8)
    d = DecisionEngine().decide(chain)
    path = tmp_path / "meta.json"
    DecisionRepository().save(d, path)
    loaded = DecisionRepository().load(path)
    assert loaded.metadata["avg_return_pct"] == 2.0
    assert loaded.metadata["chain_confidence"] == 0.8
