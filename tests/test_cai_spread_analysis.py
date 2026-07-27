import json
from pathlib import Path

import pytest

from knowledge.cai.contracts import (
    SpreadAnalysis,
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
    SPREAD_NARROWING,
    SPREAD_WIDENING,
    SPREAD_STABLE,
    SPREAD_INVERSION,
    VALID_SPREAD_TRENDS,
)
from knowledge.cai.repository import CaiRepository
from knowledge.cai.adapter import CaiEvidenceAdapter
from knowledge.evidence.evidence import Evidence
from knowledge.evidence.collection import EvidenceCollection
from knowledge.orchestration.aggregator import EvidenceAggregator
from knowledge.integrity.provenance import Provenance


# ── Creation ─────────────────────────────────────────────────────────────────


def test_spread_creation() -> None:
    spread = SpreadAnalysis(
        instrument_a="US10Y",
        instrument_b="US2Y",
        current_spread=1.25,
        historical_mean=1.50,
        standard_deviation=0.30,
        z_score=-0.83,
        trend=SPREAD_NARROWING,
        mean_reversion_signal=0.65,
        confidence=0.80,
        valid_from="2026-07-27T12:00:00Z",
        valid_until="2026-09-17T00:00:00Z",
    )
    assert spread.instrument_a == "US10Y"
    assert spread.instrument_b == "US2Y"
    assert spread.current_spread == 1.25
    assert spread.historical_mean == 1.50
    assert spread.standard_deviation == 0.30
    assert spread.z_score == -0.83
    assert spread.trend == SPREAD_NARROWING
    assert spread.mean_reversion_signal == 0.65
    assert spread.confidence == 0.80
    assert spread.valid_from == "2026-07-27T12:00:00Z"
    assert spread.valid_until == "2026-09-17T00:00:00Z"


def test_spread_defaults() -> None:
    spread = SpreadAnalysis(
        instrument_a="US10Y",
        instrument_b="US2Y",
        current_spread=1.25,
        historical_mean=1.50,
        standard_deviation=0.30,
        z_score=-0.83,
        trend=SPREAD_NARROWING,
        mean_reversion_signal=0.65,
        confidence=0.80,
    )
    assert spread.confidence == 0.80
    assert spread.valid_from == ""
    assert spread.valid_until == ""
    assert spread.time_horizon == ""
    assert spread.provenance is None
    assert spread.evidence_references == []
    assert spread.cross_references is None
    assert spread.methodology_version is None
    assert spread.scenario_analysis is None


def test_spread_all_trends() -> None:
    for trend in (SPREAD_NARROWING, SPREAD_WIDENING, SPREAD_STABLE, SPREAD_INVERSION):
        spread = SpreadAnalysis(
            instrument_a="US10Y",
            instrument_b="US2Y",
            current_spread=1.0,
            historical_mean=1.0,
            standard_deviation=0.3,
            z_score=0.0,
            trend=trend,
            mean_reversion_signal=0.5,
            confidence=0.7,
            valid_from="2026-07-27T12:00:00Z",
            valid_until="2026-09-17T00:00:00Z",
        )
        assert spread.trend == trend
    assert VALID_SPREAD_TRENDS == {
        SPREAD_NARROWING, SPREAD_WIDENING, SPREAD_STABLE, SPREAD_INVERSION,
    }


def test_spread_various_instruments() -> None:
    pairs = [
        ("US10Y", "US2Y"),
        ("DE10Y", "US10Y"),
        ("HY_CDX", "IG_CDX"),
        ("SPX_IV", "VIX"),
        ("XAU", "XAG"),
    ]
    for a, b in pairs:
        spread = SpreadAnalysis(
            instrument_a=a,
            instrument_b=b,
            current_spread=0.5,
            historical_mean=0.4,
            standard_deviation=0.1,
            z_score=1.0,
            trend=SPREAD_WIDENING,
            mean_reversion_signal=0.3,
            confidence=0.7,
            valid_from="2026-07-27T12:00:00Z",
            valid_until="2026-09-17T00:00:00Z",
        )
        assert spread.instrument_a == a
        assert spread.instrument_b == b


