from __future__ import annotations

from pathlib import Path
from datetime import datetime

import pytest

from knowledge.integrity.provenance import Provenance
from knowledge.integrity.lineage import LineageRelationType, LineageRecord, LineageRegistry
from knowledge.integrity.versioning import VersionedEntity, VersionedStore
from knowledge.integrity.source_data import SourceData
from knowledge.integrity.knowledge_record import KnowledgeRecord
from knowledge.decision.decision import Decision
from knowledge.decision.context import DecisionContext
from knowledge.reasoning.chain import ReasoningChain
from knowledge.reasoning.context import ReasoningContext
from knowledge.reasoning.step import ReasoningStep
from knowledge.evidence.evidence import Evidence
from knowledge.models.lesson import Lesson


# ── Provenance ──────────────────────────────────────────────────────────────

def test_provenance_creation() -> None:
    p = Provenance(created_at="2026-01-01T00:00:00", created_by="test", entity_version="1.0.0")
    assert p.created_at == "2026-01-01T00:00:00"
    assert p.created_by == "test"
    assert p.entity_version == "1.0.0"
    assert p.previous_version_id is None
    assert p.metadata == {}


def test_provenance_with_previous_version() -> None:
    p = Provenance(
        created_at="2026-01-02T00:00:00",
        created_by="test",
        entity_version="2.0.0",
        previous_version_id="v1",
        metadata={"reason": "update"},
    )
    assert p.previous_version_id == "v1"
    assert p.metadata == {"reason": "update"}


def test_provenance_is_frozen() -> None:
    p = Provenance(created_at="2026-01-01T00:00:00", created_by="test", entity_version="1.0.0")
    with pytest.raises(AttributeError):
        p.created_at = "2026-02-01T00:00:00"  # type: ignore[misc]


# ── Lineage ─────────────────────────────────────────────────────────────────

def test_lineage_record_creation() -> None:
    r = LineageRecord(
        source_id="dec_1", source_type="decision",
        target_id="chain_1", target_type="reasoning_chain",
        relation_type=LineageRelationType.DERIVES_FROM,
    )
    assert r.source_id == "dec_1"
    assert r.source_type == "decision"
    assert r.target_id == "chain_1"
    assert r.target_type == "reasoning_chain"
    assert r.relation_type == "derives_from"
    assert r.timestamp is not None


def test_lineage_registry_add_and_query() -> None:
    reg = LineageRegistry()
    reg.add("dec_1", "decision", "chain_1", "reasoning_chain", LineageRelationType.REFERENCES)
    reg.add("chain_1", "reasoning_chain", "ev_1", "evidence", LineageRelationType.REFERENCES)

    forward = reg.query(entity_id="dec_1", direction="forward")
    assert len(forward) == 1
    assert forward[0].target_id == "chain_1"

    backward = reg.query(entity_id="ev_1", direction="backward")
    assert len(backward) == 1
    assert backward[0].source_id == "chain_1"


def test_lineage_registry_query_by_type() -> None:
    reg = LineageRegistry()
    reg.add("dec_1", "decision", "chain_1", "reasoning_chain")
    reg.add("chain_1", "reasoning_chain", "ev_1", "evidence")
    reg.add("ev_1", "evidence", "kr_1", "knowledge_record")

    decisions = reg.query(entity_type="decision", direction="forward")
    assert len(decisions) == 1
    assert decisions[0].source_id == "dec_1"

    evidence = reg.query(entity_type="evidence", direction="backward")
    assert len(evidence) == 1
    assert evidence[0].target_id == "ev_1"


def test_lineage_registry_query_by_relation() -> None:
    reg = LineageRegistry()
    reg.add("a", "type_a", "b", "type_b", "derives_from")
    reg.add("b", "type_b", "c", "type_c", "references")
    results = reg.query(relation_type="derives_from")
    assert len(results) == 1
    assert results[0].source_id == "a"


def test_lineage_registry_trace_full_path() -> None:
    reg = LineageRegistry()
    reg.add("dec_1", "decision", "chain_1", "reasoning_chain")
    reg.add("chain_1", "reasoning_chain", "ev_1", "evidence")
    reg.add("ev_1", "evidence", "kr_1", "knowledge_record")
    reg.add("kr_1", "knowledge_record", "lesson_1", "lesson")
    reg.add("lesson_1", "lesson", "src_1", "source_data")

    path = reg.trace("src_1", "source_data")
    assert len(path) == 5


