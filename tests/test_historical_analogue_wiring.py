"""Correction 025-B: connect the historical gold analogue to the W-path.

Focused tests:

A. lesson index rebuild deterministic
B. SituationQuery construction from current configuration
C. HistoricalSituationRetriever consumes LessonEpisodeQuery directly
D. exact multi-key match
E. mismatch rejects appropriately
F. metadata provenance preserved
G. historical_analogue round-trip
H. empty/missing index degrades cleanly
I. ThesisBuilder appends historical analogue explanation
J. ThesisUpdate preserves it
K. NUMERIC INVARIANCE: analogue enabled vs disabled produces identical
   institutional confidence / evidence quality / counter evidence / composite
   / risk-reward / decision numerics
"""

from __future__ import annotations

from pathlib import Path

import re

import pandas as pd
import pytest

from counter_evidence.assessor import CounterEvidenceAssessor
from decision_engine.engine import DecisionEngine
from evidence_collection.contracts import Evidence, EvidenceCollection
from evidence_reasoning.contracts import EvidenceReasoning
from evidence_reasoning.historical_analogue import (
    build_historical_analogue,
    build_situation_query,
    current_context_trends,
)
from evidence_reasoning.reasoner import EvidenceReasoner
from knowledge.regime.constants import (
    DEFLATIONARY_CRISIS,
    INFLATIONARY,
    NORMAL_GROWTH,
)
from knowledge.reasoning.retrieval import HistoricalSituationRetriever
from knowledge.temporal.lesson_index import (
    LessonEpisodeQuery,
    build_lesson_episode_index,
    load_lesson_episode_index,
    rebuild_lesson_episode_index,
)
from orchestration.stages import _evidence_reasoning
from risk_reward_validation.validator import RiskRewardValidator
from scenario_generation.generator import ScenarioGenerator
from thesis_construction.builder import ThesisBuilder
from thesis_construction.constructor import ThesisConstructor
from thesis_update.updater import ThesisUpdater

REPO_ROOT = Path(__file__).resolve().parents[1]
LESSON_ARTIFACT = REPO_ROOT / "data" / "lessons" / "cpi_gold_lessons.csv"
REAL_YIELD_FILE = REPO_ROOT / "data" / "economic" / "DFII10.csv"
DXY_FILE = REPO_ROOT / "data" / "context" / "dxy" / "dxy.csv"


def _lesson_row(**overrides: object) -> dict[str, object]:
    row: dict[str, object] = {
        "lesson_id": "CPI_GOLD_2015-03-01",
        "event_date": "2015-03-01",
        "anchor_gold_date": "2015-04-08",
        "cpi_pressure": "inflation_pressure_up",
        "macro_regime": "CONTRACTION",
        "us10y_trend": "yields_rising",
        "dxy_trend": "dxy_flat",
        "gold_close_at_event": 1203.099976,
        "gold_return_1d_pct": -0.789627,
        "gold_return_5d_pct": -0.132988,
        "gold_return_20d_pct": -1.063912,
        "gold_direction_1d": "DOWN",
        "gold_direction_5d": "DOWN",
        "gold_direction_20d": "DOWN",
        "primary_horizon_days": 20,
        "release_timestamp": "2015-04-08T08:30:00",
        "source_artifact_path": "data/economic/CPIAUCSL.csv",
        "source_artifact_sha256": "abc123",
    }
    row.update(overrides)
    return row


def _three_episode_frame() -> pd.DataFrame:
    return pd.DataFrame([
        _lesson_row(),
        _lesson_row(
            lesson_id="CPI_GOLD_2015-04-01",
            event_date="2015-04-01",
            us10y_trend="yields_falling",
            dxy_trend="dxy_rising",
            macro_regime="EXPANSION",
            gold_return_1d_pct=0.5,
        ),
        _lesson_row(
            lesson_id="CPI_GOLD_2015-05-01",
            event_date="2015-05-01",
            cpi_pressure="inflation_pressure_down",
            us10y_trend="yields_flat",
            dxy_trend="dxy_falling",
            macro_regime="RECOVERY",
            gold_return_1d_pct=-0.2,
        ),
    ])


