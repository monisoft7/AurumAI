"""Correction 009: surface the current CPI release into the institutional W5/W6 path.

The current CPI release (already computed upstream as CPIEvent.extraction and
stored on the briefing boundary) is mapped into a ClassifiedObservation by the
W5 assembler (observation identity: instrument="CPI Release",
source="cpi_release"), then linked by W6 EvidenceCollector to the real CPI
KnowledgeRecords via the existing cpi_condition.  All assertions verify the
boundary handoff only: no classifier, scoring, threshold or decision changes.
"""

import json

import pytest

from counter_evidence.contracts import CounterEvidenceAssessment
from evidence_collection.collector import EvidenceCollector, INSTRUMENT_TO_EVENT_TYPE
from evidence_reasoning.contracts import EvidenceReasoning
from evidence_reasoning.reasoner import EvidenceReasoner
from knowledge.events.cpi import CPIEvent
from knowledge.graph.builder import GraphBuilder
from pre_market.contracts import OvernightPriceChange, PreMarketBriefing
from signal_assessment.assembler import SignalAssessmentAssembler
from signal_assessment.classifier import NoiseSignalClassifier
from signal_assessment.contracts import ClassifiedObservation, ClassificationLabel
from thesis_construction.builder import ThesisBuilder
from test_evidence_collection import _cpi_semantics_records

CPI_RELEASE_METADATA = {
    "event_type": "CPI",
    "reference_period": "2026-07-01",
    "value": 332.813,
    "cpi_change_pct": 0.0737,
    "cpi_pressure": "inflation_pressure_up",
    "priority": "Tier 1",
    "expected_impact": "high",
    "release_date": "2026-08-12",
}


def _make_briefing(**overrides) -> PreMarketBriefing:
    return PreMarketBriefing(
        briefing_id=overrides.get("briefing_id", "premarket_009"),
        timestamp=overrides.get("timestamp", "2026-08-13T06:00:00"),
        regime=overrides.get("regime", "NORMAL_GROWTH"),
        regime_confidence=overrides.get("regime_confidence", 0.85),
        overnight_changes=overrides.get(
            "overnight_changes",
            (
                OvernightPriceChange("XAU/USD", 1900.0, 1912.0, 0.63, 1.4, "APAC"),
                OvernightPriceChange("DXY", 100.0, 99.4, -0.6, 0.9, "APAC"),
            ),
        ),
        positioning_snapshot=overrides.get("positioning_snapshot", None),
        metadata=overrides.get("metadata", {}),
    )


def _cpi_briefing(**overrides) -> PreMarketBriefing:
    return _make_briefing(
        metadata=overrides.pop("metadata", {"cpi_release": dict(CPI_RELEASE_METADATA)}),
        **overrides,
    )


def _cpi_observation(briefing: PreMarketBriefing) -> ClassifiedObservation:
    assessment = SignalAssessmentAssembler(regime=briefing.regime).assemble(briefing)
    for obs in assessment.observations:
        if obs.instrument == "CPI Release":
            return obs
    raise AssertionError("CPI Release observation not produced")


def _collect_cpi_evidence(briefing: PreMarketBriefing):
    assessment = SignalAssessmentAssembler(regime=briefing.regime).assemble(briefing)
    kg = GraphBuilder().build(_cpi_semantics_records())
    collection = EvidenceCollector(knowledge_graph=kg).collect(
        assessment,
        regime_weight=0.8,
        cpi_condition={"cpi_pressure": "inflation_pressure_up"},
    )
    return assessment, collection


def _kr_set(reasoning):
    for s in reasoning.evidence_sets:
        if "knowledge_rationale" in s.metadata:
            return s
    raise AssertionError("no KR-backed evidence set in reasoning")


def _make_assessment_for(reasoning, supporting_set_id: str) -> CounterEvidenceAssessment:
    return CounterEvidenceAssessment(
        assessment_id="cea_009",
        reasoning_id=reasoning.reasoning_id,
        timestamp="2026-08-13T00:00:00",
        regime=reasoning.regime,
        related_set_ids=(supporting_set_id,),
        supporting_set_ids=(supporting_set_id,),
        contradicting_set_ids=(),
        conflict_severity=0.0,
        confidence_penalty=0.0,
        regime_conflict=False,
        bias_flags=(),
    )


