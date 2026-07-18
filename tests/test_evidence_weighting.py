from __future__ import annotations

from datetime import datetime, timezone

import pytest

from knowledge.evidence.evidence import Evidence
from knowledge.evidence.collection import EvidenceCollection
from knowledge.evidence.weighting import (
    EvidenceWeighter,
    WeightConfig,
    WeightFactors,
    WeightedAggregate,
)
from knowledge.integrity.provenance import Provenance
from knowledge.orchestration.context import OrchestrationContext


def _ev(
    evidence_id: str = "ev_1",
    confidence: float = 0.8,
    sample_count: int = 100,
    average_return_pct: float = 1.0,
    bias: str = "gold_positive_bias",
    event_type: str = "CPI",
    provenance: Provenance | None = None,
) -> Evidence:
    return Evidence(
        evidence_id=evidence_id,
        source_node_id=f"src_{evidence_id}",
        event_type=event_type,
        condition={},
        horizon_days=30,
        sample_count=sample_count,
        average_return_pct=average_return_pct,
        confidence=confidence,
        bias=bias,
        explanation="test",
        provenance=provenance,
    )


class TestWeightConfig:
    def test_defaults(self):
        cfg = WeightConfig()
        assert cfg.confidence_exponent == 2.0
        assert cfg.sample_baseline == 100
        assert cfg.provenance_bonus == 0.3
        assert cfg.consistency_bonus == 0.2
        assert cfg.recency_days == 365
        assert cfg.combine_method == "geometric"

    def test_custom_values(self):
        cfg = WeightConfig(
            confidence_exponent=1.0,
            sample_baseline=200,
            provenance_bonus=0.5,
            consistency_bonus=0.3,
            recency_days=180,
            combine_method="arithmetic",
        )
        assert cfg.confidence_exponent == 1.0
        assert cfg.combine_method == "arithmetic"


class TestWeightFactors:
    def test_dataclass(self):
        f = WeightFactors("ev_1", 0.8, 0.5, 1.0, 0.9, 1.0, 0.82)
        assert f.evidence_id == "ev_1"
        assert f.composite_weight == 0.82

    def test_immutable(self):
        f = WeightFactors("ev_1", 0.8, 0.5, 1.0, 0.9, 1.0, 0.82)
        with pytest.raises(Exception):
            f.composite_weight = 0.0


class TestWeightedAggregate:
    def test_dataclass(self):
        agg = WeightedAggregate(
            weighted_avg_return=0.5,
            weighted_avg_confidence=0.7,
            effective_sample_size=50.0,
            total_raw_weight=10.0,
            item_count=5,
        )
        assert agg.weighted_avg_return == 0.5
        assert agg.effective_sample_size == 50.0

    def test_immutable(self):
        agg = WeightedAggregate(0.5, 0.7, 50.0, 10.0, 5)
        with pytest.raises(Exception):
            agg.total_raw_weight = 0.0

    def test_empty_weight_factors_default(self):
        agg = WeightedAggregate(0.5, 0.7, 50.0, 10.0, 5)
        assert agg.weight_factors == ()


class TestEvidenceWeighterEmpty:
    def test_empty_collection(self):
        weighter = EvidenceWeighter()
        result = weighter.weigh(EvidenceCollection())
        assert result.item_count == 0
        assert result.total_raw_weight == 0.0
        assert result.effective_sample_size == 0.0
        assert result.weighted_avg_return == 0.0
        assert result.weighted_avg_confidence == 0.0
        assert result.weight_factors == ()


class TestEvidenceWeighterConfidenceFactor:
    def test_squared_weight(self):
        weighter = EvidenceWeighter()
        coll = EvidenceCollection([
            _ev("ev_1", confidence=0.5),
            _ev("ev_2", confidence=1.0),
        ])
        result = weighter.weigh(coll)
        factors = list(result.weight_factors)
        f1 = next(f for f in factors if f.evidence_id == "ev_1")
        f2 = next(f for f in factors if f.evidence_id == "ev_2")
        assert f1.confidence_factor == pytest.approx(0.25)
        assert f2.confidence_factor == pytest.approx(1.0)

    def test_exponent_one(self):
        cfg = WeightConfig(confidence_exponent=1.0)
        weighter = EvidenceWeighter(cfg)
        coll = EvidenceCollection([
            _ev("ev_1", confidence=0.5),
            _ev("ev_2", confidence=1.0),
        ])
        result = weighter.weigh(coll)
        factors = list(result.weight_factors)
        f1 = next(f for f in factors if f.evidence_id == "ev_1")
        f2 = next(f for f in factors if f.evidence_id == "ev_2")
        assert f1.confidence_factor == pytest.approx(0.5)
        assert f2.confidence_factor == pytest.approx(1.0)


