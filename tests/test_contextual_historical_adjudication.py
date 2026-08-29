"""Correction 030: focused tests for the explanation-only contextual
historical adjudication.

Covers: context effect mapping (supportive / weakening / contradictory /
neutral), mixed and horizon-dependent history preservation, regime
precedence representation, factor-conflict representation, the causal
boundary (support is never causal proof), deterministic invalidation
conditions, clean degradation (no adjudication / no factor rationale),
provenance survival, deterministic repeated execution, JSON serialization,
thesis chunk propagation (W8) and ThesisUpdate preservation (W10), and
numeric invariance (contextual adjudication enabled vs disabled).
"""

from __future__ import annotations

import json

import pytest

from counter_evidence.assessor import CounterEvidenceAssessor
from evidence_collection.contracts import Evidence, EvidenceCollection
from evidence_reasoning.contextual_historical_adjudication import (
    EFFECT_CONTRADICTORY,
    EFFECT_NEUTRAL,
    EFFECT_SUPPORTIVE,
    EFFECT_WEAKENING,
    build_contextual_historical_adjudication,
)
from evidence_reasoning.historical_adjudication import (
    build_historical_adjudication,
)
from evidence_reasoning.reasoner import EvidenceReasoner
from knowledge.regime.constants import NORMAL_GROWTH
from thesis_construction.constructor import ThesisConstructor
from thesis_update.updater import ThesisUpdater

_SOURCE_PATH = "artifacts/lesson_episodes.json"
_SOURCE_SHA = "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"

_BASE_CONDITION = {
    "cpi_pressure": "inflation_pressure_up",
    "us10y_trend": "yields_rising",
    "dxy_trend": "dxy_falling",
}

_QUERY = {
    "event_type": "CPI",
    "condition": dict(_BASE_CONDITION),
    "institutional_context": {"regime": "INFLATIONARY"},
    "regime": "INFLATIONARY",
    "maturity_days": 20,
    "retrieval_method": "exact",
}


def _direction(ret: float) -> str:
    if ret > 0:
        return "UP"
    if ret < 0:
        return "DOWN"
    return "FLAT"


def _match(
    lesson_id: str,
    event_date: str,
    r1: float,
    r5: float,
    r20: float,
    condition: dict[str, str] | None = None,
) -> dict[str, object]:
    return {
        "lesson_id": lesson_id,
        "event_date": event_date,
        "gold_outcome": {
            "average_return_pct": r20,
            "horizon_days": 20,
            "gold_return_1d_pct": r1,
            "gold_return_5d_pct": r5,
            "gold_return_20d_pct": r20,
            "gold_direction_1d": _direction(r1),
            "gold_direction_5d": _direction(r5),
            "gold_direction_20d": _direction(r20),
            "gold_close_at_event": 1300.0,
            "anchor_gold_date": event_date,
        },
        "historical_condition": condition or dict(_BASE_CONDITION),
        "historical_regime": {"regime": "INFLATIONARY"},
        "provenance": {
            "source_artifact_path": _SOURCE_PATH,
            "source_artifact_sha256": _SOURCE_SHA,
        },
        "similarity": {
            "overall_similarity": 0.8123,
            "event_type_similarity": 1.0,
            "condition_similarity": 1.0,
            "horizon_similarity": 1.0,
            "maturity_similarity": 1.0,
            "temporal_similarity": 1.0,
            "institutional_context_similarity": 1.0,
            "retrieval_method": "exact",
        },
    }


def _payload(matches: list[dict[str, object]]) -> dict[str, object]:
    return {
        "query": dict(_QUERY),
        "match_count": len(matches),
        "matches": matches,
        "aggregate": {
            "count": len(matches),
            "avg_confidence": 1.0,
            "avg_sample_count": 1.0,
            "avg_return_pct": 0.0,
        },
    }


def _uniform_positive_payload() -> dict[str, object]:
    return _payload(
        [
            _match("EP_1", "2017-07-01", r1=1.0, r5=0.5, r20=2.0),
            _match("EP_2", "2018-02-01", r1=2.0, r5=1.0, r20=3.0),
            _match("EP_3", "2025-05-01", r1=3.0, r5=1.5, r20=4.0),
        ]
    )


def _uniform_negative_payload() -> dict[str, object]:
    return _payload(
        [
            _match("EP_1", "2017-07-01", r1=-1.0, r5=-0.5, r20=-2.0),
            _match("EP_2", "2018-02-01", r1=-2.0, r5=-1.0, r20=-3.0),
            _match("EP_3", "2025-05-01", r1=-3.0, r5=-1.5, r20=-4.0),
        ]
    )