class TestW5CpiObservation:
    def test_a_cpi_obs_identity(self):
        obs = _cpi_observation(_cpi_briefing())
        assert obs.instrument == "CPI Release"
        assert obs.source == "cpi_release"
        assert obs.value == 332.813
        assert obs.change_pct == 0.0737
        assert obs.change_sigma == 0.0

    def test_b_cpi_obs_survives_w5_as_watch(self):
        obs = _cpi_observation(_cpi_briefing())
        assert obs.classification == ClassificationLabel.WATCH.value
        assert obs.confidence == 0.3
        passed = [c.criterion for c in obs.evidence if c.passed]
        assert passed == ["narrative_fit"]

    def test_b_low_impact_obs_falls_to_ignore_honestly(self):
        briefing = _cpi_briefing(
            metadata={"cpi_release": {
                **CPI_RELEASE_METADATA, "expected_impact": "low",
            }},
        )
        obs = _cpi_observation(briefing)
        assert obs.classification == ClassificationLabel.IGNORE.value
        assert [c.criterion for c in obs.evidence if c.passed] == []

    def test_c_observation_id_deterministic(self):
        obs = _cpi_observation(_cpi_briefing())
        assert obs.observation_id == "obs_cpi_release_2026-07-01"

    def test_d_breakeven_inflation_untouched(self):
        briefing = _cpi_briefing(
            overnight_changes=(
                OvernightPriceChange("Breakeven Inflation", 2.4, 2.6, 8.3, 0.8, "APAC"),
            ),
        )
        assessment = SignalAssessmentAssembler(regime=briefing.regime).assemble(briefing)
        instruments = {o.instrument for o in assessment.observations}
        assert "Breakeven Inflation" in instruments
        assert "T5YIE" not in instruments
        for obs in assessment.observations:
            if obs.instrument == "Breakeven Inflation":
                assert obs.source == "overnight_price"
                assert obs.observation_id.startswith("obs_Breakeven Inflation_")
                assert not obs.observation_id.startswith("obs_cpi_release_")

    def test_m_no_metadata_no_cpi_obs(self):
        briefing = _make_briefing(metadata={})
        assessment = SignalAssessmentAssembler(regime=briefing.regime).assemble(briefing)
        assert not any(o.instrument == "CPI Release" for o in assessment.observations)

    def test_m_malformed_metadata_tolerated(self):
        briefing = _make_briefing(metadata={"cpi_release": {"event_type": "OTHER"}})
        assessment = SignalAssessmentAssembler(regime=briefing.regime).assemble(briefing)
        assert not any(o.instrument == "CPI Release" for o in assessment.observations)


class TestW6CpiKnowledgeLinkage:
    def test_e_collector_event_type_mapping(self):
        assert INSTRUMENT_TO_EVENT_TYPE["CPI Release"] == "INFLATION"

    def test_f_condition_selects_real_up_kr(self):
        _, collection = _collect_cpi_evidence(_cpi_briefing())
        ev = [e for e in collection.items if e.source_label == "cpi_release"][0]
        assert ev.source_kr_node_id == "CPI_XAU/USD_inflation_pressure_up_1D"

    def test_g_provenance_is_knowledge_record(self):
        _, collection = _collect_cpi_evidence(_cpi_briefing())
        ev = [e for e in collection.items if e.source_label == "cpi_release"][0]
        assert ev.metadata["provenance_type"] == "knowledge_record"
        assert ev.metadata["knowledge_record_id"] == "CPI_XAU/USD_inflation_pressure_up_1D"
        assert ev.provenance.metadata["knowledge_record_link"] == ev.source_kr_id

    def test_h_semantics_match_node_props_exactly(self):
        _, collection = _collect_cpi_evidence(_cpi_briefing())
        ev = [e for e in collection.items if e.source_label == "cpi_release"][0]
        graph = GraphBuilder().build(_cpi_semantics_records())
        node_props = graph.get_node(ev.source_kr_node_id).properties
        semantics = ev.metadata["knowledge_semantics"]
        for field in (
            "condition",
            "horizon_days",
            "sample_count",
            "average_return_pct",
            "confidence",
            "positive_return_rate_pct",
            "bias",
            "last_event_date",
            "institutional_context",
        ):
            assert semantics[field] == node_props[field]
        assert semantics["condition"] == {"cpi_pressure": "inflation_pressure_up"}
        assert semantics["sample_count"] == 118

    def test_h_without_condition_fallback_links_real_kr_only(self):
        briefing = _cpi_briefing()
        assessment = SignalAssessmentAssembler(regime=briefing.regime).assemble(briefing)
        kg = GraphBuilder().build(_cpi_semantics_records())
        real_ids = {r["knowledge_id"] for r in _cpi_semantics_records()}
        collection = EvidenceCollector(knowledge_graph=kg).collect(
            assessment, regime_weight=0.8, cpi_condition=None
        )
        ev = [e for e in collection.items if e.source_label == "cpi_release"][0]
        assert ev.source_kr_node_id in real_ids


