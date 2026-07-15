import json
from pathlib import Path

from knowledge.causal.relation import (
    CausalRelation,
    RELATION_CAUSATION,
    RELATION_CORRELATION,
    RELATION_COINCIDENCE,
    VALID_RELATION_TYPES,
    DIRECTION_SOURCE_TO_TARGET,
    DIRECTION_BIDIRECTIONAL,
    DIRECTION_UNKNOWN,
    VALID_DIRECTIONS,
)
from knowledge.causal.hypothesis import (
    CausalHypothesis,
    HYPOTHESIS_PROPOSED,
    HYPOTHESIS_SUPPORTED,
    HYPOTHESIS_CONTRADICTED,
    HYPOTHESIS_INCONCLUSIVE,
    VALID_HYPOTHESIS_STATUSES,
)
from knowledge.causal.evidence import (
    CausalEvidence,
    EVIDENCE_ROLE_SUPPORTING,
    EVIDENCE_ROLE_CONTRADICTING,
    EVIDENCE_ROLE_CONTEXTUAL,
    VALID_EVIDENCE_ROLES,
)
from knowledge.causal.graph import CausalGraph
from knowledge.causal.analyzer import CausalAnalyzer
from knowledge.causal.repository import CausalRepository


# ── CausalRelation ───────────────────────────────────────────────────────────

def test_causal_relation_defaults() -> None:
    r = CausalRelation(
        relation_id="cr1",
        source_id="node_a",
        target_id="node_b",
        relation_type=RELATION_CAUSATION,
        strength=0.75,
        confidence=0.85,
    )
    assert r.relation_id == "cr1"
    assert r.direction == DIRECTION_UNKNOWN
    assert r.evidence_ids == ()
    assert r.temporal_lag == 0


def test_causal_relation_full() -> None:
    r = CausalRelation(
        relation_id="cr2",
        source_id="cpi_high",
        target_id="gold_up",
        relation_type=RELATION_CAUSATION,
        strength=0.8,
        confidence=0.9,
        direction=DIRECTION_SOURCE_TO_TARGET,
        evidence_ids=("ev_001", "ev_002"),
        temporal_lag=5,
        explanation="CPI increase causes gold to rise within 5 days",
        metadata={"source": "knowledge_graph"},
    )
    assert r.direction == DIRECTION_SOURCE_TO_TARGET
    assert r.temporal_lag == 5


def test_valid_relation_types() -> None:
    assert RELATION_CAUSATION in VALID_RELATION_TYPES
    assert RELATION_CORRELATION in VALID_RELATION_TYPES
    assert RELATION_COINCIDENCE in VALID_RELATION_TYPES


def test_valid_directions() -> None:
    assert DIRECTION_SOURCE_TO_TARGET in VALID_DIRECTIONS
    assert DIRECTION_BIDIRECTIONAL in VALID_DIRECTIONS
    assert DIRECTION_UNKNOWN in VALID_DIRECTIONS


# ── CausalHypothesis ─────────────────────────────────────────────────────────

def test_causal_hypothesis_defaults() -> None:
    h = CausalHypothesis(
        hypothesis_id="hyp1",
        name="CPI drives Gold",
        description="CPI increases cause gold prices to rise",
        cause_node_id="node_cpi",
        effect_node_id="node_gold",
    )
    assert h.status == HYPOTHESIS_PROPOSED
    assert h.confidence == 0.0
    assert h.supporting_evidence_ids == ()


def test_causal_hypothesis_with_evidence() -> None:
    h = CausalHypothesis(
        hypothesis_id="hyp2",
        name="Fed Rate cuts boost equities",
        description="Fed rate cuts cause equity markets to rally",
        cause_node_id="node_fed",
        effect_node_id="node_equities",
        status=HYPOTHESIS_SUPPORTED,
        supporting_evidence_ids=("ev_001", "ev_002"),
        contradicting_evidence_ids=("ev_003",),
        confidence=0.75,
    )
    assert h.status == HYPOTHESIS_SUPPORTED
    assert len(h.supporting_evidence_ids) == 2
    assert h.confidence == 0.75


def test_valid_hypothesis_statuses() -> None:
    assert HYPOTHESIS_PROPOSED in VALID_HYPOTHESIS_STATUSES
    assert HYPOTHESIS_SUPPORTED in VALID_HYPOTHESIS_STATUSES
    assert HYPOTHESIS_CONTRADICTED in VALID_HYPOTHESIS_STATUSES
    assert HYPOTHESIS_INCONCLUSIVE in VALID_HYPOTHESIS_STATUSES


# ── CausalEvidence ───────────────────────────────────────────────────────────

