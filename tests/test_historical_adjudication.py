"""Correction 028: focused tests for the explanation-only historical
analogue adjudication.

Covers: three horizon groups (1d / 5d / 20d), three analogue episodes per
group, no cross-horizon mixing, LegacyReasoningEngine receiving multiple
same-event items, engine direction-conflict / neutralization where applicable,
horizon-dependent and uniform interpretations, provenance survival,
deterministic repeated execution, clean degradation when the analogue is
missing, thesis chunk propagation and ThesisUpdate preservation, and numeric
invariance (adjudication enabled vs disabled).
"""

from __future__ import annotations

import pytest

from counter_evidence.assessor import CounterEvidenceAssessor
from evidence_collection.contracts import Evidence, EvidenceCollection
from evidence_reasoning.historical_adjudication import (
    build_historical_adjudication,
)
from evidence_reasoning.reasoner import EvidenceReasoner
from knowledge.regime.constants import DEFLATIONARY_CRISIS, NORMAL_GROWTH
from scenario_generation.generator import ScenarioGenerator
from thesis_construction.constructor import ThesisConstructor
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


def _runtime_018_payload() -> dict[str, object]:
    """Real Runtime-018 exact-match cohort (CPI / INFLATIONARY)."""
    return _payload(
        [
            _match(
                "CPI_GOLD_2017-07-01",
                "2017-07-01",
                r1=0.841,
                r5=0.306,
                r20=5.664,
            ),
            _match(
                "CPI_GOLD_2018-02-01",
                "2018-02-01",
                r1=-0.574,
                r5=-0.279,
                r20=1.057,
            ),
            _match(
                "CPI_GOLD_2025-05-01",
                "2025-05-01",
                r1=1.794,
                r5=2.062,
                r20=-0.117,
            ),
        ]
    )


def _horizon_dependent_payload() -> dict[str, object]:
    return _payload(
        [
            _match("EP_1", "2017-07-01", r1=1.0, r5=0.3, r20=2.0),
            _match("EP_2", "2018-02-01", r1=-0.5, r5=0.5, r20=3.0),
            _match("EP_3", "2025-05-01", r1=0.8, r5=0.8, r20=4.0),
        ]
    )


def _uniform_payload() -> dict[str, object]:
    return _payload(
        [
            _match("EP_1", "2017-07-01", r1=1.0, r5=0.5, r20=2.0),
            _match("EP_2", "2018-02-01", r1=2.0, r5=1.0, r20=3.0),
            _match("EP_3", "2025-05-01", r1=3.0, r5=1.5, r20=4.0),
        ]
    )


def _conflict_payload(neg: float) -> dict[str, object]:
    """Two distinct (condition) groups with disagreeing directions."""
    return _payload(
        [
            _match(
                "EP_1",
                "2017-07-01",
                r1=1.0,
                r5=1.0,
                r20=1.0,
                condition=dict(_BASE_CONDITION),
            ),
            _match(
                "EP_2",
                "2018-02-01",
                r1=neg,
                r5=neg,
                r20=neg,
                condition={**_BASE_CONDITION, "dxy_trend": "dxy_flat"},
            ),
            _match(
                "EP_3",
                "2025-05-01",
                r1=neg,
                r5=neg,
                r20=neg,
                condition={**_BASE_CONDITION, "dxy_trend": "dxy_flat"},
            ),
        ]
    )


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


class TestHorizonGroups:
    def test_three_horizon_groups_created(self) -> None:
        adjudication = build_historical_adjudication(_runtime_018_payload())
        assert adjudication is not None
        assert set(adjudication["horizon_results"].keys()) == {"1d", "5d", "20d"}
        for result in adjudication["horizon_results"].values():
            assert result["count"] == 3

    def test_each_group_contains_three_episodes(self) -> None:
        adjudication = build_historical_adjudication(_runtime_018_payload())
        assert adjudication is not None
        lesson_ids = [
            "CPI_GOLD_2017-07-01",
            "CPI_GOLD_2018-02-01",
            "CPI_GOLD_2025-05-01",
        ]
        for result in adjudication["horizon_results"].values():
            assert [i["lesson_id"] for i in result["inputs"]] == lesson_ids
        assert adjudication["evidence_ids"] == lesson_ids

    def test_no_cross_horizon_mixing(self) -> None:
        adjudication = build_historical_adjudication(_runtime_018_payload())
        assert adjudication is not None
        assert adjudication["horizon_results"]["1d"]["returns_pct"] == [
            0.841,
            -0.574,
            1.794,
        ]
        assert adjudication["horizon_results"]["5d"]["returns_pct"] == [
            0.306,
            -0.279,
            2.062,
        ]
        assert adjudication["horizon_results"]["20d"]["returns_pct"] == [
            5.664,
            1.057,
            -0.117,
        ]
        assert adjudication["horizon_results"]["1d"]["directions"] == [
            "positive",
            "negative",
            "positive",
        ]
        assert adjudication["horizon_results"]["5d"]["directions"] == [
            "positive",
            "negative",
            "positive",
        ]
        assert adjudication["horizon_results"]["20d"]["directions"] == [
            "positive",
            "positive",
            "negative",
        ]

    def test_engine_receives_multiple_same_event_items(self) -> None:
        adjudication = build_historical_adjudication(_runtime_018_payload())
        assert adjudication is not None
        for result in adjudication["horizon_results"].values():
            assert "based on 3 evidence items" in result["engine_conclusion"]
            assert result["aggregation"]["count"] == 3
            assert result["aggregation"]["effective_sample_size"] == pytest.approx(
                3.0, abs=1e-2
            )
            assert result["aggregation"]["attribution"] == {"CPI": 1.0}
        assert adjudication["horizon_results"]["1d"]["aggregation"][
            "avg_return_pct"
        ] == pytest.approx(0.687, abs=1e-3)
        assert adjudication["horizon_results"]["20d"]["aggregation"][
            "avg_return_pct"
        ] == pytest.approx(2.201, abs=1e-3)


