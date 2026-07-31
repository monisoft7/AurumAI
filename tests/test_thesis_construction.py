"""Unit + integration tests for W8 Institutional Thesis Construction."""

import json

import pytest

from counter_evidence.contracts import CounterEvidenceAssessment
from evidence_reasoning.contracts import EvidenceReasoning, EvidenceSet
from knowledge.integrity.provenance import Provenance
from thesis_construction.builder import ThesisBuilder
from thesis_construction.constructor import ThesisConstructor
from thesis_construction.contracts import (
    VALID_DIRECTIONS,
    InvestmentThesis,
    ThesisConstruction,
)
from thesis_construction.ranker import ThesisRanker


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
        reasoning_id="er_w8_test",
        collection_id="ec_w8_test",
        timestamp="2026-07-30T18:00:00",
        regime=regime,
        evidence_sets=sets,
        total_evidence_sets=len(sets),
        total_evidence_items=sum(len(s.evidence_ids) for s in sets),
    )


def _make_assessment(
    regime: str = "NORMAL_GROWTH",
    contradicting_set_ids: tuple[str, ...] = (),
    missing_evidence: tuple[str, ...] = (),
    bias_flags: tuple[str, ...] = (),
    conflict_severity: float = 0.0,
    confidence_penalty: float = 0.0,
    regime_conflict: bool = False,
) -> CounterEvidenceAssessment:
    return CounterEvidenceAssessment(
        assessment_id="cea_w8_test",
        reasoning_id="er_w8_test",
        timestamp="2026-07-30T18:00:00",
        regime=regime,
        related_set_ids=("es_reallyield", "es_usd_fx"),
        supporting_set_ids=("es_reallyield",),
        contradicting_set_ids=contradicting_set_ids,
        missing_evidence=missing_evidence,
        bias_flags=bias_flags,
        conflict_severity=conflict_severity,
        confidence_penalty=confidence_penalty,
        regime_conflict=regime_conflict,
        explanation="w8 test assessment",
        provenance_chain=(
            Provenance(
                created_at="2026-07-30T18:00:00",
                created_by="W7 CounterEvidenceAssessor",
                entity_version="1.0.0",
            ),
        ),
    )


# =========================================================================
# Contract tests
# =========================================================================


class TestInvestmentThesis:
    def test_minimal_thesis(self):
        thesis = InvestmentThesis(
            thesis_id="th_test",
            direction="bullish",
            regime="NORMAL_GROWTH",
        )
        assert thesis.thesis_id == "th_test"
        assert thesis.direction == "bullish"
        assert thesis.time_horizon_days == 90
        assert thesis.institutional_support == 0.0

    def test_to_dict_from_dict_roundtrip(self):
        prov = Provenance(
            created_at="2026-07-30T18:00:00",
            created_by="W8 ThesisBuilder",
            entity_version="1.0.0",
        )
        thesis = InvestmentThesis(
            thesis_id="th_rt",
            direction="bearish",
            supporting_set_ids=("es_usd_fx",),
            counter_evidence_ids=("es_reallyield",),
            regime="NORMAL_GROWTH",
            economic_mechanism="US dollar valuation channel",
            time_horizon_days=120,
            invalidating_conditions=("DXY reversal",),
            remaining_unknowns=("INFLATION",),
            confidence_inputs={"raw_support": 0.5},
            institutional_support=0.45,
            explanation="test",
            provenance_chain=(prov,),
        )
        d = thesis.to_dict()
        restored = InvestmentThesis.from_dict(d)
        assert restored.thesis_id == thesis.thesis_id
        assert restored.direction == thesis.direction
        assert restored.institutional_support == 0.45
        assert len(restored.provenance_chain) == 1

    def test_validate_passes_for_valid(self):
        thesis = InvestmentThesis(
            thesis_id="th_valid", direction="bullish",
            institutional_support=0.5, time_horizon_days=90,
        )
        errors = thesis.validate()
        assert not errors

    def test_validate_detects_invalid_direction(self):
        thesis = InvestmentThesis(
            thesis_id="th_bad", direction="aggressive_buy",
        )
        errors = thesis.validate()
        assert any("direction" in e for e in errors)

    def test_validate_detects_out_of_range_support(self):
        thesis = InvestmentThesis(
            thesis_id="th_sup", direction="bullish",
            institutional_support=1.5,
        )
        errors = thesis.validate()
        assert any("institutional_support" in e for e in errors)

    def test_validate_detects_zero_horizon(self):
        thesis = InvestmentThesis(
            thesis_id="th_hor", direction="bullish",
            time_horizon_days=0,
        )
        errors = thesis.validate()
        assert any("time_horizon_days" in e for e in errors)

    def test_json_serializable(self):
        thesis = InvestmentThesis(
            thesis_id="th_json", direction="neutral",
            institutional_support=0.3,
        )
        serialized = json.dumps(thesis.to_dict())
        restored = InvestmentThesis.from_dict(json.loads(serialized))
        assert restored.thesis_id == "th_json"

    def test_valid_directions(self):
        assert VALID_DIRECTIONS == {"bullish", "bearish", "neutral"}