def test_causal_evidence_defaults() -> None:
    ce = CausalEvidence(
        causal_evidence_id="ce1",
        hypothesis_id="hyp1",
        evidence_id="ev_001",
        role=EVIDENCE_ROLE_SUPPORTING,
        strength=0.8,
        explanation="CPI up 1% leads to gold up 1.5%",
    )
    assert ce.role == EVIDENCE_ROLE_SUPPORTING
    assert ce.strength == 0.8


def test_causal_evidence_contradicting() -> None:
    ce = CausalEvidence(
        causal_evidence_id="ce2",
        hypothesis_id="hyp1",
        evidence_id="ev_003",
        role=EVIDENCE_ROLE_CONTRADICTING,
        strength=-0.6,
        explanation="CPI up led to gold down in this instance",
    )
    assert ce.role == EVIDENCE_ROLE_CONTRADICTING
    assert ce.strength == -0.6


def test_valid_evidence_roles() -> None:
    assert EVIDENCE_ROLE_SUPPORTING in VALID_EVIDENCE_ROLES
    assert EVIDENCE_ROLE_CONTRADICTING in VALID_EVIDENCE_ROLES
    assert EVIDENCE_ROLE_CONTEXTUAL in VALID_EVIDENCE_ROLES


# ── CausalGraph: Relations ───────────────────────────────────────────────────

def test_graph_add_and_get_relation() -> None:
    g = CausalGraph()
    r = CausalRelation("cr1", "a", "b", RELATION_CAUSATION, 0.8, 0.9)
    g.add_relation(r)
    assert g.get_relation("cr1") == r
    assert g.relation_count() == 1


def test_graph_relations_between() -> None:
    g = CausalGraph()
    g.add_relation(CausalRelation("cr1", "a", "b", RELATION_CAUSATION, 0.8, 0.9))
    g.add_relation(CausalRelation("cr2", "a", "c", RELATION_CORRELATION, 0.5, 0.6))
    results = g.relations_between("a", "b")
    assert len(results) == 1
    assert results[0].relation_id == "cr1"


def test_graph_relations_from_and_to() -> None:
    g = CausalGraph()
    g.add_relation(CausalRelation("cr1", "a", "b", RELATION_CAUSATION, 0.8, 0.9))
    g.add_relation(CausalRelation("cr2", "a", "c", RELATION_CORRELATION, 0.5, 0.6))
    assert len(g.relations_from("a")) == 2
    assert len(g.relations_to("b")) == 1
    assert len(g.relations_to("c")) == 1


def test_graph_remove_relation() -> None:
    g = CausalGraph()
    g.add_relation(CausalRelation("cr1", "a", "b", RELATION_CAUSATION, 0.8, 0.9))
    assert g.relation_count() == 1
    g.remove_relation("cr1")
    assert g.relation_count() == 0


# ── CausalGraph: Hypotheses ──────────────────────────────────────────────────

def test_graph_add_and_get_hypothesis() -> None:
    g = CausalGraph()
    h = CausalHypothesis("hyp1", "Test", "Test hypothesis", "node_a", "node_b")
    g.add_hypothesis(h)
    assert g.get_hypothesis("hyp1") == h
    assert g.hypothesis_count() == 1


def test_graph_hypotheses_for() -> None:
    g = CausalGraph()
    g.add_hypothesis(CausalHypothesis("hyp1", "H1", "D1", "a", "b"))
    g.add_hypothesis(CausalHypothesis("hyp2", "H2", "D2", "a", "b"))
    results = g.hypotheses_for("a", "b")
    assert len(results) == 2


def test_graph_competing_hypotheses() -> None:
    g = CausalGraph()
    g.add_hypothesis(CausalHypothesis("hyp1", "H1", "D1", "a", "b"))
    g.add_hypothesis(CausalHypothesis("hyp2", "H2", "D2", "b", "a"))
    results = g.competing_hypotheses("a", "b")
    assert len(results) == 2


# ── CausalGraph: Causal Evidence ─────────────────────────────────────────────

def test_graph_add_and_get_causal_evidence() -> None:
    g = CausalGraph()
    ce = CausalEvidence("ce1", "hyp1", "ev_001", EVIDENCE_ROLE_SUPPORTING, 0.8)
    g.add_causal_evidence(ce)
    assert g.get_causal_evidence("ce1") == ce
    assert g.causal_evidence_count() == 1