def test_spread_frozen_dataclass() -> None:
    spread = SpreadAnalysis(
        instrument_a="US10Y",
        instrument_b="US2Y",
        current_spread=1.25,
        historical_mean=1.50,
        standard_deviation=0.30,
        z_score=-0.83,
        trend=SPREAD_NARROWING,
        mean_reversion_signal=0.65,
        confidence=0.80,
        valid_from="2026-07-27T12:00:00Z",
        valid_until="2026-09-17T00:00:00Z",
    )
    with pytest.raises(AttributeError):
        spread.current_spread = 2.0
    with pytest.raises(AttributeError):
        spread.trend = SPREAD_WIDENING


def test_spread_z_score_range() -> None:
    for z in (-3.0, -1.5, 0.0, 1.5, 3.0):
        spread = SpreadAnalysis(
            instrument_a="US10Y",
            instrument_b="US2Y",
            current_spread=1.0,
            historical_mean=1.0,
            standard_deviation=0.3,
            z_score=z,
            trend=SPREAD_STABLE,
            mean_reversion_signal=0.5,
            confidence=0.7,
            valid_from="2026-07-27T12:00:00Z",
            valid_until="2026-09-17T00:00:00Z",
        )
        assert spread.z_score == z


def test_spread_negative_spread() -> None:
    spread = SpreadAnalysis(
        instrument_a="US2Y",
        instrument_b="US10Y",
        current_spread=-0.25,
        historical_mean=0.10,
        standard_deviation=0.20,
        z_score=-1.75,
        trend=SPREAD_INVERSION,
        mean_reversion_signal=0.80,
        confidence=0.85,
        valid_from="2026-07-27T12:00:00Z",
        valid_until="2026-09-17T00:00:00Z",
    )
    assert spread.current_spread == -0.25
    assert spread.trend == SPREAD_INVERSION


def test_spread_with_full_optional_fields() -> None:
    provenance = Provenance(
        created_at="2026-07-27T12:00:00Z",
        created_by="analyst_03",
        entity_version="1.0.0",
    )
    ev_refs = [
        {
            "source_category": "market_data",
            "source_descriptor": "Bloomberg US yield curve analytics",
            "contribution": "primary measurement",
            "confidence_contribution": "high",
        }
    ]
    spread = SpreadAnalysis(
        instrument_a="US10Y",
        instrument_b="US2Y",
        current_spread=1.25,
        historical_mean=1.50,
        standard_deviation=0.30,
        z_score=-0.83,
        trend=SPREAD_NARROWING,
        mean_reversion_signal=0.65,
        confidence=0.80,
        valid_from="2026-07-27T12:00:00Z",
        valid_until="2026-09-17T00:00:00Z",
        time_horizon="T3",
        provenance=provenance,
        evidence_references=ev_refs,
        cross_references=["CBI:RatePathProjection:FED:2026-07-27"],
        methodology_version="1.0.0",
        scenario_analysis=[
            {"label": "curve_inversion", "probability": 0.15, "spread_shift": -0.5}
        ],
    )
    assert spread.provenance is not None
    assert spread.provenance.created_by == "analyst_03"
    assert len(spread.evidence_references) == 1
    assert spread.cross_references == ["CBI:RatePathProjection:FED:2026-07-27"]
    assert spread.methodology_version == "1.0.0"
    assert len(spread.scenario_analysis) == 1
    assert spread.time_horizon == "T3"


def test_spread_inherits_base_contract() -> None:
    spread = SpreadAnalysis(
        instrument_a="US10Y",
        instrument_b="US2Y",
        current_spread=1.25,
        historical_mean=1.50,
        standard_deviation=0.30,
        z_score=-0.83,
        trend=SPREAD_NARROWING,
        mean_reversion_signal=0.65,
        confidence=0.80,
        valid_from="2026-07-27T12:00:00Z",
        valid_until="2026-09-17T00:00:00Z",
    )
    assert isinstance(spread, CaiBaseContract)