def _mixed_payload() -> dict[str, object]:
    """Mixed cohort: every horizon contains positive and negative episodes."""
    return _payload(
        [
            _match("EP_1", "2017-07-01", r1=1.0, r5=0.3, r20=2.0),
            _match("EP_2", "2018-02-01", r1=-0.5, r5=-0.2, r20=-1.0),
            _match("EP_3", "2025-05-01", r1=0.8, r5=0.7, r20=1.0),
        ]
    )


def _horizon_dependent_payload() -> dict[str, object]:
    """Mixed at 1d, uniformly positive at 5d/20d."""
    return _payload(
        [
            _match("EP_1", "2017-07-01", r1=1.0, r5=0.3, r20=2.0),
            _match("EP_2", "2018-02-01", r1=-0.5, r5=0.5, r20=3.0),
            _match("EP_3", "2025-05-01", r1=0.8, r5=0.8, r20=4.0),
        ]
    )


def _factor_rationale(
    composite_bias: str = "strong_bullish",
    regime: str = "INFLATIONARY",
    dominant: str = "real_yield_10y",
    weaker: str = "us_dollar_index",
) -> dict[str, object]:
    if composite_bias == "strong_bearish":
        ry_bias, dxy_bias = "bearish", "bearish"
    elif composite_bias == "mixed":
        ry_bias, dxy_bias = "bullish", "bearish"
    else:
        ry_bias, dxy_bias = "bullish", "bullish"
    return {
        "rule_id": "gold_rule_001",
        "observation_date": "2026-08-19",
        "composite_bias": composite_bias,
        "composite_strength": 0.6,
        "composite_confidence": 0.7,
        "signal_dispersion": 0.1,
        "status": "ok",
        "factors": [
            {
                "factor_id": "real_yield_10y",
                "observation_date": "2026-08-19",
                "value": 1.5,
                "z_score": 0.3,
                "percentile": 0.62,
                "direction": "up",
                "influence_bias": ry_bias,
                "influence_strength": 0.5,
                "confidence": 0.8,
                "data_quality": "high",
                "status": "current",
            },
            {
                "factor_id": "us_dollar_index",
                "observation_date": "2026-08-19",
                "value": 103.0,
                "z_score": 0.2,
                "percentile": 0.58,
                "direction": "down",
                "influence_bias": dxy_bias,
                "influence_strength": 0.4,
                "confidence": 0.7,
                "data_quality": "high",
                "status": "current",
            },
        ],
        "explanation": "test factor rationale",
        "regime": regime,
        "dominant_factor": dominant,
        "weaker_factor": weaker,
        "precedence_reason": (
            f"Under {regime}, the factor hierarchy ranks {dominant} above "
            f"{weaker}."
        ),
        "adjudicated_interpretation": (
            "The conflicting signals are explained, not reweighted."
        ),
    }


def _adjudication(payload: dict[str, object]) -> dict[str, object]:
    result = build_historical_adjudication(payload)
    assert result is not None
    return result


def _collection() -> EvidenceCollection:
    return EvidenceCollection(
        collection_id="col_1",
        assessment_id="ass_1",
        timestamp="2026-08-14T00:00:00+00:00",
        regime=NORMAL_GROWTH,
        items=(
            Evidence(
                evidence_id="e1",
                source_kr_id="kr_1",
                source_kr_node_id="kr_node_1",
                event_type="CPI",
                condition={"cpi_pressure": "inflation_pressure_up"},
                bias="bullish",
                base_confidence=0.7,
                regime_weight=0.8,
                composite_weight=0.56,
                explanation="CPI pressure up",
                regime=NORMAL_GROWTH,
                source_label="knowledge",
            ),
        ),
    )