def test_graph_evidence_for_hypothesis() -> None:
    g = CausalGraph()
    g.add_causal_evidence(CausalEvidence("ce1", "hyp1", "ev_001", EVIDENCE_ROLE_SUPPORTING, 0.8))
    g.add_causal_evidence(CausalEvidence("ce2", "hyp1", "ev_002", EVIDENCE_ROLE_CONTRADICTING, -0.5))
    g.add_causal_evidence(CausalEvidence("ce3", "hyp2", "ev_003", EVIDENCE_ROLE_SUPPORTING, 0.6))
    assert len(g.evidence_for_hypothesis("hyp1")) == 2
    assert len(g.supporting_evidence("hyp1")) == 1
    assert len(g.contradicting_evidence("hyp1")) == 1


# ── CausalGraph: Evaluate Hypothesis ─────────────────────────────────────────

def test_graph_evaluate_proposed() -> None:
    g = CausalGraph()
    g.add_hypothesis(CausalHypothesis("hyp1", "Test", "Desc", "a", "b"))
    assert g.evaluate_hypothesis("hyp1") == HYPOTHESIS_PROPOSED


def test_graph_evaluate_supported() -> None:
    g = CausalGraph()
    g.add_hypothesis(CausalHypothesis("hyp1", "Test", "Desc", "a", "b"))
    g.add_causal_evidence(CausalEvidence("ce1", "hyp1", "ev_001", EVIDENCE_ROLE_SUPPORTING, 0.8))
    g.add_causal_evidence(CausalEvidence("ce2", "hyp1", "ev_002", EVIDENCE_ROLE_SUPPORTING, 0.7))
    assert g.evaluate_hypothesis("hyp1") == HYPOTHESIS_SUPPORTED


def test_graph_evaluate_contradicted() -> None:
    g = CausalGraph()
    g.add_hypothesis(CausalHypothesis("hyp1", "Test", "Desc", "a", "b"))
    g.add_causal_evidence(CausalEvidence("ce1", "hyp1", "ev_001", EVIDENCE_ROLE_CONTRADICTING, -0.8))
    g.add_causal_evidence(CausalEvidence("ce2", "hyp1", "ev_002", EVIDENCE_ROLE_CONTRADICTING, -0.7))
    assert g.evaluate_hypothesis("hyp1") == HYPOTHESIS_CONTRADICTED


def test_graph_evaluate_mixed() -> None:
    g = CausalGraph()
    g.add_hypothesis(CausalHypothesis("hyp1", "Test", "Desc", "a", "b"))
    g.add_causal_evidence(CausalEvidence("ce1", "hyp1", "ev_001", EVIDENCE_ROLE_SUPPORTING, 0.8))
    g.add_causal_evidence(CausalEvidence("ce2", "hyp1", "ev_002", EVIDENCE_ROLE_CONTRADICTING, -0.8))
    result = g.evaluate_hypothesis("hyp1")
    assert result in (HYPOTHESIS_SUPPORTED, HYPOTHESIS_CONTRADICTED, HYPOTHESIS_INCONCLUSIVE)


def test_graph_evaluate_inconclusive() -> None:
    g = CausalGraph()
    g.add_hypothesis(CausalHypothesis("hyp1", "Test", "Desc", "a", "b"))
    g.add_causal_evidence(CausalEvidence("ce1", "hyp1", "ev_001", EVIDENCE_ROLE_SUPPORTING, 0.3))
    result = g.evaluate_hypothesis("hyp1")
    assert result == HYPOTHESIS_INCONCLUSIVE


def test_graph_evaluate_nonexistent() -> None:
    g = CausalGraph()
    assert g.evaluate_hypothesis("nonexistent") is None


# ── CausalGraph: Clear ───────────────────────────────────────────────────────

def test_graph_clear() -> None:
    g = CausalGraph()
    g.add_relation(CausalRelation("cr1", "a", "b", RELATION_CAUSATION, 0.8, 0.9))
    g.add_hypothesis(CausalHypothesis("hyp1", "Test", "Desc", "a", "b"))
    g.add_causal_evidence(CausalEvidence("ce1", "hyp1", "ev_001", EVIDENCE_ROLE_SUPPORTING, 0.8))
    assert g.relation_count() == 1
    assert g.hypothesis_count() == 1
    assert g.causal_evidence_count() == 1
    g.clear()
    assert g.relation_count() == 0
    assert g.hypothesis_count() == 0
    assert g.causal_evidence_count() == 0


# ── CausalAnalyzer: Relation Analysis ────────────────────────────────────────

