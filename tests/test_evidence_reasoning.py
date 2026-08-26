"""Unit + integration tests for W6 Institutional Evidence Reasoning."""

import json
from datetime import datetime, timezone

import pytest

from evidence_collection.contracts import Evidence, EvidenceCollection
from evidence_reasoning.contracts import EvidenceReasoning, EvidenceSet, OPPOSITE_BIAS, VALID_BIASES
from evidence_reasoning.detector import EvidenceDetector
from evidence_reasoning.grouper import EvidenceGrouper
from evidence_reasoning.reasoner import EvidenceReasoner
from evidence_reasoning.weighter import EvidenceWeighter
from knowledge.integrity.provenance import Provenance


# =========================================================================
# Helpers
# =========================================================================

def _make_evidence(
    evidence_id: str = "ev_001",
    source_kr_id: str = "KR-001",
    event_type: str = "REAL_YIELD",
    bias: str = "bullish",
    composite_weight: float = 0.68,
    regime: str = "NORMAL_GROWTH",
    temporal_recency: float = 0.85,
    instrument: str = "XAU/USD",
    provenance: Provenance | None = None,
) -> Evidence:
    return Evidence(
        evidence_id=evidence_id,
        source_kr_id=source_kr_id,
        source_kr_node_id=source_kr_id,
        event_type=event_type,
        condition={"instrument": instrument},
        bias=bias,
        base_confidence=0.85,
        regime_weight=0.8,
        composite_weight=composite_weight,
        explanation=f"{bias} evidence for {event_type}",
        regime=regime,
        source_label="overnight_price",
        supporting_observation_ids=(),
        contradicting_observation_ids=(),
        mechanism="test mechanism",
        provenance=provenance,
        temporal_recency=temporal_recency,
        metadata={
            "classification": "Signal",
            "instrument": instrument,
            "change_pct": 0.5,
            "change_sigma": 1.2,
        },
    )


def _make_collection(items: list[Evidence] | None = None) -> EvidenceCollection:
    if items is None:
        items = [_make_evidence()]
    return EvidenceCollection(
        collection_id="ec_w6_test",
        assessment_id="sa_w6_test",
        timestamp="2026-07-30T06:00:00",
        regime="NORMAL_GROWTH",
        items=tuple(items),
        total_classified=len(items),
        signals_count=sum(1 for e in items),
    )


# =========================================================================
# Contract tests
# =========================================================================


