import json
from pathlib import Path

import pytest

from knowledge.cai.contracts import (
    CrossAssetCorrelation,
    CaiBaseContract,
    EQUITIES,
    FIXED_INCOME,
    FX,
    COMMODITIES,
    CREDIT,
    RATES,
    VOLATILITY,
    REAL_ESTATE,
    CRYPTO,
    EM,
    VALID_ASSET_CLASSES,
    CORRELATION_POSITIVE,
    CORRELATION_NEGATIVE,
    CORRELATION_DIVERGING,
    CORRELATION_CONVERGING,
    CORRELATION_DECOUPLING,
    VALID_CORRELATION_DIRECTIONS,
    WINDOW_SHORT,
    WINDOW_MEDIUM,
    WINDOW_LONG,
    VALID_TIME_WINDOWS,
)
from knowledge.cai.repository import CaiRepository
from knowledge.cai.adapter import CaiEvidenceAdapter
from knowledge.evidence.evidence import Evidence
from knowledge.evidence.collection import EvidenceCollection
from knowledge.orchestration.aggregator import EvidenceAggregator
from knowledge.integrity.provenance import Provenance
from knowledge._compat import FrozenDict


# ── Creation ─────────────────────────────────────────────────────────────────


def test_correlation_creation() -> None:
    corr = CrossAssetCorrelation(
        asset_class_a=EQUITIES,
        asset_class_b=FIXED_INCOME,
        correlation_coefficient=-0.45,
        lookback_periods=60,
        trend_direction=CORRELATION_NEGATIVE,
        rolling_window=WINDOW_MEDIUM,
        regime_stability=0.85,
        confidence=0.80,
        valid_from="2026-07-26T12:00:00Z",
        valid_until="2026-09-17T00:00:00Z",
    )
    assert corr.asset_class_a == EQUITIES
    assert corr.asset_class_b == FIXED_INCOME
    assert corr.correlation_coefficient == -0.45
    assert corr.lookback_periods == 60
    assert corr.trend_direction == CORRELATION_NEGATIVE
    assert corr.rolling_window == WINDOW_MEDIUM
    assert corr.regime_stability == 0.85
    assert corr.confidence == 0.80
    assert corr.valid_from == "2026-07-26T12:00:00Z"
    assert corr.valid_until == "2026-09-17T00:00:00Z"


def test_correlation_defaults() -> None:
    corr = CrossAssetCorrelation(
        asset_class_a=EQUITIES,
        asset_class_b=FIXED_INCOME,
        correlation_coefficient=-0.45,
        lookback_periods=60,
        trend_direction=CORRELATION_NEGATIVE,
        rolling_window=WINDOW_MEDIUM,
        regime_stability=0.85,
        confidence=0.80,
    )
    assert corr.confidence == 0.80
    assert corr.valid_from == ""
    assert corr.valid_until == ""
    assert corr.time_horizon == ""
    assert corr.provenance is None
    assert corr.evidence_references == []
    assert corr.cross_references is None
    assert corr.methodology_version is None
    assert corr.scenario_analysis is None


def test_correlation_all_directions() -> None:
    for direction in (
        CORRELATION_POSITIVE, CORRELATION_NEGATIVE,
        CORRELATION_DIVERGING, CORRELATION_CONVERGING,
        CORRELATION_DECOUPLING,
    ):
        corr = CrossAssetCorrelation(
            asset_class_a=EQUITIES,
            asset_class_b=FIXED_INCOME,
            correlation_coefficient=0.0,
            lookback_periods=30,
            trend_direction=direction,
            rolling_window=WINDOW_MEDIUM,
            regime_stability=0.5,
            confidence=0.7,
            valid_from="2026-07-26T12:00:00Z",
            valid_until="2026-09-17T00:00:00Z",
        )
        assert corr.trend_direction == direction