class TestThesisConstruction:
    def test_empty_construction(self):
        tc = ThesisConstruction(
            construction_id="tc_empty",
            reasoning_id="er_empty",
            assessment_id="cea_empty",
            timestamp="2026-07-30T18:00:00",
            regime="NORMAL_GROWTH",
        )
        assert tc.total_theses == 0
        assert tc.primary_thesis is None
        assert tc.primary_thesis_id == ""

    def test_to_dict_from_dict_roundtrip(self):
        thesis = InvestmentThesis(
            thesis_id="th_1", direction="bullish",
            institutional_support=0.7,
        )
        tc = ThesisConstruction(
            construction_id="tc_rt",
            reasoning_id="er_rt",
            assessment_id="cea_rt",
            timestamp="2026-07-30T18:00:00",
            regime="NORMAL_GROWTH",
            theses=(thesis,),
            ranked_thesis_ids=("th_1",),
            total_theses=1,
            primary_thesis_id="th_1",
        )
        d = tc.to_dict()
        restored = ThesisConstruction.from_dict(d)
        assert restored.construction_id == tc.construction_id
        assert restored.total_theses == 1
        assert restored.primary_thesis_id == "th_1"
        assert restored.primary_thesis is not None
        assert restored.primary_thesis.direction == "bullish"

    def test_primary_thesis_returns_none_when_missing(self):
        thesis = InvestmentThesis(
            thesis_id="th_1", direction="bullish",
        )
        tc = ThesisConstruction(
            construction_id="tc_miss",
            reasoning_id="er_miss",
            assessment_id="cea_miss",
            timestamp="2026-07-30T18:00:00",
            regime="NORMAL_GROWTH",
            theses=(thesis,),
            total_theses=1,
            primary_thesis_id="th_nonexistent",
        )
        assert tc.primary_thesis is None


# =========================================================================
# ThesisBuilder tests
# =========================================================================