class TestContextEffect:
    def test_historical_positive_context_aligned_supportive(self) -> None:
        result = build_contextual_historical_adjudication(
            _adjudication(_uniform_positive_payload()),
            _factor_rationale(composite_bias="strong_bullish"),
            _QUERY,
        )
        assert result is not None
        assert result["historical_tendency"]["tendency"] == "positive"
        assert result["context_effect"] == EFFECT_SUPPORTIVE
        assert result["current_context"]["composite_bias"] == "strong_bullish"
        assert "supportive" in result["context_reason"]
        assert not any(
            "contradicted in the current context" in c
            for c in result["invalidation_conditions"]
        )

    def test_historical_negative_context_aligned_supportive(self) -> None:
        result = build_contextual_historical_adjudication(
            _adjudication(_uniform_negative_payload()),
            _factor_rationale(composite_bias="strong_bearish"),
            _QUERY,
        )
        assert result is not None
        assert result["historical_tendency"]["tendency"] == "negative"
        assert result["context_effect"] == EFFECT_SUPPORTIVE

    def test_historical_positive_context_opposing_contradictory(self) -> None:
        result = build_contextual_historical_adjudication(
            _adjudication(_uniform_positive_payload()),
            _factor_rationale(composite_bias="strong_bearish"),
            _QUERY,
        )
        assert result is not None
        assert result["context_effect"] == EFFECT_CONTRADICTORY
        assert any(
            "opposes the historical tendency" in c
            for c in result["invalidation_conditions"]
        )

    def test_historical_negative_context_opposing_contradictory(self) -> None:
        result = build_contextual_historical_adjudication(
            _adjudication(_uniform_negative_payload()),
            _factor_rationale(composite_bias="strong_bullish"),
            _QUERY,
        )
        assert result is not None
        assert result["context_effect"] == EFFECT_CONTRADICTORY

    def test_historical_positive_context_conflicting_weakening(self) -> None:
        result = build_contextual_historical_adjudication(
            _adjudication(_uniform_positive_payload()),
            _factor_rationale(composite_bias="mixed"),
            _QUERY,
        )
        assert result is not None
        assert result["context_effect"] == EFFECT_WEAKENING
        assert result["current_context"]["factor_conflict"] is True
        assert any(
            "cannot be confirmed by the current factor context" in c
            for c in result["invalidation_conditions"]
        )

    def test_mixed_history_remains_mixed_neutral(self) -> None:
        result = build_contextual_historical_adjudication(
            _adjudication(_mixed_payload()),
            _factor_rationale(composite_bias="strong_bullish"),
            _QUERY,
        )
        assert result is not None
        assert result["historical_tendency"]["tendency"] == "mixed"
        assert result["context_effect"] == EFFECT_NEUTRAL
        assert any(
            "ambiguous, not directional" in c
            for c in result["invalidation_conditions"]
        )
        assert "not converted into a directional label" in result["context_reason"]


class TestHorizonAssessment:
    def test_horizon_dependent_history_preserved(self) -> None:
        result = build_contextual_historical_adjudication(
            _adjudication(_horizon_dependent_payload()),
            _factor_rationale(composite_bias="strong_bullish"),
            _QUERY,
        )
        assert result is not None
        assessment = result["horizon_assessment"]
        assert assessment["horizon_dependent"] is True
        assert assessment["uniform"] is False
        assert assessment["statuses"]["1d"]["status"] == "mixed"
        assert assessment["statuses"]["5d"]["status"] == "positive"
        assert assessment["statuses"]["20d"]["status"] == "positive"
        assert result["historical_tendency"]["statuses"] == {
            "1d": "mixed",
            "5d": "positive",
            "20d": "positive",
        }
        assert "horizon-dependent" in result["overall_interpretation"]
        assert result["context_effect"] == EFFECT_NEUTRAL

    def test_uniform_history_not_horizon_dependent(self) -> None:
        result = build_contextual_historical_adjudication(
            _adjudication(_uniform_positive_payload()),
            _factor_rationale(composite_bias="strong_bullish"),
            _QUERY,
        )
        assert result is not None
        assert result["horizon_assessment"]["horizon_dependent"] is False
        assert result["horizon_assessment"]["uniform"] is True
        assert result["historical_tendency"]["horizon_dependent"] is False