class TestEvidenceSet:
    def test_minimal_evidence_set(self):
        es = EvidenceSet(
            set_id="es_reallyield",
            event_type="REAL_YIELD",
            bias="bullish",
        )
        assert es.set_id == "es_reallyield"
        assert es.net_institutional_weight == 0.0
        assert es.consensus_score == 0.0
        assert es.conflict_score == 0.0

    def test_to_dict_from_dict_roundtrip(self):
        prov = Provenance(
            created_at="2026-07-30T06:00:00",
            created_by="W6 EvidenceReasoner",
            entity_version="1.0.0",
        )
        es = EvidenceSet(
            set_id="es_roundtrip",
            event_type="USD_FX",
            bias="bearish",
            evidence_ids=("ev_001", "ev_002"),
            supporting_evidence_ids=("ev_001",),
            contradicting_evidence_ids=("ev_002",),
            net_institutional_weight=0.65,
            consensus_score=0.5,
            conflict_score=0.5,
            regime_dependency="NORMAL_GROWTH",
            confidence_contribution=0.325,
            explanation="test roundtrip",
            provenance_chain=(prov,),
            metadata={"instrument_count": 2},
        )
        d = es.to_dict()
        restored = EvidenceSet.from_dict(d)
        assert restored.set_id == es.set_id
        assert restored.net_institutional_weight == 0.65
        assert restored.consensus_score == 0.5
        assert restored.conflict_score == 0.5
        assert len(restored.provenance_chain) == 1
        assert restored.provenance_chain[0].created_by == "W6 EvidenceReasoner"

    def test_validate_passes_for_valid(self):
        es = EvidenceSet(
            set_id="es_valid", event_type="REAL_YIELD", bias="bullish",
            net_institutional_weight=0.5, consensus_score=0.8, conflict_score=0.2,
            confidence_contribution=0.4,
        )
        errors = es.validate()
        assert not errors

    def test_validate_detects_out_of_range_weights(self):
        es = EvidenceSet(
            set_id="es_bad", event_type="REAL_YIELD", bias="bullish",
            net_institutional_weight=1.5, consensus_score=0.8, conflict_score=0.2,
            confidence_contribution=0.4,
        )
        errors = es.validate()
        assert any("net_institutional_weight" in e for e in errors)

    def test_validate_detects_invalid_bias(self):
        es = EvidenceSet(
            set_id="es_bias", event_type="REAL_YIELD", bias="invalid_bias",
            net_institutional_weight=0.5, consensus_score=0.8, conflict_score=0.2,
            confidence_contribution=0.4,
        )
        errors = es.validate()
        assert any("bias" in e for e in errors)

    def test_validate_detects_missing_event_type(self):
        es = EvidenceSet(
            set_id="es_noet", event_type="", bias="bullish",
            net_institutional_weight=0.5, consensus_score=0.8, conflict_score=0.2,
            confidence_contribution=0.4,
        )
        errors = es.validate()
        assert any("event_type" in e for e in errors)

    def test_json_serializable(self):
        es = EvidenceSet(
            set_id="es_json", event_type="INFLATION", bias="bullish",
            evidence_ids=("ev_001",), net_institutional_weight=0.6,
            consensus_score=1.0, conflict_score=0.0, confidence_contribution=0.6,
        )
        serialized = json.dumps(es.to_dict())
        restored = EvidenceSet.from_dict(json.loads(serialized))
        assert restored.set_id == "es_json"


class TestEvidenceReasoning:
    def test_empty_reasoning(self):
        er = EvidenceReasoning(
            reasoning_id="er_empty",
            collection_id="ec_empty",
            timestamp="2026-07-30T06:00:00",
            regime="NORMAL_GROWTH",
        )
        assert er.total_evidence_sets == 0
        assert er.total_evidence_items == 0
        assert er.avg_consensus_score == 0.0
        assert er.avg_conflict_score == 0.0

    def test_to_dict_from_dict_roundtrip(self):
        es = EvidenceSet(
            set_id="es_rt", event_type="REAL_YIELD", bias="bullish",
            evidence_ids=("ev_001",), net_institutional_weight=0.6,
            consensus_score=1.0, conflict_score=0.0, confidence_contribution=0.6,
            regime_dependency="NORMAL_GROWTH",
        )
        er = EvidenceReasoning(
            reasoning_id="er_rt",
            collection_id="ec_rt",
            timestamp="2026-07-30T06:00:00",
            regime="NORMAL_GROWTH",
            evidence_sets=(es,),
            total_evidence_sets=1,
            total_evidence_items=1,
            duplicates_removed=0,
        )
        d = er.to_dict()
        restored = EvidenceReasoning.from_dict(d)
        assert restored.reasoning_id == er.reasoning_id
        assert restored.total_evidence_sets == 1
        assert len(restored.evidence_sets) == 1

    def test_avg_consensus_conflict_scores(self):
        es1 = EvidenceSet("es_1", "REAL_YIELD", "bullish",
                          evidence_ids=("ev_1",), net_institutional_weight=0.6,
                          consensus_score=0.9, conflict_score=0.1, confidence_contribution=0.54)
        es2 = EvidenceSet("es_2", "USD_FX", "bearish",
                          evidence_ids=("ev_2",), net_institutional_weight=0.4,
                          consensus_score=0.7, conflict_score=0.3, confidence_contribution=0.28)
        er = EvidenceReasoning(
            reasoning_id="er_avg", collection_id="ec_avg",
            timestamp="2026-07-30T06:00:00", regime="NORMAL_GROWTH",
            evidence_sets=(es1, es2),
            total_evidence_sets=2, total_evidence_items=2,
        )
        assert er.avg_consensus_score == 0.8
        assert er.avg_conflict_score == 0.2


