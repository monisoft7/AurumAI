import json
from pathlib import Path

import pytest

from knowledge.cai.contracts import (
    VolatilityRegime,
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
    VOL_LOW,
    VOL_MODERATE,
    VOL_ELEVATED,
    VOL_HIGH,
    VOL_EXTREME,
    VALID_VOLATILITY_STATES,
)
from knowledge.cai.repository import CaiRepository
from knowledge.cai.adapter import CaiEvidenceAdapter
from knowledge.evidence.evidence import Evidence
from knowledge.evidence.collection import EvidenceCollection
from knowledge.orchestration.aggregator import EvidenceAggregator
from knowledge.integrity.provenance import Provenance


# ── Creation ─────────────────────────────────────────────────────────────────


def test_volatility_regime_creation() -> None:
    vol = VolatilityRegime(
        asset_class=EQUITIES,
        current_state=VOL_ELEVATED,
        previous_state=VOL_MODERATE,
        regime_persistence=0.75,
        mean_reversion_half_life_days=12.5,
        tail_risk_index=0.40,
        confidence=0.80,
        valid_from="2026-07-27T12:00:00Z",
        valid_until="2026-09-17T00:00:00Z",
    )
    assert vol.asset_class == EQUITIES
    assert vol.current_state == VOL_ELEVATED
    assert vol.previous_state == VOL_MODERATE
    assert vol.regime_persistence == 0.75
    assert vol.mean_reversion_half_life_days == 12.5
    assert vol.tail_risk_index == 0.40
    assert vol.confidence == 0.80
    assert vol.valid_from == "2026-07-27T12:00:00Z"
    assert vol.valid_until == "2026-09-17T00:00:00Z"


def test_volatility_regime_defaults() -> None:
    vol = VolatilityRegime(
        asset_class=EQUITIES,
        current_state=VOL_ELEVATED,
        previous_state=VOL_MODERATE,
        regime_persistence=0.75,
        mean_reversion_half_life_days=12.5,
        tail_risk_index=0.40,
        confidence=0.80,
    )
    assert vol.confidence == 0.80
    assert vol.valid_from == ""
    assert vol.valid_until == ""
    assert vol.time_horizon == ""
    assert vol.provenance is None
    assert vol.evidence_references == []
    assert vol.cross_references is None
    assert vol.methodology_version is None
    assert vol.scenario_analysis is None
    assert vol.regime_drivers is None


def test_volatility_regime_all_states() -> None:
    for state in (VOL_LOW, VOL_MODERATE, VOL_ELEVATED, VOL_HIGH, VOL_EXTREME):
        vol = VolatilityRegime(
            asset_class=EQUITIES,
            current_state=state,
            previous_state=VOL_MODERATE,
            regime_persistence=0.5,
            mean_reversion_half_life_days=10.0,
            tail_risk_index=0.3,
            confidence=0.7,
            valid_from="2026-07-27T12:00:00Z",
            valid_until="2026-09-17T00:00:00Z",
        )
        assert vol.current_state == state
    assert VALID_VOLATILITY_STATES == {
        VOL_LOW, VOL_MODERATE, VOL_ELEVATED, VOL_HIGH, VOL_EXTREME,
    }


def test_volatility_regime_all_asset_classes() -> None:
    for ac in (EQUITIES, FIXED_INCOME, FX, COMMODITIES, CREDIT, RATES, VOLATILITY, REAL_ESTATE, CRYPTO, EM):
        vol = VolatilityRegime(
            asset_class=ac,
            current_state=VOL_MODERATE,
            previous_state=VOL_LOW,
            regime_persistence=0.5,
            mean_reversion_half_life_days=10.0,
            tail_risk_index=0.2,
            confidence=0.7,
            valid_from="2026-07-27T12:00:00Z",
            valid_until="2026-09-17T00:00:00Z",
        )
        assert vol.asset_class == ac
    assert VALID_ASSET_CLASSES == {
        EQUITIES, FIXED_INCOME, FX, COMMODITIES, CREDIT,
        RATES, VOLATILITY, REAL_ESTATE, CRYPTO, EM,
    }


