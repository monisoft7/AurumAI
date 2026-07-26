import json
from pathlib import Path

import pytest

from knowledge.cbi.contracts import (
    ForwardGuidanceRecord,
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
    GUIDANCE_CALENDAR_BASED,
    GUIDANCE_STATE_CONTINGENT,
    GUIDANCE_OPEN_ENDED,
    GUIDANCE_QUANTITATIVE,
    VALID_GUIDANCE_TYPES,
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


def test_forward_guidance_creation() -> None:
    fgr = ForwardGuidanceRecord(
        central_bank=FED,
        guidance_type=GUIDANCE_CALENDAR_BASED,
        guidance_text="The Committee expects to begin tapering asset purchases.",
        credibility_score=0.85,
        language_delta="Added 'begin tapering' language, removed 'patient' reference.",
        confidence=0.8,
        valid_from="2026-07-26T12:00:00Z",
        valid_until="2026-09-17T00:00:00Z",
        time_horizon=HORIZON_T3,
    )
    assert fgr.central_bank == FED
    assert fgr.guidance_type == GUIDANCE_CALENDAR_BASED
    assert fgr.guidance_text == "The Committee expects to begin tapering asset purchases."
    assert fgr.credibility_score == 0.85
    assert fgr.language_delta == "Added 'begin tapering' language, removed 'patient' reference."
    assert fgr.confidence == 0.8
    assert fgr.valid_from == "2026-07-26T12:00:00Z"
    assert fgr.valid_until == "2026-09-17T00:00:00Z"
    assert fgr.time_horizon == HORIZON_T3


def test_forward_guidance_defaults() -> None:
    fgr = ForwardGuidanceRecord(
        central_bank=ECB,
        guidance_type=GUIDANCE_STATE_CONTINGENT,
        guidance_text="Rates will remain at current levels until inflation reaches 2%.",
        credibility_score=0.7,
        language_delta="Initial guidance statement.",
        confidence=0.75,
        valid_from="2026-07-26T12:00:00Z",
        valid_until="2026-09-10T00:00:00Z",
    )
    assert fgr.central_bank == ECB
    assert fgr.guidance_type == GUIDANCE_STATE_CONTINGENT
    assert fgr.credibility_score == 0.7
    assert fgr.data_quality_flags is None
    assert fgr.provenance is None
    assert fgr.evidence_references == []
    assert fgr.cross_references is None
    assert fgr.time_horizon == HORIZON_T0


def test_forward_guidance_all_types() -> None:
    for gtype in (GUIDANCE_CALENDAR_BASED, GUIDANCE_STATE_CONTINGENT,
                  GUIDANCE_OPEN_ENDED, GUIDANCE_QUANTITATIVE):
        fgr = ForwardGuidanceRecord(
            central_bank=FED,
            guidance_type=gtype,
            guidance_text="Test guidance.",
            credibility_score=0.5,
            language_delta="",
            confidence=0.5,
            valid_from="2026-07-26T12:00:00Z",
            valid_until="2026-09-17T00:00:00Z",
        )
        assert fgr.guidance_type == gtype
    assert VALID_GUIDANCE_TYPES == {
        GUIDANCE_CALENDAR_BASED, GUIDANCE_STATE_CONTINGENT,
        GUIDANCE_OPEN_ENDED, GUIDANCE_QUANTITATIVE,
    }


def test_forward_guidance_all_central_banks() -> None:
    for cb in (FED, ECB, BOJ, BOE, PBOC, SNB, RBA, RBNZ, BOC):
        fgr = ForwardGuidanceRecord(
            central_bank=cb,
            guidance_type=GUIDANCE_OPEN_ENDED,
            guidance_text="Guidance for test.",
            credibility_score=0.5,
            language_delta="",
            confidence=0.5,
            valid_from="2026-07-26T12:00:00Z",
            valid_until="2026-09-17T00:00:00Z",
        )
        assert fgr.central_bank == cb


def test_forward_guidance_frozen() -> None:
    fgr = ForwardGuidanceRecord(
        central_bank=FED,
        guidance_type=GUIDANCE_CALENDAR_BASED,
        guidance_text="Test.",
        credibility_score=0.5,
        language_delta="",
        confidence=0.5,
        valid_from="2026-07-26T12:00:00Z",
        valid_until="2026-09-17T00:00:00Z",
    )
    with pytest.raises(AttributeError):
        fgr.credibility_score = 0.9
    with pytest.raises(AttributeError):
        fgr.guidance_text = "Modified."


def test_forward_guidance_credibility_range() -> None:
    for score in (0.0, 0.25, 0.5, 0.75, 1.0):
        fgr = ForwardGuidanceRecord(
            central_bank=FED,
            guidance_type=GUIDANCE_CALENDAR_BASED,
            guidance_text="Test.",
            credibility_score=score,
            language_delta="",
            confidence=0.5,
            valid_from="2026-07-26T12:00:00Z",
            valid_until="2026-09-17T00:00:00Z",
        )
        assert fgr.credibility_score == score


def test_forward_guidance_with_data_quality_flags() -> None:
    fgr = ForwardGuidanceRecord(
        central_bank=BOJ,
        guidance_type=GUIDANCE_STATE_CONTINGENT,
        guidance_text="Maintain accommodative policy.",
        credibility_score=0.6,
        language_delta="Updated inflation forecast.",
        confidence=0.7,
        valid_from="2026-07-26T12:00:00Z",
        valid_until="2026-09-20T00:00:00Z",
        data_quality_flags=["source_translation_delayed", "unofficial_transcript"],
    )
    assert fgr.data_quality_flags == ["source_translation_delayed", "unofficial_transcript"]


def test_forward_guidance_empty_language_delta() -> None:
    fgr = ForwardGuidanceRecord(
        central_bank=FED,
        guidance_type=GUIDANCE_CALENDAR_BASED,
        guidance_text="No change in forward guidance.",
        credibility_score=0.8,
        language_delta="",
        confidence=0.7,
        valid_from="2026-07-26T12:00:00Z",
        valid_until="2026-09-17T00:00:00Z",
    )
    assert fgr.language_delta == ""


def test_forward_guidance_long_text() -> None:
    long_text = "The Committee continues to assess incoming data and the outlook for " * 20
    fgr = ForwardGuidanceRecord(
        central_bank=FED,
        guidance_type=GUIDANCE_OPEN_ENDED,
        guidance_text=long_text,
        credibility_score=0.7,
        language_delta="Rephrased forward guidance.",
        confidence=0.75,
        valid_from="2026-07-26T12:00:00Z",
        valid_until="2026-09-17T00:00:00Z",
    )
    assert len(fgr.guidance_text) > 120


def test_forward_guidance_with_full_optional_fields() -> None:
    provenance = Provenance(
        created_at="2026-07-26T12:00:00Z",
        created_by="analyst_02",
        entity_version="2.1.0",
    )
    ev_refs = [
        {
            "source_category": "central_bank_statement",
            "source_descriptor": "FOMC Statement July 2026",
            "contribution": "primary guidance source",
            "confidence_contribution": "high",
        }
    ]
    fgr = ForwardGuidanceRecord(
        central_bank=FED,
        guidance_type=GUIDANCE_CALENDAR_BASED,
        guidance_text="The Committee expects to maintain the current federal funds rate target range.",
        credibility_score=0.8,
        language_delta="Removed reference to 'appropriate policy firming'.",
        confidence=0.8,
        valid_from="2026-07-26T12:00:00Z",
        valid_until="2026-09-17T00:00:00Z",
        time_horizon=HORIZON_T3,
        provenance=provenance,
        evidence_references=ev_refs,
        cross_references=["CBI:PolicyBiasScore:FED:2026-07-26"],
        methodology_version="2.1.0",
        scenario_analysis=[
            {"label": "hawkish_guidance_change", "probability": 0.25}
        ],
        data_quality_flags=["transcript_unofficial"],
    )
    assert fgr.provenance is not None
    assert fgr.provenance.created_by == "analyst_02"
    assert len(fgr.evidence_references) == 1
    assert fgr.cross_references == ["CBI:PolicyBiasScore:FED:2026-07-26"]
    assert fgr.methodology_version == "2.1.0"
    assert len(fgr.scenario_analysis) == 1
    assert fgr.data_quality_flags == ["transcript_unofficial"]


def test_forward_guidance_inherits_base_contract() -> None:
    fgr = ForwardGuidanceRecord(
        central_bank=FED,
        guidance_type=GUIDANCE_CALENDAR_BASED,
        guidance_text="Test.",
        credibility_score=0.5,
        language_delta="",
        confidence=0.5,
        valid_from="2026-07-26T12:00:00Z",
        valid_until="2026-09-17T00:00:00Z",
    )
    assert isinstance(fgr, CbiBaseContract)


# ── Repository ───────────────────────────────────────────────────────────────


def test_repository_save_and_load_forward_guidance(tmp_path: Path) -> None:
    repo = CbiRepository()
    fgr = ForwardGuidanceRecord(
        central_bank=FED,
        guidance_type=GUIDANCE_CALENDAR_BASED,
        guidance_text="The Committee expects to begin tapering asset purchases.",
        credibility_score=0.85,
        language_delta="Added tapering language.",
        confidence=0.8,
        valid_from="2026-07-26T12:00:00Z",
        valid_until="2026-09-17T00:00:00Z",
        time_horizon=HORIZON_T3,
    )
    p = tmp_path / "forward_guidance.json"
    repo.save_forward_guidance(fgr, p)
    loaded = repo.load_forward_guidance(p)
    assert loaded.central_bank == FED
    assert loaded.guidance_type == GUIDANCE_CALENDAR_BASED
    assert loaded.credibility_score == 0.85
    assert loaded.confidence == 0.8


def test_repository_roundtrip_preserves_all_fields(tmp_path: Path) -> None:
    repo = CbiRepository()
    provenance = Provenance(
        created_at="2026-07-26T12:00:00Z",
        created_by="analyst_02",
        entity_version="2.0.0",
    )
    original = ForwardGuidanceRecord(
        central_bank=ECB,
        guidance_type=GUIDANCE_STATE_CONTINGENT,
        guidance_text="Rates remain at current levels until inflation converges to target.",
        credibility_score=0.72,
        language_delta="Strengthened conditionality language.",
        confidence=0.78,
        valid_from="2026-07-26T12:00:00Z",
        valid_until="2026-09-10T00:00:00Z",
        time_horizon=HORIZON_T3,
        provenance=provenance,
        evidence_references=[
            {"source_category": "press_conference",
             "source_descriptor": "ECB Press Conference July 2026"}
        ],
        cross_references=["CBI:PolicyBiasScore:ECB:2026-07-26"],
        methodology_version="2.0.0",
        scenario_analysis=[{"label": "dovish_delay", "probability": 0.3}],
        data_quality_flags=["machine_translated"],
    )
    p = tmp_path / "ecb_guidance.json"
    repo.save_forward_guidance(original, p)
    loaded = repo.load_forward_guidance(p)
    assert loaded.central_bank == original.central_bank
    assert loaded.guidance_type == original.guidance_type
    assert loaded.guidance_text == original.guidance_text
    assert loaded.credibility_score == original.credibility_score
    assert loaded.language_delta == original.language_delta
    assert loaded.confidence == original.confidence
    assert loaded.valid_from == original.valid_from
    assert loaded.valid_until == original.valid_until
    assert loaded.time_horizon == original.time_horizon
    assert loaded.provenance is not None
    assert loaded.provenance.created_by == "analyst_02"
    assert loaded.provenance.entity_version == "2.0.0"
    assert loaded.evidence_references == original.evidence_references
    assert loaded.cross_references == original.cross_references
    assert loaded.methodology_version == original.methodology_version
    assert loaded.scenario_analysis == original.scenario_analysis
    assert loaded.data_quality_flags == original.data_quality_flags


def test_repository_roundtrip_with_none_optionals(tmp_path: Path) -> None:
    repo = CbiRepository()
    original = ForwardGuidanceRecord(
        central_bank=BOJ,
        guidance_type=GUIDANCE_OPEN_ENDED,
        guidance_text="Policy will remain accommodative.",
        credibility_score=0.65,
        language_delta="No material change.",
        confidence=0.6,
        valid_from="2026-07-26T12:00:00Z",
        valid_until="2026-09-20T00:00:00Z",
    )
    p = tmp_path / "boj_guidance.json"
    repo.save_forward_guidance(original, p)
    loaded = repo.load_forward_guidance(p)
    assert loaded.provenance is None
    assert loaded.evidence_references == []
    assert loaded.cross_references is None
    assert loaded.methodology_version is None
    assert loaded.scenario_analysis is None
    assert loaded.data_quality_flags is None


def test_repository_json_structure(tmp_path: Path) -> None:
    repo = CbiRepository()
    fgr = ForwardGuidanceRecord(
        central_bank=FED,
        guidance_type=GUIDANCE_CALENDAR_BASED,
        guidance_text="The Committee expects to begin tapering.",
        credibility_score=0.85,
        language_delta="Added tapering language.",
        confidence=0.8,
        valid_from="2026-07-26T12:00:00Z",
        valid_until="2026-09-17T00:00:00Z",
        time_horizon=HORIZON_T3,
    )
    p = tmp_path / "forward_guidance.json"
    repo.save_forward_guidance(fgr, p)
    raw = json.loads(p.read_text())
    assert raw["central_bank"] == "FED"
    assert raw["guidance_type"] == "calendar_based"
    assert raw["guidance_text"] == "The Committee expects to begin tapering."
    assert raw["credibility_score"] == 0.85
    assert raw["language_delta"] == "Added tapering language."
    assert raw["confidence"] == 0.8
    assert raw["valid_from"] == "2026-07-26T12:00:00Z"
    assert raw["valid_until"] == "2026-09-17T00:00:00Z"
    assert raw["time_horizon"] == "T3"
    assert raw["provenance"] is None
    assert raw["data_quality_flags"] is None


# ── Adapter ──────────────────────────────────────────────────────────────────


def test_adapter_forward_guidance_to_evidence_basic() -> None:
    adapter = CbiEvidenceAdapter()
    fgr = ForwardGuidanceRecord(
        central_bank=FED,
        guidance_type=GUIDANCE_CALENDAR_BASED,
        guidance_text="The Committee expects to begin tapering asset purchases.",
        credibility_score=0.85,
        language_delta="Added tapering language.",
        confidence=0.8,
        valid_from="2026-07-26T12:00:00Z",
        valid_until="2026-09-17T00:00:00Z",
    )
    ev = adapter.forward_guidance_to_evidence(fgr)
    assert isinstance(ev, Evidence)
    assert ev.event_type == "CBI_GUIDANCE"
    assert ev.bias == "neutral"
    assert ev.confidence == 0.8
    assert ev.evidence_id == "cbi_guidance_FED"
    assert ev.source_node_id == "cbi_FED"
    assert ev.condition == {"central_bank": "FED", "guidance_type": "calendar_based"}


def test_adapter_forward_guidance_all_types() -> None:
    adapter = CbiEvidenceAdapter()
    for gtype in (GUIDANCE_CALENDAR_BASED, GUIDANCE_STATE_CONTINGENT,
                  GUIDANCE_OPEN_ENDED, GUIDANCE_QUANTITATIVE):
        fgr = ForwardGuidanceRecord(
            central_bank=ECB,
            guidance_type=gtype,
            guidance_text="Test guidance text.",
            credibility_score=0.5,
            language_delta="",
            confidence=0.5,
            valid_from="2026-07-26T12:00:00Z",
            valid_until="2026-09-10T00:00:00Z",
        )
        ev = adapter.forward_guidance_to_evidence(fgr)
        assert ev.condition["guidance_type"] == gtype


def test_adapter_preserves_provenance() -> None:
    adapter = CbiEvidenceAdapter()
    provenance = Provenance(
        created_at="2026-07-26T12:00:00Z",
        created_by="analyst_02",
        entity_version="2.0.0",
    )
    fgr = ForwardGuidanceRecord(
        central_bank=FED,
        guidance_type=GUIDANCE_CALENDAR_BASED,
        guidance_text="Test guidance.",
        credibility_score=0.8,
        language_delta="Updated language.",
        confidence=0.8,
        valid_from="2026-07-26T12:00:00Z",
        valid_until="2026-09-17T00:00:00Z",
        provenance=provenance,
    )
    ev = adapter.forward_guidance_to_evidence(fgr)
    assert ev.provenance is not None
    assert ev.provenance.created_by == "analyst_02"
    assert ev.provenance.created_at == "2026-07-26T12:00:00Z"
    assert ev.provenance.entity_version == "2.0.0"


def test_adapter_preserves_confidence() -> None:
    adapter = CbiEvidenceAdapter()
    fgr = ForwardGuidanceRecord(
        central_bank=FED,
        guidance_type=GUIDANCE_CALENDAR_BASED,
        guidance_text="Test.",
        credibility_score=0.8,
        language_delta="",
        confidence=0.82,
        valid_from="2026-07-26T12:00:00Z",
        valid_until="2026-09-17T00:00:00Z",
    )
    ev = adapter.forward_guidance_to_evidence(fgr)
    assert ev.confidence == 0.82


def test_adapter_preserves_evidence_references() -> None:
    adapter = CbiEvidenceAdapter()
    ev_refs = [
        {
            "source_category": "central_bank_statement",
            "source_descriptor": "FOMC Statement July 2026",
            "contribution": "primary guidance source",
            "confidence_contribution": "high",
        }
    ]
    fgr = ForwardGuidanceRecord(
        central_bank=FED,
        guidance_type=GUIDANCE_CALENDAR_BASED,
        guidance_text="Test.",
        credibility_score=0.8,
        language_delta="",
        confidence=0.8,
        valid_from="2026-07-26T12:00:00Z",
        valid_until="2026-09-17T00:00:00Z",
        evidence_references=ev_refs,
    )
    ev = adapter.forward_guidance_to_evidence(fgr)
    assert ev.metadata["evidence_references"] == ev_refs


def test_adapter_preserves_validity() -> None:
    adapter = CbiEvidenceAdapter()
    fgr = ForwardGuidanceRecord(
        central_bank=FED,
        guidance_type=GUIDANCE_CALENDAR_BASED,
        guidance_text="Test.",
        credibility_score=0.8,
        language_delta="",
        confidence=0.8,
        valid_from="2026-07-26T12:00:00Z",
        valid_until="2026-09-17T00:00:00Z",
        time_horizon=HORIZON_T3,
    )
    ev = adapter.forward_guidance_to_evidence(fgr)
    assert ev.metadata["valid_from"] == "2026-07-26T12:00:00Z"
    assert ev.metadata["valid_until"] == "2026-09-17T00:00:00Z"
    assert ev.metadata["time_horizon"] == HORIZON_T3


def test_adapter_preserves_credibility_score() -> None:
    adapter = CbiEvidenceAdapter()
    fgr = ForwardGuidanceRecord(
        central_bank=ECB,
        guidance_type=GUIDANCE_STATE_CONTINGENT,
        guidance_text="Test.",
        credibility_score=0.73,
        language_delta="",
        confidence=0.7,
        valid_from="2026-07-26T12:00:00Z",
        valid_until="2026-09-10T00:00:00Z",
    )
    ev = adapter.forward_guidance_to_evidence(fgr)
    assert ev.metadata["credibility_score"] == 0.73


def test_adapter_preserves_language_delta() -> None:
    adapter = CbiEvidenceAdapter()
    fgr = ForwardGuidanceRecord(
        central_bank=FED,
        guidance_type=GUIDANCE_CALENDAR_BASED,
        guidance_text="Test.",
        credibility_score=0.8,
        language_delta="Removed 'patient' reference, added 'data-dependent' language.",
        confidence=0.8,
        valid_from="2026-07-26T12:00:00Z",
        valid_until="2026-09-17T00:00:00Z",
    )
    ev = adapter.forward_guidance_to_evidence(fgr)
    assert ev.metadata["language_delta"] == "Removed 'patient' reference, added 'data-dependent' language."


def test_adapter_preserves_data_quality_flags() -> None:
    adapter = CbiEvidenceAdapter()
    fgr = ForwardGuidanceRecord(
        central_bank=BOJ,
        guidance_type=GUIDANCE_STATE_CONTINGENT,
        guidance_text="Test.",
        credibility_score=0.6,
        language_delta="Updated inflation forecast.",
        confidence=0.7,
        valid_from="2026-07-26T12:00:00Z",
        valid_until="2026-09-20T00:00:00Z",
        data_quality_flags=["unofficial_transcript"],
    )
    ev = adapter.forward_guidance_to_evidence(fgr)
    assert ev.metadata["data_quality_flags"] == ["unofficial_transcript"]


def test_adapter_truncates_long_text_in_explanation() -> None:
    adapter = CbiEvidenceAdapter()
    long_text = "The Committee expects to maintain the current federal funds rate " * 10
    fgr = ForwardGuidanceRecord(
        central_bank=FED,
        guidance_type=GUIDANCE_OPEN_ENDED,
        guidance_text=long_text,
        credibility_score=0.7,
        language_delta="Minor rephrasing.",
        confidence=0.7,
        valid_from="2026-07-26T12:00:00Z",
        valid_until="2026-09-17T00:00:00Z",
    )
    ev = adapter.forward_guidance_to_evidence(fgr)
    assert len(ev.explanation) < len(long_text) + 100
    assert ev.explanation.startswith("ForwardGuidanceRecord for FED: open_ended —")


def test_adapter_preserves_full_text_in_metadata() -> None:
    adapter = CbiEvidenceAdapter()
    long_text = "The Committee expects to begin tapering asset purchases in the coming months."
    fgr = ForwardGuidanceRecord(
        central_bank=FED,
        guidance_type=GUIDANCE_CALENDAR_BASED,
        guidance_text=long_text,
        credibility_score=0.85,
        language_delta="Added tapering reference.",
        confidence=0.8,
        valid_from="2026-07-26T12:00:00Z",
        valid_until="2026-09-17T00:00:00Z",
    )
    ev = adapter.forward_guidance_to_evidence(fgr)
    assert ev.metadata["guidance_text"] == long_text
    assert ev.metadata["object_type"] == "ForwardGuidanceRecord"


def test_adapter_preserves_cross_references() -> None:
    adapter = CbiEvidenceAdapter()
    fgr = ForwardGuidanceRecord(
        central_bank=FED,
        guidance_type=GUIDANCE_CALENDAR_BASED,
        guidance_text="Test.",
        credibility_score=0.8,
        language_delta="",
        confidence=0.8,
        valid_from="2026-07-26T12:00:00Z",
        valid_until="2026-09-17T00:00:00Z",
        cross_references=["CBI:PolicyBiasScore:FED:2026-07-26"],
    )
    ev = adapter.forward_guidance_to_evidence(fgr)
    assert ev.metadata["cross_references"] == ["CBI:PolicyBiasScore:FED:2026-07-26"]


# ── EvidenceAggregator integration ───────────────────────────────────────────


def test_forward_guidance_evidence_merges_via_aggregator() -> None:
    adapter = CbiEvidenceAdapter()
    fgr = ForwardGuidanceRecord(
        central_bank=FED,
        guidance_type=GUIDANCE_CALENDAR_BASED,
        guidance_text="The Committee expects to begin tapering.",
        credibility_score=0.85,
        language_delta="Added tapering language.",
        confidence=0.8,
        valid_from="2026-07-26T12:00:00Z",
        valid_until="2026-09-17T00:00:00Z",
    )
    ev = adapter.forward_guidance_to_evidence(fgr)

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


def test_forward_guidance_evidence_conflict_free_with_event() -> None:
    adapter = CbiEvidenceAdapter()
    fgr = ForwardGuidanceRecord(
        central_bank=FED,
        guidance_type=GUIDANCE_CALENDAR_BASED,
        guidance_text="Test.",
        credibility_score=0.8,
        language_delta="",
        confidence=0.8,
        valid_from="2026-07-26T12:00:00Z",
        valid_until="2026-09-17T00:00:00Z",
    )
    ev = adapter.forward_guidance_to_evidence(fgr)

    event_evidence = EvidenceCollection([
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
        "economic": event_evidence,
        "cbi": EvidenceCollection([ev]),
    })
    assert len(result.conflicts) == 0


def test_forward_guidance_evidence_same_id_conflict() -> None:
    adapter = CbiEvidenceAdapter()
    fgr = ForwardGuidanceRecord(
        central_bank=FED,
        guidance_type=GUIDANCE_CALENDAR_BASED,
        guidance_text="Test.",
        credibility_score=0.8,
        language_delta="",
        confidence=0.8,
        valid_from="2026-07-26T12:00:00Z",
        valid_until="2026-09-17T00:00:00Z",
    )
    ev = adapter.forward_guidance_to_evidence(fgr)

    conflicting = Evidence(
        evidence_id="cbi_guidance_FED",
        source_node_id="cbi_FED",
        event_type="CBI_GUIDANCE",
        condition={"central_bank": "FED", "guidance_type": "calendar_based"},
        horizon_days=0,
        sample_count=1,
        average_return_pct=0.0,
        confidence=0.8,
        bias="bullish",
        explanation="Conflicting bias.",
    )

    agg = EvidenceAggregator()
    result = agg.merge({
        "cbi_v1": EvidenceCollection([ev]),
        "cbi_v2": EvidenceCollection([conflicting]),
    })
    assert len(result.conflicts) >= 1