def test_lineage_registry_trace_partial() -> None:
    reg = LineageRegistry()
    reg.add("dec_1", "decision", "chain_1", "reasoning_chain")
    reg.add("chain_1", "reasoning_chain", "ev_1", "evidence")

    path = reg.trace("ev_1", "evidence")
    assert len(path) == 2


def test_lineage_registry_clear() -> None:
    reg = LineageRegistry()
    reg.add("a", "t", "b", "t")
    assert len(reg.all_records()) == 1
    reg.clear()
    assert len(reg.all_records()) == 0


def test_lineage_registry_all_records() -> None:
    reg = LineageRegistry()
    assert reg.all_records() == []
    reg.add("a", "t", "b", "t")
    assert len(reg.all_records()) == 1


# ── Versioning ──────────────────────────────────────────────────────────────

def test_versioned_entity_creation() -> None:
    ve = VersionedEntity(version_number=1, entity={"key": "value"})
    assert ve.version_number == 1
    assert ve.entity == {"key": "value"}
    assert ve.previous_version_file is None


def test_versioned_store_save_and_load(tmp_path: Path) -> None:
    store = VersionedStore[dict](tmp_path)
    ve = store.save("entity_1", {"data": "hello"})
    assert ve.version_number == 1
    assert (tmp_path / "entity_1" / "v0001.json").exists()

    loaded = store.load_version("entity_1", 1)
    assert loaded is not None
    assert loaded.version_number == 1
    assert loaded.entity["data"] == "hello"


def test_versioned_store_latest_version(tmp_path: Path) -> None:
    store = VersionedStore[dict](tmp_path)
    store.save("e1", {"v": 1})
    store.save("e1", {"v": 2})
    latest = store.latest_version("e1")
    assert latest is not None
    assert latest.version_number == 2
    assert latest.entity["v"] == 2


def test_versioned_store_all_versions(tmp_path: Path) -> None:
    store = VersionedStore[dict](tmp_path)
    store.save("e1", {"v": 1})
    store.save("e1", {"v": 2})
    store.save("e1", {"v": 3})
    all_v = store.all_versions("e1")
    assert len(all_v) == 3
    assert [v.version_number for v in all_v] == [1, 2, 3]


def test_versioned_store_missing_entity(tmp_path: Path) -> None:
    store = VersionedStore[dict](tmp_path)
    assert store.latest_version("nonexistent") is None
    assert store.load_version("nonexistent", 1) is None
    assert store.all_versions("nonexistent") == []


def test_versioned_store_version_number_increment(tmp_path: Path) -> None:
    store = VersionedStore[dict](tmp_path)
    v1 = store.save("e1", {"x": 1})
    assert v1.version_number == 1
    v2 = store.save("e1", {"x": 2})
    assert v2.version_number == 2
    v3 = store.save("e1", {"x": 3})
    assert v3.version_number == 3


def test_versioned_store_explicit_version_number(tmp_path: Path) -> None:
    store = VersionedStore[dict](tmp_path)
    ve = store.save("e1", {"x": 10}, version_number=99)
    assert ve.version_number == 99
    loaded = store.load_version("e1", 99)
    assert loaded is not None
    assert loaded.entity["x"] == 10


def test_versioned_store_rejects_overwrite(tmp_path: Path) -> None:
    store = VersionedStore[dict](tmp_path)
    store.save("e1", {"x": 1}, version_number=1)
    with pytest.raises(FileExistsError):
        store.save("e1", {"x": 2}, version_number=1)


def test_versioned_store_previous_version_link(tmp_path: Path) -> None:
    store = VersionedStore[dict](tmp_path)
    v1 = store.save("e1", {"x": 1})
    v2 = store.save("e1", {"x": 2}, previous_version_file=f"v{v1.version_number:04d}.json")
    assert v2.previous_version_file == "v0001.json"


# ── Provenance on Entities ──────────────────────────────────────────────────

def test_decision_accepts_provenance() -> None:
    p = Provenance(created_at="2026-01-01T00:00:00", created_by="test", entity_version="1.0.0")
    ctx = DecisionContext(event_type="CPI")
    d = Decision(
        decision_id="dec_1", decision_type="NEUTRAL", confidence=0.5,
        reasoning_chain_id="chain_1", evidence_count=5, explanation="test",
        context=ctx, provenance=p,
    )
    assert d.provenance is not None
    assert d.provenance.created_by == "test"