def test_analyzer_causation() -> None:
    analyzer = CausalAnalyzer()
    source_evidence = [
        {"evidence_id": "ev_001", "average_return_pct": 2.0, "confidence": 0.8, "horizon_days": 5},
        {"evidence_id": "ev_002", "average_return_pct": 1.5, "confidence": 0.7, "horizon_days": 5},
        {"evidence_id": "ev_003", "average_return_pct": 2.5, "confidence": 0.9, "horizon_days": 5},
    ]
    target_evidence = [
        {"evidence_id": "ev_004", "average_return_pct": 2.2, "confidence": 0.85, "horizon_days": 5},
        {"evidence_id": "ev_005", "average_return_pct": 1.8, "confidence": 0.75, "horizon_days": 5},
    ]
    result = analyzer.analyze_relation(
        "cr_test", "cpi_node", "gold_node",
        source_evidence, target_evidence,
    )
    assert result.relation_type == RELATION_CAUSATION
    assert result.strength >= 0.5
    assert result.confidence >= 0.5


def test_analyzer_correlation() -> None:
    analyzer = CausalAnalyzer()
    source_evidence = [
        {"evidence_id": "ev_001", "average_return_pct": 1.0, "confidence": 0.5, "horizon_days": 5},
    ]
    target_evidence = [
        {"evidence_id": "ev_002", "average_return_pct": 0.8, "confidence": 0.5, "horizon_days": 5},
    ]
    result = analyzer.analyze_relation(
        "cr_corr", "node_a", "node_b",
        source_evidence, target_evidence,
    )
    assert result.relation_type in (RELATION_CAUSATION, RELATION_CORRELATION)


def test_analyzer_coincidence() -> None:
    analyzer = CausalAnalyzer()
    source_evidence = [
        {"evidence_id": "ev_001", "average_return_pct": 0.1, "confidence": 0.2, "horizon_days": 5},
    ]
    target_evidence = [
        {"evidence_id": "ev_002", "average_return_pct": -0.1, "confidence": 0.2, "horizon_days": 5},
    ]
    result = analyzer.analyze_relation(
        "cr_coin", "node_x", "node_y",
        source_evidence, target_evidence,
    )
    assert result.relation_type == RELATION_COINCIDENCE


def test_analyzer_empty_evidence() -> None:
    analyzer = CausalAnalyzer()
    result = analyzer.analyze_relation("cr_empty", "a", "b", [], [])
    assert result.relation_type == RELATION_COINCIDENCE
    assert result.strength == 0.0
    assert result.confidence == 0.0


# ── CausalAnalyzer: Low causation due to insufficient evidence ───────────────

def test_analyzer_insufficient_evidence_for_causation() -> None:
    analyzer = CausalAnalyzer()
    source_evidence = [
        {"evidence_id": "ev_001", "average_return_pct": 2.0, "confidence": 0.8, "horizon_days": 5},
    ]
    target_evidence = []
    result = analyzer.analyze_relation("cr_insuf", "a", "b", source_evidence, target_evidence)
    assert result.relation_type in (RELATION_CORRELATION, RELATION_COINCIDENCE)


# ── CausalAnalyzer: Create Hypothesis ────────────────────────────────────────

def test_analyzer_create_hypothesis() -> None:
    graph = CausalGraph()
    analyzer = CausalAnalyzer()
    evidence_list = [
        CausalEvidence("ce1", "hyp_new", "ev_001", EVIDENCE_ROLE_SUPPORTING, 0.8),
        CausalEvidence("ce2", "hyp_new", "ev_002", EVIDENCE_ROLE_SUPPORTING, 0.7),
    ]
    hypothesis = analyzer.create_hypothesis(
        "hyp_new", "CPI drives Gold",
        "CPI increases cause gold prices to rise",
        "node_cpi", "node_gold",
        evidence_list, graph,
    )
    assert hypothesis.hypothesis_id == "hyp_new"
    assert hypothesis.confidence > 0.0
    assert graph.get_hypothesis("hyp_new") == hypothesis
    assert graph.causal_evidence_count() == 2


def test_analyzer_create_hypothesis_mixed() -> None:
    graph = CausalGraph()
    analyzer = CausalAnalyzer()
    evidence_list = [
        CausalEvidence("ce1", "hyp_mix", "ev_001", EVIDENCE_ROLE_SUPPORTING, 0.8),
        CausalEvidence("ce2", "hyp_mix", "ev_002", EVIDENCE_ROLE_CONTRADICTING, -0.8),
    ]
    hypothesis = analyzer.create_hypothesis(
        "hyp_mix", "Mixed evidence",
        "Hypothesis with mixed evidence",
        "node_a", "node_b",
        evidence_list, graph,
    )
    assert len(hypothesis.supporting_evidence_ids) == 1
    assert len(hypothesis.contradicting_evidence_ids) == 1


# ── CausalAnalyzer: Update Hypothesis with Evidence ──────────────────────────