class TestRegimeAndFactorContext:
    def test_regime_precedence_represented(self) -> None:
        result = build_contextual_historical_adjudication(
            _adjudication(_uniform_positive_payload()),
            _factor_rationale(composite_bias="mixed"),
            _QUERY,
        )
        assert result is not None
        regime = result["regime_context"]
        assert regime["regime"] == "INFLATIONARY"
        assert regime["dominant_factor"] == "real_yield_10y"
        assert regime["weaker_factor"] == "us_dollar_index"
        assert regime["precedence_reason"] == (
            "Under INFLATIONARY, the factor hierarchy ranks real_yield_10y "
            "above us_dollar_index."
        )
        assert "precedence ranks real_yield_10y above us_dollar_index" in (
            result["context_reason"]
        )
        assert "no reweighting" in result["overall_interpretation"]

    def test_factor_conflict_represented(self) -> None:
        result = build_contextual_historical_adjudication(
            _adjudication(_uniform_positive_payload()),
            _factor_rationale(composite_bias="mixed"),
            _QUERY,
        )
        assert result is not None
        factors = result["current_context"]["factors"]
        biases = [f["influence_bias"] for f in factors]
        assert biases == ["bullish", "bearish"]
        assert result["current_context"]["factor_conflict"] is True
        assert result["current_context"]["signal_dispersion"] == 0.1

    def test_regime_mismatch_invalidation(self) -> None:
        result = build_contextual_historical_adjudication(
            _adjudication(_uniform_positive_payload()),
            _factor_rationale(
                composite_bias="strong_bullish", regime="NORMAL_GROWTH"
            ),
            _QUERY,
        )
        assert result is not None
        assert any(
            "regime in the factor rationale differs" in c
            for c in result["invalidation_conditions"]
        )

    def test_adjudicated_query_regime_mismatch_invalidation(self) -> None:
        adjudication = _adjudication(_uniform_positive_payload())
        result = build_contextual_historical_adjudication(
            adjudication,
            _factor_rationale(composite_bias="strong_bullish"),
            {**_QUERY, "institutional_context": {"regime": "NORMAL_GROWTH"}},
        )
        assert result is not None
        assert any(
            "adjudicated query differs from the current query" in c
            for c in result["invalidation_conditions"]
        )

    def test_query_condition_mismatch_invalidation(self) -> None:
        result = build_contextual_historical_adjudication(
            _adjudication(_uniform_positive_payload()),
            _factor_rationale(composite_bias="strong_bullish"),
            {
                **_QUERY,
                "condition": {
                    "cpi_pressure": "inflation_pressure_down",
                    "us10y_trend": "yields_falling",
                    "dxy_trend": "dxy_rising",
                },
            },
        )
        assert result is not None
        assert any(
            "Current query condition differs" in c
            for c in result["invalidation_conditions"]
        )

    def test_partial_horizon_invalidation(self) -> None:
        adjudication = {
            "horizon_results": {
                "1d": {"status": "positive", "direction_summary": "positive"},
            },
            "overall_interpretation": "partial",
            "evidence_ids": ["EP_1"],
            "query": dict(_QUERY),
        }
        result = build_contextual_historical_adjudication(
            adjudication,
            _factor_rationale(composite_bias="strong_bullish"),
            _QUERY,
        )
        assert result is not None
        assert result["historical_tendency"]["tendency"] == "positive"
        assert result["context_effect"] == EFFECT_SUPPORTIVE
        assert any("partial" in c for c in result["invalidation_conditions"])

    def test_neutralized_history_invalidation(self) -> None:
        adjudication = {
            "horizon_results": {
                "1d": {"status": "neutralized", "direction_summary": "neutral"},
                "5d": {"status": "neutralized", "direction_summary": "neutral"},
                "20d": {"status": "neutralized", "direction_summary": "neutral"},
            },
            "overall_interpretation": "neutralized",
            "evidence_ids": ["EP_1", "EP_2"],
            "query": dict(_QUERY),
        }
        result = build_contextual_historical_adjudication(
            adjudication,
            _factor_rationale(composite_bias="strong_bullish"),
            _QUERY,
        )
        assert result is not None
        assert result["historical_tendency"]["tendency"] == "neutralized"
        assert result["context_effect"] == EFFECT_NEUTRAL
        assert any(
            "historical tendency is neutralized" in c
            for c in result["invalidation_conditions"]
        )


class TestCausalBoundary:
    def test_no_causal_claim(self) -> None:
        result = build_contextual_historical_adjudication(
            _adjudication(_uniform_positive_payload()),
            _factor_rationale(composite_bias="strong_bullish"),
            _QUERY,
        )
        assert result is not None
        assert "does not establish causality" in result["overall_interpretation"]
        assert "not causal proof" in result["overall_interpretation"]
        assert "supportive" in result["overall_interpretation"]
        for condition in result["invalidation_conditions"]:
            assert "does not establish causality" in condition


