from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import pytest

from knowledge._compat import (
    FrozenDict,
    atomic_write_json,
    freeze_dict,
    locked_write_json,
)


# ═════════════════════════════════════════════════════════════════════════════
# 1. FrozenDict — immutability, nested access, serialization
# ═════════════════════════════════════════════════════════════════════════════

class TestFrozenDictConstruction:
    def test_empty(self) -> None:
        d = FrozenDict()
        assert len(d) == 0
        assert dict(d) == {}

    def test_from_dict(self) -> None:
        d = FrozenDict({"a": 1, "b": 2})
        assert d["a"] == 1
        assert d["b"] == 2
        assert len(d) == 2

    def test_from_kwargs(self) -> None:
        d = FrozenDict(a=1, b=2)
        assert d["a"] == 1
        assert d["b"] == 2

    def test_freeze_dict_wraps_plain_dict(self) -> None:
        d = freeze_dict({"x": 10})
        assert isinstance(d, FrozenDict)
        assert d["x"] == 10

    def test_freeze_dict_returns_frozen_dict_unchanged(self) -> None:
        original = FrozenDict({"x": 10})
        result = freeze_dict(original)
        assert result is original

    def test_freeze_dict_none_returns_empty(self) -> None:
        result = freeze_dict(None)
        assert isinstance(result, FrozenDict)
        assert len(result) == 0


class TestFrozenDictImmutability:
    def test_setitem_raises(self) -> None:
        d = FrozenDict({"a": 1})
        with pytest.raises(TypeError, match="immutable"):
            d["a"] = 2

    def test_delitem_raises(self) -> None:
        d = FrozenDict({"a": 1})
        with pytest.raises(TypeError, match="immutable"):
            del d["a"]

    def test_clear_raises(self) -> None:
        d = FrozenDict({"a": 1})
        with pytest.raises(TypeError, match="immutable"):
            d.clear()

    def test_pop_raises(self) -> None:
        d = FrozenDict({"a": 1})
        with pytest.raises(TypeError, match="immutable"):
            d.pop("a")

    def test_popitem_raises(self) -> None:
        d = FrozenDict({"a": 1})
        with pytest.raises(TypeError, match="immutable"):
            d.popitem()

    def test_update_raises(self) -> None:
        d = FrozenDict({"a": 1})
        with pytest.raises(TypeError, match="immutable"):
            d.update({"b": 2})

    def test_copy_returns_mutable_equivalent(self) -> None:
        d = FrozenDict({"a": 1})
        c = d.copy()
        assert isinstance(c, FrozenDict)
        assert c == {"a": 1}
        # A shallow copy is also frozen
        with pytest.raises(TypeError):
            c["b"] = 2


class TestFrozenDictNestedAccess:
    def test_nested_dict_is_not_auto_frozen(self) -> None:
        inner = {"nested": 1}
        d = FrozenDict({"outer": inner})
        # The outer dict is frozen but inner plain dict remains mutable
        inner["nested"] = 99
        assert d["outer"]["nested"] == 99

    def test_deep_freeze_via_freeze_dict_flat(self) -> None:
        d = freeze_dict({"a": {"b": 1}})
        assert d["a"]["b"] == 1
        # Inner is still a plain dict — freeze_dict is shallow
        inner = d["a"]
        inner["c"] = 2
        assert d["a"]["c"] == 2


class TestFrozenDictSerialization:
    def test_json_dumps(self) -> None:
        d = FrozenDict({"a": [1, 2], "b": {"c": 3}})
        serialized = json.dumps(d)
        parsed = json.loads(serialized)
        assert parsed == {"a": [1, 2], "b": {"c": 3}}

    def test_json_dumps_via_dict_conversion(self) -> None:
        d = freeze_dict({"k": "v"})
        serialized = json.dumps(dict(d))
        assert json.loads(serialized) == {"k": "v"}

    def test_round_trip_through_file(self, tmp_path: Path) -> None:
        d = FrozenDict({"x": 1, "y": [2, 3]})
        p = tmp_path / "data.json"
        p.write_text(json.dumps(d))
        loaded = json.loads(p.read_text())
        assert loaded == {"x": 1, "y": [2, 3]}


# ═════════════════════════════════════════════════════════════════════════════
# 2. atomic_write_json — success, overwrite, interrupted, invalid, datetime
# ═════════════════════════════════════════════════════════════════════════════

