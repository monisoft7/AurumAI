"""Unit + integration tests for W5 Institutional Evidence Collection."""

import json
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from evidence_collection.collector import EvidenceCollector
from evidence_collection.contracts import Evidence, EvidenceCollection
from evidence_collection.strength import EvidenceStrengthComputer
from knowledge.graph.graph import KnowledgeGraph
from knowledge.graph.node import GraphNode
from knowledge.integrity.provenance import Provenance
from signal_assessment.contracts import (
    ClassificationLabel,
    ClassifiedObservation,
    CriterionScore,
    SignalAssessment,
)


# =========================================================================
# Contract tests
# =========================================================================


class TestEvidence:
    def test_minimal_evidence(self):
        ev = Evidence(
            evidence_id="ev_test_001",
            source_kr_id="KR-001",
            source_kr_node_id="KR-001",
            event_type="REAL_YIELD",
            condition={"instrument": "XAU/USD"},
            bias="bullish",
            base_confidence=0.85,
            regime_weight=0.8,
            composite_weight=0.68,
            explanation="test evidence",
            regime="NORMAL_GROWTH",
            source_label="overnight_price",
        )
        assert ev.evidence_id == "ev_test_001"
        assert ev.composite_weight == 0.68

    def test_to_dict_from_dict_roundtrip(self):
        ev = Evidence(
            evidence_id="ev_rt_001",
            source_kr_id="KR-001",
            source_kr_node_id="KR-001",
            event_type="REAL_YIELD",
            condition={"instrument": "XAU/USD"},
            bias="bullish",
            base_confidence=0.85,
            regime_weight=0.8,
            composite_weight=0.68,
            explanation="roundtrip test",
            regime="NORMAL_GROWTH",
            source_label="overnight_price",
            supporting_observation_ids=("persistence", "breadth"),
            contradicting_observation_ids=("narrative_fit",),
            mechanism="Real yield opportunity cost channel",
            provenance=Provenance(
                created_at="2026-07-29T06:00:00",
                created_by="W5 EvidenceCollector",
                entity_version="1.0.0",
            ),
            temporal_recency=0.85,
        )
        d = ev.to_dict()
        restored = Evidence.from_dict(d)
        assert restored.evidence_id == ev.evidence_id
        assert restored.bias == ev.bias
        assert restored.composite_weight == ev.composite_weight
        assert restored.provenance is not None
        assert restored.provenance.created_by == "W5 EvidenceCollector"

    def test_validate_passes_for_valid(self):
        ev = Evidence(
            evidence_id="ev_val_001",
            source_kr_id="KR-001",
            source_kr_node_id="KR-001",
            event_type="REAL_YIELD",
            condition={"instrument": "XAU/USD"},
            bias="bullish",
            base_confidence=0.85,
            regime_weight=0.8,
            composite_weight=0.68,
            explanation="valid test",
            regime="NORMAL_GROWTH",
            source_label="overnight_price",
        )
        errors = ev.validate()
        assert not errors

    def test_validate_detects_bad_composite(self):
        ev = Evidence(
            evidence_id="ev_bad_001",
            source_kr_id="KR-001",
            source_kr_node_id="KR-001",
            event_type="REAL_YIELD",
            condition={},
            bias="bullish",
            base_confidence=0.85,
            regime_weight=0.8,
            composite_weight=0.99,
            explanation="bad composite",
            regime="NORMAL_GROWTH",
            source_label="overnight_price",
        )
        errors = ev.validate()
        assert any("composite_weight" in e for e in errors)

    def test_validate_detects_invalid_bias(self):
        ev = Evidence(
            evidence_id="ev_bias_001",
            source_kr_id="KR-001",
            source_kr_node_id="KR-001",
            event_type="REAL_YIELD",
            condition={},
            bias="invalid_bias",
            base_confidence=0.85,
            regime_weight=0.8,
            composite_weight=0.68,
            explanation="bad bias",
            regime="NORMAL_GROWTH",
            source_label="overnight_price",
        )
        errors = ev.validate()
        assert any("bias" in e for e in errors)

    def test_json_serializable(self):
        ev = Evidence(
            evidence_id="ev_json_001",
            source_kr_id="KR-001",
            source_kr_node_id="KR-001",
            event_type="REAL_YIELD",
            condition={"instrument": "XAU/USD"},
            bias="neutral",
            base_confidence=0.5,
            regime_weight=0.8,
            composite_weight=0.4,
            explanation="json test",
            regime="INFLATIONARY",
            source_label="news",
        )
        serialized = json.dumps(ev.to_dict())
        restored = Evidence.from_dict(json.loads(serialized))
        assert restored.evidence_id == "ev_json_001"


