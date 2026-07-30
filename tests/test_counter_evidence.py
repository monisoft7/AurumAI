"""Unit + integration tests for W7 Counter-Evidence & Bias Analysis."""

import json

import pytest

from counter_evidence.analyzer import BiasAnalyzer
from counter_evidence.assessor import CounterEvidenceAssessor
from counter_evidence.contracts import (
    VALID_BIAS_FLAGS,
    CounterEvidenceAssessment,
)
from counter_evidence.detector import ConflictDetector
from evidence_reasoning.contracts import EvidenceReasoning, EvidenceSet
from knowledge.integrity.provenance import Provenance


# =========================================================================
# Helpers
# =========================================================================


def _make_evidence_set(
    set_id: str = "es_reallyield",
    event_type: str = "REAL_YIELD",
    bias: str = "bullish",
    consensus_score: float = 0.8,
    conflict_score: float = 0.2,
    net_weight: float = 0.6,
    evidence_ids: tuple[str, ...] = ("ev_001",),
    regime_dependency: str = "NORMAL_GROWTH",
) -> EvidenceSet:
    return EvidenceSet(
        set_id=set_id,
        event_type=event_type,
        bias=bias,
        evidence_ids=evidence_ids,
        supporting_evidence_ids=evidence_ids,
        net_institutional_weight=net_weight,
        consensus_score=consensus_score,
        conflict_score=conflict_score,
        confidence_contribution=round(net_weight * consensus_score, 4),
        regime_dependency=regime_dependency,
        explanation=f"{bias} set for {event_type}",
        metadata={
            "bias_distribution": {bias: len(evidence_ids)},
            "instruments": ["XAU/USD"],
        },
    )


def _make_reasoning(
    sets: tuple[EvidenceSet, ...] | None = None,
    regime: str = "NORMAL_GROWTH",
) -> EvidenceReasoning:
    if sets is None:
        sets = (_make_evidence_set(),)
    return EvidenceReasoning(
        reasoning_id="er_w7_test",
        collection_id="ec_w7_test",
        timestamp="2026-07-30T18:00:00",
        regime=regime,
        evidence_sets=sets,
        total_evidence_sets=len(sets),
        total_evidence_items=sum(len(s.evidence_ids) for s in sets),
    )


# =========================================================================
# Contract tests
# =========================================================================


class TestCounterEvidenceAssessment:
    def test_minimal_assessment(self):
        cea = CounterEvidenceAssessment(
            assessment_id="cea_test",
            reasoning_id="er_test",
            timestamp="2026-07-30T18:00:00",
            regime="NORMAL_GROWTH",
        )
        assert cea.assessment_id == "cea_test"
        assert cea.conflict_severity == 0.0
        assert cea.confidence_penalty == 0.0
        assert cea.regime_conflict is False

    def test_to_dict_from_dict_roundtrip(self):
        prov = Provenance(
            created_at="2026-07-30T18:00:00",
            created_by="W7 CounterEvidenceAssessor",
            entity_version="1.0.0",
        )
        cea = CounterEvidenceAssessment(
            assessment_id="cea_rt",
            reasoning_id="er_rt",
            timestamp="2026-07-30T18:00:00",
            regime="NORMAL_GROWTH",
            related_set_ids=("es_reallyield", "es_usd_fx"),
            supporting_set_ids=("es_reallyield",),
            contradicting_set_ids=("es_usd_fx",),
            missing_evidence=("INFLATION",),
            bias_flags=("cross_set_conflict", "missing_evidence"),
            conflict_severity=0.45,
            confidence_penalty=0.25,
            regime_conflict=False,
            explanation="test roundtrip",
            provenance_chain=(prov,),
        )
        d = cea.to_dict()
        restored = CounterEvidenceAssessment.from_dict(d)
        assert restored.assessment_id == cea.assessment_id
        assert restored.conflict_severity == 0.45
        assert restored.confidence_penalty == 0.25
        assert len(restored.provenance_chain) == 1
        assert restored.provenance_chain[0].created_by == "W7 CounterEvidenceAssessor"

    def test_validate_passes_for_valid(self):
        cea = CounterEvidenceAssessment(
            assessment_id="cea_valid",
            reasoning_id="er_valid",
            timestamp="2026-07-30T18:00:00",
            regime="NORMAL_GROWTH",
            conflict_severity=0.3,
            confidence_penalty=0.1,
        )
        errors = cea.validate()
        assert not errors

    def test_validate_detects_out_of_range_severity(self):
        cea = CounterEvidenceAssessment(
            assessment_id="cea_bad",
            reasoning_id="er_bad",
            timestamp="2026-07-30T18:00:00",
            regime="NORMAL_GROWTH",
            conflict_severity=1.5,
        )
        errors = cea.validate()
        assert any("conflict_severity" in e for e in errors)

    def test_validate_detects_unknown_bias_flag(self):
        cea = CounterEvidenceAssessment(
            assessment_id="cea_flag",
            reasoning_id="er_flag",
            timestamp="2026-07-30T18:00:00",
            regime="NORMAL_GROWTH",
            bias_flags=("unknown_flag",),
        )
        errors = cea.validate()
        assert any("bias flag" in e for e in errors)

    def test_validate_detects_missing_regime(self):
        cea = CounterEvidenceAssessment(
            assessment_id="cea_reg",
            reasoning_id="er_reg",
            timestamp="2026-07-30T18:00:00",
            regime="",
        )
        errors = cea.validate()
        assert any("regime" in e for e in errors)

    def test_json_serializable(self):
        cea = CounterEvidenceAssessment(
            assessment_id="cea_json",
            reasoning_id="er_json",
            timestamp="2026-07-30T18:00:00",
            regime="INFLATIONARY",
            conflict_severity=0.5,
            confidence_penalty=0.3,
        )
        serialized = json.dumps(cea.to_dict())
        restored = CounterEvidenceAssessment.from_dict(json.loads(serialized))
        assert restored.assessment_id == "cea_json"

    def test_valid_bias_flags(self):
        assert "confirmation_bias" in VALID_BIAS_FLAGS
        assert "source_concentration" in VALID_BIAS_FLAGS
        assert "regime_conflict" in VALID_BIAS_FLAGS
        assert "missing_evidence" in VALID_BIAS_FLAGS
        assert "cross_set_conflict" in VALID_BIAS_FLAGS


