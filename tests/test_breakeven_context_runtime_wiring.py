# tests/test_breakeven_context_runtime_wiring.py

"""Regression tests for Breakeven Inflation (T5YIE) runtime wiring.

The T5YIE data layer (cached FRED CSV) already exists; these tests pin the
runtime wiring that enables it:

1. The runtime config default and the shipped runtime_config.json resolve
   ``breakeven_data_path`` to the committed T5YIE dataset.
2. The production stage ``_build_legacy_pipeline`` passes the breakeven path
   into the PipelineContext and adds the enriched ``t5yie_*`` columns to the
   institutional context, so the context reaches knowledge records and
   reasoning.
3. Backward compatibility: without a breakeven path the pipeline behaves
   exactly as before (no t5yie columns requested, no crash).
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]


def _load_module(rel_path: str, name: str):
    import importlib.util
    import sys

    spec = importlib.util.spec_from_file_location(name, ROOT / rel_path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


RUN = _load_module("run.py", "runtime_entry")


def _write_csv(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(path, index=False)


def _write_calendar(base_path: Path) -> str:
    cal_dir = base_path / "calendar"
    cal_dir.mkdir(parents=True, exist_ok=True)
    cal_path = cal_dir / "cpi_releases.csv"
    pd.DataFrame([
        {"reference_period": "2020-01-01", "release_date": "2020-01-14", "release_time": "08:30", "timezone": "US/Eastern"},
        {"reference_period": "2020-02-01", "release_date": "2020-02-01", "release_time": "08:30", "timezone": "US/Eastern"},
        {"reference_period": "2020-03-01", "release_date": "2020-03-02", "release_time": "08:30", "timezone": "US/Eastern"},
        {"reference_period": "2020-04-01", "release_date": "2020-04-01", "release_time": "08:30", "timezone": "US/Eastern"},
    ]).to_csv(cal_path, index=False)
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


def _breakeven_rows() -> list[dict]:
    return [
        {"Date": "2019-12-01", "Value": 1.40},
        {"Date": "2020-01-01", "Value": 1.60},
        {"Date": "2020-02-01", "Value": 1.90},
        {"Date": "2020-03-01", "Value": 1.80},
        {"Date": "2020-04-01", "Value": 1.85},
    ]


def _event_rows() -> list[dict]:
    return [
        {"Date": "2020-01-01", "Value": 100.0},
        {"Date": "2020-02-01", "Value": 101.0},
        {"Date": "2020-03-01", "Value": 99.0},
        {"Date": "2020-04-01", "Value": 102.0},
    ]


def _base_params(tmp_path: Path, *, with_breakeven: bool, with_dxy: bool = False, with_yield: bool = False) -> dict:
    event_path = tmp_path / "cpi.csv"
    gold_path = tmp_path / "gold.csv"
    cal_path = _write_calendar(tmp_path)
    _write_csv(event_path, _event_rows())
    _write_csv(gold_path, _gold_rows())
    output_dir = tmp_path / "output"

    params = {
        "_event": None,  # replaced below to avoid import order issues
        "data_path": str(event_path),
        "gold_path": str(gold_path),
        "gold_lessons_path": str(gold_path),
        "output_dir": str(output_dir),
        "release_calendar_path": cal_path,
        "asset": "GOLD",
        "reasoning_horizon": 5,
    }
    if with_breakeven:
        breakeven_path = tmp_path / "t5yie.csv"
        _write_csv(breakeven_path, _breakeven_rows())
        params["breakeven_data_path"] = str(breakeven_path)
    if with_dxy:
        dxy_path = tmp_path / "dxy.csv"
        _write_csv(dxy_path, [
            {"Date": "2019-12-01", "Value": 96.0},
            {"Date": "2020-01-01", "Value": 97.0},
            {"Date": "2020-02-01", "Value": 99.0},
            {"Date": "2020-03-01", "Value": 97.5},
            {"Date": "2020-04-01", "Value": 98.0},
        ])
        params["dxy_data_path"] = str(dxy_path)
    if with_yield:
        yield_path = tmp_path / "dfii10.csv"
        _write_csv(yield_path, [
            {"Date": "2019-12-01", "Value": 1.50},
            {"Date": "2020-01-01", "Value": 1.60},
            {"Date": "2020-02-01", "Value": 1.90},
            {"Date": "2020-03-01", "Value": 1.70},
            {"Date": "2020-04-01", "Value": 1.72},
        ])
        params["yield_data_path"] = str(yield_path)
    return params


# ===========================================================================
# Config gating removal
# ===========================================================================


class TestConfigGatingRemoved:
    def test_run_default_config_points_to_t5yie(self) -> None:
        assert RUN.DEFAULT_CONFIG["breakeven_data_path"] == "data/economic/T5YIE.csv"
        assert (ROOT / RUN.DEFAULT_CONFIG["breakeven_data_path"]).exists()

    def test_shipped_runtime_config_points_to_t5yie(self) -> None:
        raw = json.loads((ROOT / "runtime_config.json").read_text(encoding="utf-8"))
        assert raw["breakeven_data_path"] == "data/economic/T5YIE.csv"
        assert (ROOT / raw["breakeven_data_path"]).exists()

    def test_load_config_resolves_default_breakeven_path(self) -> None:
        config = RUN._load_config(ROOT / "runtime_config.json")
        assert config["breakeven_data_path"] == "data/economic/T5YIE.csv"


# ===========================================================================
# Production stage wiring
# ===========================================================================


class TestBuildLegacyPipelineWiring:
    def test_breakeven_path_reaches_pipeline_context(self, tmp_path: Path) -> None:
        from knowledge.events.cpi import CPIEvent
        from orchestration.stages import _build_legacy_pipeline

        params = _base_params(tmp_path, with_breakeven=True)
        params["_event"] = CPIEvent()
        result = _build_legacy_pipeline(params, {})

        pipeline = result["pipeline_result"]
        assert pipeline.context.breakeven_data_path == Path(params["breakeven_data_path"])
        assert "t5yie_level" in pipeline.context.institutional_context_columns
        assert "t5yie_trend" in pipeline.context.institutional_context_columns

    def test_breakeven_context_reaches_lessons_and_knowledge(
        self, tmp_path: Path
    ) -> None:
        from knowledge.events.cpi import CPIEvent
        from orchestration.stages import _build_legacy_pipeline

        params = _base_params(tmp_path, with_breakeven=True)
        params["_event"] = CPIEvent()
        result = _build_legacy_pipeline(params, {})

        pipeline = result["pipeline_result"]
        lessons = pipeline.lessons["dataframe"]
        assert "t5yie_level" in lessons.columns
        assert "t5yie_trend" in lessons.columns

        knowledge = pipeline.knowledge_summary
        assert knowledge["record_count"] >= 1
        records_with_context = [
            record
            for record in knowledge["records"]
            if record["institutional_context"]
        ]
        assert records_with_context, (
            "Expected knowledge records to carry the T5YIE context"
        )
        first = records_with_context[0]["institutional_context"]
        assert "t5yie_level" in first
        assert "t5yie_trend" in first

    def test_reasoning_chain_carries_breakeven_context(self, tmp_path: Path) -> None:
        from knowledge.events.cpi import CPIEvent
        from orchestration.stages import _build_legacy_pipeline

        params = _base_params(tmp_path, with_breakeven=True)
        params["_event"] = CPIEvent()
        result = _build_legacy_pipeline(params, {})

        chain = result["pipeline_result"].reasoning_chain
        assert chain is not None
        assert "breakeven" in chain.final_conclusion or any(
            "breakeven" in step.conclusion for step in chain.steps
        )

    def test_breakeven_dxy_and_yield_context_coexist(self, tmp_path: Path) -> None:
        from knowledge.events.cpi import CPIEvent
        from orchestration.stages import _build_legacy_pipeline

        params = _base_params(tmp_path, with_breakeven=True, with_dxy=True, with_yield=True)
        params["_event"] = CPIEvent()
        result = _build_legacy_pipeline(params, {})

        pipeline = result["pipeline_result"]
        assert set(pipeline.context.institutional_context_columns) == {
            "us10y_level",
            "us10y_trend",
            "dxy_level",
            "dxy_trend",
            "t5yie_level",
            "t5yie_trend",
        }
        lessons = pipeline.lessons["dataframe"]
        assert "us10y_trend" in lessons.columns
        assert "dxy_trend" in lessons.columns
        assert "t5yie_trend" in lessons.columns


# ===========================================================================
# Backward compatibility
# ===========================================================================


class TestBackwardCompatibility:
    def test_pipeline_without_breakeven_path_is_unchanged(self, tmp_path: Path) -> None:
        from knowledge.events.cpi import CPIEvent
        from orchestration.stages import _build_legacy_pipeline

        params = _base_params(tmp_path, with_breakeven=False)
        params["_event"] = CPIEvent()
        result = _build_legacy_pipeline(params, {})

        pipeline = result["pipeline_result"]
        assert pipeline.context.breakeven_data_path is None
        assert "t5yie_level" not in pipeline.context.institutional_context_columns
        lessons = pipeline.lessons["dataframe"]
        assert "t5yie_level" not in lessons.columns
        assert pipeline.decision is not None

    def test_explicit_null_breakeven_path_in_config_stays_disabled(
        self, tmp_path: Path
    ) -> None:
        from knowledge.events.cpi import CPIEvent
        from orchestration.stages import _build_legacy_pipeline

        params = _base_params(tmp_path, with_breakeven=False)
        params["breakeven_data_path"] = None
        params["_event"] = CPIEvent()
        result = _build_legacy_pipeline(params, {})

        pipeline = result["pipeline_result"]
        assert pipeline.context.breakeven_data_path is None
        assert "t5yie_level" not in pipeline.context.institutional_context_columns


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
