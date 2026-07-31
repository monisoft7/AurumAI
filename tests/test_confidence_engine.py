"""Unit + integration tests for W9 Institutional Confidence Engine."""

import json

import pytest

from confidence_engine.computer import ConfidenceComputer
from confidence_engine.contracts import (
    VALID_RELIABILITY,
    InstitutionalConfidence,
    ThesisConfidence,
)
from confidence_engine.engine import ConfidenceEngine
from confidence_engine.ranker import ConfidenceRanker
from knowledge.integrity.provenance import Provenance
from thesis_construction.contracts import InvestmentThesis, ThesisConstruction


# =========================================================================
# Helpers
# =========================================================================


def _make_thesis(
    thesis_id: str = "th_1",
    direction: str = "bullish",
    regime: str = "NORMAL_GROWTH",
    supporting_set_ids: tuple[str, ...] = ("es_reallyield",),
    counter_evidence_ids: tuple[str, ...] = (),
    remaining_unknowns: tuple[str, ...] = (),
    confidence_inputs: dict | None = None,
    institutional_support: float = 0.7,
    provenance_count: int = 2,
    metadata: dict | None = None,
) -> InvestmentThesis:
    if confidence_inputs is None:
        confidence_inputs = {
            "avg_supporting_weight": 0.6,
            "avg_supporting_consensus": 0.8,
            "conflict_severity": 0.2,
            "confidence_penalty": 0.1,
            "raw_support": 0.48,
        }
    chain = tuple(
        Provenance(
            created_at=f"2026-07-30T18:00:0{i}",
            created_by=f"source_{i}",
            entity_version="1.0.0",
        )
        for i in range(provenance_count)
    )
    return InvestmentThesis(
        thesis_id=thesis_id,
        direction=direction,
        supporting_set_ids=supporting_set_ids,
        counter_evidence_ids=counter_evidence_ids,
        regime=regime,
        economic_mechanism="test mechanism",
        time_horizon_days=90,
        invalidating_conditions=("test condition",),
        remaining_unknowns=remaining_unknowns,
        confidence_inputs=confidence_inputs,
        institutional_support=institutional_support,
        explanation="test thesis",
        provenance_chain=chain,
        metadata=metadata or {},
    )


def _make_construction(
    theses: tuple[InvestmentThesis, ...] | None = None,
    regime: str = "NORMAL_GROWTH",
) -> ThesisConstruction:
    if theses is None:
        theses = (_make_thesis(),)
    return ThesisConstruction(
        construction_id="tc_w9_test",
        reasoning_id="er_w9_test",
        assessment_id="cea_w9_test",
        timestamp="2026-07-30T18:00:00",
        regime=regime,
        theses=theses,
        ranked_thesis_ids=tuple(t.thesis_id for t in theses),
        total_theses=len(theses),
        primary_thesis_id=theses[0].thesis_id if theses else "",
    )


# =========================================================================
# Contract tests
# =========================================================================