# =========================================================================
# EvidenceGrouper tests
# =========================================================================


class TestEvidenceGrouper:
    def test_group_by_event_type(self):
        items = [
            _make_evidence("ev_1", event_type="REAL_YIELD"),
            _make_evidence("ev_2", event_type="USD_FX"),
            _make_evidence("ev_3", source_kr_id="KR-003", event_type="REAL_YIELD"),
        ]
        grouper = EvidenceGrouper()
        groups, dups = grouper.group(items)
        assert len(groups) == 2
        real_yield_group = [g for g in groups if g[0].event_type == "REAL_YIELD"]
        usd_fx_group = [g for g in groups if g[0].event_type == "USD_FX"]
        assert len(real_yield_group[0]) == 2
        assert len(usd_fx_group[0]) == 1
        assert len(dups) == 0

    def test_deduplicates_same_source_kr_id(self):
        items = [
            _make_evidence("ev_1", source_kr_id="KR-001", composite_weight=0.68),
            _make_evidence("ev_2", source_kr_id="KR-001", composite_weight=0.72),
        ]
        grouper = EvidenceGrouper()
        groups, dups = grouper.group(items)
        assert len(dups) == 1
        assert dups[0] == "ev_1"

    def test_deduplicates_keeps_highest_weight(self):
        items = [
            _make_evidence("ev_low", source_kr_id="KR-001", composite_weight=0.4),
            _make_evidence("ev_high", source_kr_id="KR-001", composite_weight=0.9),
        ]
        grouper = EvidenceGrouper()
        groups, dups = grouper.group(items)
        assert "ev_low" in dups
        assert "ev_high" not in dups
        assert len(groups) == 1
        assert groups[0][0].evidence_id == "ev_high"

    def test_assign_set_id(self):
        assert EvidenceGrouper.assign_set_id("REAL_YIELD") == "es_real_yield"
        assert EvidenceGrouper.assign_set_id("USD_FX") == "es_usd_fx"


# =========================================================================
# EvidenceDetector tests
# =========================================================================


class TestEvidenceDetector:
    def test_analyze_group_majority_bias(self):
        items = [
            _make_evidence("ev_1", bias="bullish"),
            _make_evidence("ev_2", bias="bullish"),
            _make_evidence("ev_3", bias="bearish"),
        ]
        result = EvidenceDetector.analyze_group(items, "es_reallyield", "REAL_YIELD", [])
        assert result.bias == "bullish"
        assert len(result.supporting_evidence_ids) == 2
        assert len(result.contradicting_evidence_ids) == 1

    def test_analyze_group_all_supporting(self):
        items = [
            _make_evidence("ev_1", bias="bullish"),
            _make_evidence("ev_2", bias="bullish"),
        ]
        result = EvidenceDetector.analyze_group(items, "es_reallyield", "REAL_YIELD", [])
        assert result.bias == "bullish"
        assert len(result.supporting_evidence_ids) == 2
        assert len(result.contradicting_evidence_ids) == 0

    def test_analyze_group_neutral_vs_directional(self):
        # Correction 060: neutral evidence is uninformative against a
        # directional majority -- it never enters contradicting_evidence_ids.
        items = [
            _make_evidence("ev_1", bias="bullish"),
            _make_evidence("ev_2", bias="neutral"),
        ]
        result = EvidenceDetector.analyze_group(items, "es_reallyield", "REAL_YIELD", [])
        assert result.bias == "bullish"
        assert result.supporting_evidence_ids == ("ev_1",)
        assert result.contradicting_evidence_ids == ()
        assert set(result.evidence_ids) == {"ev_1", "ev_2"}

    def test_analyze_group_duplicate_ids(self):
        items = [
            _make_evidence("ev_1", bias="bullish"),
            _make_evidence("ev_dup", bias="bullish"),
        ]
        result = EvidenceDetector.analyze_group(items, "es_reallyield", "REAL_YIELD", ["ev_dup"])
        assert "ev_dup" in result.duplicate_evidence_ids

    def test_analyze_group_tracks_provenance(self):
        prov = Provenance("2026-07-30T06:00:00", "test", "1.0.0")
        items = [_make_evidence("ev_1", bias="bullish", provenance=prov)]
        result = EvidenceDetector.analyze_group(items, "es_reallyield", "REAL_YIELD", [])
        assert len(result.provenance_chain) == 1

    def test_correlated_event_types(self):
        items = [
            _make_evidence("ev_1", event_type="REAL_YIELD", instrument="XAU/USD"),
            _make_evidence("ev_2", event_type="USD_FX", instrument="XAU/USD"),
            _make_evidence("ev_3", event_type="INFLATION", instrument="EUR/USD"),
        ]
        result = EvidenceDetector.correlated_event_types(items)
        assert "XAU/USD" in result
        assert "EUR/USD" not in result
        assert set(result["XAU/USD"]) == {"REAL_YIELD", "USD_FX"}