def test_analyzer_update_hypothesis() -> None:
    graph = CausalGraph()
    analyzer = CausalAnalyzer()

    initial = [
        CausalEvidence("ce1", "hyp_upd", "ev_001", EVIDENCE_ROLE_SUPPORTING, 0.8),
    ]
    hypothesis = analyzer.create_hypothesis(
        "hyp_upd", "Updatable", "Desc", "a", "b",
        initial, graph,
    )
    assert len(hypothesis.supporting_evidence_ids) == 1

    new_evidence = [
        CausalEvidence("ce2", "hyp_upd", "ev_002", EVIDENCE_ROLE_SUPPORTING, 0.9),
    ]
    updated = analyzer.update_hypothesis_with_evidence(
        hypothesis, new_evidence, graph,
    )
    assert len(updated.supporting_evidence_ids) == 2
    assert updated.confidence > hypothesis.confidence


# ── CausalAnalyzer: Config property ──────────────────────────────────────────

def test_analyzer_default_thresholds() -> None:
    analyzer = CausalAnalyzer()
    thresholds = analyzer.thresholds
    assert thresholds["causation_min_confidence"] == 0.65
    assert thresholds["causation_min_strength"] == 0.5


def test_analyzer_custom_thresholds() -> None:
    analyzer = CausalAnalyzer({"causation_min_confidence": 0.8})
    assert analyzer.thresholds["causation_min_confidence"] == 0.8
    assert analyzer.thresholds["correlation_min_confidence"] == 0.4


# ── CausalRepository ─────────────────────────────────────────────────────────

def test_repository_save_and_load_graph(tmp_path: Path) -> None:
    graph = CausalGraph()
    graph.add_relation(CausalRelation(
        "cr_save", "node_a", "node_b", RELATION_CAUSATION, 0.8, 0.9,
        evidence_ids=("ev_001",),
        explanation="A causes B",
    ))
    graph.add_hypothesis(CausalHypothesis(
        "hyp_save", "Test Hyp", "Description",
        "node_a", "node_b", status=HYPOTHESIS_SUPPORTED,
    ))
    graph.add_causal_evidence(CausalEvidence(
        "ce_save", "hyp_save", "ev_001",
        EVIDENCE_ROLE_SUPPORTING, 0.8,
    ))

    path = tmp_path / "graph.json"
    CausalRepository().save_graph(graph, path)
    assert path.exists()

    loaded = CausalRepository().load_graph(path)
    assert loaded.relation_count() == 1
    assert loaded.hypothesis_count() == 1
    assert loaded.causal_evidence_count() == 1

    rel = loaded.get_relation("cr_save")
    assert rel is not None
    assert rel.relation_type == RELATION_CAUSATION
    assert rel.strength == 0.8

    hyp = loaded.get_hypothesis("hyp_save")
    assert hyp is not None
    assert hyp.status == HYPOTHESIS_SUPPORTED


def test_repository_empty_graph(tmp_path: Path) -> None:
    graph = CausalGraph()
    path = tmp_path / "empty_graph.json"
    CausalRepository().save_graph(graph, path)
    loaded = CausalRepository().load_graph(path)
    assert loaded.relation_count() == 0
    assert loaded.hypothesis_count() == 0


def test_repository_roundtrip_preserves_evidence_ids(tmp_path: Path) -> None:
    graph = CausalGraph()
    graph.add_relation(CausalRelation(
        "cr_rt", "a", "b", RELATION_CAUSATION, 0.75, 0.85,
        evidence_ids=("ev_001", "ev_002", "ev_003"),
    ))
    path = tmp_path / "rt_graph.json"
    CausalRepository().save_graph(graph, path)
    loaded = CausalRepository().load_graph(path)
    rel = loaded.get_relation("cr_rt")
    assert rel is not None
    assert len(rel.evidence_ids) == 3
    assert rel.evidence_ids[0] == "ev_001"


def test_repository_preserves_hypothesis_conflicting_evidence(tmp_path: Path) -> None:
    graph = CausalGraph()
    graph.add_hypothesis(CausalHypothesis(
        "hyp_conflict", "Conflicting", "Desc",
        "a", "b",
        supporting_evidence_ids=("ev_001",),
        contradicting_evidence_ids=("ev_002",),
        confidence=0.5,
    ))
    path = tmp_path / "conflict.json"
    CausalRepository().save_graph(graph, path)
    loaded = CausalRepository().load_graph(path)
    hyp = loaded.get_hypothesis("hyp_conflict")
    assert hyp is not None
    assert len(hyp.supporting_evidence_ids) == 1
    assert len(hyp.contradicting_evidence_ids) == 1