class TestThesisBuilder:
    def test_build_bullish_thesis(self):
        reasoning = _make_reasoning(
            (_make_evidence_set("es_reallyield", bias="bullish"),)
        )
        assessment = _make_assessment()
        builder = ThesisBuilder()
        thesis = builder.build_thesis(
            direction="bullish",
            reasoning=reasoning,
            assessment=assessment,
            supporting_set_ids=["es_reallyield"],
            counter_set_ids=[],
        )
        assert isinstance(thesis, InvestmentThesis)
        assert thesis.direction == "bullish"
        assert thesis.regime == "NORMAL_GROWTH"
        assert "es_reallyield" in thesis.supporting_set_ids
        assert thesis.institutional_support > 0.0
        assert thesis.economic_mechanism != ""

    def test_build_with_counter_evidence(self):
        reasoning = _make_reasoning(
            (_make_evidence_set("es_reallyield", bias="bullish"),)
        )
        assessment = _make_assessment(contradicting_set_ids=("es_usd_fx",))
        builder = ThesisBuilder()
        thesis = builder.build_thesis(
            direction="bullish",
            reasoning=reasoning,
            assessment=assessment,
            supporting_set_ids=["es_reallyield"],
            counter_set_ids=["es_usd_fx"],
        )
        assert "es_usd_fx" in thesis.counter_evidence_ids
        assert any("Counter-evidence" in c for c in thesis.invalidating_conditions)

    def test_build_includes_missing_evidence(self):
        reasoning = _make_reasoning(
            (_make_evidence_set("es_reallyield", bias="bullish"),)
        )
        assessment = _make_assessment(
            missing_evidence=("INFLATION", "USD_FX"),
            bias_flags=("missing_evidence",),
        )
        builder = ThesisBuilder()
        thesis = builder.build_thesis(
            direction="bullish",
            reasoning=reasoning,
            assessment=assessment,
            supporting_set_ids=["es_reallyield"],
            counter_set_ids=[],
        )
        assert "INFLATION" in thesis.remaining_unknowns
        assert any("INFLATION" in c for c in thesis.invalidating_conditions)

    def test_build_support_penalized_by_confidence_penalty(self):
        reasoning = _make_reasoning(
            (_make_evidence_set("es_reallyield", bias="bullish", net_weight=0.8, consensus_score=1.0),)
        )
        assessment = _make_assessment(confidence_penalty=0.5)
        builder = ThesisBuilder()
        thesis = builder.build_thesis(
            direction="bullish",
            reasoning=reasoning,
            assessment=assessment,
            supporting_set_ids=["es_reallyield"],
            counter_set_ids=[],
        )
        assert 0.0 < thesis.institutional_support <= 1.0
        assert thesis.confidence_inputs["confidence_penalty"] == 0.5

    def test_build_regime_conflict_in_invalidating_conditions(self):
        reasoning = _make_reasoning(
            (_make_evidence_set("es_reallyield", bias="bearish"),)
        )
        assessment = _make_assessment(
            regime_conflict=True,
            bias_flags=("regime_conflict",),
        )
        builder = ThesisBuilder()
        thesis = builder.build_thesis(
            direction="bearish",
            reasoning=reasoning,
            assessment=assessment,
            supporting_set_ids=["es_reallyield"],
            counter_set_ids=[],
        )
        assert any("regime" in c.lower() for c in thesis.invalidating_conditions)

    def test_build_no_supporting_sets(self):
        reasoning = _make_reasoning()
        assessment = _make_assessment()
        builder = ThesisBuilder()
        thesis = builder.build_thesis(
            direction="neutral",
            reasoning=reasoning,
            assessment=assessment,
            supporting_set_ids=[],
            counter_set_ids=[],
        )
        assert thesis.institutional_support == 0.0
        assert thesis.economic_mechanism == "No active evidence channels identified"

    def test_build_provenance_chain(self):
        reasoning = _make_reasoning(
            (_make_evidence_set("es_reallyield", bias="bullish"),)
        )
        assessment = _make_assessment()
        builder = ThesisBuilder()
        thesis = builder.build_thesis(
            direction="bullish",
            reasoning=reasoning,
            assessment=assessment,
            supporting_set_ids=["es_reallyield"],
            counter_set_ids=[],
        )
        assert len(thesis.provenance_chain) >= 1
        assert thesis.provenance_chain[-1].created_by == "W8 ThesisBuilder"

    def test_derive_mechanism_multiple_channels(self):
        reasoning = _make_reasoning(
            (
                _make_evidence_set("es_reallyield", event_type="REAL_YIELD", bias="bullish"),
                _make_evidence_set("es_usd", event_type="USD_FX", bias="bullish"),
            )
        )
        assessment = _make_assessment()
        builder = ThesisBuilder()
        thesis = builder.build_thesis(
            direction="bullish",
            reasoning=reasoning,
            assessment=assessment,
            supporting_set_ids=["es_reallyield", "es_usd"],
            counter_set_ids=[],
        )
        assert "Real yield" in thesis.economic_mechanism
        assert "dollar" in thesis.economic_mechanism.lower()


