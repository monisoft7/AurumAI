import json
from pathlib import Path

import pytest

from knowledge.cbi.contracts import (
    PolicyBiasScore,
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
    DIRECTION_TIGHTENING,
    DIRECTION_EASING,
    DIRECTION_NEUTRAL,
    VALID_DIRECTIONS,
    HORIZON_T0,
    HORIZON_T3,
    VALID_TIME_HORIZONS,
)
from knowledge.cbi.repository import CbiRepository
from knowledge.cbi.adapter import CbiEvidenceAdapter
from knowledge.evidence.evidence import Evidence
from knowledge.evidence.collection import EvidenceCollection
from knowledge.orchestration.aggregator import EvidenceAggregator
from knowledge.integrity.provenance import Provenance
from knowledge._compat import FrozenDict


# ── Creation ─────────────────────────────────────────────────────────────────


def test_policy_bias_creation() -> None:
    pbs = PolicyBiasScore(
        central_bank=FED,
        score=2,
        direction=DIRECTION_TIGHTENING,
        confidence=0.8,
        valid_from="2026-07-26T12:00:00Z",
        valid_until="2026-09-17T00:00:00Z",
        time_horizon=HORIZON_T3,
    )
    assert pbs.central_bank == FED
    assert pbs.score == 2
    assert pbs.direction == DIRECTION_TIGHTENING
    assert pbs.confidence == 0.8
    assert pbs.valid_from == "2026-07-26T12:00:00Z"
    assert pbs.valid_until == "2026-09-17T00:00:00Z"
    assert pbs.time_horizon == HORIZON_T3


def test_policy_bias_defaults() -> None:
    pbs = PolicyBiasScore(
        central_bank=ECB,
        score=0,
        direction=DIRECTION_NEUTRAL,
        confidence=0.5,
        valid_from="2026-07-26T12:00:00Z",
        valid_until="2026-09-10T00:00:00Z",
    )
    assert pbs.central_bank == ECB
    assert pbs.score == 0
    assert pbs.direction == DIRECTION_NEUTRAL
    assert pbs.confidence == 0.5
    assert pbs.score_components == FrozenDict()
    assert pbs.provenance is None
    assert pbs.evidence_references == []
    assert pbs.cross_references is None
    assert pbs.methodology_version is None
    assert pbs.scenario_analysis is None
    assert pbs.time_horizon == HORIZON_T0


def test_policy_bias_all_directions() -> None:
    for direction in (DIRECTION_TIGHTENING, DIRECTION_EASING, DIRECTION_NEUTRAL):
        pbs = PolicyBiasScore(
            central_bank=FED,
            score=1 if direction == DIRECTION_TIGHTENING else -1,
            direction=direction,
            confidence=0.7,
            valid_from="2026-07-26T12:00:00Z",
            valid_until="2026-09-17T00:00:00Z",
        )
        assert pbs.direction == direction


def test_policy_bias_all_central_banks() -> None:
    for cb in (FED, ECB, BOJ, BOE, PBOC, SNB, RBA, RBNZ, BOC):
        pbs = PolicyBiasScore(
            central_bank=cb,
            score=0,
            direction=DIRECTION_NEUTRAL,
            confidence=0.5,
            valid_from="2026-07-26T12:00:00Z",
            valid_until="2026-09-17T00:00:00Z",
        )
        assert pbs.central_bank == cb
    assert VALID_CENTRAL_BANKS == {FED, ECB, BOJ, BOE, PBOC, SNB, RBA, RBNZ, BOC}


def test_policy_bias_frozen_dataclass() -> None:
    pbs = PolicyBiasScore(
        central_bank=FED,
        score=2,
        direction=DIRECTION_TIGHTENING,
        confidence=0.8,
        valid_from="2026-07-26T12:00:00Z",
        valid_until="2026-09-17T00:00:00Z",
    )
    with pytest.raises(AttributeError):
        pbs.score = 3
    with pytest.raises(AttributeError):
        pbs.direction = DIRECTION_EASING


def test_policy_bias_score_components_frozen() -> None:
    pbs = PolicyBiasScore(
        central_bank=FED,
        score=2,
        direction=DIRECTION_TIGHTENING,
        confidence=0.8,
        valid_from="2026-07-26T12:00:00Z",
        valid_until="2026-09-17T00:00:00Z",
        score_components={"statement_language_weight": 0.5, "speech_weight": 0.3},
    )
    assert isinstance(pbs.score_components, FrozenDict)
    assert pbs.score_components["statement_language_weight"] == 0.5
    with pytest.raises(TypeError):
        pbs.score_components["speech_weight"] = 0.4


