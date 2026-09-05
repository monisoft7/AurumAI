"""Regression coverage for valid supporting KnowledgeRecord confidence."""

from dataclasses import replace

import pytest

from evidence_reasoning.detector import EvidenceDetector
from evidence_reasoning.contracts import EvidenceReasoning
from thesis_construction.builder import ThesisBuilder

from confidence_engine.computer import ConfidenceComputer
from counter_evidence.assessor import CounterEvidenceAssessor
from evidence_collection.collector import EvidenceCollector
from evidence_reasoning.reasoner import EvidenceReasoner
from knowledge.graph.graph import KnowledgeGraph
from knowledge.graph.node import GraphNode
from signal_assessment.contracts import ClassifiedObservation, SignalAssessment
from thesis_construction.constructor import ThesisConstructor


def _assessment() -> SignalAssessment:
    observation = ClassifiedObservation(
        observation_id="obs-fixed",
        source="overnight_price",
        classification="Signal",
        confidence=0.8,
        regime="NORMAL_GROWTH",
        reason="fixed audit input",
        instrument="Breakeven Inflation",
        change_pct=0.5,
        change_sigma=1.0,
    )
    return SignalAssessment(
        assessment_id="assessment-fixed",
        briefing_id="briefing-fixed",
        timestamp="2026-09-05T00:00:00+00:00",
        regime="NORMAL_GROWTH",
        regime_confidence=0.8,
        observations=(observation,),
    )


def _evaluate(graph: KnowledgeGraph):
    collection = EvidenceCollector(knowledge_graph=graph).collect(_assessment())
    reasoning = EvidenceReasoner().reason(collection)
    counter = CounterEvidenceAssessor().assess(reasoning)
    construction = ThesisConstructor().construct(reasoning, counter)
    thesis = next(t for t in construction.theses if t.direction == "bullish")
    confidence = ConfidenceComputer().compute(thesis)
    return collection.items[0], reasoning.evidence_sets[0], thesis, confidence


def test_observation_fallback_does_not_earn_knowledge_record_quality():
    valid_graph = KnowledgeGraph()
    valid_graph.add_node(GraphNode(
        node_id="CPI-XAU-valid",
        node_type="knowledge_record",
        properties={"knowledge_id": "CPI-XAU-valid", "event_type": "CPI"},
    ))

    linked_ev, linked_set, _, linked_confidence = _evaluate(valid_graph)
    fallback_ev, fallback_set, fallback_thesis, fallback_confidence = _evaluate(
        KnowledgeGraph()
    )
    no_chain_confidence = ConfidenceComputer().compute(
        replace(fallback_thesis, provenance_chain=())
    )

    confidence_delta = round(
        fallback_confidence["final_confidence"]
        - no_chain_confidence["final_confidence"],
        4,
    )
    print({
        "linked": {
            "source_kr_id": linked_ev.source_kr_id,
            "net_weight": linked_set.net_institutional_weight,
            "knowledge_record_quality": linked_confidence["confidence_breakdown"]["knowledge_record_quality"],
            "final_confidence": linked_confidence["final_confidence"],
        },
        "fallback": {
            "source_kr_id": fallback_ev.source_kr_id,
            "knowledge_record_id": fallback_ev.metadata["knowledge_record_id"],
            "provenance_type": fallback_ev.metadata["provenance_type"],
            "net_weight": fallback_set.net_institutional_weight,
            "knowledge_record_quality": fallback_confidence["confidence_breakdown"]["knowledge_record_quality"],
            "final_confidence": fallback_confidence["final_confidence"],
            "final_without_workflow_provenance": no_chain_confidence["final_confidence"],
            "confidence_delta": confidence_delta,
        },
    })

    assert linked_ev.metadata["provenance_type"] == "knowledge_record"
    assert fallback_ev.source_kr_id.startswith("no_kr_")
    assert fallback_ev.metadata["knowledge_record_id"] is None
    assert fallback_ev.metadata["provenance_type"] == "observation"
    assert fallback_set.net_institutional_weight == linked_set.net_institutional_weight
    assert fallback_thesis.provenance_chain
    assert fallback_thesis.confidence_inputs["valid_knowledge_record_count"] == 0
    assert linked_set.metadata["supporting_knowledge_record_ids"] == ["CPI-XAU-valid"]
    assert linked_confidence["confidence_breakdown"]["knowledge_record_quality"] == 0.3333
    assert linked_confidence["final_confidence"] > fallback_confidence["final_confidence"]
    assert confidence_delta == 0.0
    assert (
        fallback_confidence["confidence_breakdown"]["knowledge_record_quality"]
        == 0.0
    ), "fallback evidence has no KnowledgeRecord and must not earn KR quality"


def _evidence(evidence_id, kr_id="KR-A", **changes):
    template = EvidenceCollector(knowledge_graph=KnowledgeGraph()).collect(_assessment()).items[0]
    return replace(
        template, evidence_id=evidence_id, source_kr_id=kr_id,
        metadata={"provenance_type": "knowledge_record", "knowledge_record_id": kr_id},
        **changes,
    )