# =========================================================================
# ConflictDetector tests
# =========================================================================


class TestConflictDetector:
    def test_cross_set_conflicts_no_conflict(self):
        sets = (
            _make_evidence_set("es_1", bias="bullish"),
            _make_evidence_set("es_2", bias="bullish"),
        )
        contra, supp, _ = ConflictDetector.cross_set_conflicts(sets)
        assert len(contra) == 0
        assert sorted(supp) == ["es_1", "es_2"]

    def test_cross_set_conflicts_with_opposing(self):
        sets = (
            _make_evidence_set("es_1", bias="bullish"),
            _make_evidence_set("es_2", bias="bearish"),
        )
        contra, supp, _ = ConflictDetector.cross_set_conflicts(sets)
        assert "es_2" in contra
        assert "es_1" in supp

    def test_cross_set_conflicts_empty(self):
        contra, supp, _ = ConflictDetector.cross_set_conflicts(())
        assert contra == []
        assert supp == []

    def test_regime_conflict_detected(self):
        sets = (_make_evidence_set("es_1", bias="bearish"),)
        assert ConflictDetector.regime_conflict(sets, "NORMAL_GROWTH") is True

    def test_regime_conflict_not_detected(self):
        sets = (_make_evidence_set("es_1", bias="bullish"),)
        assert ConflictDetector.regime_conflict(sets, "NORMAL_GROWTH") is False

    def test_source_concentration_single_set(self):
        sets = (_make_evidence_set("es_1"),)
        assert ConflictDetector.source_concentration(sets) is True

    def test_source_concentration_multiple_sets(self):
        sets = (
            _make_evidence_set("es_1"),
            _make_evidence_set("es_2"),
        )
        assert ConflictDetector.source_concentration(sets) is False

    def test_missing_event_types(self):
        sets = (_make_evidence_set(event_type="REAL_YIELD"),)
        missing = ConflictDetector.missing_event_types(sets, "NORMAL_GROWTH")
        assert "REAL_YIELD" not in missing
        assert "USD_FX" in missing
        assert "INFLATION" in missing

    def test_missing_event_types_all_present(self):
        sets = (
            _make_evidence_set("es_1", event_type="REAL_YIELD"),
            _make_evidence_set("es_2", event_type="USD_FX"),
            _make_evidence_set("es_3", event_type="INFLATION"),
            _make_evidence_set("es_4", event_type="ETF_FLOW"),
        )
        missing = ConflictDetector.missing_event_types(sets, "NORMAL_GROWTH")
        assert missing == []

    def test_missing_event_types_unknown_regime(self):
        sets = (_make_evidence_set(event_type="REAL_YIELD"),)
        missing = ConflictDetector.missing_event_types(sets, "UNKNOWN_REGIME")
        assert missing == []


# =========================================================================
# BiasAnalyzer tests
# =========================================================================