# ── Repository ───────────────────────────────────────────────────────────────


def test_repository_save_and_load_spread(tmp_path: Path) -> None:
    repo = CaiRepository()
    spread = SpreadAnalysis(
        instrument_a="US10Y",
        instrument_b="US2Y",
        current_spread=1.25,
        historical_mean=1.50,
        standard_deviation=0.30,
        z_score=-0.83,
        trend=SPREAD_NARROWING,
        mean_reversion_signal=0.65,
        confidence=0.80,
        valid_from="2026-07-27T12:00:00Z",
        valid_until="2026-09-17T00:00:00Z",
    )
    p = tmp_path / "spread.json"
    repo.save_spread(spread, p)
    loaded = repo.load_spread(p)
    assert loaded.instrument_a == "US10Y"
    assert loaded.instrument_b == "US2Y"
    assert loaded.current_spread == 1.25
    assert loaded.z_score == -0.83
    assert loaded.trend == SPREAD_NARROWING
    assert loaded.confidence == 0.80


def test_repository_roundtrip_preserves_all_fields(tmp_path: Path) -> None:
    repo = CaiRepository()
    provenance = Provenance(
        created_at="2026-07-27T12:00:00Z",
        created_by="analyst_03",
        entity_version="1.0.0",
    )
    original = SpreadAnalysis(
        instrument_a="DE10Y",
        instrument_b="US10Y",
        current_spread=-0.15,
        historical_mean=0.10,
        standard_deviation=0.25,
        z_score=-1.0,
        trend=SPREAD_INVERSION,
        mean_reversion_signal=0.72,
        confidence=0.75,
        valid_from="2026-07-27T12:00:00Z",
        valid_until="2026-09-10T00:00:00Z",
        time_horizon="T3",
        provenance=provenance,
        evidence_references=[
            {"source_category": "market_data", "source_descriptor": "Bloomberg Bund-Treasury spread"}
        ],
        cross_references=["CBI:RatePathProjection:ECB:2026-07-27"],
        methodology_version="1.2.0",
        scenario_analysis=[{"label": "convergence", "probability": 0.25}],
    )
    p = tmp_path / "de_us_spread.json"
    repo.save_spread(original, p)
    loaded = repo.load_spread(p)
    assert loaded.instrument_a == original.instrument_a
    assert loaded.instrument_b == original.instrument_b
    assert loaded.current_spread == original.current_spread
    assert loaded.historical_mean == original.historical_mean
    assert loaded.standard_deviation == original.standard_deviation
    assert loaded.z_score == original.z_score
    assert loaded.trend == original.trend
    assert loaded.mean_reversion_signal == original.mean_reversion_signal
    assert loaded.confidence == original.confidence
    assert loaded.valid_from == original.valid_from
    assert loaded.valid_until == original.valid_until
    assert loaded.time_horizon == original.time_horizon
    assert loaded.provenance is not None
    assert loaded.provenance.created_by == "analyst_03"
    assert loaded.provenance.entity_version == "1.0.0"
    assert loaded.evidence_references == original.evidence_references
    assert loaded.cross_references == original.cross_references
    assert loaded.methodology_version == original.methodology_version
    assert loaded.scenario_analysis == original.scenario_analysis


def test_repository_roundtrip_with_none_optionals(tmp_path: Path) -> None:
    repo = CaiRepository()
    original = SpreadAnalysis(
        instrument_a="HY_CDX",
        instrument_b="IG_CDX",
        current_spread=3.50,
        historical_mean=3.00,
        standard_deviation=0.50,
        z_score=1.0,
        trend=SPREAD_WIDENING,
        mean_reversion_signal=0.40,
        confidence=0.65,
        valid_from="2026-07-27T12:00:00Z",
        valid_until="2026-09-20T00:00:00Z",
    )
    p = tmp_path / "credit_spread.json"
    repo.save_spread(original, p)
    loaded = repo.load_spread(p)
    assert loaded.provenance is None
    assert loaded.evidence_references == []
    assert loaded.cross_references is None
    assert loaded.methodology_version is None
    assert loaded.scenario_analysis is None