def _thesis(sets, supporting_ids, counter_ids=()):
    reasoning = EvidenceReasoning(
        reasoning_id="reason-fixed", collection_id="collection-fixed",
        timestamp="2026-09-05T00:00:00+00:00", regime="NORMAL_GROWTH",
        evidence_sets=tuple(sets),
    )
    assessment = CounterEvidenceAssessor().assess(reasoning)
    return ThesisBuilder().build_thesis(
        "bullish", reasoning, assessment, list(supporting_ids), list(counter_ids),
    )


def test_distinct_supporting_kr_ids_are_sorted_and_counted_once_across_sets():
    items = [_evidence("ev-z", "KR-Z"), _evidence("ev-a"), _evidence("ev-a2")]
    first = EvidenceDetector.analyze_group(items, "s1", "CPI", [])
    reversed_set = EvidenceDetector.analyze_group(list(reversed(items)), "s1", "CPI", [])
    second = EvidenceDetector.analyze_group([items[1]], "s2", "USD_FX", [])
    assert first.metadata["supporting_knowledge_record_ids"] == ["KR-A", "KR-Z"]
    assert reversed_set.metadata == first.metadata
    single = _thesis([first], ["s1"])
    repeated = _thesis([first, second], ["s1", "s2"])
    assert single.confidence_inputs["valid_knowledge_record_count"] == 2
    assert repeated.confidence_inputs["valid_knowledge_record_count"] == 2
    assert ConfidenceComputer().compute(repeated)["confidence_breakdown"]["knowledge_record_quality"] == 0.5


@pytest.mark.parametrize("metadata", [
    {},
    {"provenance_type": "observation", "knowledge_record_id": "KR-A"},
    {"provenance_type": "knowledge_record", "knowledge_record_id": None},
    {"provenance_type": "knowledge_record", "knowledge_record_id": ""},
    {"provenance_type": "knowledge_record", "knowledge_record_id": "   "},
    {"provenance_type": "knowledge_record", "knowledge_record_id": 123},
    {"provenance_type": "knowledge_record", "knowledge_record_id": "KR-other"},
])
def test_workflow_provenance_cannot_validate_invalid_kr_metadata(metadata):
    ev = replace(_evidence("ev-invalid"), metadata=metadata)
    assert ev.provenance is not None
    evidence_set = EvidenceDetector.analyze_group([ev], "s1", "CPI", [])
    assert evidence_set.metadata["supporting_knowledge_record_ids"] == []
    thesis = _thesis([evidence_set], ["s1"])
    assert thesis.confidence_inputs["valid_knowledge_record_count"] == 0
    assert ConfidenceComputer().compute(thesis)["confidence_breakdown"]["knowledge_record_quality"] == 0.0


def test_contradicting_kr_items_and_counter_sets_do_not_earn_kr_quality():
    supporting = replace(_evidence("obs-support", composite_weight=0.9), metadata={})
    opposing = _evidence("kr-counter", bias="bearish", composite_weight=0.1)
    mixed = EvidenceDetector.analyze_group([supporting, opposing], "s1", "CPI", [])
    counter = EvidenceDetector.analyze_group([opposing], "counter", "USD_FX", [])
    assert mixed.supporting_evidence_ids == ("obs-support",)
    assert mixed.contradicting_evidence_ids == ("kr-counter",)
    assert mixed.metadata["supporting_knowledge_record_ids"] == []
    assert counter.metadata["supporting_knowledge_record_ids"] == ["KR-A"]
    thesis = _thesis([mixed, counter], ["s1"], ["counter"])
    assert thesis.confidence_inputs["valid_knowledge_record_count"] == 0
    assert ConfidenceComputer().compute(thesis)["confidence_breakdown"]["knowledge_record_quality"] == 0.0


def test_legacy_thesis_without_kr_count_defaults_to_zero():
    evidence_set = EvidenceDetector.analyze_group([_evidence("ev")], "s1", "CPI", [])
    thesis = _thesis([evidence_set], ["s1"])
    assert thesis.provenance_chain
    assert ConfidenceComputer().compute(thesis)["confidence_breakdown"]["knowledge_record_quality"] > 0
    inputs = dict(thesis.confidence_inputs)
    del inputs["valid_knowledge_record_count"]
    legacy = replace(thesis, confidence_inputs=inputs)
    assert ConfidenceComputer().compute(legacy)["confidence_breakdown"]["knowledge_record_quality"] == 0.0


def test_empty_or_legacy_supporting_sets_default_to_zero():
    empty = EvidenceDetector.analyze_group([], "empty", "CPI", [])
    assert empty.metadata["supporting_knowledge_record_ids"] == []
    legacy_set = replace(empty, metadata={})
    for sets, ids in [([], []), ([legacy_set], ["empty"])]:
        thesis = _thesis(sets, ids)
        assert thesis.confidence_inputs["valid_knowledge_record_count"] == 0