class TestEvidenceCollection:
    def test_empty_collection(self):
        ec = EvidenceCollection(
            collection_id="ec_empty",
            assessment_id="sa_empty",
            timestamp="2026-07-29T06:00:00",
            regime="NORMAL_GROWTH",
        )
        assert ec.evidence_count == 0
        assert ec.avg_composite_weight == 0.0

    def test_to_dict_from_dict_roundtrip(self):
        ec = EvidenceCollection(
            collection_id="ec_rt_001",
            assessment_id="sa_rt_001",
            timestamp="2026-07-29T06:00:00",
            regime="NORMAL_GROWTH",
            items=(
                Evidence(
                    evidence_id="ev_001", source_kr_id="KR-001", source_kr_node_id="KR-001",
                    event_type="REAL_YIELD", condition={}, bias="bullish",
                    base_confidence=0.85, regime_weight=0.8, composite_weight=0.68,
                    explanation="test", regime="NORMAL_GROWTH", source_label="overnight_price",
                ),
                Evidence(
                    evidence_id="ev_002", source_kr_id="KR-002", source_kr_node_id="KR-002",
                    event_type="USD_FX", condition={}, bias="bearish",
                    base_confidence=0.72, regime_weight=0.8, composite_weight=0.576,
                    explanation="test2", regime="NORMAL_GROWTH", source_label="news",
                ),
            ),
            total_classified=10,
            signals_count=2,
            weak_signals_count=1,
            watch_count=1,
            filtered_noise_count=4,
            filtered_ignore_count=2,
        )
        d = ec.to_dict()
        restored = EvidenceCollection.from_dict(d)
        assert restored.collection_id == ec.collection_id
        assert restored.evidence_count == 2
        assert restored.signals_count == 2
        assert restored.filtered_noise_count == 4

    def test_avg_composite_weight(self):
        ec = EvidenceCollection(
            collection_id="ec_avg",
            assessment_id="sa_avg",
            timestamp="2026-07-29T06:00:00",
            regime="NORMAL_GROWTH",
            items=(
                Evidence("ev_1", "KR-1", "KR-1", "REAL_YIELD", {}, "bullish",
                         0.8, 0.8, 0.64, "test", "NORMAL_GROWTH", "overnight_price"),
                Evidence("ev_2", "KR-2", "KR-2", "USD_FX", {}, "bearish",
                         0.6, 0.8, 0.48, "test", "NORMAL_GROWTH", "news"),
            ),
        )
        assert ec.avg_composite_weight == 0.56


# =========================================================================
# EvidenceStrengthComputer tests
# =========================================================================


class TestEvidenceStrengthComputer:
    def test_compute_strength_returns_value(self):
        ev = Evidence(
            evidence_id="ev_str_001", source_kr_id="KR-001", source_kr_node_id="KR-001",
            event_type="REAL_YIELD", condition={}, bias="bullish",
            base_confidence=0.85, regime_weight=0.8, composite_weight=0.68,
            explanation="strength test", regime="NORMAL_GROWTH", source_label="overnight_price",
            temporal_recency=0.9,
        )
        strength = EvidenceStrengthComputer.compute_strength(ev)
        assert 0.0 <= strength <= 1.0

    def test_strength_higher_with_supporting(self):
        ev_with = Evidence(
            evidence_id="ev_sup", source_kr_id="KR-001", source_kr_node_id="KR-001",
            event_type="REAL_YIELD", condition={}, bias="bullish",
            base_confidence=0.85, regime_weight=0.8, composite_weight=0.68,
            explanation="with support", regime="NORMAL_GROWTH", source_label="overnight_price",
            temporal_recency=0.9, supporting_observation_ids=("a", "b", "c"),
        )
        ev_without = Evidence(
            evidence_id="ev_nosup", source_kr_id="KR-001", source_kr_node_id="KR-001",
            event_type="REAL_YIELD", condition={}, bias="bullish",
            base_confidence=0.85, regime_weight=0.8, composite_weight=0.68,
            explanation="without support", regime="NORMAL_GROWTH", source_label="overnight_price",
            temporal_recency=0.9,
        )
        assert (
            EvidenceStrengthComputer.compute_strength(ev_with)
            > EvidenceStrengthComputer.compute_strength(ev_without)
        )

    def test_compute_collection_aggregates(self):
        ec = EvidenceCollection(
            collection_id="ec_agg", assessment_id="sa_agg",
            timestamp="2026-07-29T06:00:00", regime="NORMAL_GROWTH",
            items=(
                Evidence("ev_1", "KR-1", "KR-1", "REAL_YIELD", {}, "bullish",
                         0.8, 0.8, 0.64, "t", "NORMAL_GROWTH", "overnight_price",
                         temporal_recency=0.9),
                Evidence("ev_2", "KR-2", "KR-2", "USD_FX", {}, "bearish",
                         0.6, 0.8, 0.48, "t", "NORMAL_GROWTH", "news",
                         temporal_recency=0.7),
            ),
        )
        agg = EvidenceStrengthComputer.compute_collection_aggregates(ec)
        assert agg["evidence_count"] == 2
        assert "avg_strength" in agg
        assert "bias_distribution" in agg
        assert agg["bias_distribution"].get("bullish", 0) == 1
        assert agg["bias_distribution"].get("bearish", 0) == 1