class TestConflictDetection:
    def test_direction_conflict_detected(self) -> None:
        adjudication = build_historical_adjudication(_conflict_payload(neg=-1.0))
        assert adjudication is not None
        agg = adjudication["horizon_results"]["1d"]["aggregation"]
        assert agg["direction_conflict"] is True
        assert agg["dominant_direction"] == "negative"
        assert agg["dominance_ratio"] == pytest.approx(2.0 / 3.0, abs=1e-6)
        assert adjudication["horizon_results"]["1d"]["status"] == "negative"
        assert "based on 3 evidence items" in adjudication["horizon_results"]["1d"][
            "engine_conclusion"
        ]

    def test_neutralization_below_dominance_threshold(self) -> None:
        adjudication = build_historical_adjudication(_conflict_payload(neg=-0.5))
        assert adjudication is not None
        agg = adjudication["horizon_results"]["1d"]["aggregation"]
        assert agg["direction_conflict"] is True
        assert agg["dominant_direction"] == "neutral"
        assert agg["avg_return_pct"] == 0.0
        assert adjudication["horizon_results"]["1d"]["status"] == "neutralized"


class TestInterpretation:
    def test_horizon_dependent_interpretation(self) -> None:
        adjudication = build_historical_adjudication(_horizon_dependent_payload())
        assert adjudication is not None
        results = adjudication["horizon_results"]
        assert results["1d"]["status"] == "mixed"
        assert results["5d"]["status"] == "positive"
        assert results["20d"]["status"] == "positive"
        interpretation = adjudication["overall_interpretation"]
        assert "horizon-dependent" in interpretation
        assert "mixed at 1 day" in interpretation
        assert "positive at 5 days" in interpretation
        assert "positive at 20 days" in interpretation

    def test_uniform_interpretation(self) -> None:
        adjudication = build_historical_adjudication(_uniform_payload())
        assert adjudication is not None
        interpretation = adjudication["overall_interpretation"]
        assert "consistently positive across 1 day, 5 days, 20 days" in (
            interpretation
        )
        assert "uniform" in interpretation


class TestProvenanceAndDeterminism:
    def test_provenance_survives(self) -> None:
        adjudication = build_historical_adjudication(_runtime_018_payload())
        assert adjudication is not None
        inputs = adjudication["horizon_results"]["1d"]["inputs"]
        assert len(inputs) == 3
        for entry in inputs:
            assert entry["source_artifact_path"] == _SOURCE_PATH
            assert entry["source_artifact_sha256"] == _SOURCE_SHA
            assert entry["horizon"] == "1d"
            assert entry["event_date"]
            assert entry["lesson_id"].startswith("CPI_GOLD_")
        assert adjudication["query"] == _QUERY

    def test_deterministic_repeated_execution(self) -> None:
        first = build_historical_adjudication(_runtime_018_payload())
        second = build_historical_adjudication(_runtime_018_payload())
        assert first == second


class TestDegradation:
    def test_missing_analogue_no_adjudication(self) -> None:
        assert build_historical_adjudication(None) is None
        assert build_historical_adjudication({}) is None
        assert build_historical_adjudication({"matches": []}) is None
        single = _payload([_match("EP_1", "2017-07-01", 1.0, 0.5, 2.0)])
        assert build_historical_adjudication(single) is None

        reasoning = EvidenceReasoner().reason(
            self._collection(),
            regime=NORMAL_GROWTH,
            historical_analogue=None,
        )
        assert "historical_analogue" not in reasoning.metadata
        assert "historical_adjudication" not in reasoning.metadata

        reasoning = EvidenceReasoner().reason(
            self._collection(),
            regime=NORMAL_GROWTH,
            historical_analogue=single,
        )
        assert "historical_analogue" in reasoning.metadata
        assert "historical_adjudication" not in reasoning.metadata

    @staticmethod
    def _collection() -> EvidenceCollection:
        return _collection()