class TestDegradation:
    def test_no_historical_adjudication_none(self) -> None:
        rationale = _factor_rationale()
        assert build_contextual_historical_adjudication(None, rationale, _QUERY) is None
        assert build_contextual_historical_adjudication({}, rationale, _QUERY) is None
        assert (
            build_contextual_historical_adjudication(
                {"horizon_results": {}}, rationale, _QUERY
            )
            is None
        )

    def test_no_factor_rationale_none(self) -> None:
        adjudication = _adjudication(_uniform_positive_payload())
        assert build_contextual_historical_adjudication(adjudication, None, _QUERY) is None
        assert build_contextual_historical_adjudication(adjudication, {}, _QUERY) is None

    def test_reasoner_without_payload_no_contextual(self) -> None:
        reasoning = EvidenceReasoner().reason(
            _collection(), regime=NORMAL_GROWTH, historical_analogue=None
        )
        assert "contextual_historical_adjudication" not in reasoning.metadata

    def test_reasoner_without_factor_rationale_degrades(self, monkeypatch) -> None:
        import evidence_reasoning.reasoner as reasoner_module

        monkeypatch.setattr(
            reasoner_module, "build_cross_factor_rationale", lambda **_: None
        )
        reasoning = reasoner_module.EvidenceReasoner().reason(
            _collection(),
            regime=NORMAL_GROWTH,
            historical_analogue=_uniform_positive_payload(),
        )
        assert "factor_rationale" not in reasoning.metadata
        assert "contextual_historical_adjudication" not in reasoning.metadata


class TestProvenanceAndDeterminism:
    def test_provenance_preservation(self) -> None:
        adjudication = _adjudication(_uniform_positive_payload())
        result = build_contextual_historical_adjudication(
            adjudication,
            _factor_rationale(),
            _QUERY,
        )
        assert result is not None
        provenance = result["provenance"]
        assert (
            provenance["created_by"]
            == "evidence_reasoning.contextual_historical_adjudication"
        )
        assert provenance["created_at"] == ""
        assert provenance["evidence_ids"] == adjudication["evidence_ids"]
        assert (
            provenance["input_sources"]["factor_rationale_rule_id"]
            == "gold_rule_001"
        )
        assert provenance["input_sources"]["query"]["event_type"] == "CPI"
        assert result["historical_tendency"]["evidence_ids"] == (
            adjudication["evidence_ids"]
        )

    def test_deterministic_repeated_execution(self) -> None:
        first = build_contextual_historical_adjudication(
            _adjudication(_uniform_positive_payload()),
            _factor_rationale(composite_bias="mixed"),
            _QUERY,
        )
        second = build_contextual_historical_adjudication(
            _adjudication(_uniform_positive_payload()),
            _factor_rationale(composite_bias="mixed"),
            _QUERY,
        )
        assert first == second

    def test_json_serializable(self) -> None:
        result = build_contextual_historical_adjudication(
            _adjudication(_horizon_dependent_payload()),
            _factor_rationale(composite_bias="mixed"),
            _QUERY,
        )
        assert result is not None
        payload = json.dumps(result, sort_keys=True)
        assert json.loads(payload) == result


class TestThesisPropagation:
    def _reasoning(self, payload: dict[str, object] | None) -> object:
        return EvidenceReasoner().reason(
            _collection(), regime=NORMAL_GROWTH, historical_analogue=payload
        )

    def test_builder_appends_contextual_chunk(self) -> None:
        reasoning = self._reasoning(_uniform_positive_payload())
        assert "contextual_historical_adjudication" in reasoning.metadata
        assessment = CounterEvidenceAssessor().assess(reasoning)
        construction = ThesisConstructor().construct(reasoning, assessment)
        thesis = construction.primary_thesis
        assert "contextual_historical_adjudication:" in thesis.explanation
        assert thesis.explanation.index("historical_adjudication:") < (
            thesis.explanation.index("contextual_historical_adjudication:")
        )

    def test_update_preserves_contextual_chunk(self) -> None:
        reasoning = self._reasoning(_uniform_positive_payload())
        assessment = CounterEvidenceAssessor().assess(reasoning)
        construction = ThesisConstructor().construct(reasoning, assessment)
        update = ThesisUpdater().update(construction, reasoning, assessment)
        assert "contextual_historical_adjudication:" in (
            update.updated_thesis.explanation
        )
        assert update.updated_thesis.explanation.index(
            "historical_adjudication:"
        ) < update.updated_thesis.explanation.index(
            "contextual_historical_adjudication:"
        )

    def test_no_contextual_chunk_without_payload(self) -> None:
        reasoning = self._reasoning(None)
        assessment = CounterEvidenceAssessor().assess(reasoning)
        construction = ThesisConstructor().construct(reasoning, assessment)
        thesis = construction.primary_thesis
        assert "contextual_historical_adjudication:" not in thesis.explanation