@pytest.fixture()
def episodes_json(tmp_path: Path) -> Path:
    frame = _three_episode_frame()
    csv_path = tmp_path / "lessons.csv"
    frame.to_csv(csv_path, index=False)
    index_path = tmp_path / "lesson_episodes.json"
    rebuild_lesson_episode_index(csv_path, index_path)
    return index_path


# ── A. lesson index rebuild deterministic ──────────────────────────────────

class TestRebuildDeterministic:
    def test_rebuild_is_deterministic(self, tmp_path: Path) -> None:
        frame = _three_episode_frame()
        csv_path = tmp_path / "lessons.csv"
        frame.to_csv(csv_path, index=False)

        first_path = tmp_path / "first.json"
        second_path = tmp_path / "second.json"
        first = rebuild_lesson_episode_index(csv_path, first_path)
        second = rebuild_lesson_episode_index(csv_path, second_path)

        first_loaded = load_lesson_episode_index(first_path)
        second_loaded = load_lesson_episode_index(second_path)
        assert first_loaded.entry_count() == 3
        assert [
            s.state_id for s in first_loaded._ensure_sorted()
        ] == [s.state_id for s in second_loaded._ensure_sorted()]
        for a, b in zip(first_loaded._ensure_sorted(), second_loaded._ensure_sorted()):
            assert a.date == b.date
            assert dict(a.metadata) == dict(b.metadata)
        assert [s.state_id for s in first._ensure_sorted()] == [
            s.state_id for s in second._ensure_sorted()
        ]

    def test_artifact_is_source_of_truth(self, episodes_json: Path) -> None:
        assert episodes_json.is_file()
        rebuilt = load_lesson_episode_index(episodes_json)
        assert rebuilt.entry_count() == 3
        for state in rebuilt._ensure_sorted():
            assert state.source_type == "lesson"
            assert state.state_id == state.source_id


# ── B. SituationQuery construction from current configuration ─────────────

class TestSituationQueryConstruction:
    def test_query_from_current_configuration(self) -> None:
        query = build_situation_query(
            cpi_condition={"cpi_pressure": "inflation_pressure_up"},
            trends={"us10y_trend": "yields_rising", "dxy_trend": "dxy_flat"},
            regime=DEFLATIONARY_CRISIS,
        )
        assert query.event_type == "CPI"
        assert query.condition == {
            "cpi_pressure": "inflation_pressure_up",
            "us10y_trend": "yields_rising",
            "dxy_trend": "dxy_flat",
        }
        assert query.institutional_context == {"regime": DEFLATIONARY_CRISIS}

    def test_missing_trends_shrink_condition_only(self) -> None:
        query = build_situation_query(
            cpi_condition={"cpi_pressure": "inflation_pressure_up"},
        )
        assert query is not None
        assert query.condition == {"cpi_pressure": "inflation_pressure_up"}
        assert query.institutional_context == {}

    def test_invalid_cpi_condition_rejected(self) -> None:
        assert build_situation_query(cpi_condition=None) is None
        assert build_situation_query(cpi_condition={}) is None
        assert build_situation_query(
            cpi_condition={"cpi_pressure": "unknown_value"}
        ) is None

    def test_current_context_trends_from_committed_observations(self) -> None:
        trends = current_context_trends(
            real_yield_path=REAL_YIELD_FILE,
            dxy_path=DXY_FILE,
            lookback_days=30,
            as_of_date="2015-03-01",
        )
        assert set(trends) <= {"us10y_trend", "dxy_trend"}
        if "us10y_trend" in trends:
            assert trends["us10y_trend"] in (
                "yields_rising", "yields_falling", "yields_flat",
            )
        if "dxy_trend" in trends:
            assert trends["dxy_trend"] in (
                "dxy_rising", "dxy_falling", "dxy_flat",
            )

    def test_missing_trend_files_omit_trends(self, tmp_path: Path) -> None:
        trends = current_context_trends(
            real_yield_path=tmp_path / "missing.csv",
            dxy_path=tmp_path / "missing.csv",
            as_of_date="2015-03-01",
        )
        assert trends == {}