def test_correlation_all_asset_classes() -> None:
    for ac in (EQUITIES, FIXED_INCOME, FX, COMMODITIES, CREDIT, RATES, VOLATILITY, REAL_ESTATE, CRYPTO, EM):
        corr = CrossAssetCorrelation(
            asset_class_a=ac,
            asset_class_b=EQUITIES,
            correlation_coefficient=0.0,
            lookback_periods=30,
            trend_direction=CORRELATION_POSITIVE,
            rolling_window=WINDOW_MEDIUM,
            regime_stability=0.5,
            confidence=0.7,
            valid_from="2026-07-26T12:00:00Z",
            valid_until="2026-09-17T00:00:00Z",
        )
        assert corr.asset_class_a == ac
    assert VALID_ASSET_CLASSES == {
        EQUITIES, FIXED_INCOME, FX, COMMODITIES, CREDIT,
        RATES, VOLATILITY, REAL_ESTATE, CRYPTO, EM,
    }


def test_correlation_frozen_dataclass() -> None:
    corr = CrossAssetCorrelation(
        asset_class_a=EQUITIES,
        asset_class_b=FIXED_INCOME,
        correlation_coefficient=-0.45,
        lookback_periods=60,
        trend_direction=CORRELATION_NEGATIVE,
        rolling_window=WINDOW_MEDIUM,
        regime_stability=0.85,
        confidence=0.80,
        valid_from="2026-07-26T12:00:00Z",
        valid_until="2026-09-17T00:00:00Z",
    )
    with pytest.raises(AttributeError):
        corr.correlation_coefficient = 0.0
    with pytest.raises(AttributeError):
        corr.trend_direction = CORRELATION_POSITIVE


def test_correlation_all_time_windows() -> None:
    for window in VALID_TIME_WINDOWS:
        corr = CrossAssetCorrelation(
            asset_class_a=EQUITIES,
            asset_class_b=FIXED_INCOME,
            correlation_coefficient=0.0,
            lookback_periods=30,
            trend_direction=CORRELATION_POSITIVE,
            rolling_window=window,
            regime_stability=0.5,
            confidence=0.7,
            valid_from="2026-07-26T12:00:00Z",
            valid_until="2026-09-17T00:00:00Z",
        )
        assert corr.rolling_window == window


def test_correlation_coefficient_range() -> None:
    for coeff in (-1.0, -0.5, 0.0, 0.5, 1.0):
        corr = CrossAssetCorrelation(
            asset_class_a=EQUITIES,
            asset_class_b=FIXED_INCOME,
            correlation_coefficient=coeff,
            lookback_periods=30,
            trend_direction=CORRELATION_POSITIVE,
            rolling_window=WINDOW_MEDIUM,
            regime_stability=0.5,
            confidence=0.7,
            valid_from="2026-07-26T12:00:00Z",
            valid_until="2026-09-17T00:00:00Z",
        )
        assert corr.correlation_coefficient == coeff


def test_correlation_with_full_optional_fields() -> None:
    provenance = Provenance(
        created_at="2026-07-26T12:00:00Z",
        created_by="analyst_01",
        entity_version="1.0.0",
    )
    ev_refs = [
        {
            "source_category": "market_data",
            "source_descriptor": "Bloomberg 60-day rolling correlation",
            "contribution": "primary measurement",
            "confidence_contribution": "high",
        }
    ]
    corr = CrossAssetCorrelation(
        asset_class_a=EQUITIES,
        asset_class_b=FIXED_INCOME,
        correlation_coefficient=-0.45,
        lookback_periods=60,
        trend_direction=CORRELATION_NEGATIVE,
        rolling_window=WINDOW_MEDIUM,
        regime_stability=0.85,
        confidence=0.80,
        valid_from="2026-07-26T12:00:00Z",
        valid_until="2026-09-17T00:00:00Z",
        time_horizon="T3",
        provenance=provenance,
        evidence_references=ev_refs,
        cross_references=["CBI:PolicyBiasScore:FED:2026-07-26"],
        methodology_version="1.0.0",
        scenario_analysis=[
            {"label": "regime_change", "probability": 0.2, "correlation_shift": -0.3}
        ],
    )
    assert corr.provenance is not None
    assert corr.provenance.created_by == "analyst_01"
    assert len(corr.evidence_references) == 1
    assert corr.cross_references == ["CBI:PolicyBiasScore:FED:2026-07-26"]
    assert corr.methodology_version == "1.0.0"
    assert len(corr.scenario_analysis) == 1
    assert corr.time_horizon == "T3"


