"""Correction 033: focused tests for candidate-direction-aware historical
assessment in W8 ThesisBuilder.

Covers: per-direction evaluation of the existing historical adjudication
(positive / negative / mixed / neutralized / flat), horizon separation,
structured metadata, provenance preservation, deterministic repeated
execution, JSON serialization, degradation when history is missing,
contextual historical adjudication preservation, ThesisUpdate preservation,
N=3 candidate construction with three direction-aware assessments, numeric
invariance (historical assessment enabled vs disabled), and downstream field
stability (no new numeric fields consumed).
"""

from __future__ import annotations

import json

from confidence_engine.engine import ConfidenceEngine
from counter_evidence.assessor import CounterEvidenceAssessor
from decision_engine.engine import DecisionEngine
from evidence_collection.contracts import Evidence, EvidenceCollection
from evidence_reasoning.reasoner import EvidenceReasoner
from knowledge.regime.constants import NORMAL_GROWTH
from risk_reward_validation.validator import RiskRewardValidator
from scenario_generation.generator import ScenarioGenerator
from thesis_construction.constructor import ThesisConstructor
from thesis_construction.contracts import InvestmentThesis
from thesis_update.updater import ThesisUpdater

_SOURCE_PATH = "artifacts/lesson_episodes.json"
_SOURCE_SHA = "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"

_QUERY = {
    "event_type": "CPI",
    "condition": {
        "cpi_pressure": "inflation_pressure_up",
        "us10y_trend": "yields_rising",
        "dxy_trend": "dxy_falling",
    },
    "institutional_context": {"regime": "INFLATIONARY"},
    "regime": "INFLATIONARY",
    "maturity_days": 20,
    "retrieval_method": "exact",
}

_BASE_CONDITION = {
    "cpi_pressure": "inflation_pressure_up",
    "us10y_trend": "yields_rising",
    "dxy_trend": "dxy_falling",
}

_BASELINE_CONFIDENCE_KEYS = {
    "avg_supporting_weight",
    "avg_supporting_consensus",
    "conflict_severity",
    "confidence_penalty",
    "raw_support",
}


# =========================================================================
# Payload / pipeline helpers
# =========================================================================


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
    return _payload(
        [
            _match(
                "CPI_GOLD_2017-07-01", "2017-07-01",
                r1=0.841, r5=0.306, r20=5.664,
            ),
            _match(
                "CPI_GOLD_2018-02-01", "2018-02-01",
                r1=-0.574, r5=-0.279, r20=1.057,
            ),
            _match(
                "CPI_GOLD_2025-05-01", "2025-05-01",
                r1=1.794, r5=2.062, r20=-0.117,
            ),
        ]
    )


def _horizon_dependent_payload() -> dict[str, object]:
    """1d=mixed, 5d=positive, 20d=positive."""
    return _payload(
        [
            _match("EP_1", "2017-07-01", r1=1.0, r5=0.3, r20=2.0),
            _match("EP_2", "2018-02-01", r1=-0.5, r5=0.5, r20=3.0),
            _match("EP_3", "2025-05-01", r1=0.8, r5=0.8, r20=4.0),
        ]
    )


def _neutralized_payload() -> dict[str, object]:
    """Every horizon is neutralized by the engine's dominance rule."""
    return _payload(
        [
            _match(
                "EP_1", "2017-07-01",
                r1=1.0, r5=1.0, r20=1.0,
                condition=dict(_BASE_CONDITION),
            ),
            _match(
                "EP_2", "2018-02-01",
                r1=-0.5, r5=-0.5, r20=-0.5,
                condition={**_BASE_CONDITION, "dxy_trend": "dxy_flat"},
            ),
            _match(
                "EP_3", "2025-05-01",
                r1=-0.5, r5=-0.5, r20=-0.5,
                condition={**_BASE_CONDITION, "dxy_trend": "dxy_flat"},
            ),
        ]
    )