# =========================================================================
# ThesisRanker tests
# =========================================================================


class TestThesisRanker:
    def test_rank_sorts_descending(self):
        t1 = InvestmentThesis("th_1", "bullish", institutional_support=0.7)
        t2 = InvestmentThesis("th_2", "bearish", institutional_support=0.4)
        t3 = InvestmentThesis("th_3", "neutral", institutional_support=0.6)
        sorted_theses, ranked_ids = ThesisRanker.rank([t1, t2, t3])
        assert ranked_ids == ["th_1", "th_3", "th_2"]
        assert sorted_theses[0].institutional_support == 0.7

    def test_rank_empty(self):
        sorted_theses, ranked_ids = ThesisRanker.rank([])
        assert sorted_theses == []
        assert ranked_ids == []

    def test_rank_ties_preserved(self):
        t1 = InvestmentThesis("th_1", "bullish", institutional_support=0.5)
        t2 = InvestmentThesis("th_2", "bearish", institutional_support=0.5)
        sorted_theses, ranked_ids = ThesisRanker.rank([t1, t2])
        assert set(ranked_ids) == {"th_1", "th_2"}


# =========================================================================
# ThesisConstructor integration tests
# =========================================================================


class TestThesisConstructor:
    def test_construct_single_direction(self):
        reasoning = _make_reasoning(
            (_make_evidence_set("es_reallyield", bias="bullish"),)
        )
        assessment = _make_assessment()
        constructor = ThesisConstructor()
        result = constructor.construct(reasoning, assessment)
        assert isinstance(result, ThesisConstruction)
        assert result.reasoning_id == reasoning.reasoning_id
        assert result.assessment_id == assessment.assessment_id
        assert result.total_theses > 0
        assert result.primary_thesis_id != ""

    def test_construct_competing_theses(self):
        reasoning = _make_reasoning(
            (
                _make_evidence_set("es_reallyield", bias="bullish"),
                _make_evidence_set(set_id="es_usd", bias="bearish"),
            )
        )
        assessment = _make_assessment(contradicting_set_ids=("es_usd",))
        constructor = ThesisConstructor()
        result = constructor.construct(reasoning, assessment)
        directions = {t.direction for t in result.theses}
        assert "bullish" in directions
        assert "bearish" in directions
        assert "neutral" in directions

    def test_construct_bullish_with_neutral(self):
        reasoning = _make_reasoning(
            (_make_evidence_set("es_reallyield", bias="bullish"),)
        )
        assessment = _make_assessment()
        constructor = ThesisConstructor()
        result = constructor.construct(reasoning, assessment)
        directions = {t.direction for t in result.theses}
        assert "bullish" in directions
        assert "neutral" in directions

    def test_construct_bearish_with_neutral(self):
        reasoning = _make_reasoning(
            (_make_evidence_set("es_reallyield", bias="bearish"),)
        )
        assessment = _make_assessment()
        constructor = ThesisConstructor()
        result = constructor.construct(reasoning, assessment)
        directions = {t.direction for t in result.theses}
        assert "bearish" in directions
        assert "neutral" in directions

    def test_construct_empty_reasoning(self):
        reasoning = _make_reasoning(())
        assessment = _make_assessment()
        constructor = ThesisConstructor()
        result = constructor.construct(reasoning, assessment)
        assert result.total_theses == 1
        assert result.theses[0].direction == "neutral"

    def test_ranked_order_matches_support(self):
        reasoning = _make_reasoning(
            (
                _make_evidence_set(
                    "es_bull", bias="bullish", net_weight=0.9, consensus_score=0.95,
                ),
                _make_evidence_set(
                    "es_bear", bias="bearish", net_weight=0.4, consensus_score=0.5,
                ),
            )
        )
        assessment = _make_assessment(contradicting_set_ids=("es_bear",))
        constructor = ThesisConstructor()
        result = constructor.construct(reasoning, assessment)
        supports = [t.institutional_support for t in result.theses]
        assert supports == sorted(supports, reverse=True)
        assert result.ranked_thesis_ids[0] == result.primary_thesis_id

    def test_json_roundtrip(self):
        reasoning = _make_reasoning(
            (
                _make_evidence_set("es_reallyield", bias="bullish"),
                _make_evidence_set("es_usd", bias="bearish"),
            )
        )
        assessment = _make_assessment(contradicting_set_ids=("es_usd",))
        constructor = ThesisConstructor()
        result = constructor.construct(reasoning, assessment)
        serialized = json.dumps(result.to_dict())
        restored = ThesisConstruction.from_dict(json.loads(serialized))
        assert restored.construction_id == result.construction_id
        assert restored.total_theses == result.total_theses
        assert restored.primary_thesis_id == result.primary_thesis_id

    def test_theses_validate(self):
        reasoning = _make_reasoning(
            (
                _make_evidence_set("es_reallyield", bias="bullish"),
                _make_evidence_set("es_usd", bias="bearish"),
            )
        )
        assessment = _make_assessment(contradicting_set_ids=("es_usd",))
        constructor = ThesisConstructor()
        result = constructor.construct(reasoning, assessment)
        for thesis in result.theses:
            errors = thesis.validate()
            assert not errors, f"Thesis {thesis.thesis_id} validation failed: {errors}"