class TestEvidenceWeighterSampleFactor:
    def test_at_baseline(self):
        weighter = EvidenceWeighter()
        coll = EvidenceCollection([
            _ev("ev_1", sample_count=100),
        ])
        result = weighter.weigh(coll)
        f = result.weight_factors[0]
        assert f.sample_factor == pytest.approx(1.0)

    def test_half_baseline(self):
        weighter = EvidenceWeighter()
        coll = EvidenceCollection([
            _ev("ev_1", sample_count=50),
        ])
        result = weighter.weigh(coll)
        f = result.weight_factors[0]
        assert f.sample_factor == pytest.approx(0.5)

    def test_exceeds_baseline(self):
        weighter = EvidenceWeighter()
        coll = EvidenceCollection([
            _ev("ev_1", sample_count=500),
        ])
        result = weighter.weigh(coll)
        f = result.weight_factors[0]
        assert f.sample_factor == pytest.approx(1.0)

    def test_zero_samples(self):
        weighter = EvidenceWeighter()
        coll = EvidenceCollection([
            _ev("ev_1", sample_count=0),
        ])
        result = weighter.weigh(coll)
        f = result.weight_factors[0]
        assert f.sample_factor == pytest.approx(0.0)
        assert f.composite_weight == pytest.approx(0.0)


class TestEvidenceWeighterProvenanceFactor:
    def test_with_provenance(self):
        weighter = EvidenceWeighter()
        prov = Provenance(created_at="2026-01-01T00:00:00+00:00", created_by="test", entity_version="1.0")
        coll = EvidenceCollection([
            _ev("ev_1", provenance=prov),
        ])
        result = weighter.weigh(coll)
        f = result.weight_factors[0]
        assert f.provenance_factor == pytest.approx(1.0)

    def test_without_provenance(self):
        weighter = EvidenceWeighter()
        coll = EvidenceCollection([
            _ev("ev_1", provenance=None),
        ])
        result = weighter.weigh(coll)
        f = result.weight_factors[0]
        assert f.provenance_factor == pytest.approx(0.3)

    def test_custom_bonus(self):
        cfg = WeightConfig(provenance_bonus=0.0)
        weighter = EvidenceWeighter(cfg)
        coll = EvidenceCollection([
            _ev("ev_1", provenance=None),
        ])
        result = weighter.weigh(coll)
        f = result.weight_factors[0]
        assert f.provenance_factor == pytest.approx(0.0)


class TestEvidenceWeighterConsistencyFactor:
    def test_agrees_with_majority(self):
        weighter = EvidenceWeighter()
        coll = EvidenceCollection([
            _ev("ev_1", bias="gold_positive_bias", event_type="CPI"),
            _ev("ev_2", bias="gold_positive_bias", event_type="CPI"),
            _ev("ev_3", bias="gold_negative_bias", event_type="CPI"),
        ])
        result = weighter.weigh(coll)
        f1 = next(f for f in result.weight_factors if f.evidence_id == "ev_1")
        f2 = next(f for f in result.weight_factors if f.evidence_id == "ev_3")
        assert f1.consistency_factor == pytest.approx(1.0)
        assert f2.consistency_factor == pytest.approx(0.8)

    def test_tie_goes_mixed(self):
        weighter = EvidenceWeighter()
        coll = EvidenceCollection([
            _ev("ev_1", bias="gold_positive_bias", event_type="CPI"),
            _ev("ev_2", bias="gold_negative_bias", event_type="CPI"),
        ])
        result = weighter.weigh(coll)
        for f in result.weight_factors:
            assert f.consistency_factor == pytest.approx(0.5 + 0.2 / 2.0)

    def test_single_item_is_consistent(self):
        weighter = EvidenceWeighter()
        coll = EvidenceCollection([
            _ev("ev_1", bias="gold_positive_bias", event_type="CPI"),
        ])
        result = weighter.weigh(coll)
        f = result.weight_factors[0]
        assert f.consistency_factor == pytest.approx(1.0)

    def test_multiple_event_types_independent(self):
        weighter = EvidenceWeighter()
        coll = EvidenceCollection([
            _ev("ev_1", bias="gold_positive_bias", event_type="CPI"),
            _ev("ev_2", bias="gold_positive_bias", event_type="CPI"),
            _ev("ev_3", bias="gold_negative_bias", event_type="NFP"),
            _ev("ev_4", bias="gold_negative_bias", event_type="NFP"),
        ])
        result = weighter.weigh(coll)
        f1 = next(f for f in result.weight_factors if f.evidence_id == "ev_1")
        f3 = next(f for f in result.weight_factors if f.evidence_id == "ev_3")
        assert f1.consistency_factor == pytest.approx(1.0)
        assert f3.consistency_factor == pytest.approx(1.0)