# =========================================================================
# EvidenceWeighter tests
# =========================================================================


class TestEvidenceWeighter:
    def test_weight_set_assigns_scores(self):
        ev1 = _make_evidence("ev_1", bias="bullish", composite_weight=0.8, temporal_recency=0.9)
        ev2 = _make_evidence("ev_2", bias="bullish", composite_weight=0.6, temporal_recency=0.7)
        items = [ev1, ev2]
        raw_set = EvidenceDetector.analyze_group(items, "es_reallyield", "REAL_YIELD", [])
        weighter = EvidenceWeighter()
        result = weighter.weight_set(raw_set, items)
        assert 0.0 <= result.net_institutional_weight <= 1.0
        assert result.consensus_score == 1.0
        assert result.conflict_score == 0.0
        assert result.confidence_contribution == result.net_institutional_weight

    def test_weight_set_with_conflict(self):
        ev1 = _make_evidence("ev_1", bias="bullish", composite_weight=0.8)
        ev2 = _make_evidence("ev_2", bias="bearish", composite_weight=0.6)
        items = [ev1, ev2]
        raw_set = EvidenceDetector.analyze_group(items, "es_reallyield", "REAL_YIELD", [])
        weighter = EvidenceWeighter()
        result = weighter.weight_set(raw_set, items)
        assert result.consensus_score == 0.5
        assert result.conflict_score == 0.5

    def test_weight_set_empty_group(self):
        es = EvidenceSet(set_id="es_empty", event_type="REAL_YIELD", bias="neutral")
        weighter = EvidenceWeighter()
        result = weighter.weight_set(es, [])
        assert result.net_institutional_weight == 0.0

    def test_compute_net_weight_provenance_boost(self):
        prov = Provenance("2026-07-30T06:00:00", "test", "1.0.0")
        items = [
            _make_evidence("ev_1", composite_weight=0.5, temporal_recency=0.5, provenance=prov),
        ]
        raw_set = EvidenceDetector.analyze_group(items, "es_test", "REAL_YIELD", [])
        weighter = EvidenceWeighter()
        result = weighter.weight_set(raw_set, items)
        assert result.net_institutional_weight > 0.25
        assert result.net_institutional_weight < 1.0

    def test_explanation_format(self):
        items = [_make_evidence("ev_1", bias="bullish")]
        raw_set = EvidenceDetector.analyze_group(items, "es_test", "REAL_YIELD", [])
        weighter = EvidenceWeighter()
        result = weighter.weight_set(raw_set, items)
        assert "EvidenceSet es_test" in result.explanation
        assert "event_type=REAL_YIELD" in result.explanation


# =========================================================================
# EvidenceReasoner integration tests
# =========================================================================


