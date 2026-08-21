"""Correction 034: candidate-scoped historical assessment persistence.

Proves the candidate-specific ``historical_assessment`` built by W8 and
preserved by W10 is exposed by the existing finalize serialization boundary
(``_finalize`` -> ``finalize.json``) without touching any decision logic.

Covers: 3-candidate persistence, all directions, per-horizon results,
provenance, query, lesson ids, multiple candidate ids, W10-versioned
primary, deterministic serialization, JSON round-trip, missing-payload
degradation, N=1 backward compatibility, numeric invariance, and existing
finalize schema compatibility.
"""

from __future__ import annotations

import json

from knowledge.integrity.provenance import Provenance
from orchestration.stages import (
    _construction_from_update,
    _finalize,
)
from thesis_construction.builder import ThesisBuilder
from thesis_construction.contracts import InvestmentThesis, ThesisConstruction
from thesis_update.contracts import ThesisUpdate

TIMESTAMP = "2026-08-19T00:00:00Z"
UPDATE_TIMESTAMP = "2026-08-19T01:00:00Z"
REGIME = "NORMAL_GROWTH"
REASONING_ID = "rsn_034"
ASSESSMENT_ID = "cea_034"

_SOURCE_PATH = "artifacts/lesson_episodes.json"
_SOURCE_SHA = "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
_LESSON_IDS = ("CPI_GOLD_2017-07-01", "CPI_GOLD_2018-02-01", "CPI_GOLD_2025-05-01")

_QUERY = {
    "event_type": "CPI",
    "condition": {
        "cpi_pressure": "inflation_pressure_up",
        "us10y_trend": "yields_rising",
        "dxy_trend": "dxy_falling",
    },
    "institutional_context": {"regime": "INFLATIONARY"},
}

_PROV_W8 = Provenance(
    created_at=TIMESTAMP, created_by="W8 ThesisBuilder", entity_version="1.0.0"
)
_PROV_W10 = Provenance(
    created_at=UPDATE_TIMESTAMP, created_by="W10 ThesisUpdater", entity_version="1.0.0"
)

_FINALIZE_KEYS = (
    "decision",
    "legacy_decision",
    "risk_decision",
    "forecast_result",
    "confidence",
    "validation",
    "context",
    "risk_metrics",
    "position_sizing",
    "risk_budget",
    "position_sizing_status",
)


# =========================================================================
# Helpers
# =========================================================================


def _assessment(direction: str, status: str = "mixed") -> dict:
    """Realistic in-memory historical_assessment built with the production
    verdict/summary machinery (W8 static methods)."""
    horizon_results: dict[str, dict] = {}
    statuses: dict[str, str] = {}
    for hk in ("1d", "5d", "20d"):
        statuses[hk] = status
        horizon_results[hk] = {
            "status": status,
            "direction_summary": status,
            "count": 3,
            "verdict": ThesisBuilder._direction_verdict(direction, status),
        }
    verdicts = {
        hk: entry["verdict"] for hk, entry in horizon_results.items()
    }
    summary = ThesisBuilder._direction_support_summary(
        direction, statuses, verdicts
    )
    return {
        "thesis_direction": direction,
        "horizon_results": horizon_results,
        "direction_support_summary": summary,
        "evidence_ids": list(_LESSON_IDS),
        "provenance": {
            "query": dict(_QUERY),
            "sources": [
                {
                    "lesson_id": lesson_id,
                    "event_date": {
                        "CPI_GOLD_2017-07-01": "2017-07-01",
                        "CPI_GOLD_2018-02-01": "2018-02-01",
                        "CPI_GOLD_2025-05-01": "2025-05-01",
                    }[lesson_id],
                    "horizon": "1d",
                    "source_artifact_path": _SOURCE_PATH,
                    "source_artifact_sha256": _SOURCE_SHA,
                }
                for lesson_id in _LESSON_IDS
            ],
            "similarity": {
                lesson_id: {
                    "overall_similarity": 0.8123,
                    "retrieval_method": "exact",
                }
                for lesson_id in _LESSON_IDS
            },
        },
    }