def test_volatility_regime_frozen_dataclass() -> None:
    vol = VolatilityRegime(
        asset_class=EQUITIES,
        current_state=VOL_ELEVATED,
        previous_state=VOL_MODERATE,
        regime_persistence=0.75,
        mean_reversion_half_life_days=12.5,
        tail_risk_index=0.40,
        confidence=0.80,
        valid_from="2026-07-27T12:00:00Z",
        valid_until="2026-09-17T00:00:00Z",
    )
    with pytest.raises(AttributeError):
        vol.current_state = VOL_HIGH
    with pytest.raises(AttributeError):
        vol.tail_risk_index = 0.9


def test_volatility_regime_persistence_range() -> None:
    for p in (0.0, 0.25, 0.5, 0.75, 1.0):
        vol = VolatilityRegime(
            asset_class=EQUITIES,
            current_state=VOL_MODERATE,
            previous_state=VOL_LOW,
            regime_persistence=p,
            mean_reversion_half_life_days=10.0,
            tail_risk_index=0.2,
            confidence=0.7,
            valid_from="2026-07-27T12:00:00Z",
            valid_until="2026-09-17T00:00:00Z",
        )
        assert vol.regime_persistence == p


def test_volatility_regime_with_drivers() -> None:
    vol = VolatilityRegime(
        asset_class=EQUITIES,
        current_state=VOL_HIGH,
        previous_state=VOL_ELEVATED,
        regime_persistence=0.85,
        mean_reversion_half_life_days=20.0,
        tail_risk_index=0.65,
        confidence=0.78,
        valid_from="2026-07-27T12:00:00Z",
        valid_until="2026-09-17T00:00:00Z",
        regime_drivers=["geopolitical_escalation", "earnings_season", "options_expiry"],
    )
    assert vol.regime_drivers == ["geopolitical_escalation", "earnings_season", "options_expiry"]


def test_volatility_regime_state_transition() -> None:
    for prev, curr in [(VOL_LOW, VOL_MODERATE), (VOL_MODERATE, VOL_HIGH),
                        (VOL_HIGH, VOL_EXTREME), (VOL_EXTREME, VOL_ELEVATED),
                        (VOL_ELEVATED, VOL_LOW)]:
        vol = VolatilityRegime(
            asset_class=EQUITIES,
            current_state=curr,
            previous_state=prev,
            regime_persistence=0.5,
            mean_reversion_half_life_days=10.0,
            tail_risk_index=0.3,
            confidence=0.7,
            valid_from="2026-07-27T12:00:00Z",
            valid_until="2026-09-17T00:00:00Z",
        )
        assert vol.previous_state == prev
        assert vol.current_state == curr


def test_volatility_regime_with_full_optional_fields() -> None:
    provenance = Provenance(
        created_at="2026-07-27T12:00:00Z",
        created_by="analyst_04",
        entity_version="1.0.0",
    )
    ev_refs = [
        {
            "source_category": "market_data",
            "source_descriptor": "CBOE VIX term structure analytics",
            "contribution": "primary measurement",
            "confidence_contribution": "high",
        }
    ]
    vol = VolatilityRegime(
        asset_class=EQUITIES,
        current_state=VOL_ELEVATED,
        previous_state=VOL_MODERATE,
        regime_persistence=0.75,
        mean_reversion_half_life_days=12.5,
        tail_risk_index=0.40,
        confidence=0.80,
        valid_from="2026-07-27T12:00:00Z",
        valid_until="2026-09-17T00:00:00Z",
        time_horizon="T3",
        provenance=provenance,
        evidence_references=ev_refs,
        cross_references=["CAI:CrossAssetCorrelation:equities_fixed_income:2026-07-27"],
        methodology_version="1.0.0",
        scenario_analysis=[
            {"label": "vol_spike", "probability": 0.20, "vix_target": 35.0}
        ],
        regime_drivers=["fed_meeting", "cpi_release"],
    )
    assert vol.provenance is not None
    assert vol.provenance.created_by == "analyst_04"
    assert len(vol.evidence_references) == 1
    assert vol.cross_references == ["CAI:CrossAssetCorrelation:equities_fixed_income:2026-07-27"]
    assert vol.methodology_version == "1.0.0"
    assert len(vol.scenario_analysis) == 1
    assert vol.time_horizon == "T3"
    assert vol.regime_drivers == ["fed_meeting", "cpi_release"]