# ── C. retriever consumes LessonEpisodeQuery directly ─────────────────────

class TestRetrieverConsumesLessonQuery:
    def test_retriever_accepts_lesson_episode_query(self, episodes_json: Path) -> None:
        indexer = load_lesson_episode_index(episodes_json)
        query_surface = LessonEpisodeQuery(indexer)
        matches = HistoricalSituationRetriever().retrieve(
            build_situation_query(
                cpi_condition={"cpi_pressure": "inflation_pressure_up"},
                trends={"us10y_trend": "yields_rising", "dxy_trend": "dxy_flat"},
                regime=DEFLATIONARY_CRISIS,
            ),
            query_surface,
        )
        assert isinstance(matches, list)
        assert matches
        assert matches[0].evidence.event_type == "CPI"


# ── D / E / F. exact match, mismatch, provenance ──────────────────────────

class TestHistoricalAnalogue:
    def test_exact_multi_key_match(self, episodes_json: Path) -> None:
        payload = build_historical_analogue(
            cpi_condition={"cpi_pressure": "inflation_pressure_up"},
            regime=DEFLATIONARY_CRISIS,
            trends={"us10y_trend": "yields_rising", "dxy_trend": "dxy_flat"},
            episodes_index_path=episodes_json,
        )
        assert payload is not None
        assert payload["match_count"] == 1
        top = payload["matches"][0]
        assert top["lesson_id"] == "CPI_GOLD_2015-03-01"
        assert top["event_date"] == "2015-03-01"
        assert top["similarity"]["condition_similarity"] == pytest.approx(1.0)
        assert top["similarity"]["institutional_context_similarity"] == pytest.approx(1.0)
        assert top["similarity"]["retrieval_method"] == "exact"
        assert top["historical_condition"] == {
            "cpi_pressure": "inflation_pressure_up",
            "us10y_trend": "yields_rising",
            "dxy_trend": "dxy_flat",
        }
        assert top["historical_regime"] == {"regime": DEFLATIONARY_CRISIS}
        assert top["gold_outcome"]["average_return_pct"] == pytest.approx(-0.789627)
        assert top["gold_outcome"]["horizon_days"] == 20
        assert top["gold_outcome"]["gold_direction_1d"] == "DOWN"
        assert top["gold_outcome"]["gold_close_at_event"] == pytest.approx(1203.099976)
        assert payload["aggregate"]["count"] == 1
        assert payload["aggregate"]["avg_return_pct"] == pytest.approx(-0.789627)
        assert payload["query"]["condition"] == {
            "cpi_pressure": "inflation_pressure_up",
            "us10y_trend": "yields_rising",
            "dxy_trend": "dxy_flat",
        }
        assert payload["query"]["institutional_context"] == {
            "regime": DEFLATIONARY_CRISIS
        }

    def test_full_configuration_mismatch_rejects(self, episodes_json: Path) -> None:
        # Genuine mismatch: no episode carries the INFLATIONARY regime, so
        # institutional-context similarity is 0 for every candidate and the
        # retriever's similarity floor excludes them all.
        payload = build_historical_analogue(
            cpi_condition={"cpi_pressure": "inflation_pressure_down"},
            regime=INFLATIONARY,
            trends={"us10y_trend": "yields_falling", "dxy_trend": "dxy_rising"},
            episodes_index_path=episodes_json,
        )
        assert payload is None

    def test_provenance_preserved(self, episodes_json: Path) -> None:
        payload = build_historical_analogue(
            cpi_condition={"cpi_pressure": "inflation_pressure_up"},
            regime=DEFLATIONARY_CRISIS,
            trends={"us10y_trend": "yields_rising", "dxy_trend": "dxy_flat"},
            episodes_index_path=episodes_json,
        )
        assert payload is not None
        prov = payload["matches"][0]["provenance"]
        assert prov["source_artifact_path"] == "data/economic/CPIAUCSL.csv"
        assert prov["source_artifact_sha256"] == "abc123"