def test_repository_json_structure(tmp_path: Path) -> None:
    repo = CaiRepository()
    spread = SpreadAnalysis(
        instrument_a="US10Y",
        instrument_b="US2Y",
        current_spread=1.25,
        historical_mean=1.50,
        standard_deviation=0.30,
        z_score=-0.83,
        trend=SPREAD_NARROWING,
        mean_reversion_signal=0.65,
        confidence=0.80,
        valid_from="2026-07-27T12:00:00Z",
        valid_until="2026-09-17T00:00:00Z",
    )
    p = tmp_path / "spread.json"
    repo.save_spread(spread, p)
    raw = json.loads(p.read_text())
    assert raw["instrument_a"] == "US10Y"
    assert raw["instrument_b"] == "US2Y"
    assert raw["current_spread"] == 1.25
    assert raw["historical_mean"] == 1.50
    assert raw["standard_deviation"] == 0.30
    assert raw["z_score"] == -0.83
    assert raw["trend"] == "narrowing"
    assert raw["mean_reversion_signal"] == 0.65
    assert raw["confidence"] == 0.80
    assert raw["valid_from"] == "2026-07-27T12:00:00Z"
    assert raw["valid_until"] == "2026-09-17T00:00:00Z"
    assert raw["provenance"] is None
    assert raw["evidence_references"] == []
    assert raw["cross_references"] is None


# ── Adapter ──────────────────────────────────────────────────────────────────


def test_adapter_spread_to_evidence_narrowing() -> None:
    adapter = CaiEvidenceAdapter()
    spread = SpreadAnalysis(
        instrument_a="US10Y",
        instrument_b="US2Y",
        current_spread=1.25,
        historical_mean=1.50,
        standard_deviation=0.30,
        z_score=-0.83,
        trend=SPREAD_NARROWING,
        mean_reversion_signal=0.65,
        confidence=0.80,
        valid_from="2026-07-27T12:00:00Z",
        valid_until="2026-09-17T00:00:00Z",
    )
    ev = adapter.spread_analysis_to_evidence(spread)
    assert isinstance(ev, Evidence)
    assert ev.event_type == "CAI_SPREAD"
    assert ev.bias == "bullish"
    assert ev.confidence == 0.80
    assert ev.evidence_id == "cai_spread_US10Y_US2Y"
    assert ev.source_node_id == "cai_US10Y_US2Y"
    assert ev.condition == {"instrument_a": "US10Y", "instrument_b": "US2Y", "trend": "narrowing"}


def test_adapter_spread_to_evidence_widening() -> None:
    adapter = CaiEvidenceAdapter()
    spread = SpreadAnalysis(
        instrument_a="HY_CDX",
        instrument_b="IG_CDX",
        current_spread=3.50,
        historical_mean=3.00,
        standard_deviation=0.50,
        z_score=1.0,
        trend=SPREAD_WIDENING,
        mean_reversion_signal=0.40,
        confidence=0.75,
        valid_from="2026-07-27T12:00:00Z",
        valid_until="2026-09-17T00:00:00Z",
    )
    ev = adapter.spread_analysis_to_evidence(spread)
    assert ev.bias == "bearish"
    assert ev.evidence_id == "cai_spread_HY_CDX_IG_CDX"


def test_adapter_spread_to_evidence_stable() -> None:
    adapter = CaiEvidenceAdapter()
    spread = SpreadAnalysis(
        instrument_a="US10Y",
        instrument_b="US2Y",
        current_spread=1.50,
        historical_mean=1.50,
        standard_deviation=0.30,
        z_score=0.0,
        trend=SPREAD_STABLE,
        mean_reversion_signal=0.50,
        confidence=0.70,
        valid_from="2026-07-27T12:00:00Z",
        valid_until="2026-09-17T00:00:00Z",
    )
    ev = adapter.spread_analysis_to_evidence(spread)
    assert ev.bias == "neutral"


