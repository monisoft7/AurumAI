"""Correction 008-B: explanation-only knowledge rationale in the chain.

The preserved KnowledgeRecord semantics (Correction 008-A) are mirrored into
EvidenceSet metadata as a deterministic rationale via the legacy
ReasoningEngine, then composed into InvestmentThesis explanations (W8) and
recomposed on update (W10).  All assertions verify that the rationale is
purely explanatory: no scoring field changes.
"""

import json

from counter_evidence.contracts import CounterEvidenceAssessment
from evidence_collection.collector import EvidenceCollector
from evidence_collection.contracts import Evidence, EvidenceCollection
from evidence_reasoning.contracts import EvidenceReasoning, EvidenceSet
from evidence_reasoning.knowledge_rationale import build_knowledge_rationale
from evidence_reasoning.reasoner import EvidenceReasoner
from knowledge.evidence.collection import EvidenceCollection as KnowledgeCollection
from knowledge.evidence.evidence import Evidence as KnowledgeEvidence
from knowledge.graph.builder import GraphBuilder
from knowledge.reasoning.context import ReasoningContext
from knowledge.reasoning.engine import ReasoningEngine
from thesis_construction.builder import ThesisBuilder
from thesis_construction.contracts import ThesisConstruction
from thesis_update.updater import ThesisUpdater
from test_evidence_collection import (
    _cpi_semantics_records,
    _make_assessment,
    _make_observation,
)


def _collect_and_reason() -> tuple[EvidenceCollection, EvidenceReasoning]:
    obs = _make_observation(
        obs_id="obs_008b_cpi",
        classification="Signal",
        confidence=0.8,
        instrument="Breakeven Inflation",
        evidence_count=3,
    )
    assessment = _make_assessment([obs])
    kg = GraphBuilder().build(_cpi_semantics_records())
    collection = EvidenceCollector(knowledge_graph=kg).collect(
        assessment,
        regime_weight=0.8,
        cpi_condition={"cpi_pressure": "inflation_pressure_up"},
    )
    reasoning = EvidenceReasoner().reason(collection)
    return collection, reasoning


def _kr_set(reasoning: EvidenceReasoning) -> EvidenceSet:
    for s in reasoning.evidence_sets:
        if "knowledge_rationale" in s.metadata:
            return s
    raise AssertionError("no KR-backed evidence set in reasoning")


def _make_assessment_for(
    reasoning: EvidenceReasoning, supporting_set_id: str
) -> CounterEvidenceAssessment:
    return CounterEvidenceAssessment(
        assessment_id="cea_008b",
        reasoning_id=reasoning.reasoning_id,
        timestamp="2026-08-13T00:00:00",
        regime=reasoning.regime,
        related_set_ids=(supporting_set_id,),
        supporting_set_ids=(supporting_set_id,),
        contradicting_set_ids=(),
        conflict_severity=0.0,
        confidence_penalty=0.0,
        regime_conflict=False,
        bias_flags=(),
    )


def _make_construction(
    thesis, reasoning_id: str, assessment_id: str
) -> ThesisConstruction:
    return ThesisConstruction(
        construction_id="construction_008b",
        reasoning_id=reasoning_id,
        assessment_id=assessment_id,
        timestamp="2026-08-13T00:00:00",
        regime=thesis.regime,
        theses=(thesis,),
        ranked_thesis_ids=(thesis.thesis_id,),
        total_theses=1,
        primary_thesis_id=thesis.thesis_id,
    )