def test_policy_bias_all_time_horizons() -> None:
    for horizon in VALID_TIME_HORIZONS:
        pbs = PolicyBiasScore(
            central_bank=FED,
            score=0,
            direction=DIRECTION_NEUTRAL,
            confidence=0.5,
            valid_from="2026-07-26T12:00:00Z",
            valid_until="2026-09-17T00:00:00Z",
            time_horizon=horizon,
        )
        assert pbs.time_horizon == horizon


def test_policy_bias_score_range() -> None:
    for score in (-5, -3, 0, 3, 5):
        pbs = PolicyBiasScore(
            central_bank=FED,
            score=score,
            direction=DIRECTION_NEUTRAL,
            confidence=0.5,
            valid_from="2026-07-26T12:00:00Z",
            valid_until="2026-09-17T00:00:00Z",
        )
        assert pbs.score == score


def test_policy_bias_with_full_optional_fields() -> None:
    provenance = Provenance(
        created_at="2026-07-26T12:00:00Z",
        created_by="analyst_01",
        entity_version="1.0.0",
    )
    ev_refs = [
        {
            "source_category": "central_bank_statement",
            "source_descriptor": "FOMC Statement July 2026",
            "contribution": "primary directional signal",
            "confidence_contribution": "high",
        }
    ]
    pbs = PolicyBiasScore(
        central_bank=FED,
        score=2,
        direction=DIRECTION_TIGHTENING,
        confidence=0.8,
        valid_from="2026-07-26T12:00:00Z",
        valid_until="2026-09-17T00:00:00Z",
        time_horizon=HORIZON_T3,
        provenance=provenance,
        evidence_references=ev_refs,
        cross_references=["CAI:CrossAssetRegime:2026-07-26"],
        methodology_version="1.0.0",
        scenario_analysis=[
            {"label": "hawkish_outcome", "probability": 0.3, "deviation": "+50bps"}
        ],
        score_components={"statement_language_weight": 0.5, "speech_weight": 0.3},
    )
    assert pbs.provenance is not None
    assert pbs.provenance.created_by == "analyst_01"
    assert len(pbs.evidence_references) == 1
    assert pbs.cross_references == ["CAI:CrossAssetRegime:2026-07-26"]
    assert pbs.methodology_version == "1.0.0"
    assert len(pbs.scenario_analysis) == 1
    assert pbs.score_components["statement_language_weight"] == 0.5


def test_policy_bias_inherits_base_contract() -> None:
    pbs = PolicyBiasScore(
        central_bank=FED,
        score=2,
        direction=DIRECTION_TIGHTENING,
        confidence=0.8,
        valid_from="2026-07-26T12:00:00Z",
        valid_until="2026-09-17T00:00:00Z",
    )
    assert isinstance(pbs, CbiBaseContract)


# ── Repository ───────────────────────────────────────────────────────────────


def test_repository_save_and_load_policy_bias(tmp_path: Path) -> None:
    repo = CbiRepository()
    pbs = PolicyBiasScore(
        central_bank=FED,
        score=2,
        direction=DIRECTION_TIGHTENING,
        confidence=0.8,
        valid_from="2026-07-26T12:00:00Z",
        valid_until="2026-09-17T00:00:00Z",
        time_horizon=HORIZON_T3,
        score_components={"statement_language_weight": 0.5},
    )
    p = tmp_path / "policy_bias.json"
    repo.save_policy_bias(pbs, p)
    loaded = repo.load_policy_bias(p)
    assert loaded.central_bank == FED
    assert loaded.score == 2
    assert loaded.direction == DIRECTION_TIGHTENING
    assert loaded.confidence == 0.8


def test_repository_roundtrip_preserves_all_fields(tmp_path: Path) -> None:
    repo = CbiRepository()
    provenance = Provenance(
        created_at="2026-07-26T12:00:00Z",
        created_by="analyst_01",
        entity_version="1.0.0",
    )
    original = PolicyBiasScore(
        central_bank=ECB,
        score=-3,
        direction=DIRECTION_EASING,
        confidence=0.75,
        valid_from="2026-07-26T12:00:00Z",
        valid_until="2026-09-10T00:00:00Z",
        time_horizon=HORIZON_T3,
        provenance=provenance,
        evidence_references=[
            {"source_category": "speech", "source_descriptor": "ECB Press Conference"}
        ],
        cross_references=["CFI:FlowReport:2026-07-26"],
        methodology_version="1.2.0",
        scenario_analysis=[{"label": "dovish_surprise", "probability": 0.2}],
        score_components={"statement_language_weight": 0.4, "speech_weight": 0.6},
    )
    p = tmp_path / "ecb_policy_bias.json"
    repo.save_policy_bias(original, p)
    loaded = repo.load_policy_bias(p)
    assert loaded.central_bank == original.central_bank
    assert loaded.score == original.score
    assert loaded.direction == original.direction
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
    assert loaded.score_components == original.score_components