def test_adapter_spread_to_evidence_inversion() -> None:
    adapter = CaiEvidenceAdapter()
    spread = SpreadAnalysis(
        instrument_a="US2Y",
        instrument_b="US10Y",
        current_spread=-0.25,
        historical_mean=0.10,
        standard_deviation=0.20,
        z_score=-1.75,
        trend=SPREAD_INVERSION,
        mean_reversion_signal=0.80,
        confidence=0.85,
        valid_from="2026-07-27T12:00:00Z",
        valid_until="2026-09-17T00:00:00Z",
    )
    ev = adapter.spread_analysis_to_evidence(spread)
    assert ev.bias == "bearish"


def test_adapter_preserves_provenance() -> None:
    adapter = CaiEvidenceAdapter()
    provenance = Provenance(
        created_at="2026-07-27T12:00:00Z",
        created_by="analyst_03",
        entity_version="1.0.0",
    )
    spread = SpreadAnalysis(
        instrument_a="US10Y",
        instrument_b="US2Y",
        current_spread=1.25,
        historical_mean=1.50,
        standard_deviation=0.30,
        z_score=-0.83,
        trend=SPREAD_NARROWING,
        mean_reversion_signal=0.65,
        confidence=0.80,
        valid_from="2026-07-27T12:00:00Z",
        valid_until="2026-09-17T00:00:00Z",
        provenance=provenance,
    )
    ev = adapter.spread_analysis_to_evidence(spread)
    assert ev.provenance is not None
    assert ev.provenance.created_by == "analyst_03"
    assert ev.provenance.created_at == "2026-07-27T12:00:00Z"
    assert ev.provenance.entity_version == "1.0.0"


def test_adapter_preserves_confidence() -> None:
    adapter = CaiEvidenceAdapter()
    spread = SpreadAnalysis(
        instrument_a="US10Y",
        instrument_b="US2Y",
        current_spread=1.25,
        historical_mean=1.50,
        standard_deviation=0.30,
        z_score=-0.83,
        trend=SPREAD_NARROWING,
        mean_reversion_signal=0.65,
        confidence=0.92,
        valid_from="2026-07-27T12:00:00Z",
        valid_until="2026-09-17T00:00:00Z",
    )
    ev = adapter.spread_analysis_to_evidence(spread)
    assert ev.confidence == 0.92


def test_adapter_preserves_evidence_references() -> None:
    adapter = CaiEvidenceAdapter()
    ev_refs = [
        {
            "source_category": "market_data",
            "source_descriptor": "Bloomberg US yield curve analytics",
            "contribution": "primary measurement",
            "confidence_contribution": "high",
        }
    ]
    spread = SpreadAnalysis(
        instrument_a="US10Y",
        instrument_b="US2Y",
        current_spread=1.25,
        historical_mean=1.50,
        standard_deviation=0.30,
        z_score=-0.83,
        trend=SPREAD_NARROWING,
        mean_reversion_signal=0.65,
        confidence=0.80,
        valid_from="2026-07-27T12:00:00Z",
        valid_until="2026-09-17T00:00:00Z",
        evidence_references=ev_refs,
    )
    ev = adapter.spread_analysis_to_evidence(spread)
    assert ev.metadata["evidence_references"] == ev_refs


def test_adapter_preserves_validity_information() -> None:
    adapter = CaiEvidenceAdapter()
    spread = SpreadAnalysis(
        instrument_a="US10Y",
        instrument_b="US2Y",
        current_spread=1.25,
        historical_mean=1.50,
        standard_deviation=0.30,
        z_score=-0.83,
        trend=SPREAD_NARROWING,
        mean_reversion_signal=0.65,
        confidence=0.80,
        valid_from="2026-07-27T12:00:00Z",
        valid_until="2026-09-17T00:00:00Z",
        time_horizon="T3",
    )
    ev = adapter.spread_analysis_to_evidence(spread)
    assert ev.metadata["valid_from"] == "2026-07-27T12:00:00Z"
    assert ev.metadata["valid_until"] == "2026-09-17T00:00:00Z"
    assert ev.metadata["time_horizon"] == "T3"