def test_decision_provenance_default_none() -> None:
    ctx = DecisionContext(event_type="CPI")
    d = Decision(
        decision_id="dec_1", decision_type="NEUTRAL", confidence=0.5,
        reasoning_chain_id="chain_1", evidence_count=5, explanation="test",
        context=ctx,
    )
    assert d.provenance is None


def test_reasoning_chain_accepts_provenance() -> None:
    p = Provenance(created_at="2026-01-01T00:00:00", created_by="test", entity_version="1.0.0")
    ctx = ReasoningContext(event_type="CPI")
    chain = ReasoningChain(
        chain_id="chain_1", context=ctx, steps=(),
        final_conclusion="ok", overall_confidence=0.8,
        evidence_count=3, provenance=p,
    )
    assert chain.provenance is not None
    assert chain.provenance.created_by == "test"


def test_evidence_accepts_provenance() -> None:
    p = Provenance(created_at="2026-01-01T00:00:00", created_by="test", entity_version="1.0.0")
    ev = Evidence(
        evidence_id="ev_1", source_node_id="node_1", event_type="CPI",
        condition={}, horizon_days=5, sample_count=100,
        average_return_pct=1.5, confidence=0.8, bias="bullish",
        explanation="test", provenance=p,
    )
    assert ev.provenance is not None
    assert ev.provenance.created_by == "test"


def test_lesson_accepts_provenance() -> None:
    p = Provenance(created_at="2026-01-01T00:00:00", created_by="test", entity_version="1.0.0")
    lesson = Lesson(
        event_id="evt_1", event_type="CPI", event_date=datetime(2026, 1, 1),
        event_value=100.0, event_surprise=None,
        gold_before=2000.0, gold_1d=1.0, gold_3d=2.0, gold_7d=3.0, gold_30d=5.0,
        return_1d=0.5, return_3d=1.0, return_7d=1.5, return_30d=2.0,
        trend="up", volatility=0.2, source="test", confidence=0.9,
        provenance=p,
    )
    assert lesson.provenance is not None
    assert lesson.provenance.created_by == "test"


# ── Immutable Knowledge ─────────────────────────────────────────────────────

def test_decision_is_frozen() -> None:
    ctx = DecisionContext(event_type="CPI")
    d = Decision(
        decision_id="dec_1", decision_type="NEUTRAL", confidence=0.5,
        reasoning_chain_id="chain_1", evidence_count=5, explanation="test",
        context=ctx,
    )
    with pytest.raises(AttributeError):
        d.decision_type = "POSITIVE"  # type: ignore[misc]


def test_reasoning_chain_is_frozen() -> None:
    ctx = ReasoningContext(event_type="CPI")
    chain = ReasoningChain(
        chain_id="chain_1", context=ctx, steps=(),
        final_conclusion="ok", overall_confidence=0.8, evidence_count=3,
    )
    with pytest.raises(AttributeError):
        chain.final_conclusion = "changed"  # type: ignore[misc]


def test_evidence_is_frozen() -> None:
    ev = Evidence(
        evidence_id="ev_1", source_node_id="node_1", event_type="CPI",
        condition={}, horizon_days=5, sample_count=100,
        average_return_pct=1.5, confidence=0.8, bias="bullish",
        explanation="test",
    )
    with pytest.raises(AttributeError):
        ev.confidence = 0.0  # type: ignore[misc]


def test_knowledge_record_is_frozen() -> None:
    kr = KnowledgeRecord(
        knowledge_id="kr_1", event_type="CPI", asset="GOLD",
        condition={}, horizon_days=5, sample_count=100,
        positive_return_rate_pct=60.0, negative_return_rate_pct=40.0,
        up_direction_rate_pct=50.0, down_direction_rate_pct=30.0,
        flat_direction_rate_pct=20.0, average_return_pct=1.5,
        median_return_pct=1.0, min_return_pct=-2.0, max_return_pct=5.0,
        first_event_date="2026-01-01", last_event_date="2026-06-01",
        bias="bullish", confidence=0.8, explanation="test",
    )
    with pytest.raises(AttributeError):
        kr.confidence = 0.0  # type: ignore[misc]


def test_source_data_is_frozen() -> None:
    sd = SourceData(source_id="src_1", source_path="/data.csv", source_type="csv")
    with pytest.raises(AttributeError):
        sd.source_path = "/other.csv"  # type: ignore[misc]


# ── SourceData ──────────────────────────────────────────────────────────────