def test_repository_roundtrip_with_none_optionals(tmp_path: Path) -> None:
    repo = CbiRepository()
    original = PolicyBiasScore(
        central_bank=BOJ,
        score=1,
        direction=DIRECTION_TIGHTENING,
        confidence=0.6,
        valid_from="2026-07-26T12:00:00Z",
        valid_until="2026-09-20T00:00:00Z",
    )
    p = tmp_path / "boj_policy_bias.json"
    repo.save_policy_bias(original, p)
    loaded = repo.load_policy_bias(p)
    assert loaded.provenance is None
    assert loaded.evidence_references == []
    assert loaded.cross_references is None
    assert loaded.methodology_version is None
    assert loaded.scenario_analysis is None
    assert loaded.score_components == FrozenDict()


def test_repository_json_structure(tmp_path: Path) -> None:
    repo = CbiRepository()
    pbs = PolicyBiasScore(
        central_bank=FED,
        score=2,
        direction=DIRECTION_TIGHTENING,
        confidence=0.8,
        valid_from="2026-07-26T12:00:00Z",
        valid_until="2026-09-17T00:00:00Z",
        time_horizon=HORIZON_T3,
    )
    p = tmp_path / "policy_bias.json"
    repo.save_policy_bias(pbs, p)
    raw = json.loads(p.read_text())
    assert raw["central_bank"] == "FED"
    assert raw["score"] == 2
    assert raw["direction"] == "tightening"
    assert raw["confidence"] == 0.8
    assert raw["valid_from"] == "2026-07-26T12:00:00Z"
    assert raw["valid_until"] == "2026-09-17T00:00:00Z"
    assert raw["time_horizon"] == "T3"
    assert raw["provenance"] is None
    assert raw["evidence_references"] == []
    assert raw["cross_references"] is None


# ── Adapter ──────────────────────────────────────────────────────────────────


def test_adapter_policy_bias_to_evidence_tightening() -> None:
    adapter = CbiEvidenceAdapter()
    pbs = PolicyBiasScore(
        central_bank=FED,
        score=2,
        direction=DIRECTION_TIGHTENING,
        confidence=0.8,
        valid_from="2026-07-26T12:00:00Z",
        valid_until="2026-09-17T00:00:00Z",
    )
    ev = adapter.policy_bias_to_evidence(pbs)
    assert isinstance(ev, Evidence)
    assert ev.event_type == "CBI_POLICY"
    assert ev.bias == "bearish"
    assert ev.confidence == 0.8
    assert ev.evidence_id == "cbi_policy_FED"
    assert ev.source_node_id == "cbi_FED"
    assert ev.condition == {"central_bank": "FED", "direction": "tightening"}


def test_adapter_policy_bias_to_evidence_easing() -> None:
    adapter = CbiEvidenceAdapter()
    pbs = PolicyBiasScore(
        central_bank=ECB,
        score=-3,
        direction=DIRECTION_EASING,
        confidence=0.75,
        valid_from="2026-07-26T12:00:00Z",
        valid_until="2026-09-10T00:00:00Z",
    )
    ev = adapter.policy_bias_to_evidence(pbs)
    assert ev.bias == "bullish"
    assert ev.evidence_id == "cbi_policy_ECB"


def test_adapter_policy_bias_to_evidence_neutral() -> None:
    adapter = CbiEvidenceAdapter()
    pbs = PolicyBiasScore(
        central_bank=BOJ,
        score=0,
        direction=DIRECTION_NEUTRAL,
        confidence=0.5,
        valid_from="2026-07-26T12:00:00Z",
        valid_until="2026-09-20T00:00:00Z",
    )
    ev = adapter.policy_bias_to_evidence(pbs)
    assert ev.bias == "neutral"
    assert ev.evidence_id == "cbi_policy_BOJ"


def test_adapter_preserves_provenance() -> None:
    adapter = CbiEvidenceAdapter()
    provenance = Provenance(
        created_at="2026-07-26T12:00:00Z",
        created_by="analyst_01",
        entity_version="1.0.0",
    )
    pbs = PolicyBiasScore(
        central_bank=FED,
        score=2,
        direction=DIRECTION_TIGHTENING,
        confidence=0.8,
        valid_from="2026-07-26T12:00:00Z",
        valid_until="2026-09-17T00:00:00Z",
        provenance=provenance,
    )
    ev = adapter.policy_bias_to_evidence(pbs)
    assert ev.provenance is not None
    assert ev.provenance.created_by == "analyst_01"
    assert ev.provenance.created_at == "2026-07-26T12:00:00Z"
    assert ev.provenance.entity_version == "1.0.0"