def test_volatility_regime_inherits_base_contract() -> None:
    vol = VolatilityRegime(
        asset_class=EQUITIES,
        current_state=VOL_ELEVATED,
        previous_state=VOL_MODERATE,
        regime_persistence=0.75,
        mean_reversion_half_life_days=12.5,
        tail_risk_index=0.40,
        confidence=0.80,
        valid_from="2026-07-27T12:00:00Z",
        valid_until="2026-09-17T00:00:00Z",
    )
    assert isinstance(vol, CaiBaseContract)


# ── Repository ───────────────────────────────────────────────────────────────


def test_repository_save_and_load_volatility_regime(tmp_path: Path) -> None:
    repo = CaiRepository()
    vol = VolatilityRegime(
        asset_class=EQUITIES,
        current_state=VOL_ELEVATED,
        previous_state=VOL_MODERATE,
        regime_persistence=0.75,
        mean_reversion_half_life_days=12.5,
        tail_risk_index=0.40,
        confidence=0.80,
        valid_from="2026-07-27T12:00:00Z",
        valid_until="2026-09-17T00:00:00Z",
    )
    p = tmp_path / "vol_regime.json"
    repo.save_volatility_regime(vol, p)
    loaded = repo.load_volatility_regime(p)
    assert loaded.asset_class == EQUITIES
    assert loaded.current_state == VOL_ELEVATED
    assert loaded.previous_state == VOL_MODERATE
    assert loaded.regime_persistence == 0.75
    assert loaded.tail_risk_index == 0.40
    assert loaded.confidence == 0.80


def test_repository_roundtrip_preserves_all_fields(tmp_path: Path) -> None:
    repo = CaiRepository()
    provenance = Provenance(
        created_at="2026-07-27T12:00:00Z",
        created_by="analyst_04",
        entity_version="1.0.0",
    )
    original = VolatilityRegime(
        asset_class=FX,
        current_state=VOL_HIGH,
        previous_state=VOL_ELEVATED,
        regime_persistence=0.82,
        mean_reversion_half_life_days=18.0,
        tail_risk_index=0.55,
        confidence=0.72,
        valid_from="2026-07-27T12:00:00Z",
        valid_until="2026-09-10T00:00:00Z",
        time_horizon="T3",
        provenance=provenance,
        evidence_references=[
            {"source_category": "market_data", "source_descriptor": "CVIX FX volatility index"}
        ],
        cross_references=["CAI:CrossAssetCorrelation:fx_commodities:2026-07-27"],
        methodology_version="1.2.0",
        scenario_analysis=[{"label": "vol_normalization", "probability": 0.30}],
        regime_drivers=["boj_intervention", "usd_strength"],
    )
    p = tmp_path / "fx_vol.json"
    repo.save_volatility_regime(original, p)
    loaded = repo.load_volatility_regime(p)
    assert loaded.asset_class == original.asset_class
    assert loaded.current_state == original.current_state
    assert loaded.previous_state == original.previous_state
    assert loaded.regime_persistence == original.regime_persistence
    assert loaded.mean_reversion_half_life_days == original.mean_reversion_half_life_days
    assert loaded.tail_risk_index == original.tail_risk_index
    assert loaded.confidence == original.confidence
    assert loaded.valid_from == original.valid_from
    assert loaded.valid_until == original.valid_until
    assert loaded.time_horizon == original.time_horizon
    assert loaded.provenance is not None
    assert loaded.provenance.created_by == "analyst_04"
    assert loaded.provenance.entity_version == "1.0.0"
    assert loaded.evidence_references == original.evidence_references
    assert loaded.cross_references == original.cross_references
    assert loaded.methodology_version == original.methodology_version
    assert loaded.scenario_analysis == original.scenario_analysis
    assert loaded.regime_drivers == original.regime_drivers