class TestThesisConfidence:
    def test_minimal_confidence(self):
        tc = ThesisConfidence(thesis_id="th_1")
        assert tc.thesis_id == "th_1"
        assert tc.final_confidence == 0.0
        assert tc.reliability_category == "very_low"

    def test_to_dict_from_dict_roundtrip(self):
        prov = Provenance("2026-07-30T18:00:00", "W9 ConfidenceEngine", "1.0.0")
        tc = ThesisConfidence(
            thesis_id="th_rt",
            final_confidence=0.72,
            confidence_breakdown={"evidence_quality": 0.6},
            positive_contributors=(
                {"name": "evidence_quality", "value": 0.6, "weight": 0.25},
            ),
            negative_contributors=(
                {"name": "counter_evidence", "value": 0.2, "weight": 0.35},
            ),
            confidence_penalties=(
                {"name": "counter_evidence", "value": 0.2, "penalty": 0.07},
            ),
            remaining_uncertainty=0.28,
            reliability_category="high",
            provenance_chain=(prov,),
        )
        d = tc.to_dict()
        restored = ThesisConfidence.from_dict(d)
        assert restored.thesis_id == tc.thesis_id
        assert restored.final_confidence == 0.72
        assert restored.reliability_category == "high"
        assert len(restored.positive_contributors) == 1

    def test_validate_passes_for_valid(self):
        tc = ThesisConfidence(
            thesis_id="th_valid",
            final_confidence=0.5,
            remaining_uncertainty=0.5,
            reliability_category="moderate",
        )
        errors = tc.validate()
        assert not errors

    def test_validate_detects_out_of_range(self):
        tc = ThesisConfidence(
            thesis_id="th_bad",
            final_confidence=1.5,
            reliability_category="high",
        )
        errors = tc.validate()
        assert any("final_confidence" in e for e in errors)

    def test_validate_detects_invalid_category(self):
        tc = ThesisConfidence(
            thesis_id="th_cat",
            final_confidence=0.5,
            reliability_category="super_high",
        )
        errors = tc.validate()
        assert any("reliability_category" in e for e in errors)

    def test_validate_detects_missing_thesis_id(self):
        tc = ThesisConfidence(thesis_id="")
        errors = tc.validate()
        assert any("thesis_id" in e for e in errors)

    def test_json_serializable(self):
        tc = ThesisConfidence(
            thesis_id="th_json",
            final_confidence=0.4,
            reliability_category="low",
        )
        serialized = json.dumps(tc.to_dict())
        restored = ThesisConfidence.from_dict(json.loads(serialized))
        assert restored.thesis_id == "th_json"

    def test_valid_reliability_categories(self):
        assert VALID_RELIABILITY == {"high", "moderate", "low", "very_low"}


class TestInstitutionalConfidence:
    def test_empty_confidence(self):
        ic = InstitutionalConfidence(
            confidence_id="cf_empty",
            construction_id="tc_empty",
            timestamp="2026-07-30T18:00:00",
            regime="NORMAL_GROWTH",
        )
        assert ic.avg_confidence == 0.0
        assert ic.primary_confidence is None

    def test_to_dict_from_dict_roundtrip(self):
        tc = ThesisConfidence(
            thesis_id="th_1",
            final_confidence=0.7,
            reliability_category="high",
        )
        ic = InstitutionalConfidence(
            confidence_id="cf_rt",
            construction_id="tc_rt",
            timestamp="2026-07-30T18:00:00",
            regime="NORMAL_GROWTH",
            theses_confidence=(tc,),
            ranked_thesis_ids=("th_1",),
            low_confidence_thesis_ids=(),
            conflicting_high_confidence_pairs=(),
            primary_thesis_id="th_1",
        )
        d = ic.to_dict()
        restored = InstitutionalConfidence.from_dict(d)
        assert restored.confidence_id == ic.confidence_id
        assert restored.avg_confidence == 0.7
        assert restored.primary_confidence is not None
        assert restored.primary_confidence.thesis_id == "th_1"

    def test_avg_confidence(self):
        tc1 = ThesisConfidence("th_1", final_confidence=0.8)
        tc2 = ThesisConfidence("th_2", final_confidence=0.6)
        ic = InstitutionalConfidence(
            confidence_id="cf_avg",
            construction_id="tc_avg",
            timestamp="2026-07-30T18:00:00",
            regime="NORMAL_GROWTH",
            theses_confidence=(tc1, tc2),
        )
        assert ic.avg_confidence == 0.7


# =========================================================================
# ConfidenceComputer tests
# =========================================================================