class TestRationaleAndThesisComposition:
    def test_i_rationale_produced_on_cpi_set(self):
        _, collection = _collect_cpi_evidence(_cpi_briefing())
        reasoning = EvidenceReasoner().reason(collection)
        entry = _kr_set(reasoning).metadata["knowledge_rationale"][0]
        assert entry["family"] == "CPI"
        assert entry["condition"] == {"cpi_pressure": "inflation_pressure_up"}

    def test_j_rationale_carries_real_kr_values(self):
        _, collection = _collect_cpi_evidence(_cpi_briefing())
        reasoning = EvidenceReasoner().reason(collection)
        entry = _kr_set(reasoning).metadata["knowledge_rationale"][0]
        assert entry["horizon_days"] == 1
        assert entry["sample_count"] == 118
        assert entry["average_return_pct"] == -0.033338
        assert entry["confidence"] == 0.511503
        assert entry["positive_return_rate_pct"] == 51.694915
        assert entry["engine_summary"].startswith("For CPI condition")

    def test_k_thesis_explanation_contains_knowledge_chunk(self):
        _, collection = _collect_cpi_evidence(_cpi_briefing())
        reasoning = EvidenceReasoner().reason(collection)
        kr_set = _kr_set(reasoning)
        assessment = _make_assessment_for(reasoning, kr_set.set_id)
        thesis = ThesisBuilder().build_thesis(
            "bullish", reasoning, assessment, [kr_set.set_id], []
        )
        assert "knowledge: CPI cpi_pressure=inflation_pressure_up:" in thesis.explanation
        assert "avg -0.033% over 1d" in thesis.explanation
        assert "118 samples" in thesis.explanation

    def test_k_serialization_roundtrip(self):
        _, collection = _collect_cpi_evidence(_cpi_briefing())
        reasoning = EvidenceReasoner().reason(collection)
        raw = json.dumps(reasoning.to_dict())
        restored = EvidenceReasoning.from_dict(json.loads(raw))
        assert _kr_set(restored).metadata["knowledge_rationale"] == (
            _kr_set(reasoning).metadata["knowledge_rationale"]
        )


class TestBoundaryNoRegression:
    def test_l_classifier_rules_untouched_zero_criteria_ignore(self):
        label, confidence, _ = NoiseSignalClassifier().classify(criteria_scores={})
        assert label == ClassificationLabel.IGNORE.value
        assert confidence == 0.9

    def test_l_market_evidence_weights_identical_with_and_without_cpi(self):
        plain = _collect_cpi_evidence(_make_briefing(metadata={}))
        rich = _collect_cpi_evidence(_cpi_briefing())
        plain_xau = [e for e in plain[1].items if e.condition["instrument"] == "XAU/USD"]
        rich_xau = [e for e in rich[1].items if e.condition["instrument"] == "XAU/USD"]
        assert plain_xau and rich_xau
        assert plain_xau[0].composite_weight == rich_xau[0].composite_weight
        assert plain_xau[0].bias == rich_xau[0].bias
        assert plain_xau[0].base_confidence == rich_xau[0].base_confidence

    def test_l_market_obs_classifications_unchanged_by_cpi_metadata(self):
        plain = SignalAssessmentAssembler(regime="NORMAL_GROWTH").assemble(
            _make_briefing(metadata={})
        )
        rich = SignalAssessmentAssembler(regime="NORMAL_GROWTH").assemble(
            _cpi_briefing()
        )
        plain_obs = [o for o in plain.observations if o.instrument != "CPI Release"]
        rich_obs = [o for o in rich.observations if o.instrument != "CPI Release"]
        assert {
            (o.instrument, o.classification, o.confidence) for o in plain_obs
        } == {
            (o.instrument, o.classification, o.confidence) for o in rich_obs
        }