class TestNumericInvariance:
    @staticmethod
    def _stable(d: object) -> object:
        """Strip time/id/provenance volatility from to_dict comparisons."""

        def clean(value: object) -> object:
            if isinstance(value, dict):
                out: dict[str, object] = {}
                for k, v in value.items():
                    if (
                        k == "provenance_chain"
                        or k == "timestamp"
                        or k == "thesis_ids"
                        or k.endswith("_ids")
                    ):
                        continue
                    if k == "probability_consistency" and isinstance(v, dict):
                        out[k] = sorted(float(x) for x in v.values())
                        continue
                    if str(k).endswith("_id"):
                        continue
                    out[str(k)] = clean(v)
                return out
            if isinstance(value, list):
                return [clean(v) for v in value]
            if isinstance(value, str):
                return __import__("re").sub(
                    r"\b(?:th_|sc_|es_|cea_|er_)[a-z0-9]{12}\b", "ID", value
                )
            return value

        return clean(d)

    def test_numeric_invariance(self) -> None:
        from confidence_engine.engine import ConfidenceEngine
        from scenario_generation.generator import ScenarioGenerator

        payload = _uniform_positive_payload()
        reasoner = EvidenceReasoner()
        with_payload = reasoner.reason(
            _collection(), regime=NORMAL_GROWTH, historical_analogue=payload
        )
        without_payload = reasoner.reason(
            _collection(), regime=NORMAL_GROWTH, historical_analogue=None
        )

        assert "historical_analogue" in with_payload.metadata
        assert "historical_adjudication" in with_payload.metadata
        assert "contextual_historical_adjudication" in with_payload.metadata
        assert "historical_analogue" not in without_payload.metadata
        assert "historical_adjudication" not in without_payload.metadata
        assert "contextual_historical_adjudication" not in without_payload.metadata

        # Run-003 repair (Phase 8): the adjudication now also feeds ONE
        # bounded HISTORICAL_MEMORY evidence item.  A uniform-positive
        # payload adds exactly one bullish memory set; every NON-memory set
        # stays numerically identical (no double counting, no weight
        # invention).
        mem_sets = [
            s
            for s in with_payload.evidence_sets
            if s.event_type == "HISTORICAL_MEMORY"
        ]
        assert len(mem_sets) == 1
        assert mem_sets[0].bias == "bullish"
        nonmem_a = [
            self._stable(s.to_dict())
            for s in with_payload.evidence_sets
            if s.event_type != "HISTORICAL_MEMORY"
        ]
        nonmem_b = [
            self._stable(s.to_dict()) for s in without_payload.evidence_sets
        ]
        assert nonmem_a == nonmem_b

        assess = CounterEvidenceAssessor()
        assessment_a = assess.assess(with_payload)
        assessment_b = assess.assess(without_payload)
        # Directional memory participates as an independent desk vote in the
        # cross-set conflict attribution.
        assert (
            assessment_a.supporting_set_ids != assessment_b.supporting_set_ids
        )

        construction_a = ThesisConstructor().construct(with_payload, assessment_a)
        construction_b = ThesisConstructor().construct(without_payload, assessment_b)
        # Shared candidates keep identical support; the memory vote may add
        # a directional candidate to FULL.
        dirs_a = {t.direction for t in construction_a.theses}
        dirs_b = {t.direction for t in construction_b.theses}
        assert dirs_b.issubset(dirs_a)
        for d in dirs_a & dirs_b:
            t_a = next(t for t in construction_a.theses if t.direction == d)
            t_b = next(t for t in construction_b.theses if t.direction == d)
            assert t_a.confidence_inputs["avg_supporting_weight"] >= t_b.confidence_inputs["avg_supporting_weight"]

        generation_a = ScenarioGenerator().generate(construction_a)
        generation_b = ScenarioGenerator().generate(construction_b)
        # Structural invariants hold in both worlds.
        for generation in (generation_a, generation_b):
            assert generation.total_scenarios == 3 * len(generation.thesis_ids)

        confidence_a = ConfidenceEngine().evaluate(
            construction_a, reasoning=with_payload, generation=generation_a
        )
        confidence_b = ConfidenceEngine().evaluate(
            construction_b, reasoning=without_payload, generation=generation_b
        )
        for conf in (confidence_a, confidence_b):
            for tc in conf.theses_confidence:
                assert 0.0 <= tc.final_confidence <= 1.0
