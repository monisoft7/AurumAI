import json
from pathlib import Path

import pytest

from knowledge.cbi.contracts import (
    RatePathProjection,
    CbiBaseContract,
    FED,
    ECB,
    BOJ,
    BOE,
    PBOC,
    SNB,
    RBA,
    RBNZ,
    BOC,
    VALID_CENTRAL_BANKS,
    HORIZON_T0,
    HORIZON_T3,
)
from knowledge.cbi.repository import CbiRepository
from knowledge.cbi.adapter import CbiEvidenceAdapter
from knowledge.evidence.evidence import Evidence
from knowledge.evidence.collection import EvidenceCollection
from knowledge.orchestration.aggregator import EvidenceAggregator
from knowledge.integrity.provenance import Provenance


# ── Creation ─────────────────────────────────────────────────────────────────


def test_rate_path_creation() -> None:
    rpp = RatePathProjection(
        central_bank=FED,
        base_path=[
            {"meeting_date": "2026-09-17", "rate_bps": 550},
            {"meeting_date": "2026-11-05", "rate_bps": 525},
            {"meeting_date": "2026-12-16", "rate_bps": 500},
        ],
        confidence_interval=25,
        current_rate=575,
        confidence=0.75,
        valid_from="2026-07-26T12:00:00Z",
        valid_until="2026-09-17T00:00:00Z",
        time_horizon=HORIZON_T3,
    )
    assert rpp.central_bank == FED
    assert len(rpp.base_path) == 3
    assert rpp.base_path[0]["meeting_date"] == "2026-09-17"
    assert rpp.base_path[0]["rate_bps"] == 550
    assert rpp.confidence_interval == 25
    assert rpp.current_rate == 575
    assert rpp.confidence == 0.75
    assert rpp.valid_from == "2026-07-26T12:00:00Z"
    assert rpp.valid_until == "2026-09-17T00:00:00Z"
    assert rpp.time_horizon == HORIZON_T3


def test_rate_path_defaults() -> None:
    rpp = RatePathProjection(
        central_bank=ECB,
        confidence=0.65,
        valid_from="2026-07-26T12:00:00Z",
        valid_until="2026-09-10T00:00:00Z",
    )
    assert rpp.central_bank == ECB
    assert rpp.base_path == []
    assert rpp.confidence_interval == 0
    assert rpp.current_rate == 0
    assert rpp.provenance is None
    assert rpp.evidence_references == []
    assert rpp.cross_references is None
    assert rpp.time_horizon == HORIZON_T0


def test_rate_path_all_central_banks() -> None:
    for cb in (FED, ECB, BOJ, BOE, PBOC, SNB, RBA, RBNZ, BOC):
        rpp = RatePathProjection(
            central_bank=cb,
            base_path=[],
            confidence_interval=25,
            current_rate=300,
            confidence=0.5,
            valid_from="2026-07-26T12:00:00Z",
            valid_until="2026-09-17T00:00:00Z",
        )
        assert rpp.central_bank == cb


def test_rate_path_frozen() -> None:
    rpp = RatePathProjection(
        central_bank=FED,
        base_path=[{"meeting_date": "2026-09-17", "rate_bps": 550}],
        confidence_interval=25,
        current_rate=575,
        confidence=0.75,
        valid_from="2026-07-26T12:00:00Z",
        valid_until="2026-09-17T00:00:00Z",
    )
    with pytest.raises(AttributeError):
        rpp.current_rate = 550
    with pytest.raises(AttributeError):
        rpp.confidence_interval = 50


def test_rate_path_empty_base_path() -> None:
    rpp = RatePathProjection(
        central_bank=BOJ,
        base_path=[],
        confidence_interval=10,
        current_rate=-10,
        confidence=0.5,
        valid_from="2026-07-26T12:00:00Z",
        valid_until="2026-09-20T00:00:00Z",
    )
    assert rpp.base_path == []


def test_rate_path_zero_values() -> None:
    rpp = RatePathProjection(
        central_bank=SNB,
        base_path=[{"meeting_date": "2026-09-17", "rate_bps": 0}],
        confidence_interval=0,
        current_rate=0,
        confidence=0.5,
        valid_from="2026-07-26T12:00:00Z",
        valid_until="2026-09-17T00:00:00Z",
    )
    assert rpp.confidence_interval == 0
    assert rpp.current_rate == 0