class TestThesisPropagation:
    def _reasoning_with_payload(
        self, payload: dict[str, object]
    ) -> object:
        return EvidenceReasoner().reason(
            _collection(),
            regime=NORMAL_GROWTH,
            historical_analogue=payload,
        )

    def test_builder_appends_historical_adjudication(self) -> None:
        reasoning = self._reasoning_with_payload(_runtime_018_payload())
        assessment = CounterEvidenceAssessor().assess(reasoning)
        construction = ThesisConstructor().construct(reasoning, assessment)
        thesis = construction.primary_thesis
        assert "historical_analogue:" in thesis.explanation
        assert "historical_adjudication:" in thesis.explanation
        assert "1d=mixed" in thesis.explanation
        assert thesis.explanation.index("historical_analogue:") < (
            thesis.explanation.index("historical_adjudication:")
        )

    def test_update_preserves_historical_adjudication(self) -> None:
        reasoning = self._reasoning_with_payload(_runtime_018_payload())
        assessment = CounterEvidenceAssessor().assess(reasoning)
        construction = ThesisConstructor().construct(reasoning, assessment)
        update = ThesisUpdater().update(construction, reasoning, assessment)
        assert "historical_adjudication:" in update.updated_thesis.explanation
        assert "historical_analogue:" in update.updated_thesis.explanation
        assert update.updated_thesis.explanation.index(
            "historical_analogue:"
        ) < update.updated_thesis.explanation.index("historical_adjudication:")

    def test_no_adjudication_chunk_without_payload(self) -> None:
        reasoning = self._reasoning_with_payload(None)
        assessment = CounterEvidenceAssessor().assess(reasoning)
        construction = ThesisConstructor().construct(reasoning, assessment)
        thesis = construction.primary_thesis
        assert "historical_analogue:" not in thesis.explanation
        assert "historical_adjudication:" not in thesis.explanation


class TestNumericInvariance:
    @staticmethod
    def _stable(d: object) -> object:
        """Strip time/id/provenance volatility from to_dict comparisons.

        The invariance contract covers numerics only; per-run ids,
        timestamps and provenance chains legitimately differ between the two
        otherwise-identical arms.
        """

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
        payload = _runtime_018_payload()
        reasoner = EvidenceReasoner()
        with_payload = reasoner.reason(
            _collection(), regime=NORMAL_GROWTH, historical_analogue=payload
        )
        without_payload = reasoner.reason(
            _collection(), regime=NORMAL_GROWTH, historical_analogue=None
        )

        assert "historical_analogue" in with_payload.metadata
        assert "historical_adjudication" in with_payload.metadata
        assert "historical_analogue" not in without_payload.metadata
        assert "historical_adjudication" not in without_payload.metadata

        assert self._stable(with_payload.to_dict()["evidence_sets"]) == self._stable(
            without_payload.to_dict()["evidence_sets"]
        )

        assess = CounterEvidenceAssessor()
        assessment_a = assess.assess(with_payload)
        assessment_b = assess.assess(without_payload)
        assert self._stable(assessment_a.to_dict()) == self._stable(
            assessment_b.to_dict()
        )

        construction_a = ThesisConstructor().construct(with_payload, assessment_a)
        construction_b = ThesisConstructor().construct(without_payload, assessment_b)
        for t_a, t_b in zip(construction_a.theses, construction_b.theses):
            assert t_a.institutional_support == t_b.institutional_support
            assert t_a.confidence_inputs == t_b.confidence_inputs
            assert t_a.direction == t_b.direction

        generation_a = ScenarioGenerator().generate(construction_a)
        generation_b = ScenarioGenerator().generate(construction_b)
        assert self._stable(generation_a.to_dict()) == self._stable(
            generation_b.to_dict()
        )

        from confidence_engine.engine import ConfidenceEngine

        confidence_a = ConfidenceEngine().evaluate(
            construction_a, reasoning=with_payload, generation=generation_a
        )
        confidence_b = ConfidenceEngine().evaluate(
            construction_b, reasoning=without_payload, generation=generation_b
        )
        assert self._stable(confidence_a.to_dict()) == self._stable(
            confidence_b.to_dict()
        )

        risk_a = (
            assessment_a.risk_reward if hasattr(assessment_a, "risk_reward") else None
        )
        risk_b = (
            assessment_b.risk_reward if hasattr(assessment_b, "risk_reward") else None
        )
        assert risk_a == risk_b or risk_a is None