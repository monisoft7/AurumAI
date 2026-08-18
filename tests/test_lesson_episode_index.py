"""Correction 025: per-episode lesson temporal index.

Focused tests for the derived lesson episode index:
    lesson artifact -> TemporalIndexer/TemporalRepository
                    -> TemporalEvidenceAdapter
                    -> HistoricalSituationRetriever
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from knowledge.regime.institutional_regime_detector import ECONOMIC_REGIME_LABELS
from knowledge.reasoning.retrieval import (
    HistoricalSituationRetriever,
    SituationQuery,
)
from knowledge.temporal.adapter import TemporalEvidenceAdapter
from knowledge.temporal.lesson_index import (
    LessonEpisodeQuery,
    build_lesson_episode_index,
    load_lesson_episode_index,
    save_lesson_episode_index,
)
from knowledge.temporal.state import SOURCE_TYPE_LESSON


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


def _lesson_frame(rows: list[dict[str, object]]) -> pd.DataFrame:
    return pd.DataFrame(rows)


def _three_episode_index() -> pd.DataFrame:
    return _lesson_frame([
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


class TestEpisodeIndex:
    def test_one_lesson_one_state(self) -> None:
        indexer = build_lesson_episode_index(_lesson_frame([_lesson_row()]))
        assert indexer.entry_count() == 1

    def test_state_id_equals_lesson_id(self) -> None:
        indexer = build_lesson_episode_index(_lesson_frame([_lesson_row()]))
        state = indexer._ensure_sorted()[0]
        assert state.state_id == "CPI_GOLD_2015-03-01"
        assert state.date == "2015-03-01"
        assert state.source_type == SOURCE_TYPE_LESSON

    def test_cpi_condition_preserved(self) -> None:
        indexer = build_lesson_episode_index(_lesson_frame([_lesson_row()]))
        state = indexer._ensure_sorted()[0]
        assert state.metadata["cpi_pressure"] == "inflation_pressure_up"

    def test_gold_return_preserved(self) -> None:
        indexer = build_lesson_episode_index(_lesson_frame([_lesson_row()]))
        state = indexer._ensure_sorted()[0]
        assert state.metadata["gold_return_1d_pct"] == -0.789627
        assert state.metadata["gold_return_20d_pct"] == -1.063912
        assert state.metadata["gold_direction_1d"] == "DOWN"
        assert state.metadata["gold_close_at_event"] == 1203.099976
        assert state.metadata["anchor_gold_date"] == "2015-04-08"

    def test_us10y_trend_preserved(self) -> None:
        indexer = build_lesson_episode_index(_lesson_frame([_lesson_row()]))
        state = indexer._ensure_sorted()[0]
        assert state.metadata["us10y_trend"] == "yields_rising"

    def test_dxy_trend_preserved(self) -> None:
        indexer = build_lesson_episode_index(_lesson_frame([_lesson_row()]))
        state = indexer._ensure_sorted()[0]
        assert state.metadata["dxy_trend"] == "dxy_flat"

    @pytest.mark.parametrize(
        ("macro_regime", "expected_regime"),
        [
            ("EXPANSION", "NORMAL_GROWTH"),
            ("LATE_CYCLE", "INFLATIONARY"),
            ("RECOVERY", "STAGFLATIONARY"),
            ("CONTRACTION", "DEFLATIONARY_CRISIS"),
        ],
    )
    def test_four_state_to_six_state_mapping(
        self, macro_regime: str, expected_regime: str
    ) -> None:
        assert ECONOMIC_REGIME_LABELS[macro_regime] == expected_regime
        indexer = build_lesson_episode_index(
            _lesson_frame([_lesson_row(macro_regime=macro_regime)])
        )
        state = indexer._ensure_sorted()[0]
        assert state.metadata["regime"] == expected_regime
        assert state.metadata["macro_regime"] == macro_regime

    def test_unknown_macro_regime_omits_regime(self) -> None:
        indexer = build_lesson_episode_index(
            _lesson_frame([_lesson_row(macro_regime="UNKNOWN")])
        )
        state = indexer._ensure_sorted()[0]
        assert "regime" not in state.metadata

    def test_persist_reload_roundtrip(self, tmp_path: Path) -> None:
        indexer = build_lesson_episode_index(_three_episode_index())
        path = tmp_path / "lesson_episodes.json"
        save_lesson_episode_index(indexer, path)
        assert path.is_file()
        loaded = load_lesson_episode_index(path)
        assert loaded.entry_count() == indexer.entry_count()
        for a, b in zip(
            indexer._ensure_sorted(), loaded._ensure_sorted()
        ):
            assert a.state_id == b.state_id
            assert a.date == b.date
            assert a.source_type == b.source_type
            assert dict(a.metadata) == dict(b.metadata)

    def test_missing_optional_fields_not_fabricated(self) -> None:
        indexer = build_lesson_episode_index(
            _lesson_frame([_lesson_row(dxy_trend=None, macro_regime=None)])
        )
        state = indexer._ensure_sorted()[0]
        assert "dxy_trend" not in state.metadata
        assert "regime" not in state.metadata
        assert "macro_regime" not in state.metadata
        assert state.metadata["cpi_pressure"] == "inflation_pressure_up"

    def test_row_without_lesson_id_skipped(self) -> None:
        indexer = build_lesson_episode_index(
            _lesson_frame([_lesson_row(lesson_id=None)])
        )
        assert indexer.entry_count() == 0

    def test_deterministic_rebuild(self, tmp_path: Path) -> None:
        frame = _three_episode_index()
        csv_path = tmp_path / "lessons.csv"
        frame.to_csv(csv_path, index=False)
        first = build_lesson_episode_index(frame)
        second = build_lesson_episode_index(csv_path)
        assert [s.state_id for s in first._ensure_sorted()] == [
            s.state_id for s in second._ensure_sorted()
        ]
        for a, b in zip(
            first._ensure_sorted(), second._ensure_sorted()
        ):
            assert dict(a.metadata) == dict(b.metadata)

    def test_provenance_identity_preserved(self) -> None:
        indexer = build_lesson_episode_index(_lesson_frame([_lesson_row()]))
        state = indexer._ensure_sorted()[0]
        assert state.metadata["source_artifact_path"] == "data/economic/CPIAUCSL.csv"
        assert state.metadata["source_artifact_sha256"] == "abc123"
        assert state.metadata["release_timestamp"] == "2015-04-08T08:30:00"


class TestLessonAdapterMapping:
    def test_lesson_state_to_evidence(self) -> None:
        indexer = build_lesson_episode_index(_lesson_frame([_lesson_row()]))
        state = indexer._ensure_sorted()[0]
        ev = TemporalEvidenceAdapter().state_to_evidence(state)
        assert ev.event_type == "CPI"
        assert ev.condition == {
            "cpi_pressure": "inflation_pressure_up",
            "us10y_trend": "yields_rising",
            "dxy_trend": "dxy_flat",
        }
        assert ev.metadata["institutional_context"] == {
            "regime": "DEFLATIONARY_CRISIS"
        }
        assert ev.metadata["lesson_id"] == "CPI_GOLD_2015-03-01"
        assert ev.evidence_id == "CPI_GOLD_2015-03-01"
        assert ev.source_node_id == "temporal_lesson_CPI_GOLD_2015-03-01"
        assert ev.average_return_pct == -0.789627
        assert ev.horizon_days == 20

    def test_generic_mapping_unchanged(self) -> None:
        from knowledge.temporal.state import (
            SOURCE_TYPE_ECONOMIC,
            TemporalState,
        )

        state = TemporalState(
            "ts1", "2020-06-15", SOURCE_TYPE_ECONOMIC, "st_001",
            metadata={"k": "v"},
        )
        ev = TemporalEvidenceAdapter().state_to_evidence(state)
        assert ev.event_type == "TEMPORAL"
        assert ev.condition["source_type"] == SOURCE_TYPE_ECONOMIC
        assert ev.metadata.get("institutional_context") is None

    def test_missing_fields_leave_condition_closed(self) -> None:
        indexer = build_lesson_episode_index(
            _lesson_frame([_lesson_row(dxy_trend=None, macro_regime=None)])
        )
        state = indexer._ensure_sorted()[0]
        ev = TemporalEvidenceAdapter().state_to_evidence(state)
        assert "dxy_trend" not in ev.condition
        assert ev.metadata["institutional_context"] == {}


class TestRetrieverMatching:
    def test_multi_key_situation_query_matching(self) -> None:
        indexer = build_lesson_episode_index(_three_episode_index())
        query = LessonEpisodeQuery(indexer)
        retriever = HistoricalSituationRetriever()
        matches = retriever.retrieve(
            SituationQuery(
                event_type="CPI",
                condition={
                    "cpi_pressure": "inflation_pressure_up",
                    "us10y_trend": "yields_rising",
                    "dxy_trend": "dxy_flat",
                },
                institutional_context={"regime": "DEFLATIONARY_CRISIS"},
            ),
            query,
        )
        assert matches
        top = matches[0]
        assert top.evidence.evidence_id == "CPI_GOLD_2015-03-01"
        assert top.retrieval_method == "exact"
        assert top.condition_similarity == 1.0
        assert top.institutional_context_similarity == 1.0

    def test_only_episodes_matching_all_keys_returned(self) -> None:
        indexer = build_lesson_episode_index(_three_episode_index())
        query = LessonEpisodeQuery(indexer)
        matches = query.matching(
            event_type="CPI",
            condition={"cpi_pressure": "inflation_pressure_down"},
        )
        assert [m.evidence_id for m in matches] == ["CPI_GOLD_2015-05-01"]

    def test_cross_event_strategy_lifts_event_type(self) -> None:
        from knowledge.evidence.query import RetrievalStrategy

        indexer = build_lesson_episode_index(_three_episode_index())
        query = LessonEpisodeQuery(indexer)
        matches = query.matching(
            condition={"cpi_pressure": "inflation_pressure_up"},
            strategy=RetrievalStrategy.CROSS_EVENT,
        )
        assert len(matches) == 2