def test_correlation_inherits_base_contract() -> None:
    corr = CrossAssetCorrelation(
        asset_class_a=EQUITIES,
        asset_class_b=FIXED_INCOME,
        correlation_coefficient=-0.45,
        lookback_periods=60,
        trend_direction=CORRELATION_NEGATIVE,
        rolling_window=WINDOW_MEDIUM,
        regime_stability=0.85,
        confidence=0.80,
        valid_from="2026-07-26T12:00:00Z",
        valid_until="2026-09-17T00:00:00Z",
    )
    assert isinstance(corr, CaiBaseContract)


# ── Repository ───────────────────────────────────────────────────────────────


def test_repository_save_and_load_correlation(tmp_path: Path) -> None:
    repo = CaiRepository()
    corr = CrossAssetCorrelation(
        asset_class_a=EQUITIES,
        asset_class_b=FIXED_INCOME,
        correlation_coefficient=-0.45,
        lookback_periods=60,
        trend_direction=CORRELATION_NEGATIVE,
        rolling_window=WINDOW_MEDIUM,
        regime_stability=0.85,
        confidence=0.80,
        valid_from="2026-07-26T12:00:00Z",
        valid_until="2026-09-17T00:00:00Z",
    )
    p = tmp_path / "correlation.json"
    repo.save_correlation(corr, p)
    loaded = repo.load_correlation(p)
    assert loaded.asset_class_a == EQUITIES
    assert loaded.asset_class_b == FIXED_INCOME
    assert loaded.correlation_coefficient == -0.45
    assert loaded.lookback_periods == 60
    assert loaded.trend_direction == CORRELATION_NEGATIVE
    assert loaded.confidence == 0.80


def test_repository_roundtrip_preserves_all_fields(tmp_path: Path) -> None:
    repo = CaiRepository()
    provenance = Provenance(
        created_at="2026-07-26T12:00:00Z",
        created_by="analyst_01",
        entity_version="1.0.0",
    )
    original = CrossAssetCorrelation(
        asset_class_a=FX,
        asset_class_b=COMMODITIES,
        correlation_coefficient=0.35,
        lookback_periods=90,
        trend_direction=CORRELATION_CONVERGING,
        rolling_window=WINDOW_LONG,
        regime_stability=0.72,
        confidence=0.75,
        valid_from="2026-07-26T12:00:00Z",
        valid_until="2026-09-10T00:00:00Z",
        time_horizon="T3",
        provenance=provenance,
        evidence_references=[
            {"source_category": "market_data", "source_descriptor": "Bloomberg 90d DXY/XAU"}
        ],
        cross_references=["CFI:FlowReport:2026-07-26"],
        methodology_version="1.2.0",
        scenario_analysis=[{"label": "regime_shift", "probability": 0.15}],
    )
    p = tmp_path / "fx_corr.json"
    repo.save_correlation(original, p)
    loaded = repo.load_correlation(p)
    assert loaded.asset_class_a == original.asset_class_a
    assert loaded.asset_class_b == original.asset_class_b
    assert loaded.correlation_coefficient == original.correlation_coefficient
    assert loaded.lookback_periods == original.lookback_periods
    assert loaded.trend_direction == original.trend_direction
    assert loaded.rolling_window == original.rolling_window
    assert loaded.regime_stability == original.regime_stability
    assert loaded.confidence == original.confidence
    assert loaded.valid_from == original.valid_from
    assert loaded.valid_until == original.valid_until
    assert loaded.time_horizon == original.time_horizon
    assert loaded.provenance is not None
    assert loaded.provenance.created_by == "analyst_01"
    assert loaded.provenance.entity_version == "1.0.0"
    assert loaded.evidence_references == original.evidence_references
    assert loaded.cross_references == original.cross_references
    assert loaded.methodology_version == original.methodology_version
    assert loaded.scenario_analysis == original.scenario_analysis


def test_repository_roundtrip_with_none_optionals(tmp_path: Path) -> None:
    repo = CaiRepository()
    original = CrossAssetCorrelation(
        asset_class_a=EQUITIES,
        asset_class_b=CREDIT,
        correlation_coefficient=0.65,
        lookback_periods=30,
        trend_direction=CORRELATION_POSITIVE,
        rolling_window=WINDOW_SHORT,
        regime_stability=0.6,
        confidence=0.6,
        valid_from="2026-07-26T12:00:00Z",
        valid_until="2026-09-20T00:00:00Z",
    )
    p = tmp_path / "eq_credit_corr.json"
    repo.save_correlation(original, p)
    loaded = repo.load_correlation(p)
    assert loaded.provenance is None
    assert loaded.evidence_references == []
    assert loaded.cross_references is None
    assert loaded.methodology_version is None
    assert loaded.scenario_analysis is None