class TestKnowledgeRationaleMetadata:
    def test_kr_evidence_produces_set_rationale_metadata(self):
        _, reasoning = _collect_and_reason()
        entry = _kr_set(reasoning).metadata["knowledge_rationale"][0]
        assert entry["family"] == "CPI"
        assert entry["condition"] == {"cpi_pressure": "inflation_pressure_up"}
        assert entry["horizon_days"] == 1
        assert entry["sample_count"] == 118
        assert entry["average_return_pct"] == -0.033338
        assert entry["confidence"] == 0.511503
        assert entry["positive_return_rate_pct"] == 51.694915
        assert entry["engine_summary"].startswith("For CPI condition")

    def test_engine_summary_matches_reasoning_engine_exactly(self):
        collection, _ = _collect_and_reason()
        semantics = collection.items[0].metadata["knowledge_semantics"]
        knowledge_ev = KnowledgeEvidence(
            evidence_id=collection.items[0].evidence_id,
            source_node_id=collection.items[0].source_kr_node_id,
            event_type="CPI",
            condition=dict(semantics["condition"]),
            horizon_days=semantics["horizon_days"],
            sample_count=semantics["sample_count"],
            average_return_pct=semantics["average_return_pct"],
            confidence=semantics["confidence"],
            bias=semantics["bias"],
            explanation="",
        )
        context = ReasoningContext(
            event_type="CPI",
            condition=dict(semantics["condition"]),
            horizon_days=semantics["horizon_days"],
            institutional_context=dict(semantics["institutional_context"]),
        )
        expected = ReasoningEngine().reason(
            KnowledgeCollection([knowledge_ev]), context
        ).steps[-1].conclusion
        _, reasoning = _collect_and_reason()
        entry = _kr_set(reasoning).metadata["knowledge_rationale"][0]
        assert entry["engine_summary"] == expected

    def test_no_kr_evidence_leaves_rationale_absent(self):
        assessment = _make_assessment()
        collection = EvidenceCollector().collect(assessment)
        reasoning = EvidenceReasoner().reason(collection)
        for s in reasoning.evidence_sets:
            assert "knowledge_rationale" not in s.metadata

    def test_roundtrip_preserves_rationale(self):
        _, reasoning = _collect_and_reason()
        raw = json.dumps(reasoning.to_dict())
        restored = EvidenceReasoning.from_dict(json.loads(raw))
        assert restored.evidence_sets[0].metadata["knowledge_rationale"] == (
            reasoning.evidence_sets[0].metadata["knowledge_rationale"]
        )

    def test_rationale_is_deterministic(self):
        collection, _ = _collect_and_reason()
        first = EvidenceReasoner().reason(collection)
        second = EvidenceReasoner().reason(collection)
        assert first.evidence_sets[0].metadata["knowledge_rationale"] == (
            second.evidence_sets[0].metadata["knowledge_rationale"]
        )

    def test_rationale_numeric_inertness(self):
        collection, _ = _collect_and_reason()
        ev = collection.items[0]
        plain = Evidence(
            evidence_id=ev.evidence_id,
            source_kr_id=ev.source_kr_id,
            source_kr_node_id=ev.source_kr_node_id,
            event_type=ev.event_type,
            condition={"instrument": ev.condition["instrument"]},
            bias=ev.bias,
            base_confidence=ev.base_confidence,
            regime_weight=ev.regime_weight,
            composite_weight=ev.composite_weight,
            explanation=ev.explanation,
            regime=ev.regime,
            source_label=ev.source_label,
            mechanism=ev.mechanism,
            provenance=ev.provenance,
            temporal_recency=ev.temporal_recency,
            metadata={k: v for k, v in ev.metadata.items()
                      if k != "knowledge_semantics"},
        )
        rich_set = EvidenceReasoner().reason(
            EvidenceCollection.from_dict(collection.to_dict())
        ).evidence_sets[0]
        plain_set = EvidenceReasoner().reason(
            EvidenceCollection(
                collection_id="ec_008b_plain",
                assessment_id=collection.assessment_id,
                timestamp=collection.timestamp,
                regime=collection.regime,
                items=(plain,),
            )
        ).evidence_sets[0]
        assert "knowledge_rationale" in rich_set.metadata
        assert "knowledge_rationale" not in plain_set.metadata
        assert rich_set.set_id == plain_set.set_id
        assert rich_set.bias == plain_set.bias
        assert rich_set.net_institutional_weight == plain_set.net_institutional_weight
        assert rich_set.consensus_score == plain_set.consensus_score
        assert rich_set.confidence_contribution == plain_set.confidence_contribution
        assert rich_set.explanation == plain_set.explanation