class TestConfidenceComputer:
    def test_compute_returns_normalized_score(self):
        thesis = _make_thesis()
        computer = ConfidenceComputer()
        result = computer.compute(thesis)
        assert 0.0 <= result["final_confidence"] <= 1.0

    def test_compute_breakdown_contains_all_components(self):
        thesis = _make_thesis()
        computer = ConfidenceComputer()
        result = computer.compute(thesis)
        breakdown = result["confidence_breakdown"]
        for component in (
            "evidence_quality",
            "evidence_consensus",
            "regime_alignment",
            "source_diversity",
            "knowledge_record_quality",
            "temporal_recency",
            "counter_evidence",
            "missing_evidence",
            "internal_consistency",
        ):
            assert component in breakdown

    def test_compute_positive_contributors(self):
        thesis = _make_thesis()
        computer = ConfidenceComputer()
        result = computer.compute(thesis)
        assert len(result["positive_contributors"]) == 6
        names = {c["name"] for c in result["positive_contributors"]}
        assert "evidence_quality" in names
        assert "regime_alignment" in names

    def test_compute_penalties(self):
        thesis = _make_thesis(
            confidence_inputs={
                "avg_supporting_weight": 0.6,
                "avg_supporting_consensus": 0.8,
                "conflict_severity": 0.5,
                "confidence_penalty": 0.4,
                "raw_support": 0.48,
            },
            remaining_unknowns=("INFLATION", "USD_FX"),
        )
        computer = ConfidenceComputer()
        result = computer.compute(thesis)
        assert len(result["confidence_penalties"]) == 3

    def test_higher_quality_higher_confidence(self):
        strong = _make_thesis(
            confidence_inputs={
                "avg_supporting_weight": 0.9,
                "avg_supporting_consensus": 0.95,
                "conflict_severity": 0.0,
                "confidence_penalty": 0.0,
                "raw_support": 0.855,
            },
            institutional_support=0.9,
            supporting_set_ids=("a", "b", "c"),
            provenance_count=3,
        )
        weak = _make_thesis(
            confidence_inputs={
                "avg_supporting_weight": 0.3,
                "avg_supporting_consensus": 0.4,
                "conflict_severity": 0.8,
                "confidence_penalty": 0.6,
                "raw_support": 0.12,
            },
            institutional_support=0.2,
            supporting_set_ids=(),
            provenance_count=0,
        )
        computer = ConfidenceComputer()
        strong_result = computer.compute(strong)
        weak_result = computer.compute(weak)
        assert strong_result["final_confidence"] > weak_result["final_confidence"]

    def test_regime_alignment_bullish_normal_growth(self):
        thesis = _make_thesis(direction="bullish", regime="NORMAL_GROWTH")
        computer = ConfidenceComputer()
        result = computer.compute(thesis)
        assert result["confidence_breakdown"]["regime_alignment"] == 1.0

    def test_regime_alignment_misaligned(self):
        thesis = _make_thesis(direction="bearish", regime="NORMAL_GROWTH")
        computer = ConfidenceComputer()
        result = computer.compute(thesis)
        assert result["confidence_breakdown"]["regime_alignment"] == 0.0

    def test_reliability_categories(self):
        computer = ConfidenceComputer()
        assert computer.reliability_category(0.75) == "high"
        assert computer.reliability_category(0.6) == "moderate"
        assert computer.reliability_category(0.4) == "low"
        assert computer.reliability_category(0.2) == "very_low"

    def test_remaining_uncertainty_complements_confidence(self):
        thesis = _make_thesis()
        computer = ConfidenceComputer()
        result = computer.compute(thesis)
        assert abs(result["remaining_uncertainty"] + result["final_confidence"] - 1.0) < 0.0001


# =========================================================================
# ConfidenceRanker tests
# =========================================================================