def _make_thesis(
    thesis_id: str,
    direction: str,
    support: float,
    status: str = "mixed",
    with_assessment: bool = True,
) -> InvestmentThesis:
    metadata: dict = {}
    if with_assessment:
        metadata["historical_assessment"] = _assessment(direction, status)
    return InvestmentThesis(
        thesis_id=thesis_id,
        direction=direction,
        supporting_set_ids=(),
        regime=REGIME,
        economic_mechanism="test mechanism",
        time_horizon_days=90,
        invalidating_conditions=("No specific invalidating conditions identified",),
        remaining_unknowns=(),
        confidence_inputs={
            "avg_supporting_weight": support,
            "avg_supporting_consensus": round(min(support + 0.1, 1.0), 4),
            "conflict_severity": 0.0,
            "confidence_penalty": 0.0,
            "raw_support": round(support * support, 4),
        },
        institutional_support=support,
        explanation=f"test {direction} thesis",
        provenance_chain=(_PROV_W8,),
        metadata=metadata,
    )


def _make_construction(
    theses: list[InvestmentThesis], construction_id: str = "tc_034"
) -> ThesisConstruction:
    ranked = sorted(theses, key=lambda t: t.institutional_support, reverse=True)
    return ThesisConstruction(
        construction_id=construction_id,
        reasoning_id=REASONING_ID,
        assessment_id=ASSESSMENT_ID,
        timestamp=TIMESTAMP,
        regime=REGIME,
        theses=tuple(theses),
        ranked_thesis_ids=tuple(t.thesis_id for t in ranked),
        total_theses=len(theses),
        primary_thesis_id=ranked[0].thesis_id if ranked else "",
        metadata={},
    )


def _versioned(thesis: InvestmentThesis, support_delta: float = 0.02) -> InvestmentThesis:
    metadata = dict(thesis.metadata)
    metadata["thesis_version"] = 2
    metadata["previous_thesis_id"] = thesis.thesis_id
    return InvestmentThesis(
        thesis_id=f"{thesis.thesis_id}.v2",
        direction=thesis.direction,
        supporting_set_ids=thesis.supporting_set_ids,
        counter_evidence_ids=thesis.counter_evidence_ids,
        regime=thesis.regime,
        economic_mechanism=thesis.economic_mechanism,
        time_horizon_days=thesis.time_horizon_days,
        invalidating_conditions=thesis.invalidating_conditions,
        remaining_unknowns=thesis.remaining_unknowns,
        confidence_inputs=dict(thesis.confidence_inputs),
        institutional_support=round(thesis.institutional_support + support_delta, 4),
        explanation=thesis.explanation,
        provenance_chain=tuple(thesis.provenance_chain) + (_PROV_W10,),
        metadata=metadata,
    )


def _make_update(previous: InvestmentThesis, updated: InvestmentThesis) -> ThesisUpdate:
    return ThesisUpdate(
        update_id=f"update-{previous.thesis_id}-v2",
        previous_thesis_id=previous.thesis_id,
        previous_version="v1",
        new_thesis_version="v2",
        reasoning_id=REASONING_ID,
        assessment_id=ASSESSMENT_ID,
        timestamp=UPDATE_TIMESTAMP,
        updated_evidence=("ev_a",),
        confidence_delta=round(
            updated.institutional_support - previous.institutional_support, 4
        ),
        changed_assumptions=(),
        change_summary="test",
        action="no_change",
        trigger_type="periodic",
        updated_thesis=updated,
    )


def _stub_results(
    construction: ThesisConstruction | None = None,
    update: ThesisUpdate | None = None,
) -> dict:
    """Minimal results dict for the finalize boundary; mirrors the stage
    outputs `_finalize` already consumes."""
    return {
        "build_legacy_pipeline": {"decision": {"decision": "NO_TRADE"}},
        "decision_engine": {
            "decision": "NO_TRADE",
            "institutional_confidence": 0.2417,
            "metadata": {"composite_score": 0.5389},
        },
        "risk_gate": {"action": "proceed"},
        "forecast": {"model_name": "AutoARIMA"},
        "forecast_confidence": {"confidence": {"overall": 0.7}},
        "forecast_validation": {"passed": False},
        "build_context": {"current_regime": "LATE_CYCLE"},
        "risk_measures": {"var_95": 142.0},
        "position_sizing": {"position_sizing": {"target_vol": 0.15}, "risk_budget": {"method": "risk_parity"}, "status": "ok"},
        **({"thesis_construction": construction} if construction is not None else {}),
        **({"thesis_update": update} if update is not None else {}),
    }