class TestEvidenceReasoner:
    def test_reason_produces_reasoning(self):
        items = [
            _make_evidence("ev_1", event_type="REAL_YIELD", bias="bullish"),
            _make_evidence("ev_2", event_type="USD_FX", bias="bearish"),
        ]
        collection = _make_collection(items)
        reasoner = EvidenceReasoner()
        result = reasoner.reason(collection)
        assert isinstance(result, EvidenceReasoning)
        assert result.collection_id == "ec_w6_test"
        assert result.total_evidence_sets == 2
        assert result.total_evidence_items == 2

    def test_reason_deduplicates(self):
        items = [
            _make_evidence("ev_1", source_kr_id="KR-001", event_type="REAL_YIELD"),
            _make_evidence("ev_2", source_kr_id="KR-001", event_type="REAL_YIELD", composite_weight=0.9),
        ]
        collection = _make_collection(items)
        reasoner = EvidenceReasoner()
        result = reasoner.reason(collection)
        assert result.duplicates_removed == 1
        assert result.total_evidence_items == 1

    def test_reason_all_same_event_type(self):
        items = [
            _make_evidence("ev_1", event_type="REAL_YIELD", bias="bullish"),
            _make_evidence("ev_2", event_type="REAL_YIELD", bias="bullish"),
        ]
        collection = _make_collection(items)
        reasoner = EvidenceReasoner()
        result = reasoner.reason(collection)
        assert result.total_evidence_sets == 1
        es = result.evidence_sets[0]
        assert es.consensus_score == 1.0
        assert es.conflict_score == 0.0

    def test_reason_mixed_bias(self):
        items = [
            _make_evidence("ev_1", event_type="REAL_YIELD", bias="bullish"),
            _make_evidence("ev_2", source_kr_id="KR-002", event_type="REAL_YIELD", bias="bearish"),
        ]
        collection = _make_collection(items)
        reasoner = EvidenceReasoner()
        result = reasoner.reason(collection)
        assert result.total_evidence_sets == 1
        es = result.evidence_sets[0]
        assert es.consensus_score == 0.5
        assert es.conflict_score == 0.5

    def test_reason_multiple_event_types(self):
        items = [
            _make_evidence("ev_1", event_type="REAL_YIELD"),
            _make_evidence("ev_2", event_type="USD_FX"),
            _make_evidence("ev_3", event_type="INFLATION"),
            _make_evidence("ev_4", event_type="ETF_FLOW"),
        ]
        collection = _make_collection(items)
        reasoner = EvidenceReasoner()
        result = reasoner.reason(collection)
        assert result.total_evidence_sets == 4

    def test_reason_regime_override(self):
        items = [_make_evidence("ev_1", event_type="REAL_YIELD")]
        collection = _make_collection(items)
        reasoner = EvidenceReasoner()
        result = reasoner.reason(collection, regime="INFLATIONARY")
        assert result.regime == "INFLATIONARY"

    def test_reason_empty_collection(self):
        collection = _make_collection([])
        reasoner = EvidenceReasoner()
        result = reasoner.reason(collection)
        assert result.total_evidence_sets == 0
        assert result.total_evidence_items == 0
        assert result.duplicates_removed == 0

    def test_json_roundtrip(self):
        items = [
            _make_evidence("ev_1", event_type="REAL_YIELD", bias="bullish"),
            _make_evidence("ev_2", event_type="USD_FX", bias="bearish"),
        ]
        collection = _make_collection(items)
        reasoner = EvidenceReasoner()
        result = reasoner.reason(collection)
        serialized = json.dumps(result.to_dict())
        restored = EvidenceReasoning.from_dict(json.loads(serialized))
        assert restored.reasoning_id == result.reasoning_id
        assert restored.total_evidence_sets == result.total_evidence_sets

    def test_each_set_has_correct_counts(self):
        items = [
            _make_evidence("ev_1", event_type="REAL_YIELD", bias="bullish"),
            _make_evidence("ev_2", source_kr_id="KR-002", event_type="REAL_YIELD", bias="neutral"),
        ]
        collection = _make_collection(items)
        reasoner = EvidenceReasoner()
        result = reasoner.reason(collection)
        es = result.evidence_sets[0]
        assert len(es.supporting_evidence_ids) >= 1
        assert len(es.contradicting_evidence_ids) >= 0
        assert len(es.evidence_ids) == 2

    def test_provenance_chain_preserved(self):
        prov = Provenance("2026-07-30T06:00:00", "W6 EvidenceCollector", "1.0.0")
        items = [_make_evidence("ev_1", event_type="REAL_YIELD", provenance=prov)]
        collection = _make_collection(items)
        reasoner = EvidenceReasoner()
        result = reasoner.reason(collection)
        es = result.evidence_sets[0]
        assert len(es.provenance_chain) == 1
        assert es.provenance_chain[0].created_by == "W6 EvidenceCollector"