class TestConfidenceRanker:
    def test_rank_by_confidence_descending(self):
        ranker = ConfidenceRanker()
        confs = [
            {"thesis_id": "th_1", "final_confidence": 0.7},
            {"thesis_id": "th_2", "final_confidence": 0.4},
            {"thesis_id": "th_3", "final_confidence": 0.9},
        ]
        ranked = ranker.rank_by_confidence(confs)
        assert ranked == ["th_3", "th_1", "th_2"]

    def test_detect_low_confidence(self):
        ranker = ConfidenceRanker()
        confs = [
            {"thesis_id": "th_1", "final_confidence": 0.3},
            {"thesis_id": "th_2", "final_confidence": 0.5},
            {"thesis_id": "th_3", "final_confidence": 0.2},
        ]
        low = ranker.detect_low_confidence(confs, threshold=0.35)
        assert low == ["th_1", "th_3"]

    def test_detect_conflicting_high_confidence(self):
        ranker = ConfidenceRanker()
        theses = [
            _make_thesis("th_bull", direction="bullish"),
            _make_thesis("th_bear", direction="bearish"),
            _make_thesis("th_neutral", direction="neutral"),
        ]
        confs = [
            {"thesis_id": "th_bull", "final_confidence": 0.8},
            {"thesis_id": "th_bear", "final_confidence": 0.75},
            {"thesis_id": "th_neutral", "final_confidence": 0.9},
        ]
        pairs = ranker.detect_conflicting_high_confidence(theses, confs, threshold=0.6)
        assert len(pairs) == 1
        assert set(pairs[0]) == {"th_bull", "th_bear"}

    def test_no_conflict_when_low_confidence(self):
        ranker = ConfidenceRanker()
        theses = [
            _make_thesis("th_bull", direction="bullish"),
            _make_thesis("th_bear", direction="bearish"),
        ]
        confs = [
            {"thesis_id": "th_bull", "final_confidence": 0.8},
            {"thesis_id": "th_bear", "final_confidence": 0.3},
        ]
        pairs = ranker.detect_conflicting_high_confidence(theses, confs, threshold=0.6)
        assert pairs == []

    def test_no_conflict_for_same_direction(self):
        ranker = ConfidenceRanker()
        theses = [
            _make_thesis("th_1", direction="bullish"),
            _make_thesis("th_2", direction="bullish"),
        ]
        confs = [
            {"thesis_id": "th_1", "final_confidence": 0.8},
            {"thesis_id": "th_2", "final_confidence": 0.75},
        ]
        pairs = ranker.detect_conflicting_high_confidence(theses, confs)
        assert pairs == []


# =========================================================================
# ConfidenceEngine integration tests
# =========================================================================


class TestConfidenceEngine:
    def test_evaluate_produces_confidence(self):
        construction = _make_construction((_make_thesis(),))
        engine = ConfidenceEngine()
        result = engine.evaluate(construction)
        assert isinstance(result, InstitutionalConfidence)
        assert result.construction_id == construction.construction_id
        assert result.regime == "NORMAL_GROWTH"
        assert len(result.theses_confidence) == 1

    def test_evaluate_single_thesis_ranked(self):
        construction = _make_construction((_make_thesis("th_1"),))
        engine = ConfidenceEngine()
        result = engine.evaluate(construction)
        assert result.ranked_thesis_ids == ("th_1",)
        assert result.primary_thesis_id == "th_1"
        assert result.primary_confidence is not None
        assert 0.0 <= result.primary_confidence.final_confidence <= 1.0

    def test_evaluate_multiple_theses_ranked(self):
        theses = (
            _make_thesis(
                "th_strong",
                institutional_support=0.9,
                confidence_inputs={
                    "avg_supporting_weight": 0.9,
                    "avg_supporting_consensus": 0.9,
                    "conflict_severity": 0.0,
                    "confidence_penalty": 0.0,
                    "raw_support": 0.81,
                },
            ),
            _make_thesis(
                "th_weak",
                institutional_support=0.2,
                confidence_inputs={
                    "avg_supporting_weight": 0.2,
                    "avg_supporting_consensus": 0.3,
                    "conflict_severity": 0.9,
                    "confidence_penalty": 0.8,
                    "raw_support": 0.06,
                },
            ),
        )
        construction = _make_construction(theses)
        engine = ConfidenceEngine()
        result = engine.evaluate(construction)
        assert result.ranked_thesis_ids[0] == "th_strong"

    def test_evaluate_detects_low_confidence(self):
        thesis = _make_thesis(
            "th_low",
            institutional_support=0.1,
            confidence_inputs={
                "avg_supporting_weight": 0.1,
                "avg_supporting_consensus": 0.2,
                "conflict_severity": 1.0,
                "confidence_penalty": 1.0,
                "raw_support": 0.02,
            },
        )
        construction = _make_construction((thesis,))
        engine = ConfidenceEngine()
        result = engine.evaluate(construction)
        assert "th_low" in result.low_confidence_thesis_ids

    def test_evaluate_detects_conflicting_high_confidence(self):
        theses = (
            _make_thesis(
                "th_bull",
                direction="bullish",
                institutional_support=0.9,
                confidence_inputs={
                    "avg_supporting_weight": 0.9,
                    "avg_supporting_consensus": 0.9,
                    "conflict_severity": 0.0,
                    "confidence_penalty": 0.0,
                    "raw_support": 0.81,
                },
            ),
            _make_thesis(
                "th_bear",
                direction="bearish",
                institutional_support=0.95,
                confidence_inputs={
                    "avg_supporting_weight": 0.95,
                    "avg_supporting_consensus": 0.95,
                    "conflict_severity": 0.0,
                    "confidence_penalty": 0.0,
                    "raw_support": 0.9,
                },
            ),
        )
        construction = _make_construction(theses)
        engine = ConfidenceEngine()
        result = engine.evaluate(construction)
        assert len(result.conflicting_high_confidence_pairs) == 1

    def test_evaluate_provenance_chain(self):
        construction = _make_construction((_make_thesis(),))
        engine = ConfidenceEngine()
        result = engine.evaluate(construction)
        tc = result.theses_confidence[0]
        assert len(tc.provenance_chain) >= 1
        assert tc.provenance_chain[-1].created_by == "W9 ConfidenceEngine"

    def test_evaluate_json_roundtrip(self):
        theses = (
            _make_thesis("th_1", direction="bullish"),
            _make_thesis("th_2", direction="bearish"),
        )
        construction = _make_construction(theses)
        engine = ConfidenceEngine()
        result = engine.evaluate(construction)
        serialized = json.dumps(result.to_dict())
        restored = InstitutionalConfidence.from_dict(json.loads(serialized))
        assert restored.confidence_id == result.confidence_id
        assert restored.avg_confidence == result.avg_confidence

    def test_evaluate_empty_construction(self):
        construction = _make_construction(())
        engine = ConfidenceEngine()
        result = engine.evaluate(construction)
        assert len(result.theses_confidence) == 0
        assert result.ranked_thesis_ids == ()
        assert result.avg_confidence == 0.0