def _finalized(results: dict) -> dict:
    return _finalize({}, results)


# =========================================================================
# Candidate coverage
# =========================================================================


class TestCandidateCoverage:
    def test_three_candidates_persisted(self) -> None:
        bullish = _make_thesis("th_bull", "bullish", 0.5, status="positive")
        bearish = _make_thesis("th_bear", "bearish", 0.4, status="negative")
        neutral = _make_thesis("th_neutral", "neutral", 0.6, status="mixed")
        construction = _make_construction([bullish, bearish, neutral])

        payload = _finalized(_stub_results(construction))

        assert "thesis_historical_assessments" in payload
        entries = payload["thesis_historical_assessments"]
        assert len(entries) == 3
        assert {e["thesis_id"] for e in entries} == {
            "th_bull", "th_bear", "th_neutral",
        }

    def test_all_directions_present(self) -> None:
        bullish = _make_thesis("th_bull", "bullish", 0.5, status="positive")
        bearish = _make_thesis("th_bear", "bearish", 0.4, status="negative")
        neutral = _make_thesis("th_neutral", "neutral", 0.6, status="mixed")
        construction = _make_construction([bullish, bearish, neutral])

        payload = _finalized(_stub_results(construction))

        by_id = {
            e["thesis_id"]: e for e in payload["thesis_historical_assessments"]
        }
        assert by_id["th_bull"]["thesis_direction"] == "bullish"
        assert by_id["th_bear"]["thesis_direction"] == "bearish"
        assert by_id["th_neutral"]["thesis_direction"] == "neutral"
        assert by_id["th_bull"]["historical_assessment"]["thesis_direction"] == (
            "bullish"
        )
        assert by_id["th_bear"]["historical_assessment"]["thesis_direction"] == (
            "bearish"
        )
        assert by_id["th_neutral"]["historical_assessment"]["thesis_direction"] == (
            "neutral"
        )

    def test_multiple_candidate_ids_preserved(self) -> None:
        theses = [
            _make_thesis(f"th_cand_{i}", "neutral", 0.3 + 0.1 * i, status="mixed")
            for i in range(4)
        ]
        construction = _make_construction(theses)

        payload = _finalized(_stub_results(construction))

        ids = [
            e["thesis_id"] for e in payload["thesis_historical_assessments"]
        ]
        assert ids == [t.thesis_id for t in construction.theses]


# =========================================================================
# Content preservation
# =========================================================================


class TestContentPreservation:
    def test_per_horizon_results_preserved(self) -> None:
        bullish = _make_thesis("th_bull", "bullish", 0.5, status="positive")
        construction = _make_construction([bullish])

        payload = _finalized(_stub_results(construction))
        entry = payload["thesis_historical_assessments"][0]

        assert entry["historical_assessment"]["horizon_results"] == (
            bullish.metadata["historical_assessment"]["horizon_results"]
        )
        assert list(entry["historical_assessment"]["horizon_results"]) == [
            "1d", "5d", "20d",
        ]
        for hk in ("1d", "5d", "20d"):
            result = entry["historical_assessment"]["horizon_results"][hk]
            assert result["status"] == "positive"
            assert result["verdict"] == "supports"

    def test_provenance_preserved(self) -> None:
        bullish = _make_thesis("th_bull", "bullish", 0.5, status="mixed")
        construction = _make_construction([bullish])

        payload = _finalized(_stub_results(construction))
        entry = payload["thesis_historical_assessments"][0]

        assert entry["historical_assessment"]["provenance"] == (
            bullish.metadata["historical_assessment"]["provenance"]
        )
        sources = entry["historical_assessment"]["provenance"]["sources"]
        assert len(sources) == 3
        for source in sources:
            assert source["source_artifact_path"] == _SOURCE_PATH
            assert source["source_artifact_sha256"] == _SOURCE_SHA

    def test_query_preserved(self) -> None:
        bullish = _make_thesis("th_bull", "bullish", 0.5, status="mixed")
        construction = _make_construction([bullish])

        payload = _finalized(_stub_results(construction))
        entry = payload["thesis_historical_assessments"][0]

        assert entry["historical_assessment"]["provenance"]["query"] == _QUERY

    def test_lesson_ids_preserved(self) -> None:
        bullish = _make_thesis("th_bull", "bullish", 0.5, status="mixed")
        construction = _make_construction([bullish])

        payload = _finalized(_stub_results(construction))
        entry = payload["thesis_historical_assessments"][0]

        assessment = entry["historical_assessment"]
        assert assessment["evidence_ids"] == list(_LESSON_IDS)
        source_ids = [s["lesson_id"] for s in assessment["provenance"]["sources"]]
        assert source_ids == list(_LESSON_IDS)

    def test_similarity_preserved(self) -> None:
        bullish = _make_thesis("th_bull", "bullish", 0.5, status="mixed")
        construction = _make_construction([bullish])

        payload = _finalized(_stub_results(construction))
        entry = payload["thesis_historical_assessments"][0]

        assert entry["historical_assessment"]["provenance"]["similarity"] == (
            bullish.metadata["historical_assessment"]["provenance"]["similarity"]
        )

    def test_direction_support_summary_preserved(self) -> None:
        bullish = _make_thesis("th_bull", "bullish", 0.5, status="positive")
        construction = _make_construction([bullish])

        payload = _finalized(_stub_results(construction))
        entry = payload["thesis_historical_assessments"][0]

        assert entry["historical_assessment"]["direction_support_summary"] == (
            bullish.metadata["historical_assessment"]["direction_support_summary"]
        )
        assert "uniform bullish confirmation" in (
            entry["historical_assessment"]["direction_support_summary"]
        )