class TestEvidenceWeighterRecencyFactor:
    def test_recent_evidence(self):
        recent = datetime.now(timezone.utc).isoformat()
        prov = Provenance(created_at=recent, created_by="test", entity_version="1.0")
        weighter = EvidenceWeighter()
        coll = EvidenceCollection([
            _ev("ev_1", provenance=prov),
        ])
        result = weighter.weigh(coll)
        assert result.weight_factors[0].recency_factor == pytest.approx(1.0)

    def test_no_provenance(self):
        weighter = EvidenceWeighter()
        coll = EvidenceCollection([
            _ev("ev_1", provenance=None),
        ])
        result = weighter.weigh(coll)
        assert result.weight_factors[0].recency_factor == pytest.approx(0.5)


class TestEvidenceWeighterComposite:
    def test_geometric_default(self):
        weighter = EvidenceWeighter()
        coll = EvidenceCollection([
            _ev("ev_1", confidence=0.8, sample_count=100, provenance=None),
        ])
        result = weighter.weigh(coll)
        f = result.weight_factors[0]
        expected = (
            f.confidence_factor
            * f.sample_factor
            * f.provenance_factor
            * f.consistency_factor
            * f.recency_factor
        ) ** (1.0 / 5.0)
        assert f.composite_weight == pytest.approx(expected)

    def test_arithmetic(self):
        cfg = WeightConfig(combine_method="arithmetic")
        weighter = EvidenceWeighter(cfg)
        coll = EvidenceCollection([
            _ev("ev_1", confidence=0.8, sample_count=100, provenance=None),
        ])
        result = weighter.weigh(coll)
        f = result.weight_factors[0]
        expected = (
            f.confidence_factor
            + f.sample_factor
            + f.provenance_factor
            + f.consistency_factor
            + f.recency_factor
        ) / 5.0
        assert f.composite_weight == pytest.approx(expected)

    def test_all_identical(self):
        weighter = EvidenceWeighter()
        coll = EvidenceCollection([
            _ev("ev_1", confidence=0.7, sample_count=50, average_return_pct=1.0),
            _ev("ev_2", confidence=0.7, sample_count=50, average_return_pct=1.0),
            _ev("ev_3", confidence=0.7, sample_count=50, average_return_pct=1.0),
        ])
        result = weighter.weigh(coll)
        assert result.weighted_avg_return == pytest.approx(1.0)
        assert result.weighted_avg_confidence == pytest.approx(0.7)
        assert result.item_count == 3
        assert result.total_raw_weight > 0

    def test_single_item(self):
        weighter = EvidenceWeighter()
        coll = EvidenceCollection([
            _ev("ev_1", confidence=0.9, sample_count=200, average_return_pct=2.5),
        ])
        result = weighter.weigh(coll)
        assert result.weighted_avg_return == pytest.approx(2.5)
        assert result.weighted_avg_confidence == pytest.approx(0.9)
        assert result.item_count == 1
        assert result.effective_sample_size == pytest.approx(1.0)

    def test_zero_total_weight(self):
        cfg = WeightConfig(
            confidence_exponent=1.0,
            sample_baseline=100,
            provenance_bonus=0.0,
        )
        weighter = EvidenceWeighter(cfg)
        coll = EvidenceCollection([
            _ev("ev_1", confidence=0.0, sample_count=0, provenance=None),
        ])
        result = weighter.weigh(coll)
        assert result.total_raw_weight == 0.0
        assert result.weighted_avg_return == 0.0


class TestEvidenceWeighterQualityReversal:
    def test_high_quality_reverses_low_quality_majority(self):
        prov_high = Provenance(
            created_at=datetime.now(timezone.utc).isoformat(),
            created_by="test", entity_version="1.0",
        )
        weighter = EvidenceWeighter()
        coll = EvidenceCollection([
            _ev("ev_low_1", confidence=0.30, sample_count=3, average_return_pct=0.5,
                bias="gold_positive_bias", provenance=None),
            _ev("ev_low_2", confidence=0.30, sample_count=3, average_return_pct=0.5,
                bias="gold_positive_bias", provenance=None),
            _ev("ev_low_3", confidence=0.30, sample_count=3, average_return_pct=0.5,
                bias="gold_positive_bias", provenance=None),
            _ev("ev_high", confidence=0.90, sample_count=300, average_return_pct=-2.0,
                bias="gold_negative_bias", provenance=prov_high),
        ])
        result = weighter.weigh(coll)

        raw_avg = sum(ev.average_return_pct for ev in coll) / len(coll)
        raw_conf = sum(ev.confidence for ev in coll) / len(coll)

        assert raw_avg == pytest.approx(-0.125)
        assert raw_conf == pytest.approx(0.45)

        assert result.weighted_avg_return < raw_avg * 2
        assert result.weighted_avg_confidence > raw_conf * 1.3
        assert result.weighted_avg_return < 0

        high_factor = next(f for f in result.weight_factors if f.evidence_id == "ev_high")
        low_factors = [
            f for f in result.weight_factors if f.evidence_id.startswith("ev_low")
        ]
        avg_low_w = sum(f.composite_weight for f in low_factors) / len(low_factors)
        assert high_factor.composite_weight > avg_low_w * 4