def test_adapter_preserves_confidence() -> None:
    adapter = CbiEvidenceAdapter()
    pbs = PolicyBiasScore(
        central_bank=FED,
        score=2,
        direction=DIRECTION_TIGHTENING,
        confidence=0.85,
        valid_from="2026-07-26T12:00:00Z",
        valid_until="2026-09-17T00:00:00Z",
    )
    ev = adapter.policy_bias_to_evidence(pbs)
    assert ev.confidence == 0.85


def test_adapter_preserves_evidence_references() -> None:
    adapter = CbiEvidenceAdapter()
    ev_refs = [
        {
            "source_category": "central_bank_statement",
            "source_descriptor": "FOMC Statement July 2026",
            "contribution": "primary directional signal",
            "confidence_contribution": "high",
        }
    ]
    pbs = PolicyBiasScore(
        central_bank=FED,
        score=2,
        direction=DIRECTION_TIGHTENING,
        confidence=0.8,
        valid_from="2026-07-26T12:00:00Z",
        valid_until="2026-09-17T00:00:00Z",
        evidence_references=ev_refs,
    )
    ev = adapter.policy_bias_to_evidence(pbs)
    assert ev.metadata["evidence_references"] == ev_refs


def test_adapter_preserves_validity_information() -> None:
    adapter = CbiEvidenceAdapter()
    pbs = PolicyBiasScore(
        central_bank=FED,
        score=2,
        direction=DIRECTION_TIGHTENING,
        confidence=0.8,
        valid_from="2026-07-26T12:00:00Z",
        valid_until="2026-09-17T00:00:00Z",
        time_horizon=HORIZON_T3,
    )
    ev = adapter.policy_bias_to_evidence(pbs)
    assert ev.metadata["valid_from"] == "2026-07-26T12:00:00Z"
    assert ev.metadata["valid_until"] == "2026-09-17T00:00:00Z"
    assert ev.metadata["time_horizon"] == HORIZON_T3


def test_adapter_preserves_cross_references() -> None:
    adapter = CbiEvidenceAdapter()
    pbs = PolicyBiasScore(
        central_bank=FED,
        score=2,
        direction=DIRECTION_TIGHTENING,
        confidence=0.8,
        valid_from="2026-07-26T12:00:00Z",
        valid_until="2026-09-17T00:00:00Z",
        cross_references=["CAI:CrossAssetRegime:2026-07-26"],
    )
    ev = adapter.policy_bias_to_evidence(pbs)
    assert ev.metadata["cross_references"] == ["CAI:CrossAssetRegime:2026-07-26"]


def test_adapter_preserves_score_components() -> None:
    adapter = CbiEvidenceAdapter()
    pbs = PolicyBiasScore(
        central_bank=FED,
        score=2,
        direction=DIRECTION_TIGHTENING,
        confidence=0.8,
        valid_from="2026-07-26T12:00:00Z",
        valid_until="2026-09-17T00:00:00Z",
        score_components={"statement_language_weight": 0.5, "speech_weight": 0.3},
    )
    ev = adapter.policy_bias_to_evidence(pbs)
    assert ev.metadata["score_components"] == {"statement_language_weight": 0.5, "speech_weight": 0.3}
    assert ev.metadata["object_type"] == "PolicyBiasScore"
    assert ev.metadata["score"] == 2


# ── EvidenceAggregator integration ───────────────────────────────────────────


def test_policy_bias_evidence_merges_via_aggregator() -> None:
    adapter = CbiEvidenceAdapter()
    pbs = PolicyBiasScore(
        central_bank=FED,
        score=2,
        direction=DIRECTION_TIGHTENING,
        confidence=0.8,
        valid_from="2026-07-26T12:00:00Z",
        valid_until="2026-09-17T00:00:00Z",
    )
    ev = adapter.policy_bias_to_evidence(pbs)

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


def test_policy_bias_evidence_conflict_detection() -> None:
    adapter = CbiEvidenceAdapter()
    pbs = PolicyBiasScore(
        central_bank=FED,
        score=2,
        direction=DIRECTION_TIGHTENING,
        confidence=0.8,
        valid_from="2026-07-26T12:00:00Z",
        valid_until="2026-09-17T00:00:00Z",
    )
    ev = adapter.policy_bias_to_evidence(pbs)

    conflicting = Evidence(
        evidence_id="cbi_policy_FED",
        source_node_id="cbi_FED",
        event_type="CBI_POLICY",
        condition={"central_bank": "FED", "direction": "tightening"},
        horizon_days=0,
        sample_count=1,
        average_return_pct=0.0,
        confidence=0.8,
        bias="bullish",
        explanation="Conflicting bias for same evidence_id.",
    )

    agg = EvidenceAggregator()
    result = agg.merge({
        "cbi_v1": EvidenceCollection([ev]),
        "cbi_v2": EvidenceCollection([conflicting]),
    })
    assert len(result.conflicts) >= 1