# =========================================================================
# W10 version preservation
# =========================================================================


class TestVersionPreservation:
    def test_w10_versioned_primary_preserved(self) -> None:
        neutral = _make_thesis("th_neutral", "neutral", 0.6, status="mixed")
        bullish = _make_thesis("th_bull", "bullish", 0.5, status="positive")
        bearish = _make_thesis("th_bear", "bearish", 0.4, status="negative")
        construction = _make_construction([neutral, bullish, bearish])
        updated = _versioned(neutral)
        update = _make_update(neutral, updated)

        payload = _finalized(_stub_results(construction, update))

        entries = payload["thesis_historical_assessments"]
        by_id = {e["thesis_id"]: e for e in entries}
        assert "th_neutral.v2" in by_id
        assert "th_neutral" not in by_id
        assert {e["thesis_id"] for e in entries} == {
            "th_neutral.v2", "th_bull", "th_bear",
        }
        assert by_id["th_neutral.v2"]["thesis_direction"] == "neutral"
        assert by_id["th_neutral.v2"]["historical_assessment"] == (
            updated.metadata["historical_assessment"]
        )

    def test_splice_equals_decision_boundary(self) -> None:
        neutral = _make_thesis("th_neutral", "neutral", 0.6, status="mixed")
        bullish = _make_thesis("th_bull", "bullish", 0.5, status="positive")
        construction = _make_construction([neutral, bullish])
        updated = _versioned(neutral)
        update = _make_update(neutral, updated)

        spliced = _construction_from_update(update, construction)
        payload = _finalized(_stub_results(construction, update))

        by_id = {
            e["thesis_id"]: e for e in payload["thesis_historical_assessments"]
        }
        assert set(by_id) == {t.thesis_id for t in spliced.theses}


# =========================================================================
# Determinism and serialization
# =========================================================================


class TestSerialization:
    def test_deterministic_serialization(self) -> None:
        bullish = _make_thesis("th_bull", "bullish", 0.5, status="positive")
        bearish = _make_thesis("th_bear", "bearish", 0.4, status="negative")
        neutral = _make_thesis("th_neutral", "neutral", 0.6, status="mixed")
        construction = _make_construction([bullish, bearish, neutral])

        first = json.dumps(
            _finalized(_stub_results(construction)), indent=2, sort_keys=True
        )
        second = json.dumps(
            _finalized(_stub_results(construction)), indent=2, sort_keys=True
        )
        assert first == second

    def test_json_round_trip(self) -> None:
        bullish = _make_thesis("th_bull", "bullish", 0.5, status="positive")
        construction = _make_construction([bullish])

        payload = _finalized(_stub_results(construction))
        restored = json.loads(json.dumps(payload))

        entry = restored["thesis_historical_assessments"][0]
        assert entry["thesis_id"] == "th_bull"
        assert entry["thesis_direction"] == "bullish"
        assert entry["historical_assessment"]["thesis_direction"] == "bullish"
        assert set(entry["historical_assessment"]["horizon_results"]) == {
            "1d", "5d", "20d",
        }
        assert entry["historical_assessment"]["evidence_ids"] == list(_LESSON_IDS)
        assert (
            entry["historical_assessment"]["provenance"]["query"]
            == _QUERY
        )