class TestEvidenceWeighterSampleSizeDominance:
    def test_large_samples_weigh_more_per_item(self):
        weighter = EvidenceWeighter()
        coll = EvidenceCollection([
            _ev("ev_small_1", sample_count=10, confidence=0.50, average_return_pct=0.2),
            _ev("ev_small_2", sample_count=10, confidence=0.50, average_return_pct=0.2),
            _ev("ev_large_1", sample_count=500, confidence=0.80, average_return_pct=-1.5),
        ])
        result = weighter.weigh(coll)

        raw_avg = sum(ev.average_return_pct for ev in coll) / len(coll)
        raw_conf = sum(ev.confidence for ev in coll) / len(coll)
        assert raw_avg == pytest.approx(-0.366667, rel=1e-5)

        assert result.weighted_avg_return < raw_avg
        assert result.weighted_avg_confidence > raw_conf

        large = next(f for f in result.weight_factors if f.evidence_id == "ev_large_1")
        small = next(f for f in result.weight_factors if f.evidence_id == "ev_small_1")
        assert large.composite_weight > small.composite_weight * 1.5


class TestEvidenceWeighterEffectiveSampleSize:
    def test_equal_weights_gives_n(self):
        weighter = EvidenceWeighter()
        coll = EvidenceCollection([
            _ev(f"ev_{i}", confidence=0.8, sample_count=100) for i in range(10)
        ])
        result = weighter.weigh(coll)
        assert result.effective_sample_size == pytest.approx(10.0, rel=0.01)

    def test_unequal_weights_reduces_ess(self):
        weighter = EvidenceWeighter()
        prov_high = Provenance(
            created_at=datetime.now(timezone.utc).isoformat(),
            created_by="test", entity_version="1.0",
        )
        low = _ev("ev_low", confidence=0.3, sample_count=3, provenance=None)
        high = _ev("ev_high", confidence=0.95, sample_count=500, provenance=prov_high)
        coll = EvidenceCollection([low, high])
        result = weighter.weigh(coll)
        assert result.effective_sample_size < 2.0
        assert result.effective_sample_size > 1.0


class TestEvidenceWeighterOrchestrationIntegration:
    def test_weighter_called_during_merge_pipeline(self):
        from knowledge.orchestration.aggregator import EvidenceAggregator
        from knowledge.orchestration.engine import OrchestrationEngine
        from knowledge.evidence.weighting import EvidenceWeighter

        engine = OrchestrationEngine(aggregator=EvidenceAggregator())
        ctx = OrchestrationContext(
            event_type="CPI",
            event_types=("CPI", "NFP"),
        )
        report = engine.analyze(ctx)
        assert report.weighted_aggregate is not None
        assert report.weighted_aggregate.item_count == 0
        assert report.weighted_aggregate.total_raw_weight == 0.0

    def test_weighted_aggregate_field_exists_in_report(self):
        from knowledge.orchestration.engine import OrchestrationEngine, OrchestrationReport
        report = OrchestrationReport()
        assert report.weighted_aggregate is None

        weighter = EvidenceWeighter()
        coll = EvidenceCollection([_ev("ev_1")])
        report.weighted_aggregate = weighter.weigh(coll)
        assert report.weighted_aggregate is not None
        assert report.weighted_aggregate.item_count == 1

    def test_weight_factors_in_valid_ranges(self):
        weighter = EvidenceWeighter()
        prov = Provenance(created_at=datetime.now(timezone.utc).isoformat(),
                          created_by="t", entity_version="1")
        coll = EvidenceCollection([
            _ev("ev_1", confidence=0.5, sample_count=50, provenance=None),
            _ev("ev_2", confidence=0.9, sample_count=200, provenance=prov),
        ])
        result = weighter.weigh(coll)
        for f in result.weight_factors:
            assert 0.0 <= f.composite_weight <= 1.0 or f.composite_weight == 0.0
            assert 0.0 <= f.confidence_factor <= 1.0
            assert 0.0 <= f.sample_factor <= 1.0
            assert 0.0 <= f.provenance_factor <= 1.0
            assert 0.0 <= f.consistency_factor <= 1.0
            assert 0.0 <= f.recency_factor <= 1.0