def test_rate_path_single_meeting_path() -> None:
    rpp = RatePathProjection(
        central_bank=RBA,
        base_path=[{"meeting_date": "2026-08-04", "rate_bps": 425}],
        confidence_interval=15,
        current_rate=435,
        confidence=0.7,
        valid_from="2026-07-26T12:00:00Z",
        valid_until="2026-08-04T00:00:00Z",
    )
    assert len(rpp.base_path) == 1
    assert rpp.base_path[0]["rate_bps"] == 425


def test_rate_path_eight_meeting_path() -> None:
    rpp = RatePathProjection(
        central_bank=FED,
        base_path=[
            {"meeting_date": f"2026-{m:02d}-15", "rate_bps": 550 - i * 25}
            for i, m in enumerate([9, 11, 12, 2, 3, 5, 6, 7])
        ],
        confidence_interval=25,
        current_rate=575,
        confidence=0.75,
        valid_from="2026-07-26T12:00:00Z",
        valid_until="2026-09-17T00:00:00Z",
    )
    assert len(rpp.base_path) == 8
    assert rpp.base_path[0]["rate_bps"] == 550
    assert rpp.base_path[7]["rate_bps"] == 375


def test_rate_path_with_full_optional_fields() -> None:
    provenance = Provenance(
        created_at="2026-07-26T12:00:00Z",
        created_by="analyst_03",
        entity_version="1.5.0",
    )
    ev_refs = [
        {
            "source_category": "central_bank_projection",
            "source_descriptor": "FOMC SEP June 2026",
            "contribution": "primary rate path source",
            "confidence_contribution": "high",
        }
    ]
    rpp = RatePathProjection(
        central_bank=FED,
        base_path=[{"meeting_date": "2026-09-17", "rate_bps": 550}],
        confidence_interval=25,
        current_rate=575,
        confidence=0.75,
        valid_from="2026-07-26T12:00:00Z",
        valid_until="2026-09-17T00:00:00Z",
        time_horizon=HORIZON_T3,
        provenance=provenance,
        evidence_references=ev_refs,
        cross_references=["CBI:ForwardGuidanceRecord:FED:2026-07-26"],
        methodology_version="1.5.0",
        scenario_analysis=[
            {"label": "hawkish_path", "probability": 0.3, "deviation": "+50bps"}
        ],
    )
    assert rpp.provenance is not None
    assert rpp.provenance.created_by == "analyst_03"
    assert len(rpp.evidence_references) == 1
    assert rpp.cross_references == ["CBI:ForwardGuidanceRecord:FED:2026-07-26"]
    assert rpp.methodology_version == "1.5.0"
    assert len(rpp.scenario_analysis) == 1


def test_rate_path_inherits_base_contract() -> None:
    rpp = RatePathProjection(
        central_bank=FED,
        base_path=[],
        confidence_interval=0,
        current_rate=0,
        confidence=0.5,
        valid_from="2026-07-26T12:00:00Z",
        valid_until="2026-09-17T00:00:00Z",
    )
    assert isinstance(rpp, CbiBaseContract)


# ── Repository ───────────────────────────────────────────────────────────────


def test_repository_save_and_load_rate_path(tmp_path: Path) -> None:
    repo = CbiRepository()
    rpp = RatePathProjection(
        central_bank=FED,
        base_path=[{"meeting_date": "2026-09-17", "rate_bps": 550}],
        confidence_interval=25,
        current_rate=575,
        confidence=0.75,
        valid_from="2026-07-26T12:00:00Z",
        valid_until="2026-09-17T00:00:00Z",
        time_horizon=HORIZON_T3,
    )
    p = tmp_path / "rate_path.json"
    repo.save_rate_path(rpp, p)
    loaded = repo.load_rate_path(p)
    assert loaded.central_bank == FED
    assert loaded.base_path == [{"meeting_date": "2026-09-17", "rate_bps": 550}]
    assert loaded.confidence_interval == 25
    assert loaded.current_rate == 575
    assert loaded.confidence == 0.75