class TestAtomicWriteJsonSuccess:
    def test_writes_valid_json(self, tmp_path: Path) -> None:
        p = tmp_path / "out.json"
        atomic_write_json(p, {"a": 1, "b": [2, 3]})
        assert p.exists()
        assert json.loads(p.read_text()) == {"a": 1, "b": [2, 3]}

    def test_no_tmp_file_left_behind(self, tmp_path: Path) -> None:
        p = tmp_path / "out.json"
        atomic_write_json(p, {"x": 1})
        tmp_files = list(tmp_path.glob("*.json.tmp"))
        assert len(tmp_files) == 0

    def test_creates_parent_directories(self, tmp_path: Path) -> None:
        p = tmp_path / "a" / "b" / "c" / "out.json"
        atomic_write_json(p, {"x": 1})
        assert p.exists()

    def test_nested_frozen_dict_serializes(self, tmp_path: Path) -> None:
        p = tmp_path / "frozen.json"
        data = {"items": freeze_dict({"k": "v"})}
        atomic_write_json(p, data)
        assert json.loads(p.read_text()) == {"items": {"k": "v"}}


class TestAtomicWriteJsonOverwrite:
    def test_overwrites_existing_file(self, tmp_path: Path) -> None:
        p = tmp_path / "out.json"
        p.write_text(json.dumps({"old": "data"}))
        atomic_write_json(p, {"new": "data"})
        assert json.loads(p.read_text()) == {"new": "data"}

    def test_shorter_content_does_not_leave_stale_bytes(self, tmp_path: Path) -> None:
        p = tmp_path / "out.json"
        atomic_write_json(p, {"long": "x" * 100})
        atomic_write_json(p, {"short": "y"})
        loaded = json.loads(p.read_text())
        assert loaded == {"short": "y"}
        # No trailing junk
        raw = p.read_bytes()
        assert raw[-1] == ord("}")


class TestAtomicWriteJsonInterrupted:
    def test_tmp_file_does_not_replace_target_on_failure(self, tmp_path: Path) -> None:
        """Simulate interruption by passing an unserializable object
        mid-write (the exception is raised before tmp replaces target)."""
        p = tmp_path / "out.json"
        p.write_text(json.dumps({"original": "data"}))

        class Unserializable:
            pass

        with pytest.raises(TypeError):
            atomic_write_json(p, {"bad": Unserializable()})

        # Original file must be untouched
        assert json.loads(p.read_text()) == {"original": "data"}

    def test_incomplete_tmp_does_not_replace_target(self, tmp_path: Path) -> None:
        """If an exception occurs during dumps (e.g., recursion), target is safe."""
        p = tmp_path / "out.json"
        p.write_text(json.dumps({"safe": "value"}))

        obj: dict[str, object] = {}
        obj["self"] = obj  # circular reference

        with pytest.raises(ValueError):
            atomic_write_json(p, obj)

        assert json.loads(p.read_text()) == {"safe": "value"}


class TestAtomicWriteJsonInvalidObject:
    def test_raises_on_unserializable_without_default(self, tmp_path: Path) -> None:
        p = tmp_path / "out.json"

        with pytest.raises(TypeError):
            atomic_write_json(p, {"date": datetime(2024, 1, 1)})

    def test_default_str_handles_datetime(self, tmp_path: Path) -> None:
        p = tmp_path / "out.json"
        atomic_write_json(p, {"date": datetime(2024, 1, 1)}, default=str)
        loaded = json.loads(p.read_text())
        assert "2024-01-01" in loaded["date"]

    def test_default_str_handles_custom_type(self, tmp_path: Path) -> None:
        p = tmp_path / "out.json"

        class Custom:
            def __str__(self) -> str:
                return "custom_repr"

        atomic_write_json(p, {"obj": Custom()}, default=str)
        assert json.loads(p.read_text()) == {"obj": "custom_repr"}

    def test_default_str_handles_decimal(self, tmp_path: Path) -> None:
        from decimal import Decimal

        p = tmp_path / "out.json"
        atomic_write_json(p, {"val": Decimal("10.5")}, default=str)
        assert json.loads(p.read_text()) == {"val": "10.5"}