def test_repository_roundtrip_with_none_optionals(tmp_path: Path) -> None:
    repo = CaiRepository()
    original = VolatilityRegime(
        asset_class=COMMODITIES,
        current_state=VOL_LOW,
        previous_state=VOL_MODERATE,
        regime_persistence=0.90,
        mean_reversion_half_life_days=25.0,
        tail_risk_index=0.10,
        confidence=0.65,
        valid_from="2026-07-27T12:00:00Z",
        valid_until="2026-09-20T00:00:00Z",
    )
    p = tmp_path / "comm_vol.json"
    repo.save_volatility_regime(original, p)
    loaded = repo.load_volatility_regime(p)
    assert loaded.provenance is None
    assert loaded.evidence_references == []
    assert loaded.cross_references is None
    assert loaded.methodology_version is None
    assert loaded.scenario_analysis is None
    assert loaded.regime_drivers is None


def test_repository_json_structure(tmp_path: Path) -> None:
    repo = CaiRepository()
    vol = VolatilityRegime(
        asset_class=EQUITIES,
        current_state=VOL_ELEVATED,
        previous_state=VOL_MODERATE,
        regime_persistence=0.75,
        mean_reversion_half_life_days=12.5,
        tail_risk_index=0.40,
        confidence=0.80,
        valid_from="2026-07-27T12:00:00Z",
        valid_until="2026-09-17T00:00:00Z",
    )
    p = tmp_path / "vol_regime.json"
    repo.save_volatility_regime(vol, p)
    raw = json.loads(p.read_text())
    assert raw["asset_class"] == "equities"
    assert raw["current_state"] == "elevated"
    assert raw["previous_state"] == "moderate"
    assert raw["regime_persistence"] == 0.75
    assert raw["mean_reversion_half_life_days"] == 12.5
    assert raw["tail_risk_index"] == 0.40
    assert raw["confidence"] == 0.80
    assert raw["valid_from"] == "2026-07-27T12:00:00Z"
    assert raw["valid_until"] == "2026-09-17T00:00:00Z"
    assert raw["provenance"] is None
    assert raw["evidence_references"] == []
    assert raw["cross_references"] is None
    assert raw["regime_drivers"] is None


# ── Adapter ──────────────────────────────────────────────────────────────────


def test_adapter_volatility_to_evidence_low() -> None:
    adapter = CaiEvidenceAdapter()
    vol = VolatilityRegime(
        asset_class=EQUITIES,
        current_state=VOL_LOW,
        previous_state=VOL_MODERATE,
        regime_persistence=0.90,
        mean_reversion_half_life_days=25.0,
        tail_risk_index=0.10,
        confidence=0.80,
        valid_from="2026-07-27T12:00:00Z",
        valid_until="2026-09-17T00:00:00Z",
    )
    ev = adapter.volatility_regime_to_evidence(vol)
    assert isinstance(ev, Evidence)
    assert ev.event_type == "CAI_VOLATILITY"
    assert ev.bias == "bullish"
    assert ev.confidence == 0.80
    assert ev.evidence_id == "cai_vol_equities"
    assert ev.source_node_id == "cai_equities"
    assert ev.condition == {"asset_class": "equities", "current_state": "low"}


def test_adapter_volatility_to_evidence_moderate() -> None:
    adapter = CaiEvidenceAdapter()
    vol = VolatilityRegime(
        asset_class=FX,
        current_state=VOL_MODERATE,
        previous_state=VOL_LOW,
        regime_persistence=0.60,
        mean_reversion_half_life_days=15.0,
        tail_risk_index=0.25,
        confidence=0.75,
        valid_from="2026-07-27T12:00:00Z",
        valid_until="2026-09-17T00:00:00Z",
    )
    ev = adapter.volatility_regime_to_evidence(vol)
    assert ev.bias == "neutral"
    assert ev.evidence_id == "cai_vol_fx"


def test_adapter_volatility_to_evidence_elevated() -> None:
    adapter = CaiEvidenceAdapter()
    vol = VolatilityRegime(
        asset_class=EQUITIES,
        current_state=VOL_ELEVATED,
        previous_state=VOL_MODERATE,
        regime_persistence=0.75,
        mean_reversion_half_life_days=12.5,
        tail_risk_index=0.40,
        confidence=0.80,
        valid_from="2026-07-27T12:00:00Z",
        valid_until="2026-09-17T00:00:00Z",
    )
    ev = adapter.volatility_regime_to_evidence(vol)
    assert ev.bias == "bearish"