def test_repository_roundtrip_preserves_all_fields(tmp_path: Path) -> None:
    repo = CbiRepository()
    provenance = Provenance(
        created_at="2026-07-26T12:00:00Z",
        created_by="analyst_03",
        entity_version="1.5.0",
    )
    original = RatePathProjection(
        central_bank=ECB,
        base_path=[
            {"meeting_date": "2026-09-10", "rate_bps": 350},
            {"meeting_date": "2026-10-22", "rate_bps": 325},
        ],
        confidence_interval=20,
        current_rate=375,
        confidence=0.68,
        valid_from="2026-07-26T12:00:00Z",
        valid_until="2026-09-10T00:00:00Z",
        time_horizon=HORIZON_T3,
        provenance=provenance,
        evidence_references=[
            {"source_category": "central_bank_projection",
             "source_descriptor": "ECB Staff Projections July 2026"}
        ],
        cross_references=["CBI:ForwardGuidanceRecord:ECB:2026-07-26"],
        methodology_version="1.5.0",
        scenario_analysis=[{"label": "dovish_path", "probability": 0.25}],
    )
    p = tmp_path / "ecb_rate_path.json"
    repo.save_rate_path(original, p)
    loaded = repo.load_rate_path(p)
    assert loaded.central_bank == original.central_bank
    assert loaded.base_path == original.base_path
    assert loaded.confidence_interval == original.confidence_interval
    assert loaded.current_rate == original.current_rate
    assert loaded.confidence == original.confidence
    assert loaded.valid_from == original.valid_from
    assert loaded.valid_until == original.valid_until
    assert loaded.time_horizon == original.time_horizon
    assert loaded.provenance is not None
    assert loaded.provenance.created_by == "analyst_03"
    assert loaded.evidence_references == original.evidence_references
    assert loaded.cross_references == original.cross_references
    assert loaded.methodology_version == original.methodology_version
    assert loaded.scenario_analysis == original.scenario_analysis


def test_repository_roundtrip_with_none_optionals(tmp_path: Path) -> None:
    repo = CbiRepository()
    original = RatePathProjection(
        central_bank=BOJ,
        base_path=[{"meeting_date": "2026-09-20", "rate_bps": -10}],
        confidence_interval=10,
        current_rate=-10,
        confidence=0.5,
        valid_from="2026-07-26T12:00:00Z",
        valid_until="2026-09-20T00:00:00Z",
    )
    p = tmp_path / "boj_rate_path.json"
    repo.save_rate_path(original, p)
    loaded = repo.load_rate_path(p)
    assert loaded.provenance is None
    assert loaded.evidence_references == []
    assert loaded.cross_references is None
    assert loaded.methodology_version is None
    assert loaded.scenario_analysis is None


def test_repository_json_structure(tmp_path: Path) -> None:
    repo = CbiRepository()
    rpp = RatePathProjection(
        central_bank=FED,
        base_path=[{"meeting_date": "2026-09-17", "rate_bps": 550}],
        confidence_interval=25,
        current_rate=575,
        confidence=0.75,
        valid_from="2026-07-26T12:00:00Z",
        valid_until="2026-09-17T00:00:00Z",
        time_horizon=HORIZON_T3,
    )
    p = tmp_path / "rate_path.json"
    repo.save_rate_path(rpp, p)
    raw = json.loads(p.read_text())
    assert raw["central_bank"] == "FED"
    assert raw["base_path"] == [{"meeting_date": "2026-09-17", "rate_bps": 550}]
    assert raw["confidence_interval"] == 25
    assert raw["current_rate"] == 575
    assert raw["confidence"] == 0.75
    assert raw["valid_from"] == "2026-07-26T12:00:00Z"
    assert raw["valid_until"] == "2026-09-17T00:00:00Z"
    assert raw["time_horizon"] == "T3"
    assert raw["provenance"] is None


# ── Adapter ──────────────────────────────────────────────────────────────────


def test_adapter_rate_path_to_evidence_basic() -> None:
    adapter = CbiEvidenceAdapter()
    rpp = RatePathProjection(
        central_bank=FED,
        base_path=[{"meeting_date": "2026-09-17", "rate_bps": 550}],
        confidence_interval=25,
        current_rate=575,
        confidence=0.75,
        valid_from="2026-07-26T12:00:00Z",
        valid_until="2026-09-17T00:00:00Z",
    )
    ev = adapter.rate_path_to_evidence(rpp)
    assert isinstance(ev, Evidence)
    assert ev.event_type == "CBI_RATE_PATH"
    assert ev.bias == "neutral"
    assert ev.confidence == 0.75
    assert ev.evidence_id == "cbi_rate_FED"
    assert ev.source_node_id == "cbi_FED"
    assert ev.condition == {"central_bank": "FED"}