def test_repository_json_structure(tmp_path: Path) -> None:
    repo = CaiRepository()
    corr = CrossAssetCorrelation(
        asset_class_a=EQUITIES,
        asset_class_b=FIXED_INCOME,
        correlation_coefficient=-0.45,
        lookback_periods=60,
        trend_direction=CORRELATION_NEGATIVE,
        rolling_window=WINDOW_MEDIUM,
        regime_stability=0.85,
        confidence=0.80,
        valid_from="2026-07-26T12:00:00Z",
        valid_until="2026-09-17T00:00:00Z",
    )
    p = tmp_path / "correlation.json"
    repo.save_correlation(corr, p)
    raw = json.loads(p.read_text())
    assert raw["asset_class_a"] == "equities"
    assert raw["asset_class_b"] == "fixed_income"
    assert raw["correlation_coefficient"] == -0.45
    assert raw["lookback_periods"] == 60
    assert raw["trend_direction"] == "negative"
    assert raw["rolling_window"] == "medium"
    assert raw["regime_stability"] == 0.85
    assert raw["confidence"] == 0.80
    assert raw["valid_from"] == "2026-07-26T12:00:00Z"
    assert raw["valid_until"] == "2026-09-17T00:00:00Z"
    assert raw["provenance"] is None
    assert raw["evidence_references"] == []
    assert raw["cross_references"] is None


# ── Adapter ──────────────────────────────────────────────────────────────────


def test_adapter_correlation_to_evidence_positive() -> None:
    adapter = CaiEvidenceAdapter()
    corr = CrossAssetCorrelation(
        asset_class_a=EQUITIES,
        asset_class_b=FIXED_INCOME,
        correlation_coefficient=0.65,
        lookback_periods=60,
        trend_direction=CORRELATION_POSITIVE,
        rolling_window=WINDOW_MEDIUM,
        regime_stability=0.80,
        confidence=0.80,
        valid_from="2026-07-26T12:00:00Z",
        valid_until="2026-09-17T00:00:00Z",
    )
    ev = adapter.cross_asset_correlation_to_evidence(corr)
    assert isinstance(ev, Evidence)
    assert ev.event_type == "CAI_CORRELATION"
    assert ev.bias == "neutral"
    assert ev.confidence == 0.80
    assert ev.evidence_id == "cai_corr_equities_fixed_income"
    assert ev.source_node_id == "cai_equities_fixed_income"
    assert ev.condition == {"asset_a": "equities", "asset_b": "fixed_income", "trend": "positive"}


def test_adapter_correlation_to_evidence_negative() -> None:
    adapter = CaiEvidenceAdapter()
    corr = CrossAssetCorrelation(
        asset_class_a=EQUITIES,
        asset_class_b=FIXED_INCOME,
        correlation_coefficient=-0.45,
        lookback_periods=60,
        trend_direction=CORRELATION_NEGATIVE,
        rolling_window=WINDOW_MEDIUM,
        regime_stability=0.85,
        confidence=0.75,
        valid_from="2026-07-26T12:00:00Z",
        valid_until="2026-09-17T00:00:00Z",
    )
    ev = adapter.cross_asset_correlation_to_evidence(corr)
    assert ev.bias == "bearish"
    assert ev.evidence_id == "cai_corr_equities_fixed_income"


def test_adapter_correlation_to_evidence_decoupling() -> None:
    adapter = CaiEvidenceAdapter()
    corr = CrossAssetCorrelation(
        asset_class_a=EQUITIES,
        asset_class_b=FIXED_INCOME,
        correlation_coefficient=-0.1,
        lookback_periods=60,
        trend_direction=CORRELATION_DECOUPLING,
        rolling_window=WINDOW_MEDIUM,
        regime_stability=0.85,
        confidence=0.80,
        valid_from="2026-07-26T12:00:00Z",
        valid_until="2026-09-17T00:00:00Z",
    )
    ev = adapter.cross_asset_correlation_to_evidence(corr)
    assert ev.bias == "bearish"