# =========================================================================
# W7 -> W8 integration test
# =========================================================================


def test_w7_to_w8_integration():
    from evidence_collection.contracts import Evidence, EvidenceCollection
    from evidence_reasoning.reasoner import EvidenceReasoner
    from counter_evidence.assessor import CounterEvidenceAssessor

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
        collection_id="ec_w7_w8", assessment_id="sa_w7_w8",
        timestamp="2026-07-30T18:00:00", regime="NORMAL_GROWTH",
        items=(ev1, ev2), total_classified=2, signals_count=2,
    )

    reasoner = EvidenceReasoner()
    reasoning = reasoner.reason(collection)

    assessor = CounterEvidenceAssessor()
    assessment = assessor.assess(reasoning)

    constructor = ThesisConstructor()
    construction = constructor.construct(reasoning, assessment)

    assert construction.reasoning_id == reasoning.reasoning_id
    assert construction.assessment_id == assessment.assessment_id
    assert construction.regime == "NORMAL_GROWTH"
    assert construction.total_theses >= 1
    assert construction.primary_thesis is not None

    for thesis in construction.theses:
        errors = thesis.validate()
        assert not errors, f"Thesis validation failed: {errors}"
        assert thesis.direction in VALID_DIRECTIONS
        assert 0.0 <= thesis.institutional_support <= 1.0
        assert thesis.time_horizon_days > 0
        assert len(thesis.provenance_chain) >= 1


# =========================================================================
# W8 orchestration stage test
# =========================================================================


def test_w8_orchestration_stage():
    from orchestration.stages import _thesis_construction

    reasoning = _make_reasoning(
        (
            _make_evidence_set("es_reallyield", bias="bullish"),
            _make_evidence_set("es_usd", bias="bearish"),
        )
    )
    assessment = _make_assessment(contradicting_set_ids=("es_usd",))

    result = _thesis_construction(
        {},
        {
            "evidence_reasoning": reasoning.to_dict(),
            "counter_evidence": assessment.to_dict(),
        },
    )
    assert isinstance(result, ThesisConstruction)
    assert result.reasoning_id == reasoning.reasoning_id
    assert result.assessment_id == assessment.assessment_id
    assert result.total_theses >= 2


def test_w8_orchestration_stage_missing_data():
    from orchestration.stages import _thesis_construction

    result = _thesis_construction({}, {})
    assert isinstance(result, dict)
    assert "error" in result