def test_adapter_rate_path_different_central_banks() -> None:
    adapter = CbiEvidenceAdapter()
    for cb in (ECB, BOJ, BOE):
        rpp = RatePathProjection(
            central_bank=cb,
            base_path=[{"meeting_date": "2026-09-17", "rate_bps": 300}],
            confidence_interval=20,
            current_rate=325,
            confidence=0.6,
            valid_from="2026-07-26T12:00:00Z",
            valid_until="2026-09-17T00:00:00Z",
        )
        ev = adapter.rate_path_to_evidence(rpp)
        assert ev.evidence_id == f"cbi_rate_{cb}"
        assert ev.condition["central_bank"] == cb


def test_adapter_preserves_provenance() -> None:
    adapter = CbiEvidenceAdapter()
    provenance = Provenance(
        created_at="2026-07-26T12:00:00Z",
        created_by="analyst_03",
        entity_version="1.5.0",
    )
    rpp = RatePathProjection(
        central_bank=FED,
        base_path=[{"meeting_date": "2026-09-17", "rate_bps": 550}],
        confidence_interval=25,
        current_rate=575,
        confidence=0.75,
        valid_from="2026-07-26T12:00:00Z",
        valid_until="2026-09-17T00:00:00Z",
        provenance=provenance,
    )
    ev = adapter.rate_path_to_evidence(rpp)
    assert ev.provenance is not None
    assert ev.provenance.created_by == "analyst_03"
    assert ev.provenance.created_at == "2026-07-26T12:00:00Z"
    assert ev.provenance.entity_version == "1.5.0"


def test_adapter_preserves_confidence() -> None:
    adapter = CbiEvidenceAdapter()
    for conf in (0.5, 0.65, 0.8, 0.95):
        rpp = RatePathProjection(
            central_bank=FED,
            base_path=[],
            confidence_interval=25,
            current_rate=575,
            confidence=conf,
            valid_from="2026-07-26T12:00:00Z",
            valid_until="2026-09-17T00:00:00Z",
        )
        ev = adapter.rate_path_to_evidence(rpp)
        assert ev.confidence == conf


def test_adapter_preserves_validity() -> None:
    adapter = CbiEvidenceAdapter()
    rpp = RatePathProjection(
        central_bank=FED,
        base_path=[],
        confidence_interval=25,
        current_rate=575,
        confidence=0.75,
        valid_from="2026-07-26T12:00:00Z",
        valid_until="2026-09-17T00:00:00Z",
        time_horizon=HORIZON_T3,
    )
    ev = adapter.rate_path_to_evidence(rpp)
    assert ev.metadata["valid_from"] == "2026-07-26T12:00:00Z"
    assert ev.metadata["valid_until"] == "2026-09-17T00:00:00Z"
    assert ev.metadata["time_horizon"] == HORIZON_T3


def test_adapter_preserves_evidence_references() -> None:
    adapter = CbiEvidenceAdapter()
    ev_refs = [
        {
            "source_category": "central_bank_projection",
            "source_descriptor": "FOMC SEP June 2026",
            "contribution": "primary rate path source",
            "confidence_contribution": "high",
        }
    ]
    rpp = RatePathProjection(
        central_bank=FED,
        base_path=[],
        confidence_interval=25,
        current_rate=575,
        confidence=0.75,
        valid_from="2026-07-26T12:00:00Z",
        valid_until="2026-09-17T00:00:00Z",
        evidence_references=ev_refs,
    )
    ev = adapter.rate_path_to_evidence(rpp)
    assert ev.metadata["evidence_references"] == ev_refs


def test_adapter_preserves_base_path() -> None:
    adapter = CbiEvidenceAdapter()
    base_path = [
        {"meeting_date": "2026-09-17", "rate_bps": 550},
        {"meeting_date": "2026-11-05", "rate_bps": 525},
        {"meeting_date": "2026-12-16", "rate_bps": 500},
    ]
    rpp = RatePathProjection(
        central_bank=FED,
        base_path=base_path,
        confidence_interval=25,
        current_rate=575,
        confidence=0.75,
        valid_from="2026-07-26T12:00:00Z",
        valid_until="2026-09-17T00:00:00Z",
    )
    ev = adapter.rate_path_to_evidence(rpp)
    assert ev.metadata["base_path"] == base_path
    assert ev.metadata["object_type"] == "RatePathProjection"


def test_adapter_preserves_rate_fields_in_metadata() -> None:
    adapter = CbiEvidenceAdapter()
    rpp = RatePathProjection(
        central_bank=ECB,
        base_path=[{"meeting_date": "2026-09-10", "rate_bps": 350}],
        confidence_interval=20,
        current_rate=375,
        confidence=0.65,
        valid_from="2026-07-26T12:00:00Z",
        valid_until="2026-09-10T00:00:00Z",
    )
    ev = adapter.rate_path_to_evidence(rpp)
    assert ev.metadata["confidence_interval"] == 20
    assert ev.metadata["current_rate"] == 375