def test_adapter_volatility_to_evidence_high() -> None:
    adapter = CaiEvidenceAdapter()
    vol = VolatilityRegime(
        asset_class=CREDIT,
        current_state=VOL_HIGH,
        previous_state=VOL_ELEVATED,
        regime_persistence=0.85,
        mean_reversion_half_life_days=20.0,
        tail_risk_index=0.65,
        confidence=0.78,
        valid_from="2026-07-27T12:00:00Z",
        valid_until="2026-09-17T00:00:00Z",
    )
    ev = adapter.volatility_regime_to_evidence(vol)
    assert ev.bias == "bearish"


def test_adapter_volatility_to_evidence_extreme() -> None:
    adapter = CaiEvidenceAdapter()
    vol = VolatilityRegime(
        asset_class=EQUITIES,
        current_state=VOL_EXTREME,
        previous_state=VOL_HIGH,
        regime_persistence=0.50,
        mean_reversion_half_life_days=5.0,
        tail_risk_index=0.90,
        confidence=0.85,
        valid_from="2026-07-27T12:00:00Z",
        valid_until="2026-09-17T00:00:00Z",
    )
    ev = adapter.volatility_regime_to_evidence(vol)
    assert ev.bias == "bearish"


def test_adapter_preserves_provenance() -> None:
    adapter = CaiEvidenceAdapter()
    provenance = Provenance(
        created_at="2026-07-27T12:00:00Z",
        created_by="analyst_04",
        entity_version="1.0.0",
    )
    vol = VolatilityRegime(
        asset_class=EQUITIES,
        current_state=VOL_ELEVATED,
        previous_state=VOL_MODERATE,
        regime_persistence=0.75,
        mean_reversion_half_life_days=12.5,
        tail_risk_index=0.40,
        confidence=0.80,
        valid_from="2026-07-27T12:00:00Z",
        valid_until="2026-09-17T00:00:00Z",
        provenance=provenance,
    )
    ev = adapter.volatility_regime_to_evidence(vol)
    assert ev.provenance is not None
    assert ev.provenance.created_by == "analyst_04"
    assert ev.provenance.created_at == "2026-07-27T12:00:00Z"
    assert ev.provenance.entity_version == "1.0.0"


def test_adapter_preserves_confidence() -> None:
    adapter = CaiEvidenceAdapter()
    vol = VolatilityRegime(
        asset_class=EQUITIES,
        current_state=VOL_ELEVATED,
        previous_state=VOL_MODERATE,
        regime_persistence=0.75,
        mean_reversion_half_life_days=12.5,
        tail_risk_index=0.40,
        confidence=0.88,
        valid_from="2026-07-27T12:00:00Z",
        valid_until="2026-09-17T00:00:00Z",
    )
    ev = adapter.volatility_regime_to_evidence(vol)
    assert ev.confidence == 0.88


def test_adapter_preserves_evidence_references() -> None:
    adapter = CaiEvidenceAdapter()
    ev_refs = [
        {
            "source_category": "market_data",
            "source_descriptor": "CBOE VIX term structure analytics",
            "contribution": "primary measurement",
            "confidence_contribution": "high",
        }
    ]
    vol = VolatilityRegime(
        asset_class=EQUITIES,
        current_state=VOL_ELEVATED,
        previous_state=VOL_MODERATE,
        regime_persistence=0.75,
        mean_reversion_half_life_days=12.5,
        tail_risk_index=0.40,
        confidence=0.80,
        valid_from="2026-07-27T12:00:00Z",
        valid_until="2026-09-17T00:00:00Z",
        evidence_references=ev_refs,
    )
    ev = adapter.volatility_regime_to_evidence(vol)
    assert ev.metadata["evidence_references"] == ev_refs