# =========================================================================
# W8 -> W9 integration test
# =========================================================================


def test_w8_to_w9_integration():
    from evidence_collection.contracts import Evidence, EvidenceCollection
    from evidence_reasoning.reasoner import EvidenceReasoner
    from counter_evidence.assessor import CounterEvidenceAssessor
    from thesis_construction.constructor import ThesisConstructor

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
        collection_id="ec_w8_w9", assessment_id="sa_w8_w9",
        timestamp="2026-07-30T18:00:00", regime="NORMAL_GROWTH",
        items=(ev1, ev2), total_classified=2, signals_count=2,
    )

    reasoning = EvidenceReasoner().reason(collection)
    assessment = CounterEvidenceAssessor().assess(reasoning)
    construction = ThesisConstructor().construct(reasoning, assessment)

    engine = ConfidenceEngine()
    confidence = engine.evaluate(construction)

    assert confidence.construction_id == construction.construction_id
    assert len(confidence.theses_confidence) == construction.total_theses
    assert confidence.primary_thesis_id == construction.primary_thesis_id
    assert confidence.primary_confidence is not None

    for tc in confidence.theses_confidence:
        errors = tc.validate()
        assert not errors, f"Confidence validation failed: {errors}"
        assert 0.0 <= tc.final_confidence <= 1.0
        assert 0.0 <= tc.remaining_uncertainty <= 1.0
        assert tc.reliability_category in VALID_RELIABILITY
        assert "evidence_quality" in tc.confidence_breakdown
        assert "counter_evidence" in tc.confidence_breakdown


# =========================================================================
# W9 orchestration stage test
# =========================================================================


def test_w9_orchestration_stage():
    from orchestration.stages import _confidence_engine

    construction = _make_construction(
        (_make_thesis("th_1"), _make_thesis("th_2", direction="bearish"))
    )
    result = _confidence_engine({}, {"thesis_construction": construction.to_dict()})
    assert isinstance(result, InstitutionalConfidence)
    assert result.construction_id == construction.construction_id
    assert len(result.theses_confidence) == 2


def test_w9_orchestration_stage_missing_data():
    from orchestration.stages import _confidence_engine

    result = _confidence_engine({}, {})
    assert isinstance(result, dict)
    assert "error" in result