def test_source_data_creation() -> None:
    sd = SourceData(
        source_id="src_1", source_path="/path/to/data.csv",
        source_type="csv", file_hash="abc123", record_count=1000,
        description="CPI raw data",
    )
    assert sd.source_id == "src_1"
    assert sd.source_path == "/path/to/data.csv"
    assert sd.source_type == "csv"
    assert sd.file_hash == "abc123"
    assert sd.record_count == 1000
    assert sd.description == "CPI raw data"


def test_source_data_with_provenance() -> None:
    p = Provenance(created_at="2026-01-01T00:00:00", created_by="test", entity_version="1.0.0")
    sd = SourceData(source_id="src_1", source_path="/d.csv", source_type="csv", provenance=p)
    assert sd.provenance is not None


# ── KnowledgeRecord ─────────────────────────────────────────────────────────

def test_knowledge_record_creation() -> None:
    kr = KnowledgeRecord(
        knowledge_id="kr_1", event_type="CPI", asset="GOLD",
        condition={"pressure": "high"}, horizon_days=5, sample_count=100,
        positive_return_rate_pct=60.0, negative_return_rate_pct=40.0,
        up_direction_rate_pct=50.0, down_direction_rate_pct=30.0,
        flat_direction_rate_pct=20.0, average_return_pct=1.5,
        median_return_pct=1.0, min_return_pct=-2.0, max_return_pct=5.0,
        first_event_date="2026-01-01", last_event_date="2026-06-01",
        bias="bullish", confidence=0.8, explanation="CPI test",
    )
    assert kr.knowledge_id == "kr_1"
    assert kr.event_type == "CPI"
    assert kr.asset == "GOLD"
    assert kr.condition == {"pressure": "high"}
    assert kr.horizon_days == 5
    assert kr.sample_count == 100
    assert kr.confidence == 0.8
    assert kr.provenance is None


def test_knowledge_record_with_provenance() -> None:
    p = Provenance(created_at="2026-01-01T00:00:00", created_by="test", entity_version="1.0.0")
    kr = KnowledgeRecord(
        knowledge_id="kr_1", event_type="CPI", asset="GOLD",
        condition={}, horizon_days=5, sample_count=100,
        positive_return_rate_pct=0.0, negative_return_rate_pct=0.0,
        up_direction_rate_pct=0.0, down_direction_rate_pct=0.0,
        flat_direction_rate_pct=0.0, average_return_pct=0.0,
        median_return_pct=0.0, min_return_pct=0.0, max_return_pct=0.0,
        first_event_date="", last_event_date="",
        bias="neutral", confidence=0.0, explanation="",
        provenance=p,
    )
    assert kr.provenance is not None
    assert kr.provenance.entity_version == "1.0.0"


# ── Full Lineage Trace ──────────────────────────────────────────────────────

def test_full_lineage_trace() -> None:
    reg = LineageRegistry()

    reg.add("src_1", "source_data", "lesson_1", "lesson", LineageRelationType.GENERATES)
    reg.add("lesson_1", "lesson", "kr_1", "knowledge_record", LineageRelationType.GENERATES)
    reg.add("kr_1", "knowledge_record", "ev_1", "evidence", LineageRelationType.REFERENCES)
    reg.add("ev_1", "evidence", "chain_1", "reasoning_chain", LineageRelationType.REFERENCES)
    reg.add("chain_1", "reasoning_chain", "dec_1", "decision", LineageRelationType.GENERATES)

    path = reg.trace("dec_1", "decision")
    assert len(path) >= 4

    source_ids = [r.source_id for r in path]
    target_ids = [r.target_id for r in path]
    all_ids = set(source_ids + target_ids)
    assert "src_1" in all_ids
    assert "lesson_1" in all_ids
    assert "kr_1" in all_ids
    assert "ev_1" in all_ids
    assert "chain_1" in all_ids
    assert "dec_1" in all_ids


def test_full_lineage_forward_backward() -> None:
    reg = LineageRegistry()
    reg.add("src_1", "source_data", "lesson_1", "lesson")
    reg.add("lesson_1", "lesson", "kr_1", "knowledge_record")

    forward = reg.query(entity_id="src_1", direction="forward")
    assert len(forward) == 1
    assert forward[0].target_id == "lesson_1"

    backward = reg.query(entity_id="kr_1", direction="backward")
    assert len(backward) == 1
    assert backward[0].source_id == "lesson_1"