# ── G / H. round-trip and clean degradation ────────────────────────────────

class TestRoundTripAndDegradation:
    def _collection(self) -> EvidenceCollection:
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

    def test_historical_analogue_roundtrip(self, episodes_json: Path) -> None:
        payload = build_historical_analogue(
            cpi_condition={"cpi_pressure": "inflation_pressure_up"},
            regime=DEFLATIONARY_CRISIS,
            trends={"us10y_trend": "yields_rising", "dxy_trend": "dxy_flat"},
            episodes_index_path=episodes_json,
        )
        assert payload is not None
        reasoning = EvidenceReasoner().reason(
            self._collection(), regime=NORMAL_GROWTH, historical_analogue=payload
        )
        assert reasoning.metadata["historical_analogue"] == payload

        restored = EvidenceReasoning.from_dict(reasoning.to_dict())
        assert restored.metadata["historical_analogue"] == payload

    def test_missing_index_degrades_cleanly(self, tmp_path: Path) -> None:
        assert not (tmp_path / "missing.json").exists()
        assert build_historical_analogue(
            cpi_condition={"cpi_pressure": "inflation_pressure_up"},
            episodes_index_path=tmp_path / "missing.json",
        ) is None

        reasoning = EvidenceReasoner().reason(
            self._collection(), regime=NORMAL_GROWTH, historical_analogue=None
        )
        assert "historical_analogue" not in reasoning.metadata

        construction = self._construct(reasoning)
        thesis = construction.primary_thesis
        assert "historical_analogue:" not in thesis.explanation

    def test_no_match_omits_analogue(self, episodes_json: Path) -> None:
        reasoning = EvidenceReasoner().reason(
            self._collection(), regime=NORMAL_GROWTH, historical_analogue=None
        )
        assert "historical_analogue" not in reasoning.metadata

    def _construct(self, reasoning: EvidenceReasoning):
        assessment = CounterEvidenceAssessor().assess(reasoning)
        return ThesisConstructor().construct(reasoning, assessment)


# ── I / J. thesis explanation chunk ────────────────────────────────────────