# ═════════════════════════════════════════════════════════════════════════════
# 3. locked_write_json — concurrent, Windows compat, lock, corruption
# ═════════════════════════════════════════════════════════════════════════════

class TestLockedWriteJson:
    def test_writes_valid_json(self, tmp_path: Path) -> None:
        p = tmp_path / "locked.json"
        locked_write_json(p, {"a": 1})
        assert p.exists()
        assert json.loads(p.read_text()) == {"a": 1}

    def test_overwrites_existing_file(self, tmp_path: Path) -> None:
        p = tmp_path / "locked.json"
        locked_write_json(p, {"v": 1})
        locked_write_json(p, {"v": 2})
        assert json.loads(p.read_text()) == {"v": 2}

    def test_no_tmp_left_behind(self, tmp_path: Path) -> None:
        p = tmp_path / "locked.json"
        locked_write_json(p, {"x": 1})
        tmp_files = list(tmp_path.glob("*.json.tmp"))
        assert len(tmp_files) == 0

    def test_creates_parent_dirs(self, tmp_path: Path) -> None:
        p = tmp_path / "deep" / "locked.json"
        locked_write_json(p, {"ok": True})
        assert p.exists()

    def test_no_file_corruption(self, tmp_path: Path) -> None:
        p = tmp_path / "locked.json"
        for i in range(20):
            locked_write_json(p, {"iteration": i, "data": "x" * (i * 10)})
        loaded = json.loads(p.read_text())
        assert loaded["iteration"] == 19


class TestLockedWriteJsonConcurrent:
    def test_rapid_sequential_writes_no_corruption(self, tmp_path: Path) -> None:
        """Rapid sequential writes must not corrupt."""
        p = tmp_path / "rapid.json"
        for i in range(100):
            locked_write_json(p, {"idx": i, "data": "x" * 200})
        assert json.loads(p.read_text()) == {"idx": 99, "data": "x" * 200}

    def test_alternating_sizes_no_corruption(self, tmp_path: Path) -> None:
        """Alternating large and small writes must not leave stale bytes."""
        p = tmp_path / "alternating.json"
        for i in range(50):
            size = 1000 if i % 2 == 0 else 10
            locked_write_json(p, {"i": i, "pad": "x" * size})
        loaded = json.loads(p.read_text())
        assert loaded["i"] == 49
        # No trailing junk from previous larger writes
        raw = p.read_bytes()
        assert raw[-1] == ord("}")


# ═════════════════════════════════════════════════════════════════════════════
# 4. Regression — repository save/load round-trips
# ═════════════════════════════════════════════════════════════════════════════

