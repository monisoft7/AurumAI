"""Contract 4 rule 5: a non-KR graph node must not be claimed as a KR."""
import json

from evidence_collection.collector import EvidenceCollector
from knowledge.graph.graph import KnowledgeGraph
from knowledge.graph.node import GraphNode
from signal_assessment.contracts import ClassifiedObservation, SignalAssessment


def test_collector_does_not_claim_non_knowledge_node_as_kr(tmp_path):
    fixture = tmp_path / "graph_node.json"
    fixture.write_text(json.dumps({
        "node_id": "observation-cpi-001",
        "node_type": "observation",
        "properties": {"event_type": "CPI"},
    }), encoding="utf-8")
    graph = KnowledgeGraph()
    graph.add_node(GraphNode(**json.loads(fixture.read_text(encoding="utf-8"))))
    observation = ClassifiedObservation(
        observation_id="obs-001", source="overnight_price",
        classification="Signal", confidence=0.8, regime="NORMAL_GROWTH",
        reason="fixed audit input", instrument="Breakeven Inflation",
        change_pct=0.5, change_sigma=1.0,
    )
    assessment = SignalAssessment(
        assessment_id="assessment-001", briefing_id="briefing-001",
        timestamp="2026-09-05T00:00:00+00:00", regime="NORMAL_GROWTH",
        regime_confidence=0.8, observations=(observation,),
    )
    evidence = EvidenceCollector(knowledge_graph=graph).collect(assessment).items[0]
    claimed_id = evidence.metadata.get("knowledge_record_id")
    claimed_node = graph.get_node(claimed_id) if claimed_id else None
    print({"source_kr_id": evidence.source_kr_id,
           "provenance_type": evidence.metadata.get("provenance_type"),
           "knowledge_record_id": claimed_id,
           "actual_node_type": claimed_node.node_type if claimed_node else None,
           "validation_errors": evidence.validate(),
           "has_knowledge_semantics": "knowledge_semantics" in evidence.metadata})
    # Observation-only evidence is allowed; falsely claiming a KR is not.
    assert claimed_id is None
    assert claimed_node is None
    assert evidence.source_kr_id.startswith("no_kr_")
    assert evidence.metadata["provenance_type"] == "observation"


def test_collector_skips_observation_before_valid_knowledge_record(tmp_path):
    fixture = tmp_path / "graph_nodes.json"
    fixture.write_text(json.dumps([
        {
            "node_id": "observation-cpi-001",
            "node_type": "observation",
            "properties": {"event_type": "CPI"},
        },
        {
            "node_id": "CPI-XAU-valid-001",
            "node_type": "knowledge_record",
            "properties": {
                "knowledge_id": "CPI-XAU-valid-001",
                "event_type": "CPI",
            },
        },
    ]), encoding="utf-8")
    graph = KnowledgeGraph()
    for item in json.loads(fixture.read_text(encoding="utf-8")):
        graph.add_node(GraphNode(**item))

    evidence = EvidenceCollector(knowledge_graph=graph).collect(
        _assessment()
    ).items[0]

    assert evidence.source_kr_id == "CPI-XAU-valid-001"
    assert evidence.metadata["knowledge_record_id"] == "CPI-XAU-valid-001"
    assert evidence.metadata["provenance_type"] == "knowledge_record"


def test_collector_falls_back_when_knowledge_identity_is_invalid(tmp_path):
    fixture = tmp_path / "invalid_knowledge_node.json"
    fixture.write_text(json.dumps({
        "node_id": "CPI-XAU-node-001",
        "node_type": "knowledge_record",
        "properties": {
            "knowledge_id": "CPI-XAU-different-identity",
            "event_type": "CPI",
        },
    }), encoding="utf-8")
    graph = KnowledgeGraph()
    graph.add_node(GraphNode(**json.loads(fixture.read_text(encoding="utf-8"))))

    evidence = EvidenceCollector(knowledge_graph=graph).collect(
        _assessment()
    ).items[0]

    assert evidence.source_kr_id.startswith("no_kr_")
    assert evidence.metadata["knowledge_record_id"] is None
    assert evidence.metadata["provenance_type"] == "observation"


def _assessment():
    observation = ClassifiedObservation(
        observation_id="obs-001", source="overnight_price",
        classification="Signal", confidence=0.8, regime="NORMAL_GROWTH",
        reason="fixed audit input", instrument="Breakeven Inflation",
        change_pct=0.5, change_sigma=1.0,
    )
    return SignalAssessment(
        assessment_id="assessment-001", briefing_id="briefing-001",
        timestamp="2026-09-05T00:00:00+00:00", regime="NORMAL_GROWTH",
        regime_confidence=0.8, observations=(observation,),
    )