# =========================================================================
# Degradation and backward compatibility
# =========================================================================


class TestDegradation:
    def test_missing_historical_assessment_no_failure(self) -> None:
        bullish = _make_thesis(
            "th_bull", "bullish", 0.5, with_assessment=False
        )
        construction = _make_construction([bullish])

        payload = _finalized(_stub_results(construction))

        entries = payload["thesis_historical_assessments"]
        assert len(entries) == 1
        assert entries[0]["thesis_id"] == "th_bull"
        assert entries[0]["historical_assessment"] is None

    def test_no_construction_omits_key(self) -> None:
        payload = _finalized(_stub_results())
        assert "thesis_historical_assessments" not in payload

    def test_stage_error_payloads_omit_key(self) -> None:
        results = _stub_results()
        results["thesis_construction"] = {"error": "missing upstream data"}
        payload = _finalized(results)
        assert "thesis_historical_assessments" not in payload

    def test_empty_thesis_set_omits_key(self) -> None:
        construction = _make_construction([])
        payload = _finalized(_stub_results(construction))
        assert "thesis_historical_assessments" not in payload

    def test_n1_backward_compatibility(self) -> None:
        single = _make_thesis("th_only", "neutral", 0.7, status="mixed")
        construction = _make_construction([single])

        payload = _finalized(_stub_results(construction))

        entries = payload["thesis_historical_assessments"]
        assert len(entries) == 1
        assert entries[0]["thesis_id"] == "th_only"
        assert entries[0]["thesis_direction"] == "neutral"
        assert entries[0]["historical_assessment"] is not None


# =========================================================================
# Numeric invariance and schema compatibility
# =========================================================================


class TestInvariance:
    def test_numeric_invariance_assessments_on_vs_off(self) -> None:
        bullish_a = _make_thesis("th_bull", "bullish", 0.5, status="positive")
        bearish_a = _make_thesis("th_bear", "bearish", 0.4, status="negative")
        neutral_a = _make_thesis("th_neutral", "neutral", 0.6, status="mixed")
        construction_a = _make_construction([bullish_a, bearish_a, neutral_a])

        bullish_b = _make_thesis(
            "th_bull", "bullish", 0.5, status="positive", with_assessment=False
        )
        bearish_b = _make_thesis(
            "th_bear", "bearish", 0.4, status="negative", with_assessment=False
        )
        neutral_b = _make_thesis(
            "th_neutral", "neutral", 0.6, status="mixed", with_assessment=False
        )
        construction_b = _make_construction([bullish_b, bearish_b, neutral_b])

        on = _finalized(_stub_results(construction_a))
        off = _finalized(_stub_results(construction_b))

        for key in _FINALIZE_KEYS:
            assert on[key] == off[key], f"numeric drift at {key}"
        assert "thesis_historical_assessments" in on
        assert "thesis_historical_assessments" in off

    def test_numeric_invariance_vs_legacy_payload(self) -> None:
        bullish = _make_thesis("th_bull", "bullish", 0.5, status="positive")
        construction = _make_construction([bullish])

        with_assessments = _finalized(_stub_results(construction))
        legacy = _finalized(_stub_results())

        for key in _FINALIZE_KEYS:
            assert with_assessments[key] == legacy[key], f"numeric drift at {key}"
        assert "thesis_historical_assessments" in with_assessments
        assert "thesis_historical_assessments" not in legacy

    def test_existing_finalize_schema_compatibility(self) -> None:
        bullish = _make_thesis("th_bull", "bullish", 0.5, status="positive")
        construction = _make_construction([bullish])

        payload = _finalized(_stub_results(construction))

        assert all(key in payload for key in _FINALIZE_KEYS)
        assert set(payload) == set(_FINALIZE_KEYS) | {
            "thesis_historical_assessments"
        }