class TestStagingHandoff:
    def test_n_snapshot_from_upstream_extraction(self, tmp_path):
        cpi_csv = tmp_path / "cpiaucsl.csv"
        cpi_csv.write_text(
            "Date,Value\n2026-06-01,332.568\n2026-07-01,332.813\n",
            encoding="utf-8",
        )
        cal_csv = tmp_path / "cpi_releases.csv"
        cal_csv.write_text(
            "reference_period,release_date,release_time,timezone\n"
            "2026-07-01,2026-08-12,08:30,US/Eastern\n",
            encoding="utf-8",
        )
        from orchestration.stages import _cpi_release_snapshot

        params = {"data_path": str(cpi_csv), "release_calendar_path": str(cal_csv)}
        results = {
            "ingest_event": {
                "event_type": "CPIEvent",
                "event": CPIEvent(),
                "raw_data": None,
            }
        }
        snapshot = _cpi_release_snapshot(params, results)
        assert snapshot["event_type"] == "CPI"
        assert snapshot["reference_period"] == "2026-07-01"
        assert snapshot["value"] == 332.813
        assert snapshot["cpi_change_pct"] == pytest.approx(0.07370, abs=1e-3)
        assert snapshot["cpi_pressure"] == "inflation_pressure_up"
        assert snapshot["priority"] == "Tier 1"
        assert snapshot["expected_impact"] == "high"
        assert snapshot["release_date"] == "2026-08-12"

    def test_o_pre_market_scan_attaches_snapshot(self, tmp_path, monkeypatch):
        import pre_market.briefing_assembler as ba
        from orchestration.stages import _pre_market_scan

        cpi_csv = tmp_path / "cpiaucsl.csv"
        cpi_csv.write_text(
            "Date,Value\n2026-06-01,332.568\n2026-07-01,332.813\n",
            encoding="utf-8",
        )
        cal_csv = tmp_path / "cpi_releases.csv"
        cal_csv.write_text(
            "reference_period,release_date,release_time,timezone\n"
            "2026-07-01,2026-08-12,08:30,US/Eastern\n",
            encoding="utf-8",
        )

        class _StubAssembler:
            def __init__(self, *args, **kwargs):
                pass

            def assemble(self, **kwargs):
                self.calendar_csv = kwargs.get("calendar_csv")
                return _make_briefing(briefing_id="premarket_009_stage")

        monkeypatch.setattr(ba, "PreMarketBriefingAssembler", _StubAssembler)
        params = {
            "data_path": str(cpi_csv),
            "release_calendar_path": str(cal_csv),
            "regime": "NORMAL_GROWTH",
        }
        results = {
            "ingest_event": {
                "event_type": "CPIEvent",
                "event": CPIEvent(),
                "raw_data": None,
            }
        }
        briefing = _pre_market_scan(params, results)
        assert briefing.metadata["cpi_release"]["reference_period"] == "2026-07-01"
        assert briefing.metadata["cpi_release"]["cpi_pressure"] == (
            "inflation_pressure_up"
        )

    def test_p_snapshot_tolerant_of_missing_inputs(self):
        from orchestration.stages import _cpi_release_snapshot

        assert _cpi_release_snapshot({}, {}) is None
        assert _cpi_release_snapshot(
            {}, {"ingest_event": {"event_type": "CPI", "event": None}}
        ) is None
        params = {"data_path": "does/not/exist.csv"}
        results = {"ingest_event": {"event_type": "CPI", "event": CPIEvent()}}
        assert _cpi_release_snapshot(params, results) is None