def test_adapter_preserves_cross_references() -> None:
    adapter = CaiEvidenceAdapter()
    spread = SpreadAnalysis(
        instrument_a="US10Y",
        instrument_b="US2Y",
        current_spread=1.25,
        historical_mean=1.50,
        standard_deviation=0.30,
        z_score=-0.83,
        trend=SPREAD_NARROWING,
        mean_reversion_signal=0.65,
        confidence=0.80,
        valid_from="2026-07-27T12:00:00Z",
        valid_until="2026-09-17T00:00:00Z",
        cross_references=["CBI:RatePathProjection:FED:2026-07-27"],
    )
    ev = adapter.spread_analysis_to_evidence(spread)
    assert ev.metadata["cross_references"] == ["CBI:RatePathProjection:FED:2026-07-27"]


def test_adapter_preserves_all_metadata() -> None:
    adapter = CaiEvidenceAdapter()
    spread = SpreadAnalysis(
        instrument_a="US10Y",
        instrument_b="US2Y",
        current_spread=1.25,
        historical_mean=1.50,
        standard_deviation=0.30,
        z_score=-0.83,
        trend=SPREAD_NARROWING,
        mean_reversion_signal=0.65,
        confidence=0.80,
        valid_from="2026-07-27T12:00:00Z",
        valid_until="2026-09-17T00:00:00Z",
    )
    ev = adapter.spread_analysis_to_evidence(spread)
    assert ev.metadata["object_type"] == "SpreadAnalysis"
    assert ev.metadata["current_spread"] == 1.25
    assert ev.metadata["historical_mean"] == 1.50
    assert ev.metadata["standard_deviation"] == 0.30
    assert ev.metadata["z_score"] == -0.83
    assert ev.metadata["trend"] == "narrowing"
    assert ev.metadata["mean_reversion_signal"] == 0.65


# ── EvidenceAggregator integration ───────────────────────────────────────────


def test_spread_evidence_merges_via_aggregator() -> None:
    adapter = CaiEvidenceAdapter()
    spread = SpreadAnalysis(
        instrument_a="US10Y",
        instrument_b="US2Y",
        current_spread=1.25,
        historical_mean=1.50,
        standard_deviation=0.30,
        z_score=-0.83,
        trend=SPREAD_NARROWING,
        mean_reversion_signal=0.65,
        confidence=0.80,
        valid_from="2026-07-27T12:00:00Z",
        valid_until="2026-09-17T00:00:00Z",
    )
    ev = adapter.spread_analysis_to_evidence(spread)

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


def test_spread_evidence_conflict_detection() -> None:
    adapter = CaiEvidenceAdapter()
    spread = SpreadAnalysis(
        instrument_a="US10Y",
        instrument_b="US2Y",
        current_spread=1.25,
        historical_mean=1.50,
        standard_deviation=0.30,
        z_score=-0.83,
        trend=SPREAD_NARROWING,
        mean_reversion_signal=0.65,
        confidence=0.80,
        valid_from="2026-07-27T12:00:00Z",
        valid_until="2026-09-17T00:00:00Z",
    )
    ev = adapter.spread_analysis_to_evidence(spread)

    conflicting = Evidence(
        evidence_id="cai_spread_US10Y_US2Y",
        source_node_id="cai_US10Y_US2Y",
        event_type="CAI_SPREAD",
        condition={"instrument_a": "US10Y", "instrument_b": "US2Y", "trend": "widening"},
        horizon_days=0,
        sample_count=1,
        average_return_pct=0.0,
        confidence=0.80,
        bias="bearish",
        explanation="Conflicting bias for same evidence_id.",
    )

    agg = EvidenceAggregator()
    result = agg.merge({
        "cai_v1": EvidenceCollection([ev]),
        "cai_v2": EvidenceCollection([conflicting]),
    })
    assert len(result.conflicts) >= 1