# =========================================================================
# W6 evidence collection -> W6 evidence reasoning integration test
# =========================================================================


def test_w5_to_w6_integration():
    from signal_assessment.assembler import SignalAssessmentAssembler
    from evidence_collection.collector import EvidenceCollector
    from pre_market.contracts import OvernightPriceChange, NewsItem, PreMarketBriefing

    briefing = PreMarketBriefing(
        briefing_id="w5_w6_integ",
        timestamp="2026-07-30T06:00:00",
        regime="NORMAL_GROWTH",
        regime_confidence=0.85,
        overnight_changes=(
            OvernightPriceChange("XAU/USD", 1900.0, 1950.0, 2.63, 3.0, "APAC"),
            OvernightPriceChange("DXY", 100.0, 98.0, -2.0, 1.5, "APAC"),
            OvernightPriceChange("US10Y Real Yield", 2.0, 1.8, -10.0, 2.0, "APAC"),
        ),
        news_items=(
            NewsItem("Gold surges on dollar weakness", "Reuters", "2026-07-30",
                     "positive", 0.9, 0.95),
        ),
    )

    assembler = SignalAssessmentAssembler(regime="NORMAL_GROWTH")
    assessment = assembler.assemble(briefing)

    collector = EvidenceCollector()
    collection = collector.collect(assessment)

    reasoner = EvidenceReasoner()
    reasoning = reasoner.reason(collection)

    assert isinstance(reasoning, EvidenceReasoning)
    assert reasoning.collection_id == collection.collection_id
    assert reasoning.total_evidence_sets > 0
    assert reasoning.total_evidence_items > 0

    for es in reasoning.evidence_sets:
        errors = es.validate()
        assert not errors, f"EvidenceSet {es.set_id} validation failed: {errors}"
        assert 0.0 <= es.net_institutional_weight <= 1.0
        assert 0.0 <= es.consensus_score <= 1.0
        assert 0.0 <= es.conflict_score <= 1.0
        assert 0.0 <= es.confidence_contribution <= 1.0
        assert es.event_type
        assert len(es.explanation) > 0


# =========================================================================
# W6 orchestration stage integration test
# =========================================================================


def test_w6_orchestration_stage():
    from orchestration.stages import _evidence_reasoning
    from evidence_collection.contracts import EvidenceCollection

    items = [
        _make_evidence("ev_1", event_type="REAL_YIELD", bias="bullish"),
        _make_evidence("ev_2", event_type="USD_FX", bias="bearish"),
    ]
    collection = _make_collection(items)

    result = _evidence_reasoning({}, {"evidence_collection": collection.to_dict()})
    assert isinstance(result, EvidenceReasoning)
    assert result.total_evidence_sets == 2
    assert result.collection_id == collection.collection_id


def test_w6_orchestration_stage_missing_data():
    from orchestration.stages import _evidence_reasoning

    result = _evidence_reasoning({}, {})
    assert isinstance(result, dict)
    assert "error" in result