class TestBiasAnalyzer:
    def test_confirmation_bias_single_set(self):
        sets = (_make_evidence_set("es_1", bias="bullish"),)
        assert BiasAnalyzer.confirmation_bias(sets) is True

    def test_confirmation_bias_all_same(self):
        sets = (
            _make_evidence_set("es_1", bias="bullish"),
            _make_evidence_set("es_2", bias="bullish"),
        )
        assert BiasAnalyzer.confirmation_bias(sets) is True

    def test_confirmation_bias_diverse(self):
        sets = (
            _make_evidence_set("es_1", bias="bullish"),
            _make_evidence_set("es_2", bias="bearish"),
        )
        assert BiasAnalyzer.confirmation_bias(sets) is False

    def test_no_dissent_all_zero(self):
        sets = (
            _make_evidence_set("es_1", conflict_score=0.0),
            _make_evidence_set("es_2", conflict_score=0.0),
        )
        assert BiasAnalyzer.no_dissent(sets) is True

    def test_no_dissent_with_conflict(self):
        sets = (
            _make_evidence_set("es_1", conflict_score=0.3),
            _make_evidence_set("es_2", conflict_score=0.0),
        )
        assert BiasAnalyzer.no_dissent(sets) is False

    def test_compute_conflict_severity_no_contradicting(self):
        sets = (_make_evidence_set(conflict_score=0.0), _make_evidence_set(conflict_score=0.0))
        severity = BiasAnalyzer.compute_conflict_severity(sets, [])
        assert severity == 0.0

    def test_compute_conflict_severity_with_contradicting(self):
        sets = (
            _make_evidence_set("es_1", bias="bullish", conflict_score=0.2),
            _make_evidence_set("es_2", bias="bearish", conflict_score=0.6),
        )
        severity = BiasAnalyzer.compute_conflict_severity(sets, ["es_2"])
        assert 0.0 < severity <= 1.0

    def test_compute_conflict_severity_empty(self):
        assert BiasAnalyzer.compute_conflict_severity((), []) == 0.0

    def test_confidence_penalty_no_issues(self):
        penalty = BiasAnalyzer.compute_confidence_penalty(0.0, [], False)
        assert penalty == 0.0

    def test_confidence_penalty_with_conflict(self):
        penalty = BiasAnalyzer.compute_confidence_penalty(0.5, ["cross_set_conflict"], False)
        assert penalty > 0.0

    def test_confidence_penalty_with_regime_conflict(self):
        penalty = BiasAnalyzer.compute_confidence_penalty(0.0, [], True)
        assert penalty == 0.2

    def test_confidence_penalty_clamps(self):
        penalty = BiasAnalyzer.compute_confidence_penalty(1.0, ["a", "b", "c", "d", "e"], True)
        assert penalty <= 1.0


# =========================================================================
# CounterEvidenceAssessor integration tests
# =========================================================================


class TestCounterEvidenceAssessor:
    def test_assess_single_set(self):
        reasoning = _make_reasoning()
        assessor = CounterEvidenceAssessor()
        result = assessor.assess(reasoning)
        assert isinstance(result, CounterEvidenceAssessment)
        assert result.reasoning_id == reasoning.reasoning_id
        assert len(result.related_set_ids) == 1

    def test_assess_no_conflict(self):
        sets = (
            _make_evidence_set("es_1", bias="bullish", conflict_score=0.0),
            _make_evidence_set("es_2", bias="bullish", conflict_score=0.0),
        )
        reasoning = _make_reasoning(sets)
        assessor = CounterEvidenceAssessor()
        result = assessor.assess(reasoning)
        assert "confirmation_bias" in result.bias_flags
        assert result.regime_conflict is False
        assert result.conflict_severity == 0.0

    def test_assess_with_conflict(self):
        sets = (
            _make_evidence_set("es_1", bias="bullish", conflict_score=0.1),
            _make_evidence_set("es_2", bias="bearish", conflict_score=0.5),
        )
        reasoning = _make_reasoning(sets)
        assessor = CounterEvidenceAssessor()
        result = assessor.assess(reasoning)
        assert "cross_set_conflict" in result.bias_flags
        assert result.conflict_severity > 0.0
        assert result.confidence_penalty > 0.0

    def test_assess_regime_conflict(self):
        sets = (_make_evidence_set("es_1", bias="bearish"),)
        reasoning = _make_reasoning(sets, regime="NORMAL_GROWTH")
        assessor = CounterEvidenceAssessor()
        result = assessor.assess(reasoning)
        assert "regime_conflict" in result.bias_flags
        assert result.regime_conflict is True
        assert result.confidence_penalty > 0.0

    def test_assess_missing_evidence(self):
        sets = (_make_evidence_set("es_1", event_type="REAL_YIELD"),)
        reasoning = _make_reasoning(sets, regime="NORMAL_GROWTH")
        assessor = CounterEvidenceAssessor()
        result = assessor.assess(reasoning)
        assert "missing_evidence" in result.bias_flags
        assert len(result.missing_evidence) > 0

    def test_assess_source_concentration(self):
        sets = (_make_evidence_set("es_1"),)
        reasoning = _make_reasoning(sets)
        assessor = CounterEvidenceAssessor()
        result = assessor.assess(reasoning)
        assert "source_concentration" in result.bias_flags

    def test_assess_empty_reasoning(self):
        reasoning = _make_reasoning(())
        assessor = CounterEvidenceAssessor()
        result = assessor.assess(reasoning)
        assert len(result.related_set_ids) == 0
        assert "confirmation_bias" in result.bias_flags
        assert "source_concentration" in result.bias_flags

    def test_assess_json_roundtrip(self):
        sets = (
            _make_evidence_set("es_1", bias="bullish"),
            _make_evidence_set("es_2", bias="bearish"),
        )
        reasoning = _make_reasoning(sets)
        assessor = CounterEvidenceAssessor()
        result = assessor.assess(reasoning)
        serialized = json.dumps(result.to_dict())
        restored = CounterEvidenceAssessment.from_dict(json.loads(serialized))
        assert restored.assessment_id == result.assessment_id
        assert restored.conflict_severity == result.conflict_severity
        assert sorted(restored.bias_flags) == sorted(result.bias_flags)

    def test_provenance_chain_present(self):
        reasoning = _make_reasoning()
        assessor = CounterEvidenceAssessor()
        result = assessor.assess(reasoning)
        assert len(result.provenance_chain) == 1
        assert result.provenance_chain[0].created_by == "W7 CounterEvidenceAssessor"

    def test_assess_diverse_inflationary(self):
        sets = (
            _make_evidence_set("es_real", event_type="REAL_YIELD", bias="bullish"),
            _make_evidence_set("es_usd", event_type="USD_FX", bias="bearish"),
        )
        reasoning = _make_reasoning(sets, regime="INFLATIONARY")
        assessor = CounterEvidenceAssessor()
        result = assessor.assess(reasoning)
        assert result.regime == "INFLATIONARY"
        assert "confirmation_bias" not in result.bias_flags or len(result.bias_flags) >= 0