class TestExplanationComposition:
    def test_builder_composes_rationale_into_explanation(self):
        _, reasoning = _collect_and_reason()
        kr_set = _kr_set(reasoning)
        assessment = _make_assessment_for(reasoning, kr_set.set_id)
        thesis = ThesisBuilder().build_thesis(
            "bullish", reasoning, assessment, [kr_set.set_id], []
        )
        assert "knowledge: CPI cpi_pressure=inflation_pressure_up:" in thesis.explanation
        assert "avg -0.033% over 1d" in thesis.explanation
        assert "conf 0.512" in thesis.explanation
        assert "118 samples" in thesis.explanation
        assert "51.7% positive-rate" in thesis.explanation

    def test_builder_without_rationale_unchanged(self):
        assessment = _make_assessment()
        collection = EvidenceCollector().collect(assessment)
        reasoning = EvidenceReasoner().reason(collection)
        kr_set_check = [
            s for s in reasoning.evidence_sets
            if "knowledge_rationale" in s.metadata
        ]
        assert not kr_set_check
        supporting = list(reasoning.evidence_sets)
        assessment = _make_assessment_for(
            reasoning, supporting[0].set_id
        )
        thesis = ThesisBuilder().build_thesis(
            "bullish", reasoning, assessment,
            [s.set_id for s in supporting], [],
        )
        assert "knowledge:" not in thesis.explanation
        assert thesis.explanation.startswith("Thesis direction=bullish")

    def test_updater_recomposes_rationale_in_updated_thesis(self):
        _, reasoning = _collect_and_reason()
        kr_set = _kr_set(reasoning)
        assessment = _make_assessment_for(reasoning, kr_set.set_id)
        thesis = ThesisBuilder().build_thesis(
            "bullish", reasoning, assessment, [kr_set.set_id], []
        )
        update = ThesisUpdater().update(
            _make_construction(
                thesis, reasoning.reasoning_id, assessment.assessment_id
            ),
            reasoning,
            assessment,
        )
        assert "knowledge: CPI cpi_pressure=inflation_pressure_up:" in (
            update.updated_thesis.explanation
        )
        assert "UPDATED v2" in update.updated_thesis.explanation

    def test_positive_rate_suffix_only_when_present(self):
        ev = Evidence(
            evidence_id="ev_008b_no_posrate",
            source_kr_id="KR-008B",
            source_kr_node_id="KR-008B",
            event_type="INFLATION",
            condition={"instrument": "Breakeven Inflation"},
            bias="bullish",
            base_confidence=0.8,
            regime_weight=0.8,
            composite_weight=0.64,
            explanation="test",
            regime="NORMAL_GROWTH",
            source_label="overnight_price",
            metadata={
                "knowledge_semantics": {
                    "condition": {"cpi_pressure": "inflation_pressure_up"},
                    "horizon_days": 1,
                    "sample_count": 118,
                    "average_return_pct": -0.033338,
                    "confidence": 0.511503,
                },
            },
        )
        entry = build_knowledge_rationale([ev])[0]
        assert "positive_return_rate_pct" not in entry
        s = EvidenceSet(
            set_id="es_008b",
            event_type="INFLATION",
            bias="bullish",
            evidence_ids=(ev.evidence_id,),
            metadata={"knowledge_rationale": [entry]},
        )
        chunk = ThesisBuilder._compose_knowledge_rationale([s])
        assert chunk.startswith("knowledge: ")
        assert "positive-rate" not in chunk
        assert "118 samples" in chunk