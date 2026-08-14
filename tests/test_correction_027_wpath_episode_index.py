# tests/test_correction_027_wpath_episode_index.py

"""Correction 027: the W-path episode index derives from the enriched
per-run lesson artifact produced by ``build_legacy_pipeline``.

Focused tests:

1. W6 builds the episode index from the enriched runtime lesson artifact at
   the build_legacy_pipeline boundary
2. the run-local index path is used by W6 (existing ``episodes_index_path``)
3. the global ``data/state`` index is not required for runtime correctness
4. enriched fields reach episode states (cpi_pressure, us10y/dxy/t5yie
   context, macro_regime + derived regime, provenance)
5. the 3 known edge episodes remain absent (2015-02-01, 2025-10-01,
   2026-07-01) and the boundary semantics exclude first-ref and
   insufficient-horizon rows
6. deterministic rebuild: same artifact -> identical index
7. provenance preserved on every episode
8. exact multi-key query now finds genuine analogues (Runtime-017 config)
9. stale/missing/corrupt run-local index degrades safely
10. numeric invariance: the historical analogue remains explanation/context
    only (no EvidenceWeighter / ConfidenceEngine / DecisionEngine effect)
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from unittest import mock

import pandas as pd
import pytest

from counter_evidence.assessor import CounterEvidenceAssessor
from decision_engine.engine import DecisionEngine
from evidence_collection.contracts import Evidence, EvidenceCollection
from evidence_reasoning.contracts import EvidenceReasoning
from evidence_reasoning.historical_analogue import (
    DEFAULT_EPISODES_INDEX_PATH,
    build_historical_analogue,
)
from evidence_reasoning.reasoner import EvidenceReasoner
from knowledge.regime.constants import INFLATIONARY, NORMAL_GROWTH
from knowledge.temporal.lesson_index import (
    build_lesson_episode_index,
    load_lesson_episode_index,
    save_lesson_episode_index,
)
from orchestration.stages import (
    _build_legacy_pipeline,
    _build_run_local_episode_index,
    _evidence_reasoning,
    _ingest_event,
)
from risk_reward_validation.validator import RiskRewardValidator
from scenario_generation.generator import ScenarioGenerator
from thesis_construction.constructor import ThesisConstructor
from thesis_update.updater import ThesisUpdater

ROOT = Path(__file__).resolve().parents[1]
RUNTIME_ENRICHED_ARTIFACT = (
    ROOT
    / "outputs"
    / "2026-08-14"
    / "runtime_20260814_113245"
    / "artifacts"
    / "lessons.csv"
)

KNOWN_ABSENT_EPISODES = (
    "CPI_GOLD_2015-02-01",
    "CPI_GOLD_2025-10-01",
    "CPI_GOLD_2026-07-01",
)

ENRICHED_CONTEXT_COLUMNS = (
    "cpi_pressure",
    "us10y_level",
    "us10y_trend",
    "dxy_level",
    "dxy_trend",
    "t5yie_level",
    "t5yie_trend",
    "macro_regime",
    "release_timestamp",
    "source_artifact_path",
    "source_artifact_sha256",
)


# ---------------------------------------------------------------------------
# Synthetic enriched run (mirrors the production runtime wiring)
# ---------------------------------------------------------------------------


def _write_csv(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(path, index=False)


def _write_calendar(base_path: Path) -> str:
    cal_path = base_path / "calendar" / "cpi_releases.csv"
    _write_csv(cal_path, [
        {"reference_period": "2020-01-01", "release_date": "2020-01-14", "release_time": "08:30", "timezone": "US/Eastern"},
        {"reference_period": "2020-02-01", "release_date": "2020-02-03", "release_time": "08:30", "timezone": "US/Eastern"},
        {"reference_period": "2020-03-01", "release_date": "2020-03-02", "release_time": "08:30", "timezone": "US/Eastern"},
        {"reference_period": "2020-04-01", "release_date": "2020-04-01", "release_time": "08:30", "timezone": "US/Eastern"},
    ])
    return str(cal_path)


def _gold_rows() -> list[dict]:
    rows = []
    price = 1000.0
    for i in range(60):
        d = pd.Timestamp("2020-01-31") + pd.Timedelta(days=i)
        if d.weekday() >= 5:
            continue
        rows.append({"Date": d.date().isoformat(), "Close": price})
        price += 10.0
    return rows


def _synthetic_base(base: Path) -> dict:
    _write_csv(base / "cpi.csv", [
        {"Date": "2019-12-01", "Value": 100.0},
        {"Date": "2020-01-01", "Value": 101.0},
        {"Date": "2020-02-01", "Value": 102.0},
        {"Date": "2020-03-01", "Value": 103.0},
        {"Date": "2020-04-01", "Value": 104.0},
    ])
    _write_csv(base / "gold.csv", _gold_rows())
    _write_csv(base / "dfii10.csv", [
        {"Date": "2019-12-01", "Value": 1.50},
        {"Date": "2020-01-01", "Value": 1.60},
        {"Date": "2020-02-01", "Value": 1.90},
        {"Date": "2020-03-01", "Value": 1.70},
        {"Date": "2020-04-01", "Value": 1.72},
    ])
    _write_csv(base / "dxy.csv", [
        {"Date": "2019-12-01", "Value": 96.0},
        {"Date": "2020-01-01", "Value": 97.0},
        {"Date": "2020-02-01", "Value": 99.0},
        {"Date": "2020-03-01", "Value": 97.5},
        {"Date": "2020-04-01", "Value": 98.0},
    ])
    _write_csv(base / "t5yie.csv", [
        {"Date": "2019-12-01", "Value": 1.40},
        {"Date": "2020-01-01", "Value": 1.60},
        {"Date": "2020-02-01", "Value": 1.90},
        {"Date": "2020-03-01", "Value": 1.80},
        {"Date": "2020-04-01", "Value": 1.85},
    ])
    cal_path = _write_calendar(base)
    return {
        "event_type": "CPI",
        "data_path": str(base / "cpi.csv"),
        "gold_path": str(base / "gold.csv"),
        "gold_lessons_path": str(base / "gold.csv"),
        "output_dir": str(base / "output"),
        "release_calendar_path": cal_path,
        "asset": "XAU/USD",
        "reasoning_horizon": 20,
        "yield_data_path": str(base / "dfii10.csv"),
        "dxy_data_path": str(base / "dxy.csv"),
        "breakeven_data_path": str(base / "t5yie.csv"),
    }


def _run_synthetic_legacy(base: Path) -> tuple[dict, dict]:
    params = _synthetic_base(base)
    _ingest_event(params, {})
    result = _build_legacy_pipeline(params, {})
    return params, result


@pytest.fixture(scope="session")
def synthetic_run(tmp_path_factory: pytest.TempPathFactory):
    base = tmp_path_factory.mktemp("c027_synthetic")
    params, result = _run_synthetic_legacy(base)
    return params, result, Path(params["output_dir"])


@pytest.fixture()
def enriched_runtime_index(tmp_path: Path):
    """Index built from the committed enriched runtime lesson artifact."""
    assert RUNTIME_ENRICHED_ARTIFACT.is_file(), (
        f"committed enriched runtime artifact missing: {RUNTIME_ENRICHED_ARTIFACT}"
    )
    index_path = tmp_path / "lesson_episodes.json"
    indexer = build_lesson_episode_index(RUNTIME_ENRICHED_ARTIFACT)
    save_lesson_episode_index(indexer, index_path)
    return index_path


# 1. W6 builds index from the enriched runtime lesson artifact at the boundary


class TestRunLocalIndexAtBoundary:
    def test_stage_builds_run_local_index_from_enriched_lessons(
        self, synthetic_run: tuple[dict, dict, Path]
    ) -> None:
        params, result, output_dir = synthetic_run
        lessons_csv = output_dir / "lessons.csv"
        episodes_json = output_dir / "lesson_episodes.json"

        assert lessons_csv.is_file()
        assert episodes_json.is_file()
        assert params["lesson_episodes_index_path"] == str(episodes_json)
        assert result["lesson_episodes_index_path"] == str(episodes_json)

        lessons = pd.read_csv(lessons_csv)
        assert len(lessons) >= 1
        indexer = load_lesson_episode_index(episodes_json)
        assert indexer.entry_count() == len(lessons)
        assert {s.state_id for s in indexer._ensure_sorted()} == set(
            lessons["lesson_id"]
        )

    def test_enriched_fields_reach_episode_states(
        self, synthetic_run: tuple[dict, dict, Path]
    ) -> None:
        params, result, output_dir = synthetic_run
        episodes_json = output_dir / "lesson_episodes.json"
        indexer = load_lesson_episode_index(episodes_json)
        lessons = pd.read_csv(output_dir / "lessons.csv")

        # the enriched artifact carries the full institutional context
        for col in ENRICHED_CONTEXT_COLUMNS:
            assert col in lessons.columns, f"missing enriched column {col}"

        for state in indexer._ensure_sorted():
            meta = state.metadata
            row = lessons[lessons["lesson_id"] == state.state_id].iloc[0]
            assert meta["cpi_pressure"] == row["cpi_pressure"]
            assert meta["us10y_trend"] == row["us10y_trend"]
            assert meta["dxy_trend"] == row["dxy_trend"]
            assert meta["macro_regime"] == row["macro_regime"]
            assert meta["regime"] in {
                "NORMAL_GROWTH", "INFLATIONARY", "STAGFLATIONARY",
                "DEFLATIONARY_CRISIS",
            }
            assert str(meta["source_artifact_path"]) == str(row["source_artifact_path"])
            assert str(meta["source_artifact_sha256"]) == str(row["source_artifact_sha256"])
            assert re.fullmatch(r"[0-9a-f]{64}", str(meta["source_artifact_sha256"]))
            assert str(meta["release_timestamp"]).startswith("2020-02-03") or str(
                meta["release_timestamp"]
            ).startswith("2020-03-02")

    def test_boundary_semantics_exclude_first_ref_and_insufficient_horizon(
        self, synthetic_run: tuple[dict, dict, Path]
    ) -> None:
        params, result, output_dir = synthetic_run
        lessons = pd.read_csv(output_dir / "lessons.csv")
        ids = set(lessons["lesson_id"])
        # first calendar ref has no derivable CPI delta; 2020-04-01 release
        # leaves no 20-session forward gold horizon
        assert "CPI_GOLD_2020-01-01" not in ids
        assert "CPI_GOLD_2020-04-01" not in ids
        assert {"CPI_GOLD_2020-02-01", "CPI_GOLD_2020-03-01"} <= ids

        indexer = load_lesson_episode_index(output_dir / "lesson_episodes.json")
        index_ids = {s.state_id for s in indexer._ensure_sorted()}
        assert "CPI_GOLD_2020-01-01" not in index_ids
        assert "CPI_GOLD_2020-04-01" not in index_ids

    def test_no_global_data_mutation_during_runtime_preparation(
        self, tmp_path: Path
    ) -> None:
        global_index = ROOT / "data" / "state" / "lesson_episodes.json"
        canonical_lessons = ROOT / "data" / "lessons" / "cpi_gold_lessons.csv"
        before_index = global_index.read_bytes() if global_index.is_file() else None
        before_lessons = (
            canonical_lessons.read_bytes() if canonical_lessons.is_file() else None
        )

        params, result = _run_synthetic_legacy(tmp_path)

        after_index = global_index.read_bytes() if global_index.is_file() else None
        after_lessons = (
            canonical_lessons.read_bytes() if canonical_lessons.is_file() else None
        )
        assert before_index == after_index
        assert before_lessons == after_lessons


# 2. run-local index path is used by W6


class TestW6UsesRunLocalPath:
    def test_evidence_reasoning_passes_run_local_index_path(
        self, synthetic_run: tuple[dict, dict, Path]
    ) -> None:
        params, result, output_dir = synthetic_run
        collection = EvidenceCollection(
            collection_id="col_1",
            assessment_id="ass_1",
            timestamp="2026-08-14T00:00:00+00:00",
            regime=NORMAL_GROWTH,
        )
        captured: dict = {}

        with mock.patch(
            "evidence_reasoning.historical_analogue.build_historical_analogue",
            side_effect=lambda **kwargs: captured.update(kwargs) or {
                "query": {"event_type": "CPI", "condition": {}, "institutional_context": {}},
                "match_count": 0,
                "matches": [],
                "aggregate": {},
            },
        ) as fake_builder:
            reasoning = _evidence_reasoning(params, {"evidence_collection": collection, **result})

        assert fake_builder.called
        assert captured["episodes_index_path"] == str(
            output_dir / "lesson_episodes.json"
        )
        assert reasoning is not None


# 3. global data/state index not required


class TestGlobalIndexNotRequired:
    def test_runtime_correctness_without_global_index(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        params, result = _run_synthetic_legacy(tmp_path)
        output_dir = Path(params["output_dir"])
        run_local = Path(params["lesson_episodes_index_path"])
        assert run_local.is_file()
        assert run_local == output_dir / "lesson_episodes.json"

        monkeypatch.setattr(
            "evidence_reasoning.historical_analogue.DEFAULT_EPISODES_INDEX_PATH",
            tmp_path / "missing_global.json",
        )

        # build the current configuration from the enriched artifact's own
        # values -- the exact multi-key condition the W-path would use
        lessons = pd.read_csv(output_dir / "lessons.csv")
        target = lessons[lessons["lesson_id"] == "CPI_GOLD_2020-03-01"].iloc[0]

        payload = build_historical_analogue(
            cpi_condition={"cpi_pressure": str(target["cpi_pressure"])},
            trends={
                "us10y_trend": str(target["us10y_trend"]),
                "dxy_trend": str(target["dxy_trend"]),
            },
            episodes_index_path=run_local,
        )
        assert payload is not None
        assert payload["match_count"] >= 1
        matched_ids = {m["lesson_id"] for m in payload["matches"]}
        assert "CPI_GOLD_2020-03-01" in matched_ids
        assigned = next(
            m for m in payload["matches"]
            if m["lesson_id"] == "CPI_GOLD_2020-03-01"
        )
        assert assigned["similarity"]["retrieval_method"] == "exact"
        assert assigned["similarity"]["condition_similarity"] == pytest.approx(1.0)

        # without the run-local path the (missing) global default degrades to
        # None -- the W-path simply continues without an analogue
        assert build_historical_analogue(
            cpi_condition={"cpi_pressure": "inflation_pressure_up"}
        ) is None


# 4. enriched fields reach episode states (covered above) -- 5. edge episodes


class TestEdgeEpisodesAbsent:
    def test_three_known_edge_episodes_absent_from_enriched_index(
        self, enriched_runtime_index: Path
    ) -> None:
        lessons = pd.read_csv(RUNTIME_ENRICHED_ARTIFACT)
        assert len(lessons) == 135
        for edge in KNOWN_ABSENT_EPISODES:
            assert edge not in set(lessons["lesson_id"])

        indexer = load_lesson_episode_index(enriched_runtime_index)
        index_ids = {s.state_id for s in indexer._ensure_sorted()}
        assert len(index_ids) == 135
        for edge in KNOWN_ABSENT_EPISODES:
            assert edge not in index_ids
        assert {"CPI_GOLD_2015-03-01", "CPI_GOLD_2026-06-01"} <= index_ids

    def test_enriched_artifact_carries_full_context_and_provenance_columns(
        self,
    ) -> None:
        lessons = pd.read_csv(RUNTIME_ENRICHED_ARTIFACT)
        for col in ENRICHED_CONTEXT_COLUMNS:
            assert col in lessons.columns, f"missing enriched column {col}"
        assert lessons["macro_regime"].notna().all()
        assert lessons["release_timestamp"].notna().all()
        assert lessons["source_artifact_sha256"].str.fullmatch(r"[0-9a-f]{64}").all()
        assert lessons["alignment_method"].eq(
            "first_gold_session_on_or_after_release_timestamp"
        ).all()


# 6. deterministic rebuild


class TestDeterministicRebuild:
    def test_same_artifact_yields_identical_index(self, tmp_path: Path) -> None:
        first_path = tmp_path / "first.json"
        second_path = tmp_path / "second.json"
        first = build_lesson_episode_index(RUNTIME_ENRICHED_ARTIFACT)
        second = build_lesson_episode_index(RUNTIME_ENRICHED_ARTIFACT)
        save_lesson_episode_index(first, first_path)
        save_lesson_episode_index(second, second_path)

        a = first._ensure_sorted()
        b = second._ensure_sorted()
        assert [s.state_id for s in a] == [s.state_id for s in b]
        for sa, sb in zip(a, b):
            assert sa.date == sb.date
            assert dict(sa.metadata) == dict(sb.metadata)
        assert first_path.read_bytes() == second_path.read_bytes()


# 7. provenance preserved (covered above) -- 8. genuine exact analogues


class TestGenuineExactAnalogue:
    def test_exact_multi_key_query_finds_genuine_analogues(
        self, enriched_runtime_index: Path
    ) -> None:
        payload = build_historical_analogue(
            cpi_condition={"cpi_pressure": "inflation_pressure_up"},
            regime=INFLATIONARY,
            trends={"us10y_trend": "yields_flat", "dxy_trend": "dxy_flat"},
            episodes_index_path=enriched_runtime_index,
        )
        assert payload is not None
        assert payload["match_count"] >= 1
        for match in payload["matches"]:
            sim = match["similarity"]
            assert sim["retrieval_method"] == "exact"
            assert sim["condition_similarity"] == pytest.approx(1.0)
            assert sim["institutional_context_similarity"] == pytest.approx(1.0)
            assert match["historical_regime"] == {"regime": INFLATIONARY}
            assert match["provenance"]["source_artifact_sha256"]
        # Runtime-017 configuration resolves to the known 2018 exact cluster
        assert payload["matches"][0]["lesson_id"] == "CPI_GOLD_2018-01-01"


# 9. stale / missing / corrupt index degrades safely


class TestSafeDegradation:
    def test_missing_run_local_index_continues_normally(self, tmp_path: Path) -> None:
        params, result = _run_synthetic_legacy(tmp_path)
        collection = EvidenceCollection(
            collection_id="col_1",
            assessment_id="ass_1",
            timestamp="2026-08-14T00:00:00+00:00",
            regime=NORMAL_GROWTH,
        )
        params["lesson_episodes_index_path"] = str(tmp_path / "missing.json")
        reasoning = _evidence_reasoning(
            params, {"evidence_collection": collection, **result}
        )
        assert reasoning is not None
        assert "historical_analogue" not in reasoning.metadata

    def test_corrupt_index_degrades_to_none(self, tmp_path: Path) -> None:
        corrupt = tmp_path / "corrupt.json"
        corrupt.write_text("{not valid json", encoding="utf-8")
        assert build_historical_analogue(
            cpi_condition={"cpi_pressure": "inflation_pressure_up"},
            episodes_index_path=corrupt,
        ) is None

    def test_boundary_helper_degrades_safely(self, tmp_path: Path) -> None:
        assert _build_run_local_episode_index({}) is None
        assert _build_run_local_episode_index({"output_dir": str(tmp_path)}) is None

        params = {"output_dir": str(tmp_path)}
        assert _build_run_local_episode_index(params) is None
        assert "lesson_episodes_index_path" not in params
        assert not (tmp_path / "lesson_episodes.json").exists()

        lessons = pd.DataFrame([
            {
                "lesson_id": "CPI_GOLD_2020-01-01",
                "event_date": "2020-01-01",
                "cpi_pressure": "inflation_pressure_up",
            }
        ])
        lessons.to_csv(tmp_path / "lessons.csv", index=False)
        path = _build_run_local_episode_index(params)
        assert path == str(tmp_path / "lesson_episodes.json")
        assert params["lesson_episodes_index_path"] == path
        indexer = load_lesson_episode_index(tmp_path / "lesson_episodes.json")
        assert indexer.entry_count() == 1

    def test_w6_falls_back_to_run_local_location_without_param(
        self, tmp_path: Path
    ) -> None:
        params, result = _run_synthetic_legacy(tmp_path)
        output_dir = Path(params["output_dir"])
        del params["lesson_episodes_index_path"]
        collection = EvidenceCollection(
            collection_id="col_1",
            assessment_id="ass_1",
            timestamp="2026-08-14T00:00:00+00:00",
            regime=NORMAL_GROWTH,
        )
        with mock.patch(
            "evidence_reasoning.historical_analogue.build_historical_analogue"
        ) as fake_builder:
            fake_builder.return_value = {
                "query": {"event_type": "CPI", "condition": {}, "institutional_context": {}},
                "match_count": 0,
                "matches": [],
                "aggregate": {},
            }
            _evidence_reasoning(params, {"evidence_collection": collection, **result})
        assert fake_builder.called
        assert fake_builder.call_args.kwargs["episodes_index_path"] == str(
            output_dir / "lesson_episodes.json"
        )


# payload shape: explanation/context only


class TestPayloadShape:
    def test_payload_contains_only_documented_fields(
        self, enriched_runtime_index: Path
    ) -> None:
        payload = build_historical_analogue(
            cpi_condition={"cpi_pressure": "inflation_pressure_up"},
            regime=INFLATIONARY,
            trends={"us10y_trend": "yields_flat", "dxy_trend": "dxy_flat"},
            episodes_index_path=enriched_runtime_index,
        )
        assert payload is not None
        assert set(payload) == {"query", "match_count", "matches", "aggregate"}
        entry = payload["matches"][0]
        assert set(entry) == {
            "lesson_id",
            "event_date",
            "gold_outcome",
            "historical_condition",
            "historical_regime",
            "provenance",
            "similarity",
        }
        # the analogue is explanation/context only: no weighting, confidence
        # engine, or decision engine fields anywhere in the payload
        def keys_of(value: object) -> list[str]:
            if isinstance(value, dict):
                out: list[str] = []
                for k, v in value.items():
                    out.append(str(k))
                    out.extend(keys_of(v))
                return out
            if isinstance(value, list):
                return [k for item in value for k in keys_of(item)]
            return []

        assert not any(
            "weight" in k or "decision" in k for k in keys_of(payload)
        )
        assert "confidence" not in keys_of(payload)


# 10. numeric invariance: analogue is explanation/context only


class TestNumericInvariance:
    @staticmethod
    def _stable(d: object) -> object:
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
                return re.sub(r"\b(?:th_|sc_|es_|cea_)[a-z0-9]{12}\b", "ID", value)
            return value

        return clean(d)

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

    def _payload(self, enriched_runtime_index: Path) -> dict:
        payload = build_historical_analogue(
            cpi_condition={"cpi_pressure": "inflation_pressure_up"},
            regime=INFLATIONARY,
            trends={"us10y_trend": "yields_flat", "dxy_trend": "dxy_flat"},
            episodes_index_path=enriched_runtime_index,
        )
        assert payload is not None
        return payload

    def test_analogue_changes_explanation_only(self, enriched_runtime_index: Path) -> None:
        payload = self._payload(enriched_runtime_index)
        reasoner = EvidenceReasoner()
        with_payload = reasoner.reason(
            self._collection(), regime=NORMAL_GROWTH, historical_analogue=payload
        )
        without_payload = reasoner.reason(
            self._collection(), regime=NORMAL_GROWTH, historical_analogue=None
        )

        assert "historical_analogue" in with_payload.metadata
        assert "historical_analogue" not in without_payload.metadata
        assert self._stable(with_payload.to_dict()["evidence_sets"]) == (
            self._stable(without_payload.to_dict()["evidence_sets"])
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

        update_a = ThesisUpdater().update(
            construction_a, with_payload, assessment_a
        )
        update_b = ThesisUpdater().update(
            construction_b, without_payload, assessment_b
        )
        assert update_a.confidence_delta == update_b.confidence_delta
        assert update_a.action == update_b.action
        assert (
            update_a.updated_thesis.institutional_support
            == update_b.updated_thesis.institutional_support
        )
        assert "historical_analogue:" in update_a.updated_thesis.explanation
        assert "historical_analogue:" not in update_b.updated_thesis.explanation