def test_adapter_preserves_provenance() -> None:
    adapter = CaiEvidenceAdapter()
    provenance = Provenance(
        created_at="2026-07-26T12:00:00Z",
        created_by="analyst_01",
        entity_version="1.0.0",
    )
    corr = CrossAssetCorrelation(
        asset_class_a=EQUITIES,
        asset_class_b=FIXED_INCOME,
        correlation_coefficient=-0.45,
        lookback_periods=60,
        trend_direction=CORRELATION_NEGATIVE,
        rolling_window=WINDOW_MEDIUM,
        regime_stability=0.85,
        confidence=0.80,
        valid_from="2026-07-26T12:00:00Z",
        valid_until="2026-09-17T00:00:00Z",
        provenance=provenance,
    )
    ev = adapter.cross_asset_correlation_to_evidence(corr)
    assert ev.provenance is not None
    assert ev.provenance.created_by == "analyst_01"
    assert ev.provenance.created_at == "2026-07-26T12:00:00Z"
    assert ev.provenance.entity_version == "1.0.0"


def test_adapter_preserves_confidence() -> None:
    adapter = CaiEvidenceAdapter()
    corr = CrossAssetCorrelation(
        asset_class_a=EQUITIES,
        asset_class_b=FIXED_INCOME,
        correlation_coefficient=-0.45,
        lookback_periods=60,
        trend_direction=CORRELATION_NEGATIVE,
        rolling_window=WINDOW_MEDIUM,
        regime_stability=0.85,
        confidence=0.85,
        valid_from="2026-07-26T12:00:00Z",
        valid_until="2026-09-17T00:00:00Z",
    )
    ev = adapter.cross_asset_correlation_to_evidence(corr)
    assert ev.confidence == 0.85


def test_adapter_preserves_evidence_references() -> None:
    adapter = CaiEvidenceAdapter()
    ev_refs = [
        {
            "source_category": "market_data",
            "source_descriptor": "Bloomberg 60-day rolling correlation",
            "contribution": "primary measurement",
            "confidence_contribution": "high",
        }
    ]
    corr = CrossAssetCorrelation(
        asset_class_a=EQUITIES,
        asset_class_b=FIXED_INCOME,
        correlation_coefficient=-0.45,
        lookback_periods=60,
        trend_direction=CORRELATION_NEGATIVE,
        rolling_window=WINDOW_MEDIUM,
        regime_stability=0.85,
        confidence=0.80,
        valid_from="2026-07-26T12:00:00Z",
        valid_until="2026-09-17T00:00:00Z",
        evidence_references=ev_refs,
    )
    ev = adapter.cross_asset_correlation_to_evidence(corr)
    assert ev.metadata["evidence_references"] == ev_refs


def test_adapter_preserves_validity_information() -> None:
    adapter = CaiEvidenceAdapter()
    corr = CrossAssetCorrelation(
        asset_class_a=EQUITIES,
        asset_class_b=FIXED_INCOME,
        correlation_coefficient=-0.45,
        lookback_periods=60,
        trend_direction=CORRELATION_NEGATIVE,
        rolling_window=WINDOW_MEDIUM,
        regime_stability=0.85,
        confidence=0.80,
        valid_from="2026-07-26T12:00:00Z",
        valid_until="2026-09-17T00:00:00Z",
        time_horizon="T3",
    )
    ev = adapter.cross_asset_correlation_to_evidence(corr)
    assert ev.metadata["valid_from"] == "2026-07-26T12:00:00Z"
    assert ev.metadata["valid_until"] == "2026-09-17T00:00:00Z"
    assert ev.metadata["time_horizon"] == "T3"