def test_adapter_preserves_validity_information() -> None:
    adapter = CaiEvidenceAdapter()
    vol = VolatilityRegime(
        asset_class=EQUITIES,
        current_state=VOL_ELEVATED,
        previous_state=VOL_MODERATE,
        regime_persistence=0.75,
        mean_reversion_half_life_days=12.5,
        tail_risk_index=0.40,
        confidence=0.80,
        valid_from="2026-07-27T12:00:00Z",
        valid_until="2026-09-17T00:00:00Z",
        time_horizon="T3",
    )
    ev = adapter.volatility_regime_to_evidence(vol)
    assert ev.metadata["valid_from"] == "2026-07-27T12:00:00Z"
    assert ev.metadata["valid_until"] == "2026-09-17T00:00:00Z"
    assert ev.metadata["time_horizon"] == "T3"


def test_adapter_preserves_cross_references() -> None:
    adapter = CaiEvidenceAdapter()
    vol = VolatilityRegime(
        asset_class=EQUITIES,
        current_state=VOL_ELEVATED,
        previous_state=VOL_MODERATE,
        regime_persistence=0.75,
        mean_reversion_half_life_days=12.5,
        tail_risk_index=0.40,
        confidence=0.80,
        valid_from="2026-07-27T12:00:00Z",
        valid_until="2026-09-17T00:00:00Z",
        cross_references=["CAI:CrossAssetCorrelation:equities_fixed_income:2026-07-27"],
    )
    ev = adapter.volatility_regime_to_evidence(vol)
    assert ev.metadata["cross_references"] == ["CAI:CrossAssetCorrelation:equities_fixed_income:2026-07-27"]


def test_adapter_preserves_all_metadata() -> None:
    adapter = CaiEvidenceAdapter()
    vol = VolatilityRegime(
        asset_class=EQUITIES,
        current_state=VOL_ELEVATED,
        previous_state=VOL_MODERATE,
        regime_persistence=0.75,
        mean_reversion_half_life_days=12.5,
        tail_risk_index=0.40,
        confidence=0.80,
        valid_from="2026-07-27T12:00:00Z",
        valid_until="2026-09-17T00:00:00Z",
        regime_drivers=["fed_meeting", "cpi_release"],
    )
    ev = adapter.volatility_regime_to_evidence(vol)
    assert ev.metadata["object_type"] == "VolatilityRegime"
    assert ev.metadata["asset_class"] == "equities"
    assert ev.metadata["current_state"] == "elevated"
    assert ev.metadata["previous_state"] == "moderate"
    assert ev.metadata["regime_persistence"] == 0.75
    assert ev.metadata["mean_reversion_half_life_days"] == 12.5
    assert ev.metadata["tail_risk_index"] == 0.40
    assert ev.metadata["regime_drivers"] == ["fed_meeting", "cpi_release"]


# ── EvidenceAggregator integration ───────────────────────────────────────────


def test_volatility_evidence_merges_via_aggregator() -> None:
    adapter = CaiEvidenceAdapter()
    vol = VolatilityRegime(
        asset_class=EQUITIES,
        current_state=VOL_ELEVATED,
        previous_state=VOL_MODERATE,
        regime_persistence=0.75,
        mean_reversion_half_life_days=12.5,
        tail_risk_index=0.40,
        confidence=0.80,
        valid_from="2026-07-27T12:00:00Z",
        valid_until="2026-09-17T00:00:00Z",
    )
    ev = adapter.volatility_regime_to_evidence(vol)

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


def test_volatility_evidence_conflict_detection() -> None:
    adapter = CaiEvidenceAdapter()
    vol = VolatilityRegime(
        asset_class=EQUITIES,
        current_state=VOL_LOW,
        previous_state=VOL_MODERATE,
        regime_persistence=0.90,
        mean_reversion_half_life_days=25.0,
        tail_risk_index=0.10,
        confidence=0.80,
        valid_from="2026-07-27T12:00:00Z",
        valid_until="2026-09-17T00:00:00Z",
    )
    ev = adapter.volatility_regime_to_evidence(vol)

    conflicting = Evidence(
        evidence_id="cai_vol_equities",
        source_node_id="cai_equities",
        event_type="CAI_VOLATILITY",
        condition={"asset_class": "equities", "current_state": "extreme"},
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