class TestRegressionFrozenDictDataclassFields:
    """Every dataclass that was migrated must enforce FrozenDict on mutable fields."""

    def test_decision_context_metadata(self) -> None:
        from knowledge.decision.context import DecisionContext

        ctx = DecisionContext(event_type="CPI")
        assert isinstance(ctx.metadata, FrozenDict)

    def test_decision_metadata(self) -> None:
        from knowledge.decision.decision import Decision
        from knowledge.decision.context import DecisionContext

        ctx = DecisionContext(event_type="CPI")
        d = Decision(
            decision_id="d1", decision_type="NEUTRAL", confidence=0.5,
            reasoning_chain_id="rc1", evidence_count=3, explanation="x",
            context=ctx,
        )
        assert isinstance(d.metadata, FrozenDict)

    def test_temporal_state_metadata(self) -> None:
        from knowledge.temporal.state import TemporalState

        s = TemporalState(
            state_id="s1", date="2024-01-01",
            source_type="evidence", source_id="ev1",
        )
        assert isinstance(s.metadata, FrozenDict)

    def test_temporal_period_metadata(self) -> None:
        from knowledge.temporal.period import TimePeriod

        p = TimePeriod(period_id="p1", start_date="2024-01-01", end_date="2024-06-01")
        assert isinstance(p.metadata, FrozenDict)

    def test_temporal_context_metadata(self) -> None:
        from knowledge.temporal.context import TimeContext

        tc = TimeContext()
        assert isinstance(tc.metadata, FrozenDict)

    def test_economic_regime_fields(self) -> None:
        from knowledge.economics.regime import EconomicRegime

        r = EconomicRegime(
            regime_id="r1", regime_type="growth", label="Growth",
            description="Test regime", start_date="2024-01-01",
        )
        assert isinstance(r.indicators, FrozenDict)
        assert isinstance(r.metadata, FrozenDict)

    def test_economic_state_fields(self) -> None:
        from knowledge.economics.state import EconomicState

        s = EconomicState(state_id="s1", date="2024-01-01")
        assert isinstance(s.indicators, FrozenDict)
        assert isinstance(s.metadata, FrozenDict)

    def test_economic_cycle_metadata(self) -> None:
        from knowledge.economics.cycle import EconomicCycle

        c = EconomicCycle(cycle_id="c1", states=(), start_date="2024-01-01")
        assert isinstance(c.metadata, FrozenDict)

    def test_causal_relation_metadata(self) -> None:
        from knowledge.causal.relation import CausalRelation

        r = CausalRelation(
            relation_id="cr1", source_id="a", target_id="b",
            relation_type="causation", strength=0.5, confidence=0.8,
        )
        assert isinstance(r.metadata, FrozenDict)

    def test_causal_hypothesis_metadata(self) -> None:
        from knowledge.causal.hypothesis import CausalHypothesis

        h = CausalHypothesis(
            hypothesis_id="h1", name="test", description="d",
            cause_node_id="a", effect_node_id="b",
        )
        assert isinstance(h.metadata, FrozenDict)

    def test_causal_evidence_metadata(self) -> None:
        from knowledge.causal.evidence import CausalEvidence

        ce = CausalEvidence(
            causal_evidence_id="ce1", hypothesis_id="h1",
            evidence_id="e1", role="supporting", strength=0.9,
        )
        assert isinstance(ce.metadata, FrozenDict)

    def test_learning_record_details(self) -> None:
        from knowledge.learning.record import LearningRecord

        lr = LearningRecord(
            record_id="r1", decision_id="d1", reasoning_chain_id="rc1",
            event_type="CPI", decision_type="NEUTRAL", decision_confidence=0.5,
            expected_direction="UP", actual_return_pct=1.0,
            direction_correct=True, accuracy_score=0.8,
        )
        assert isinstance(lr.details, FrozenDict)

    def test_learning_session_summary(self) -> None:
        from knowledge.learning.record import LearningRecord
        from knowledge.learning.session import LearningSession

        lr = LearningRecord(
            record_id="r1", decision_id="d1", reasoning_chain_id="rc1",
            event_type="CPI", decision_type="NEUTRAL", decision_confidence=0.5,
            expected_direction="UP", actual_return_pct=1.0,
            direction_correct=True, accuracy_score=0.8,
        )
        sess = LearningSession(
            session_id="s1", records=(lr,), total_records=1,
            correct_count=1, accuracy_rate=1.0, avg_confidence=0.5,
        )
        assert isinstance(sess.summary, FrozenDict)

    def test_knowledge_feedback_fields(self) -> None:
        from knowledge.learning.feedback import KnowledgeFeedback

        kf = KnowledgeFeedback(
            feedback_id="f1", source_record_ids=("r1",),
            event_type="CPI", condition={}, horizon_days=5,
            current_confidence=0.5, suggested_confidence=0.6,
            accuracy_rate=0.8, correct_count=4, sample_count=5,
            explanation="test",
        )
        assert isinstance(kf.condition, FrozenDict)
        assert isinstance(kf.metadata, FrozenDict)

    def test_forecast_result_metadata(self) -> None:
        from forecasting.models import ForecastResult, ForecastPoint

        fr = ForecastResult(
            model_name="test", confidence_level=0.95,
            points=(ForecastPoint(ds="2024-01-01", y=100.0, y_lo=90.0, y_hi=110.0),),
            metadata={},
        )
        assert isinstance(fr.metadata, FrozenDict)

    def test_forecast_evidence_fields(self) -> None:
        from forecasting.evidence import ForecastEvidence

        fe = ForecastEvidence(
            evidence_id="e1", evidence_strength=0.8,
            evidence_sources=("src1",),
            supporting_context={}, confidence_snapshot={},
            provenance_snapshot={}, metadata={},
        )
        assert isinstance(fe.supporting_context, FrozenDict)
        assert isinstance(fe.confidence_snapshot, FrozenDict)
        assert isinstance(fe.provenance_snapshot, FrozenDict)
        assert isinstance(fe.metadata, FrozenDict)

    def test_institutional_assessment_outputs(self) -> None:
        from orchestration.models import InstitutionalAssessment

        ia = InstitutionalAssessment(
            pipeline_id="p1", trigger="manual", timestamp="2024-01-01T00:00:00",
            stages=(), cache_hits=0, wall_time_ms=100.0,
        )
        assert isinstance(ia.outputs, FrozenDict)

    def test_integrity_dataclasses_still_frozen(self) -> None:
        """Original frozen dataclass constraints must not regress."""
        from knowledge.integrity.provenance import Provenance

        p = Provenance(created_at="t", created_by="me", entity_version="1")
        with pytest.raises(AttributeError):
            p.created_at = "new"  # type: ignore[misc]

    def test_reasoning_chain_still_frozen(self) -> None:
        from knowledge.reasoning.chain import ReasoningChain
        from knowledge.reasoning.context import ReasoningContext

        ctx = ReasoningContext(event_type="CPI")
        chain = ReasoningChain(
            chain_id="c1", context=ctx, steps=(),
            final_conclusion="ok", overall_confidence=0.8, evidence_count=3,
        )
        with pytest.raises(AttributeError):
            chain.final_conclusion = "changed"  # type: ignore[misc]