def test_adapter_preserves_cross_references() -> None:
    adapter = CaiEvidenceAdapter()
    corr = CrossAssetCorrelation(
        asset_class_a=EQUITIES,
        asset_class_b=FIXED_INCOME,
        correlation_coefficient=-0.45,
        lookback_periods=60,
        trend_direction=CORRELATION_NEGATIVE,
        rolling_window=WINDOW_MEDIUM,
        regime_stability=0.85,
        confidence=0.80,
        valid_from="2026-07-26T12:00:00Z",
        valid_until="2026-09-17T00:00:00Z",
        cross_references=["CBI:PolicyBiasScore:FED:2026-07-26"],
    )
    ev = adapter.cross_asset_correlation_to_evidence(corr)
    assert ev.metadata["cross_references"] == ["CBI:PolicyBiasScore:FED:2026-07-26"]


def test_adapter_preserves_all_metadata() -> None:
    adapter = CaiEvidenceAdapter()
    corr = CrossAssetCorrelation(
        asset_class_a=EQUITIES,
        asset_class_b=FIXED_INCOME,
        correlation_coefficient=-0.45,
        lookback_periods=60,
        trend_direction=CORRELATION_NEGATIVE,
        rolling_window=WINDOW_MEDIUM,
        regime_stability=0.85,
        confidence=0.80,
        valid_from="2026-07-26T12:00:00Z",
        valid_until="2026-09-17T00:00:00Z",
    )
    ev = adapter.cross_asset_correlation_to_evidence(corr)
    assert ev.metadata["object_type"] == "CrossAssetCorrelation"
    assert ev.metadata["correlation_coefficient"] == -0.45
    assert ev.metadata["lookback_periods"] == 60
    assert ev.metadata["trend_direction"] == "negative"
    assert ev.metadata["rolling_window"] == "medium"
    assert ev.metadata["regime_stability"] == 0.85


# ── EvidenceAggregator integration ───────────────────────────────────────────


def test_correlation_evidence_merges_via_aggregator() -> None:
    adapter = CaiEvidenceAdapter()
    corr = CrossAssetCorrelation(
        asset_class_a=EQUITIES,
        asset_class_b=FIXED_INCOME,
        correlation_coefficient=-0.45,
        lookback_periods=60,
        trend_direction=CORRELATION_NEGATIVE,
        rolling_window=WINDOW_MEDIUM,
        regime_stability=0.85,
        confidence=0.80,
        valid_from="2026-07-26T12:00:00Z",
        valid_until="2026-09-17T00:00:00Z",
    )
    ev = adapter.cross_asset_correlation_to_evidence(corr)

    event_evidence = [
        Evidence(
            evidence_id="event_001",
            source_node_id="event_source",
            event_type="CPI",
            condition={"asset": "XAU/USD"},
            horizon_days=5,
            sample_count=100,
            average_return_pct=0.5,
            confidence=0.6,
            bias="bullish",
            explanation="CPI came in hot.",
        ),
    ]

    agg = EvidenceAggregator()
    result = agg.merge({
        "event": EvidenceCollection(event_evidence),
        "cai": EvidenceCollection([ev]),
    })
    assert len(result.collection) == 2
    assert result.layer_counts["cai"] == 1
    assert result.layer_counts["event"] == 1


def test_correlation_evidence_conflict_detection() -> None:
    adapter = CaiEvidenceAdapter()
    corr = CrossAssetCorrelation(
        asset_class_a=EQUITIES,
        asset_class_b=FIXED_INCOME,
        correlation_coefficient=-0.45,
        lookback_periods=60,
        trend_direction=CORRELATION_NEGATIVE,
        rolling_window=WINDOW_MEDIUM,
        regime_stability=0.85,
        confidence=0.80,
        valid_from="2026-07-26T12:00:00Z",
        valid_until="2026-09-17T00:00:00Z",
    )
    ev = adapter.cross_asset_correlation_to_evidence(corr)

    conflicting = Evidence(
        evidence_id="cai_corr_equities_fixed_income",
        source_node_id="cai_equities_fixed_income",
        event_type="CAI_CORRELATION",
        condition={"asset_a": "equities", "asset_b": "fixed_income", "trend": "positive"},
        horizon_days=0,
        sample_count=1,
        average_return_pct=0.0,
        confidence=0.80,
        bias="bullish",
        explanation="Conflicting bias for same evidence_id.",
    )

    agg = EvidenceAggregator()
    result = agg.merge({
        "cai_v1": EvidenceCollection([ev]),
        "cai_v2": EvidenceCollection([conflicting]),
    })
    assert len(result.conflicts) >= 1