# =========================================================================
# EvidenceCollector tests
# =========================================================================


def _make_observation(
    obs_id: str = "obs_test",
    source: str = "overnight_price",
    classification: str = "Signal",
    confidence: float = 0.85,
    instrument: str = "XAU/USD",
    change_pct: float = 0.5,
    change_sigma: float = 1.2,
    evidence_count: int = 3,
) -> ClassifiedObservation:
    criteria = [
        CriterionScore("persistence", 0.8, 0.5, True, "persistent"),
        CriterionScore("breadth", 0.7, 0.5, True, "broad"),
        CriterionScore("magnitude", 1.0, 2.0, True, "z=3.0"),
        CriterionScore("narrative_fit", 0.4, 0.3, True, "narrative match"),
        CriterionScore("volume_flow", 0.0, 0.5, False, "no volume data"),
    ]
    return ClassifiedObservation(
        observation_id=obs_id,
        source=source,
        classification=classification,
        confidence=confidence,
        regime="NORMAL_GROWTH",
        reason=f"{classification}: criteria met",
        evidence=tuple(criteria[:evidence_count]),
        instrument=instrument,
        value=1910.0,
        change_pct=change_pct,
        change_sigma=change_sigma,
    )


def _make_assessment(observations=None) -> SignalAssessment:
    if observations is None:
        observations = [
            _make_observation(),
            _make_observation("obs_noise", classification="Noise", confidence=0.3),
            _make_observation("obs_ignore", classification="Ignore", confidence=0.9),
        ]
    return SignalAssessment(
        assessment_id="sa_w5_test",
        briefing_id="premarket_w5_test",
        timestamp="2026-07-29T06:00:00",
        regime="NORMAL_GROWTH",
        regime_confidence=0.85,
        observations=tuple(observations),
    )


class TestEvidenceCollector:
    def test_collect_creates_evidence(self):
        assessment = _make_assessment()
        collector = EvidenceCollector()
        collection = collector.collect(assessment)
        assert isinstance(collection, EvidenceCollection)
        assert collection.assessment_id == "sa_w5_test"
        assert collection.evidence_count > 0

    def test_collect_filters_noise(self):
        assessment = _make_assessment()
        collector = EvidenceCollector()
        collection = collector.collect(assessment)
        assert collection.filtered_noise_count == 1
        assert collection.filtered_ignore_count == 1
        assert "Noise" not in {e.bias for e in collection.items}

    def test_collect_signal_always_generates_evidence(self):
        obs = _make_observation(classification="Signal", confidence=0.85)
        assessment = _make_assessment([obs])
        collector = EvidenceCollector()
        collection = collector.collect(assessment)
        assert collection.signals_count == 1
        assert len(collection.items) == 1

    def test_collect_weak_signal_generates_evidence(self):
        obs = _make_observation("obs_weak", classification="Weak Signal", confidence=0.55, evidence_count=2)
        assessment = _make_assessment([obs])
        collector = EvidenceCollector()
        collection = collector.collect(assessment)
        assert collection.weak_signals_count == 1
        assert len(collection.items) == 1

    def test_collect_watch_generates_evidence(self):
        obs = _make_observation("obs_watch", classification="Watch", confidence=0.35, evidence_count=1)
        assessment = _make_assessment([obs])
        collector = EvidenceCollector()
        collection = collector.collect(assessment)
        assert collection.watch_count == 1
        assert len(collection.items) == 1

    def test_evidence_links_to_source_and_regime(self):
        assessment = _make_assessment()
        collector = EvidenceCollector()
        collection = collector.collect(assessment)
        for ev in collection.items:
            assert ev.regime == "NORMAL_GROWTH"
            assert ev.source_label == "overnight_price"
            assert ev.provenance is not None

    def test_evidence_includes_supporting_and_contradicting(self):
        obs = _make_observation()
        assessment = _make_assessment([obs])
        collector = EvidenceCollector()
        collection = collector.collect(assessment)
        ev = collection.items[0]
        assert len(ev.supporting_observation_ids) > 0
        assert len(ev.contradicting_observation_ids) >= 0

    def test_knowledge_graph_integration(self):
        kg = KnowledgeGraph()
        kg.add_node(GraphNode(
            node_id="KR-001", node_type="knowledge_record",
            properties={"event_type": "REAL_YIELD", "title": "Real Yields KR"},
        ))
        obs = _make_observation(instrument="XAU/USD")
        assessment = _make_assessment([obs])
        collector = EvidenceCollector(knowledge_graph=kg)
        collection = collector.collect(assessment)
        assert collection.evidence_count > 0

    def test_json_roundtrip(self):
        assessment = _make_assessment()
        collector = EvidenceCollector()
        collection = collector.collect(assessment)
        serialized = json.dumps(collection.to_dict())
        restored = EvidenceCollection.from_dict(json.loads(serialized))
        assert restored.collection_id == collection.collection_id
        assert restored.evidence_count == collection.evidence_count