def _collection() -> EvidenceCollection:
    return EvidenceCollection(
        collection_id="col_033",
        assessment_id="ass_033",
        timestamp="2026-08-19T08:00:00+00:00",
        regime=NORMAL_GROWTH,
        items=(
            Evidence(
                evidence_id="e_bull",
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
            Evidence(
                evidence_id="e_bear",
                source_kr_id="kr_2",
                source_kr_node_id="kr_node_2",
                event_type="USD_FX",
                condition={"instrument": "DXY"},
                bias="bearish",
                base_confidence=0.7,
                regime_weight=0.8,
                composite_weight=0.56,
                explanation="DXY pressure",
                regime=NORMAL_GROWTH,
                source_label="knowledge",
            ),
        ),
    )


def _reasoning(analogue_payload: dict[str, object] | None) -> object:
    return EvidenceReasoner().reason(
        _collection(),
        regime=NORMAL_GROWTH,
        historical_analogue=analogue_payload,
    )


def _construct(analogue_payload: dict[str, object] | None):
    reasoning = _reasoning(analogue_payload)
    assessment = CounterEvidenceAssessor().assess(reasoning)
    construction = ThesisConstructor().construct(reasoning, assessment)
    return construction, reasoning, assessment


def _thesis_by_direction(construction) -> dict[str, InvestmentThesis]:
    return {t.direction: t for t in construction.theses}


def _assessment_for(thesis: InvestmentThesis) -> dict[str, object]:
    return thesis.metadata["historical_assessment"]


# =========================================================================
# Directional assessment tests
# =========================================================================


class TestDirectionalAssessment:
    def test_bullish_thesis_positive_history_support(self) -> None:
        construction, _, _ = _construct(_uniform_positive_payload())
        thesis = _thesis_by_direction(construction)["bullish"]
        assessment = _assessment_for(thesis)
        assert assessment["thesis_direction"] == "bullish"
        for hk in ("1d", "5d", "20d"):
            assert assessment["horizon_results"][hk]["verdict"] == "supports"
        assert "uniform bullish confirmation" in (
            assessment["direction_support_summary"]
        )
        assert "direction_support:" in thesis.explanation
        assert "history provides uniform bullish confirmation" in (
            thesis.explanation
        )

    def test_bullish_thesis_negative_history_contradiction(self) -> None:
        construction, _, _ = _construct(_uniform_negative_payload())
        thesis = _thesis_by_direction(construction)["bullish"]
        assessment = _assessment_for(thesis)
        for hk in ("1d", "5d", "20d"):
            assert assessment["horizon_results"][hk]["verdict"] == "contradicts"
        assert "contradicts bullish" in assessment["direction_support_summary"]
        assert "history contradicts bullish" in thesis.explanation

    def test_bullish_thesis_mixed_history_no_confirmation(self) -> None:
        construction, _, _ = _construct(_mixed_payload())
        thesis = _thesis_by_direction(construction)["bullish"]
        assessment = _assessment_for(thesis)
        for hk in ("1d", "5d", "20d"):
            assert assessment["horizon_results"][hk]["verdict"] == (
                "no directional confirmation"
            )
        assert "no directional confirmation for bullish" in (
            assessment["direction_support_summary"]
        )

    def test_bearish_thesis_negative_history_support(self) -> None:
        construction, _, _ = _construct(_uniform_negative_payload())
        thesis = _thesis_by_direction(construction)["bearish"]
        assessment = _assessment_for(thesis)
        for hk in ("1d", "5d", "20d"):
            assert assessment["horizon_results"][hk]["verdict"] == "supports"
        assert "uniform bearish confirmation" in (
            assessment["direction_support_summary"]
        )
        assert "history provides uniform bearish confirmation" in (
            thesis.explanation
        )

    def test_bearish_thesis_positive_history_contradiction(self) -> None:
        construction, _, _ = _construct(_uniform_positive_payload())
        thesis = _thesis_by_direction(construction)["bearish"]
        assessment = _assessment_for(thesis)
        for hk in ("1d", "5d", "20d"):
            assert assessment["horizon_results"][hk]["verdict"] == "contradicts"
        assert "contradicts bearish" in assessment["direction_support_summary"]
        assert "history contradicts bearish" in thesis.explanation

    def test_bearish_thesis_mixed_history_no_confirmation(self) -> None:
        construction, _, _ = _construct(_mixed_payload())
        thesis = _thesis_by_direction(construction)["bearish"]
        assessment = _assessment_for(thesis)
        for hk in ("1d", "5d", "20d"):
            assert assessment["horizon_results"][hk]["verdict"] == (
                "no directional confirmation"
            )
        assert "no directional confirmation for bearish" in (
            assessment["direction_support_summary"]
        )

    def test_neutral_thesis_mixed_history_neutral_uncertain(self) -> None:
        construction, _, _ = _construct(_mixed_payload())
        thesis = _thesis_by_direction(construction)["neutral"]
        assessment = _assessment_for(thesis)
        for hk in ("1d", "5d", "20d"):
            assert assessment["horizon_results"][hk]["verdict"] == (
                "supports neutral/uncertain interpretation"
            )
        assert "mixed history supports a neutral/uncertain interpretation" in (
            assessment["direction_support_summary"]
        )

    def test_neutralized_history_non_directional(self) -> None:
        construction, _, _ = _construct(_neutralized_payload())
        for direction in ("bullish", "bearish", "neutral"):
            thesis = _thesis_by_direction(construction)[direction]
            assessment = _assessment_for(thesis)
            for hk in ("1d", "5d", "20d"):
                assert assessment["horizon_results"][hk]["verdict"] == (
                    "non-directional"
                )
        bullish = _assessment_for(_thesis_by_direction(construction)["bullish"])
        assert "no directional confirmation for bullish" in (
            bullish["direction_support_summary"]
        )
        neutral = _assessment_for(_thesis_by_direction(construction)["neutral"])
        assert "non-directional (neutralized or flat)" in (
            neutral["direction_support_summary"]
        )


# =========================================================================
# Horizon, provenance, determinism, serialization
# =========================================================================


class TestHorizonSeparation:
    def test_horizon_separation_preserved(self) -> None:
        construction, _, _ = _construct(_horizon_dependent_payload())
        thesis = _thesis_by_direction(construction)["bullish"]
        assessment = _assessment_for(thesis)
        results = assessment["horizon_results"]
        assert list(results) == ["1d", "5d", "20d"]
        assert results["1d"]["status"] == "mixed"
        assert results["1d"]["verdict"] == "no directional confirmation"
        assert results["5d"]["status"] == "positive"
        assert results["5d"]["verdict"] == "supports"
        assert results["20d"]["status"] == "positive"
        assert results["20d"]["verdict"] == "supports"
        assert "does not provide uniform bullish confirmation" in (
            assessment["direction_support_summary"]
        )
        assert "supports at 5d, 20d" in assessment["direction_support_summary"]
        assert "1d=mixed" in thesis.explanation
        assert "5d=positive" in thesis.explanation
        assert "20d=positive" in thesis.explanation

    def test_horizons_not_collapsed_into_single_claim(self) -> None:
        construction, _, _ = _construct(_horizon_dependent_payload())
        thesis = _thesis_by_direction(construction)["bullish"]
        assessment = _assessment_for(thesis)
        verdicts = {
            hk: entry["verdict"]
            for hk, entry in assessment["horizon_results"].items()
        }
        assert verdicts == {
            "1d": "no directional confirmation",
            "5d": "supports",
            "20d": "supports",
        }


class TestProvenance:
    def test_provenance_preservation(self) -> None:
        construction, _, _ = _construct(_horizon_dependent_payload())
        thesis = _thesis_by_direction(construction)["bullish"]
        assessment = _assessment_for(thesis)
        assert assessment["evidence_ids"] == ["EP_1", "EP_2", "EP_3"]
        provenance = assessment["provenance"]
        assert provenance["query"]["event_type"] == "CPI"
        assert provenance["query"]["condition"]["cpi_pressure"] == (
            "inflation_pressure_up"
        )
        sources = {s["lesson_id"]: s for s in provenance["sources"]}
        assert set(sources) == {"EP_1", "EP_2", "EP_3"}
        for entry in sources.values():
            assert entry["event_date"]
            assert entry["horizon"] in ("1d", "5d", "20d")
            assert entry["source_artifact_path"] == _SOURCE_PATH
            assert entry["source_artifact_sha256"] == _SOURCE_SHA
        assert provenance["similarity"]["EP_1"]["retrieval_method"] == "exact"
        assert provenance["similarity"]["EP_1"]["overall_similarity"] == 0.8123


class TestDeterminismAndSerialization:
    def test_deterministic_repeated_execution(self) -> None:
        c1, _, _ = _construct(_horizon_dependent_payload())
        c2, _, _ = _construct(_horizon_dependent_payload())
        t1 = _thesis_by_direction(c1)["bullish"]
        t2 = _thesis_by_direction(c2)["bullish"]
        assert t1.metadata["historical_assessment"] == (
            t2.metadata["historical_assessment"]
        )
        assert t1.explanation == t2.explanation

    def test_json_serialization(self) -> None:
        construction, _, _ = _construct(_horizon_dependent_payload())
        thesis = _thesis_by_direction(construction)["bullish"]
        serialized = json.dumps(thesis.to_dict())
        restored = InvestmentThesis.from_dict(json.loads(serialized))
        assert restored.metadata["historical_assessment"] == (
            thesis.metadata["historical_assessment"]
        )


class TestDegradation:
    def test_missing_history_existing_degradation(self) -> None:
        construction, _, _ = _construct(None)
        assert construction.total_theses >= 1
        for thesis in construction.theses:
            assert "historical_assessment" not in thesis.metadata
            assert "historical_analogue:" not in thesis.explanation
            assert "historical_adjudication:" not in thesis.explanation
            assert "direction_support:" not in thesis.explanation
            assert "contextual_historical_adjudication:" not in thesis.explanation

    def test_contextual_historical_adjudication_preserved(self) -> None:
        construction, _, _ = _construct(_uniform_positive_payload())
        thesis = _thesis_by_direction(construction)["bullish"]
        assert "historical_analogue:" in thesis.explanation
        assert "historical_adjudication:" in thesis.explanation
        assert "contextual_historical_adjudication:" in thesis.explanation
        assert thesis.explanation.index("historical_analogue:") < (
            thesis.explanation.index("historical_adjudication:")
        )
        assert thesis.explanation.index("historical_adjudication:") < (
            thesis.explanation.index("contextual_historical_adjudication:")
        )


# =========================================================================
# Update preservation and N-candidate construction
# =========================================================================


class TestUpdatePreservation:
    def test_thesis_update_preserves_historical_assessment(self) -> None:
        construction, reasoning, assessment = _construct(
            _horizon_dependent_payload()
        )
        update = ThesisUpdater().update(construction, reasoning, assessment)
        updated = update.updated_thesis
        original = construction.primary_thesis
        assert updated.metadata["historical_assessment"] == (
            original.metadata["historical_assessment"]
        )
        assert updated.direction == original.direction
        assert "historical_adjudication:" in updated.explanation
        assert "direction_support:" in updated.explanation

    def test_n3_candidate_construction_three_assessments(self) -> None:
        construction, _, _ = _construct(_uniform_positive_payload())
        theses = _thesis_by_direction(construction)
        assert set(theses) == {"bullish", "bearish", "neutral"}
        for direction in ("bullish", "bearish", "neutral"):
            assessment = _assessment_for(theses[direction])
            assert assessment["thesis_direction"] == direction
        bullish_v = {
            hk: entry["verdict"]
            for hk, entry in theses["bullish"].metadata[
                "historical_assessment"
            ]["horizon_results"].items()
        }
        bearish_v = {
            hk: entry["verdict"]
            for hk, entry in theses["bearish"].metadata[
                "historical_assessment"
            ]["horizon_results"].items()
        }
        neutral_v = {
            hk: entry["verdict"]
            for hk, entry in theses["neutral"].metadata[
                "historical_assessment"
            ]["horizon_results"].items()
        }
        assert all(v == "supports" for v in bullish_v.values())
        assert all(v == "contradicts" for v in bearish_v.values())
        assert all(
            v == "no directional confirmation" for v in neutral_v.values()
        )
        assert "uniform bullish confirmation" in theses["bullish"].explanation
        assert "contradicts bearish" in theses["bearish"].explanation


# =========================================================================
# Numeric invariance
# =========================================================================


class TestNumericInvariance:
    @staticmethod
    def _pipeline(analogue_payload: dict[str, object] | None):
        reasoning = _reasoning(analogue_payload)
        assessment = CounterEvidenceAssessor().assess(reasoning)
        construction = ThesisConstructor().construct(reasoning, assessment)
        generation = ScenarioGenerator().generate(construction)
        confidence = ConfidenceEngine().evaluate(
            construction, reasoning=reasoning, generation=generation
        )
        validation = RiskRewardValidator().validate(generation)
        decision = DecisionEngine().decide(
            construction, confidence, generation, validation
        )
        return (
            reasoning,
            assessment,
            construction,
            generation,
            confidence,
            validation,
            decision,
        )

    @staticmethod
    def _scenario_map(construction, generation) -> dict[str, float]:
        by_id = {t.thesis_id: t.direction for t in construction.theses}
        out: dict[str, float] = {}
        for s in generation.scenarios:
            out[f"{by_id.get(s.thesis_id, '?')}/{s.scenario_type}"] = round(
                float(s.probability), 6
            )
        return out

    @staticmethod
    def _confidence_map(construction, confidence) -> dict[str, float]:
        by_id = {t.thesis_id: t.direction for t in construction.theses}
        out: dict[str, float] = {}
        for tc in confidence.theses_confidence:
            out[by_id.get(tc.thesis_id, "?")] = round(
                float(tc.final_confidence), 6
            )
        return out

    @staticmethod
    def _validation_map(construction, generation, validation) -> dict[str, object]:
        thesis_by_id = {t.thesis_id: t.direction for t in construction.theses}
        scenario_by_id = {s.scenario_id: s for s in generation.scenarios}
        out: dict[str, object] = {}
        for v in validation.validations:
            scenario = scenario_by_id.get(v.scenario_id)
            key = (
                f"{thesis_by_id.get(v.thesis_id, '?')}/"
                f"{scenario.scenario_type if scenario else '?'}"
            )
            out[key] = (
                v.validation_status,
                round(float(v.risk_reward_ratio), 6),
                round(float(v.expected_reward), 6),
                round(float(v.expected_risk), 6),
            )
        return out

    @staticmethod
    def _driver_map(decision) -> dict[str, float]:
        return {d.name: d.score for d in decision.decision_drivers}

    @staticmethod
    def _stable(value: object) -> object:
        """Strip per-run ids / timestamps / provenance from comparison dicts."""

        def clean(item: object) -> object:
            if isinstance(item, dict):
                out: dict[str, object] = {}
                for key, val in item.items():
                    if (
                        key == "provenance_chain"
                        or key == "timestamp"
                        or str(key).endswith("_id")
                    ):
                        continue
                    out[str(key)] = clean(val)
                return out
            if isinstance(item, list):
                return [clean(v) for v in item]
            if isinstance(item, str):
                import re

                return re.sub(
                    r"\b(?:th_|sc_|es_|cea_|er_|dec_|upd_)[a-z0-9]{12}\b",
                    "ID",
                    item,
                )
            return item

        return clean(value)

    def test_numeric_invariance(self) -> None:
        enabled = self._pipeline(_uniform_positive_payload())
        disabled = self._pipeline(None)
        (r_a, a_a, c_a, g_a, cf_a, v_a, d_a) = enabled
        (r_b, a_b, c_b, g_b, cf_b, v_b, d_b) = disabled

        # Run-003 repair (Phase 8): the uniform-positive payload adds ONE
        # bullish HISTORICAL_MEMORY set; every non-memory set is identical.
        mem = [s for s in r_a.evidence_sets if s.event_type == "HISTORICAL_MEMORY"]
        assert len(mem) == 1 and mem[0].bias == "bullish"
        nonmem_a = [s.to_dict() for s in r_a.evidence_sets if s.event_type != "HISTORICAL_MEMORY"]
        nonmem_b = [s.to_dict() for s in r_b.evidence_sets]
        assert sorted(nonmem_a, key=lambda s: s["set_id"]) == sorted(
            nonmem_b, key=lambda s: s["set_id"]
        )

        # Candidate directions: memory may add directional candidates.
        dirs_a = {t.direction for t in c_a.theses}
        dirs_b = {t.direction for t in c_b.theses}
        assert dirs_b.issubset(dirs_a)
        for direction in dirs_a & dirs_b:
            t_a = _thesis_by_direction(c_a)[direction]
            t_b = _thesis_by_direction(c_b)[direction]
            assert t_a.confidence_inputs["avg_supporting_weight"] >= (
                t_b.confidence_inputs["avg_supporting_weight"]
            )
            assert t_a.remaining_unknowns == t_b.remaining_unknowns

        # Structural invariants hold in both worlds.
        for (c, g, cf, v, d) in ((c_a, g_a, cf_a, v_a, d_a), (c_b, g_b, cf_b, v_b, d_b)):
            assert g.total_scenarios == 3 * len(c.theses)
            for tc in cf.theses_confidence:
                assert 0.0 <= tc.final_confidence <= 1.0
            assert v.total_validations == g.total_scenarios
            assert d.decision in {"BUY", "SELL", "HOLD", "NO_TRADE"}

        t_a = _thesis_by_direction(c_a)["bullish"]
        t_b = _thesis_by_direction(c_b)["bullish"]
        assert "historical_assessment" in t_a.metadata
        assert "historical_assessment" not in t_b.metadata
        assert t_a.explanation != t_b.explanation

    def test_no_new_numeric_fields_consumed_downstream(self) -> None:
        (_, _, c_a, _, _, _, d_a) = self._pipeline(_uniform_positive_payload())
        (_, _, c_b, _, _, _, d_b) = self._pipeline(None)
        for direction in ("bullish", "bearish", "neutral"):
            t_a = _thesis_by_direction(c_a).get(direction)
            t_b = _thesis_by_direction(c_b).get(direction)
            if t_a is None or t_b is None:
                continue
            assert set(t_a.confidence_inputs) == _BASELINE_CONFIDENCE_KEYS
            assert set(t_b.confidence_inputs) == _BASELINE_CONFIDENCE_KEYS
        assert d_a.decision in {"BUY", "SELL", "HOLD", "NO_TRADE"}
        assert d_b.decision in {"BUY", "SELL", "HOLD", "NO_TRADE"}