# =========================================================================
# W6 -> W7 integration test
# =========================================================================


def test_w6_to_w7_integration():
    from evidence_collection.contracts import Evidence, EvidenceCollection
    from evidence_reasoning.reasoner import EvidenceReasoner

    ev1 = Evidence(
        evidence_id="ev_gold_1", source_kr_id="KR-001", source_kr_node_id="KR-001",
        event_type="REAL_YIELD", condition={"instrument": "XAU/USD"}, bias="bullish",
        base_confidence=0.85, regime_weight=0.8, composite_weight=0.68,
        explanation="Real yields falling", regime="NORMAL_GROWTH",
        source_label="overnight_price",
        temporal_recency=0.9,
        metadata={"instrument": "XAU/USD", "classification": "Signal"},
    )
    ev2 = Evidence(
        evidence_id="ev_dxy_1", source_kr_id="KR-002", source_kr_node_id="KR-002",
        event_type="USD_FX", condition={"instrument": "DXY"}, bias="bearish",
        base_confidence=0.72, regime_weight=0.8, composite_weight=0.576,
        explanation="DXY weakening", regime="NORMAL_GROWTH",
        source_label="overnight_price",
        temporal_recency=0.85,
        metadata={"instrument": "DXY", "classification": "Signal"},
    )

    collection = EvidenceCollection(
        collection_id="ec_w6_w7", assessment_id="sa_w6_w7",
        timestamp="2026-07-30T18:00:00", regime="NORMAL_GROWTH",
        items=(ev1, ev2), total_classified=2, signals_count=2,
    )

    reasoner = EvidenceReasoner()
    reasoning = reasoner.reason(collection)

    assessor = CounterEvidenceAssessor()
    assessment = assessor.assess(reasoning)

    assert assessment.reasoning_id == reasoning.reasoning_id
    assert len(assessment.related_set_ids) == 2
    assert assessment.regime == "NORMAL_GROWTH"
    assert 0.0 <= assessment.conflict_severity <= 1.0
    assert 0.0 <= assessment.confidence_penalty <= 1.0

    errors = assessment.validate()
    assert not errors, f"Validation failed: {errors}"


# =========================================================================
# W7 orchestration stage test
# =========================================================================


def test_w7_orchestration_stage():
    from orchestration.stages import _counter_evidence

    sets = (
        _make_evidence_set("es_1", bias="bullish"),
        _make_evidence_set("es_2", bias="bearish"),
    )
    reasoning = _make_reasoning(sets)

    result = _counter_evidence({}, {"evidence_reasoning": reasoning.to_dict()})
    assert isinstance(result, CounterEvidenceAssessment)
    assert result.reasoning_id == reasoning.reasoning_id
    assert len(result.related_set_ids) == 2


def test_w7_orchestration_stage_missing_data():
    from orchestration.stages import _counter_evidence

    result = _counter_evidence({}, {})
    assert isinstance(result, dict)
    assert "error" in result