def test_adapter_explanation_includes_path_summary() -> None:
    adapter = CbiEvidenceAdapter()
    rpp = RatePathProjection(
        central_bank=FED,
        base_path=[
            {"meeting_date": "2026-09-17", "rate_bps": 550},
            {"meeting_date": "2026-11-05", "rate_bps": 525},
        ],
        confidence_interval=25,
        current_rate=575,
        confidence=0.75,
        valid_from="2026-07-26T12:00:00Z",
        valid_until="2026-09-17T00:00:00Z",
    )
    ev = adapter.rate_path_to_evidence(rpp)
    assert "RatePathProjection for FED" in ev.explanation
    assert "current 575bps" in ev.explanation
    assert "2 meeting path" in ev.explanation
    assert "CI 25bps" in ev.explanation


def test_adapter_preserves_cross_references() -> None:
    adapter = CbiEvidenceAdapter()
    rpp = RatePathProjection(
        central_bank=FED,
        base_path=[],
        confidence_interval=25,
        current_rate=575,
        confidence=0.75,
        valid_from="2026-07-26T12:00:00Z",
        valid_until="2026-09-17T00:00:00Z",
        cross_references=["CBI:ForwardGuidanceRecord:FED:2026-07-26"],
    )
    ev = adapter.rate_path_to_evidence(rpp)
    assert ev.metadata["cross_references"] == ["CBI:ForwardGuidanceRecord:FED:2026-07-26"]


# ── EvidenceAggregator integration ───────────────────────────────────────────


def test_rate_path_evidence_merges_via_aggregator() -> None:
    adapter = CbiEvidenceAdapter()
    rpp = RatePathProjection(
        central_bank=FED,
        base_path=[{"meeting_date": "2026-09-17", "rate_bps": 550}],
        confidence_interval=25,
        current_rate=575,
        confidence=0.75,
        valid_from="2026-07-26T12:00:00Z",
        valid_until="2026-09-17T00:00:00Z",
    )
    ev = adapter.rate_path_to_evidence(rpp)

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
        "cbi": EvidenceCollection([ev]),
    })
    assert len(result.collection) == 2
    assert result.layer_counts["cbi"] == 1
    assert result.layer_counts["event"] == 1


def test_rate_path_evidence_conflict_free_with_economic() -> None:
    adapter = CbiEvidenceAdapter()
    rpp = RatePathProjection(
        central_bank=FED,
        base_path=[],
        confidence_interval=25,
        current_rate=575,
        confidence=0.75,
        valid_from="2026-07-26T12:00:00Z",
        valid_until="2026-09-17T00:00:00Z",
    )
    ev = adapter.rate_path_to_evidence(rpp)

    economic_evidence = EvidenceCollection([
        Evidence(
            evidence_id="econ_001",
            source_node_id="econ_source",
            event_type="ECONOMIC",
            condition={"regime": "growth"},
            horizon_days=0,
            sample_count=1,
            average_return_pct=0.0,
            confidence=0.7,
            bias="neutral",
            explanation="Economic regime growth active.",
        ),
    ])

    agg = EvidenceAggregator()
    result = agg.merge({
        "economic": economic_evidence,
        "cbi": EvidenceCollection([ev]),
    })
    assert len(result.conflicts) == 0


def test_rate_path_evidence_same_id_conflict() -> None:
    adapter = CbiEvidenceAdapter()
    rpp = RatePathProjection(
        central_bank=FED,
        base_path=[],
        confidence_interval=25,
        current_rate=575,
        confidence=0.75,
        valid_from="2026-07-26T12:00:00Z",
        valid_until="2026-09-17T00:00:00Z",
    )
    ev = adapter.rate_path_to_evidence(rpp)

    conflicting = Evidence(
        evidence_id="cbi_rate_FED",
        source_node_id="cbi_FED",
        event_type="CBI_RATE_PATH",
        condition={"central_bank": "FED"},
        horizon_days=0,
        sample_count=1,
        average_return_pct=0.0,
        confidence=0.75,
        bias="bullish",
        explanation="Conflicting bias.",
    )

    agg = EvidenceAggregator()
    result = agg.merge({
        "cbi_v1": EvidenceCollection([ev]),
        "cbi_v2": EvidenceCollection([conflicting]),
    })
    assert len(result.conflicts) >= 1