class TestThesisExplanation:
    def _reasoning_with_payload(self, episodes_json: Path) -> EvidenceReasoning:
        payload = build_historical_analogue(
            cpi_condition={"cpi_pressure": "inflation_pressure_up"},
            regime=DEFLATIONARY_CRISIS,
            trends={"us10y_trend": "yields_rising", "dxy_trend": "dxy_flat"},
            episodes_index_path=episodes_json,
        )
        assert payload is not None
        collection = EvidenceCollection(
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
        return EvidenceReasoner().reason(
            collection, regime=NORMAL_GROWTH, historical_analogue=payload
        )

    def test_builder_appends_historical_analogue(self, episodes_json: Path) -> None:
        reasoning = self._reasoning_with_payload(episodes_json)
        construction = ThesisConstructor().construct(
            reasoning, CounterEvidenceAssessor().assess(reasoning)
        )
        thesis = construction.primary_thesis
        assert "historical_analogue: 1 comparable CPI episode matched" in (
            thesis.explanation
        )
        assert "aggregate gold outcome avg -0.790% (1d)" in thesis.explanation
        assert "top=CPI_GOLD_2015-03-01" in thesis.explanation

    def test_update_preserves_historical_analogue(self, episodes_json: Path) -> None:
        reasoning = self._reasoning_with_payload(episodes_json)
        assessment = CounterEvidenceAssessor().assess(reasoning)
        construction = ThesisConstructor().construct(reasoning, assessment)
        update = ThesisUpdater().update(construction, reasoning, assessment)
        assert "historical_analogue:" in update.updated_thesis.explanation
        assert "top=CPI_GOLD_2015-03-01" in update.updated_thesis.explanation

    def test_baseline_explanation_unchanged_without_payload(self) -> None:
        collection = EvidenceCollection(
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
        reasoning = EvidenceReasoner().reason(
            collection, regime=NORMAL_GROWTH, historical_analogue=None
        )
        assert "historical_analogue" not in reasoning.metadata
        construction = ThesisConstructor().construct(
            reasoning, CounterEvidenceAssessor().assess(reasoning)
        )
        thesis = construction.primary_thesis
        assert "historical_analogue:" not in thesis.explanation


# ── W-path stage wiring ────────────────────────────────────────────────────

class TestStageWiring:
    def test_stage_wires_analogue_into_reasoning(self, episodes_json: Path) -> None:
        collection = EvidenceCollection(
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
        params = {
            "regime": NORMAL_GROWTH,
            "lesson_episodes_index_path": str(episodes_json),
            "yield_context_lookback_days": 30,
        }
        results = {
            "evidence_collection": collection,
            "build_legacy_pipeline": {
                "reasoning_condition": {"cpi_pressure": "inflation_pressure_up"},
            },
            "regime_diagnosis": {"regime": DEFLATIONARY_CRISIS},
        }
        reasoning = _evidence_reasoning(params, results)

        # The stage resolves regime as params["regime"] first (NORMAL_GROWTH),
        # so the standalone builder must mirror that precedence.
        expected = build_historical_analogue(
            cpi_condition={"cpi_pressure": "inflation_pressure_up"},
            regime=NORMAL_GROWTH,
            real_yield_path=None,
            dxy_path=None,
            episodes_index_path=episodes_json,
        )
        assert reasoning.metadata.get("historical_analogue") == expected

        if expected is not None:
            assert expected["query"]["condition"]["cpi_pressure"] == (
                "inflation_pressure_up"
            )
            assert expected["query"]["institutional_context"] == {
                "regime": NORMAL_GROWTH
            }
            assert "historical_analogue" in reasoning.metadata

    def test_stage_without_index_continues_normally(self, tmp_path: Path) -> None:
        collection = EvidenceCollection(
            collection_id="col_1",
            assessment_id="ass_1",
            timestamp="2026-08-14T00:00:00+00:00",
            regime=NORMAL_GROWTH,
        )
        params = {
            "regime": NORMAL_GROWTH,
            "lesson_episodes_index_path": str(tmp_path / "missing.json"),
        }
        results = {
            "evidence_collection": collection,
            "build_legacy_pipeline": {
                "reasoning_condition": {"cpi_pressure": "inflation_pressure_up"},
            },
        }
        reasoning = _evidence_reasoning(params, results)
        assert "historical_analogue" not in reasoning.metadata
        assert reasoning.total_evidence_items == 0


# ── K. numeric invariance ──────────────────────────────────────────────────

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
                return re.sub(
                    r"\b(?:th_|sc_|es_|cea_)[a-z0-9]{12}\b", "ID", value
                )
            return value

        return clean(d)

    def _collection(self) -> EvidenceCollection:
        items = (
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
            Evidence(
                evidence_id="e2",
                source_kr_id="kr_2",
                source_kr_node_id="kr_node_2",
                event_type="REAL_YIELD",
                condition={"real_yield_trend": "falling"},
                bias="bullish",
                base_confidence=0.6,
                regime_weight=0.7,
                composite_weight=0.42,
                explanation="Real yield falling",
                regime=NORMAL_GROWTH,
                source_label="knowledge",
            ),
        )
        return EvidenceCollection(
            collection_id="col_1",
            assessment_id="ass_1",
            timestamp="2026-08-14T00:00:00+00:00",
            regime=NORMAL_GROWTH,
            items=items,
        )

    def _arms(self, episodes_json: Path) -> tuple[EvidenceReasoning, EvidenceReasoning]:
        payload = build_historical_analogue(
            cpi_condition={"cpi_pressure": "inflation_pressure_up"},
            regime=DEFLATIONARY_CRISIS,
            trends={"us10y_trend": "yields_rising", "dxy_trend": "dxy_flat"},
            episodes_index_path=episodes_json,
        )
        assert payload is not None
        reasoner = EvidenceReasoner()
        with_payload = reasoner.reason(
            self._collection(), regime=NORMAL_GROWTH, historical_analogue=payload
        )
        without_payload = reasoner.reason(
            self._collection(), regime=NORMAL_GROWTH, historical_analogue=None
        )
        return with_payload, without_payload

    def test_numeric_invariance(self, episodes_json: Path) -> None:
        with_payload, without_payload = self._arms(episodes_json)
        assert "historical_analogue" in with_payload.metadata
        assert "historical_analogue" not in without_payload.metadata

        # evidence_sets / scores identical
        assert self._stable(with_payload.to_dict()["evidence_sets"]) == (
            self._stable(without_payload.to_dict()["evidence_sets"])
        )

        # counter evidence identical
        assess = CounterEvidenceAssessor()
        assessment_a = assess.assess(with_payload)
        assessment_b = assess.assess(without_payload)
        assert self._stable(assessment_a.to_dict()) == self._stable(
            assessment_b.to_dict()
        )

        # thesis construction numerics identical (explanation may differ)
        construction_a = ThesisConstructor().construct(with_payload, assessment_a)
        construction_b = ThesisConstructor().construct(without_payload, assessment_b)
        for t_a, t_b in zip(
            construction_a.theses, construction_b.theses
        ):
            assert t_a.institutional_support == t_b.institutional_support
            assert t_a.confidence_inputs == t_b.confidence_inputs
            assert t_a.direction == t_b.direction

        # composite / scenario / risk-reward identical
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

        validation_a = RiskRewardValidator().validate(generation_a)
        validation_b = RiskRewardValidator().validate(generation_b)
        assert self._stable(validation_a.to_dict()) == self._stable(
            validation_b.to_dict()
        )

        decision_a = DecisionEngine().decide(
            construction_a, confidence_a, generation_a, validation_a
        )
        decision_b = DecisionEngine().decide(
            construction_b, confidence_b, generation_b, validation_b
        )
        assert self._stable(decision_a.to_dict()) == self._stable(
            decision_b.to_dict()
        )

        # thesis update numerics identical (explanation carries the chunk)
        update_a = ThesisUpdater().update(
            construction_a, with_payload, assessment_a
        )
        update_b = ThesisUpdater().update(
            construction_b, without_payload, assessment_b
        )
        assert update_a.confidence_delta == update_b.confidence_delta
        assert update_a.action == update_b.action
        assert update_a.trigger_type == update_b.trigger_type
        assert (
            update_a.updated_thesis.institutional_support
            == update_b.updated_thesis.institutional_support
        )
        assert (
            update_a.updated_thesis.confidence_inputs
            == update_b.updated_thesis.confidence_inputs
        )
        assert "historical_analogue:" in update_a.updated_thesis.explanation
        assert "historical_analogue:" not in update_b.updated_thesis.explanation
        # explanations differ only by the analogue chunk
        a_expl = update_a.updated_thesis.explanation
        b_expl = update_b.updated_thesis.explanation
        cut_a = a_expl.index(" | UPDATED v")
        cut_b = b_expl.index(" | UPDATED v")
        chunk_start = a_expl.index("historical_analogue:")
        assert chunk_start < cut_a
        # same prefix, plus the standard " | " separator before the chunk
        assert a_expl[:chunk_start] == b_expl[:cut_b] + " | "
        assert a_expl[chunk_start:cut_a].startswith("historical_analogue:")
        assert a_expl[cut_a:] == b_expl[cut_b:]