# =========================================================================
# Integration tests: W4 -> W5
# =========================================================================


def test_w4_to_w5_integration():
    from signal_assessment.assembler import SignalAssessmentAssembler
    from pre_market.contracts import (
        OvernightPriceChange, NewsItem, PreMarketBriefing,
    )

    briefing = PreMarketBriefing(
        briefing_id="integ_w5",
        timestamp="2026-07-29T06:00:00",
        regime="NORMAL_GROWTH",
        regime_confidence=0.85,
        overnight_changes=(
            OvernightPriceChange("XAU/USD", 1900.0, 1950.0, 2.63, 3.0, "APAC"),
            OvernightPriceChange("DXY", 100.0, 98.0, -2.0, 1.5, "APAC"),
        ),
        news_items=(
            NewsItem("Gold surges on dollar weakness", "Reuters", "2026-07-29",
                     "positive", 0.9, 0.95),
        ),
    )

    assembler = SignalAssessmentAssembler(regime="NORMAL_GROWTH")
    assessment = assembler.assemble(briefing)

    collector = EvidenceCollector()
    collection = collector.collect(assessment)

    assert isinstance(collection, EvidenceCollection)
    assert collection.assessment_id == assessment.assessment_id
    assert collection.regime == "NORMAL_GROWTH"
    assert collection.evidence_count > 0
    assert collection.signals_count + collection.weak_signals_count > 0

    for ev in collection.items:
        assert ev.regime == "NORMAL_GROWTH"
        assert ev.provenance is not None
        assert 0.0 <= ev.composite_weight <= 1.0
        assert ev.base_confidence > 0.0
        errors = ev.validate()
        assert not errors, f"Evidence {ev.evidence_id} validation failed: {errors}"


def test_w5_orchestration_stage():
    from orchestration.stages import _evidence_collection
    from signal_assessment.contracts import SignalAssessment

    assessment = _make_assessment()
    params: dict = {}

    result = _evidence_collection(params, {"signal_assessment": assessment.to_dict()})
    assert isinstance(result, EvidenceCollection)
    assert result.evidence_count > 0
    assert result.regime == "NORMAL_GROWTH"


def test_w5_no_noise_in_evidence():
    from orchestration.stages import _evidence_collection

    all_sources = [
        _make_observation(obs_id=f"obs_{i}", classification=cls, confidence=conf)
        for i, (cls, conf) in enumerate([
            ("Signal", 0.9), ("Weak Signal", 0.55), ("Watch", 0.35),
            ("Noise", 0.2), ("Ignore", 0.9),
        ])
    ]
    assessment = _make_assessment(all_sources)
    result = _evidence_collection({}, {"signal_assessment": assessment.to_dict()})
    assert result.signals_count == 1
    assert result.weak_signals_count == 1
    assert result.watch_count == 1
    assert result.filtered_noise_count == 1
    assert result.filtered_ignore_count == 1
    assert result.evidence_count == 3