class TestRegressionRepositoryRoundTrip:
    """Verify every repository still produces correct JSON and loads correctly."""

    def test_evidence_repository_round_trip(self, tmp_path: Path) -> None:
        from knowledge.evidence.evidence import Evidence
        from knowledge.evidence.collection import EvidenceCollection
        from knowledge.evidence.repository import EvidenceRepository

        ev = Evidence(
            evidence_id="ev_1", source_node_id="n1", event_type="CPI",
            condition={"pressure": "high"}, horizon_days=5, sample_count=100,
            average_return_pct=1.5, confidence=0.8, bias="bullish",
            explanation="test",
        )
        repo = EvidenceRepository()
        path = tmp_path / "evidence.json"
        items = EvidenceCollection([ev])
        repo.save(items, path)
        loaded = repo.load(path)
        assert len(loaded) == 1
        assert loaded[0].evidence_id == "ev_1"
        assert loaded[0].condition == {"pressure": "high"}

    def test_reasoning_repository_round_trip(self, tmp_path: Path) -> None:
        from knowledge.reasoning.chain import ReasoningChain
        from knowledge.reasoning.context import ReasoningContext
        from knowledge.reasoning.repository import ReasoningRepository
        from knowledge.reasoning.step import ReasoningStep

        ctx = ReasoningContext(event_type="CPI")
        step = ReasoningStep(
            step_id="s1", step_type="analysis", conclusion="result",
            confidence=0.9, supporting_evidence_ids=(),
        )
        chain = ReasoningChain(
            chain_id="c1", context=ctx, steps=(step,),
            final_conclusion="done", overall_confidence=0.8, evidence_count=3,
        )
        repo = ReasoningRepository()
        path = tmp_path / "chain.json"
        repo.save(chain, path)
        loaded = repo.load(path)
        assert loaded.chain_id == "c1"
        assert len(loaded.steps) == 1

    def test_decision_repository_round_trip(self, tmp_path: Path) -> None:
        from knowledge.decision.context import DecisionContext
        from knowledge.decision.decision import Decision
        from knowledge.decision.repository import DecisionRepository

        ctx = DecisionContext(event_type="CPI", metadata={"src": "test"})
        d = Decision(
            decision_id="d1", decision_type="NEUTRAL", confidence=0.5,
            reasoning_chain_id="rc1", evidence_count=3, explanation="x",
            context=ctx,
        )
        repo = DecisionRepository()
        path = tmp_path / "decision.json"
        repo.save(d, path)
        loaded = repo.load(path)
        assert loaded.decision_id == "d1"
        assert loaded.context.metadata == {"src": "test"}

    def test_graph_repository_round_trip(self, tmp_path: Path) -> None:
        from knowledge.graph.graph import KnowledgeGraph
        from knowledge.graph.node import GraphNode
        from knowledge.graph.relation import GraphRelation
        from knowledge.graph.repository import GraphRepository

        g = KnowledgeGraph()
        g.add_node(GraphNode(node_id="n1", node_type="test", properties={"k": "v"}))
        g.add_relation(GraphRelation(
            source_id="n1", target_id="n2",
            relation_type="links", properties={"w": 1},
        ))
        repo = GraphRepository()
        path = tmp_path / "graph.json"
        repo.save(g, path)
        loaded = repo.load(path)
        # n1 is added explicitly; n2 is added implicitly via relation
        assert loaded.node_count == 2

    def test_economics_repository_round_trip(self, tmp_path: Path) -> None:
        from knowledge.economics.regime import EconomicRegime
        from knowledge.economics.state import EconomicState
        from knowledge.economics.cycle import EconomicCycle
        from knowledge.economics.repository import EconomicRepository

        repo = EconomicRepository()
        regime = EconomicRegime(
            regime_id="r1", regime_type="growth", label="Growth",
            description="Test", start_date="2024-01-01",
            indicators={"gdp": 2.5}, metadata={"src": "fed"},
        )
        p = tmp_path / "regime.json"
        repo.save_regime(regime, p)
        loaded = repo.load_regime(p)
        assert loaded.regime_id == "r1"
        assert loaded.indicators == {"gdp": 2.5}

        state = EconomicState(
            state_id="s1", date="2024-01-01",
            indicators={"cpi": 3.0}, regime_ids=("r1",),
        )
        p2 = tmp_path / "state.json"
        repo.save_state(state, p2)
        loaded2 = repo.load_state(p2)
        assert loaded2.state_id == "s1"

        cycle = EconomicCycle(
            cycle_id="c1", states=(state,), start_date="2024-01-01",
            end_date="2024-06-01", metadata={"model": "test"},
        )
        p3 = tmp_path / "cycle.json"
        repo.save_cycle(cycle, p3)
        loaded3 = repo.load_cycle(p3)
        assert loaded3.cycle_id == "c1"

    def test_learning_repository_round_trip(self, tmp_path: Path) -> None:
        from knowledge.learning.record import LearningRecord
        from knowledge.learning.session import LearningSession
        from knowledge.learning.feedback import KnowledgeFeedback
        from knowledge.learning.repository import LearningRepository

        repo = LearningRepository()
        lr = LearningRecord(
            record_id="r1", decision_id="d1", reasoning_chain_id="rc1",
            event_type="CPI", decision_type="NEUTRAL", decision_confidence=0.5,
            expected_direction="UP", actual_return_pct=1.0,
            direction_correct=True, accuracy_score=0.8,
        )
        p = tmp_path / "record.json"
        repo.save_record(lr, p)
        loaded = repo.load_record(p)
        assert loaded.record_id == "r1"

        sess = LearningSession(
            session_id="s1", records=(lr,), total_records=1,
            correct_count=1, accuracy_rate=1.0, avg_confidence=0.5,
        )
        p2 = tmp_path / "session.json"
        repo.save_session(sess, p2)
        loaded2 = repo.load_session(p2)
        assert loaded2.session_id == "s1"

        kf = KnowledgeFeedback(
            feedback_id="f1", source_record_ids=("r1",),
            event_type="CPI", condition={"cpi": "high"}, horizon_days=5,
            current_confidence=0.5, suggested_confidence=0.6,
            accuracy_rate=0.8, correct_count=4, sample_count=5,
            explanation="test",
        )
        p3 = tmp_path / "feedback.json"
        repo.save_feedback(kf, p3)
        loaded3 = repo.load_feedback(p3)
        assert loaded3.feedback_id == "f1"

    def test_causal_repository_round_trip(self, tmp_path: Path) -> None:
        from knowledge.causal.relation import CausalRelation
        from knowledge.causal.hypothesis import CausalHypothesis
        from knowledge.causal.evidence import CausalEvidence
        from knowledge.causal.graph import CausalGraph
        from knowledge.causal.repository import CausalRepository

        g = CausalGraph()
        g.add_relation(CausalRelation(
            relation_id="cr1", source_id="a", target_id="b",
            relation_type="causation", strength=0.8, confidence=0.9,
        ))
        g.add_hypothesis(CausalHypothesis(
            hypothesis_id="h1", name="test", description="desc",
            cause_node_id="a", effect_node_id="b",
        ))
        g.add_causal_evidence(CausalEvidence(
            causal_evidence_id="ce1", hypothesis_id="h1",
            evidence_id="e1", role="supporting", strength=0.9,
        ))
        repo = CausalRepository()
        path = tmp_path / "causal.json"
        repo.save_graph(g, path)
        loaded = repo.load_graph(path)
        assert len(loaded.all_relations()) == 1
        assert len(loaded.all_hypotheses()) == 1

    def test_temporal_repository_round_trip(self, tmp_path: Path) -> None:
        from knowledge.temporal.context import TimeContext
        from knowledge.temporal.period import TimePeriod
        from knowledge.temporal.indexer import TemporalIndexer
        from knowledge.temporal.repository import TemporalRepository

        repo = TemporalRepository()
        ctx = TimeContext()
        indexer = TemporalIndexer(ctx)
        p = tmp_path / "index.json"
        repo.save_index(indexer, p)
        loaded_indexer = repo.load_index(p)
        assert loaded_indexer.context.timezone == "UTC"

        period = TimePeriod(
            period_id="p1", start_date="2024-01-01", end_date="2024-06-01",
        )
        p2 = tmp_path / "period.json"
        repo.save_period(period, p2)
        loaded = repo.load_period(p2)
        assert loaded.period_id == "p1"

    def test_memory_save_and_load(self, tmp_path: Path) -> None:
        from knowledge.memory import Memory

        path = tmp_path / "memory.json"
        mem = Memory(str(path))
        mem.save({"key": "value", "nested": {"a": 1}})
        loaded = mem.load()
        assert loaded["key"] == "value"
        assert loaded["nested"] == {"a": 1}

    def test_memory_namespace_round_trip(self, tmp_path: Path) -> None:
        from knowledge.memory import Memory

        path = tmp_path / "memory.json"
        mem = Memory(str(path))
        mem.set_namespace("ns1", {"data": 42})
        loaded = mem.load()
        assert loaded["ns1"]["data"] == 42

    def test_versioning_store_round_trip(self, tmp_path: Path) -> None:
        from knowledge.integrity.versioning import VersionedStore

        store = VersionedStore[dict](tmp_path)
        v1 = store.save("e1", {"x": 1})
        assert v1.version_number == 1
        loaded = store.load_version("e1", 1)
        assert loaded is not None
        assert loaded.entity["x"] == 1

    def test_versioning_store_multiple_versions(self, tmp_path: Path) -> None:
        from knowledge.integrity.versioning import VersionedStore

        store = VersionedStore[dict](tmp_path)
        store.save("e1", {"v": 1})
        store.save("e1", {"v": 2})
        all_v = store.all_versions("e1")
        assert len(all_v) == 2

    def test_lesson_summary_build_and_save(self, tmp_path: Path) -> None:
        """Verify lesson_summary.py atomic write integration."""
        from knowledge.lesson_summary import LessonSummaryConfig, LessonSummaryAggregator

        lessons_csv = tmp_path / "lessons.csv"
        lessons_csv.write_text(
            "lesson_id,event_type,event_date,cpi_pressure,"
            "gold_return_1d_pct,gold_return_5d_pct,gold_return_20d_pct,"
            "gold_direction_1d,gold_direction_5d,gold_direction_20d\n"
            "l1,CPI,2024-01-10,high,1.0,2.0,3.0,UP,UP,UP\n"
            "l2,CPI,2024-06-15,low,-0.5,-1.0,-2.0,DOWN,DOWN,DOWN\n"
        )
        output = tmp_path / "summary.json"
        config = LessonSummaryConfig(
            lessons_path=lessons_csv,
            output_path=output,
            condition_columns=("cpi_pressure",),
            horizons=(1,),
        )
        agg = LessonSummaryAggregator(config)
        summary = agg.build_and_save()
        assert summary["record_count"] == 2
        assert output.exists()
        loaded = json.loads(output.read_text())
        assert loaded["record_count"] == 2

    def test_institutional_orchestrator_checkpoint(self, tmp_path: Path) -> None:
        """Verify orchestrator checkpoint uses atomic_write_json."""
        from orchestration.institutional_orchestrator import CheckpointManager

        store = CheckpointManager(str(tmp_path))
        store.write("pipeline_a", "job_1", {"status": "running", "progress": 0.5})
        assert store.exists("pipeline_a", "job_1")
        loaded = store.read("pipeline_a", "job_1")
        assert loaded is not None
        assert loaded["status"] == "running"
        assert loaded["progress"] == 0.5
