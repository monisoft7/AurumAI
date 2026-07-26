from pathlib import Path
import json
import shutil

import pandas as pd

from knowledge.lesson_summary import LessonSummaryAggregator, LessonSummaryConfig


def runtime_dir(name: str) -> Path:
    path = Path(__file__).resolve().parent / "_runtime" / name
    if path.exists():
        shutil.rmtree(path)
    path.mkdir(parents=True)
    return path


def write_lessons(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = [
        {
            "lesson_id": "CPI_GOLD_2020-01-01",
            "event_type": "CPI",
            "event_date": "2020-01-01",
            "cpi_pressure": "inflation_pressure_up",
            "gold_return_1d_pct": 1.0,
            "gold_direction_1d": "UP",
            "gold_return_5d_pct": 2.0,
            "gold_direction_5d": "UP",
            "gold_return_20d_pct": 3.0,
            "gold_direction_20d": "UP",
        },
        {
            "lesson_id": "CPI_GOLD_2020-02-01",
            "event_type": "CPI",
            "event_date": "2020-02-01",
            "cpi_pressure": "inflation_pressure_up",
            "gold_return_1d_pct": -1.0,
            "gold_direction_1d": "DOWN",
            "gold_return_5d_pct": 1.0,
            "gold_direction_5d": "UP",
            "gold_return_20d_pct": 2.0,
            "gold_direction_20d": "UP",
        },
        {
            "lesson_id": "CPI_GOLD_2020-03-01",
            "event_type": "CPI",
            "event_date": "2020-03-01",
            "cpi_pressure": "inflation_pressure_down",
            "gold_return_1d_pct": -2.0,
            "gold_direction_1d": "DOWN",
            "gold_return_5d_pct": -3.0,
            "gold_direction_5d": "DOWN",
            "gold_return_20d_pct": -4.0,
            "gold_direction_20d": "DOWN",
        },
    ]
    pd.DataFrame(rows).to_csv(path, index=False)


def test_aggregates_lessons_into_explainable_knowledge_records() -> None:
    base_path = runtime_dir("summary")
    lessons_path = base_path / "lessons.csv"
    write_lessons(lessons_path)

    aggregator = LessonSummaryAggregator(
        LessonSummaryConfig(
            lessons_path=lessons_path,
            output_path=base_path / "summary.json",
            memory_path=base_path / "memory.json",
            institutional_context=(),
        )
    )

    summary = aggregator.build()

    assert summary["knowledge_version"] == "cpi_gold_summary_v1"
    assert summary["record_count"] == 6
    up_5d = [
        record
        for record in summary["records"]
        if record["knowledge_id"] == "CPI_GOLD_inflation_pressure_up_5D"
    ][0]
    assert up_5d["sample_count"] == 2
    assert up_5d["positive_return_rate_pct"] == 100.0
    assert up_5d["average_return_pct"] == 1.5
    assert up_5d["bias"] == "gold_positive_bias"
    assert "historical lessons" in up_5d["explanation"]


def test_institutional_context_propagates_to_knowledge_records() -> None:
    base_path = runtime_dir("institutional_summary")
    lessons_path = base_path / "lessons.csv"
    lessons_path.parent.mkdir(parents=True, exist_ok=True)
    rows = [
        {
            "lesson_id": "CPI_GOLD_2020-01-01",
            "event_type": "CPI",
            "event_date": "2020-01-01",
            "cpi_pressure": "up",
            "macro_regime": "EXPANSION",
            "gold_return_1d_pct": 1.0,
            "gold_direction_1d": "UP",
            "gold_return_5d_pct": 1.0,
            "gold_direction_5d": "UP",
            "gold_return_20d_pct": 1.0,
            "gold_direction_20d": "UP",
        },
        {
            "lesson_id": "CPI_GOLD_2020-02-01",
            "event_type": "CPI",
            "event_date": "2020-02-01",
            "cpi_pressure": "up",
            "macro_regime": "EXPANSION",
            "gold_return_1d_pct": -0.5,
            "gold_direction_1d": "DOWN",
            "gold_return_5d_pct": 1.0,
            "gold_direction_5d": "UP",
            "gold_return_20d_pct": 1.0,
            "gold_direction_20d": "UP",
        },
        {
            "lesson_id": "CPI_GOLD_2020-03-01",
            "event_type": "CPI",
            "event_date": "2020-03-01",
            "cpi_pressure": "up",
            "macro_regime": "RECESSION",
            "gold_return_1d_pct": 2.0,
            "gold_direction_1d": "UP",
            "gold_return_5d_pct": 1.0,
            "gold_direction_5d": "UP",
            "gold_return_20d_pct": 1.0,
            "gold_direction_20d": "UP",
        },
    ]
    pd.DataFrame(rows).to_csv(lessons_path, index=False)

    aggregator = LessonSummaryAggregator(
        LessonSummaryConfig(
            lessons_path=lessons_path,
            output_path=base_path / "summary.json",
            institutional_context=("macro_regime",),
        )
    )
    summary = aggregator.build()
    records = summary["records"]
    assert len(records) == 3  # 1 condition group x 3 horizons
    for record in records:
        assert "institutional_context" in record
        assert isinstance(record["institutional_context"], dict)
        assert record["institutional_context"]["macro_regime"] == "EXPANSION"  # majority (2 of 3)


def test_institutional_context_empty_when_not_configured() -> None:
    base_path = runtime_dir("no_institutional_summary")
    lessons_path = base_path / "lessons.csv"
    lessons_path.parent.mkdir(parents=True, exist_ok=True)
    rows = [
        {
            "lesson_id": "CPI_GOLD_2020-01-01",
            "event_type": "CPI",
            "event_date": "2020-01-01",
            "cpi_pressure": "up",
            "gold_return_1d_pct": 1.0,
            "gold_direction_1d": "UP",
            "gold_return_5d_pct": 1.0,
            "gold_direction_5d": "UP",
            "gold_return_20d_pct": 1.0,
            "gold_direction_20d": "UP",
        },
    ]
    pd.DataFrame(rows).to_csv(lessons_path, index=False)

    aggregator = LessonSummaryAggregator(
        LessonSummaryConfig(
            lessons_path=lessons_path,
            output_path=base_path / "summary.json",
            institutional_context=(),
        )
    )
    summary = aggregator.build()
    records = summary["records"]
    assert len(records) == 3  # 1 condition group x 3 horizons
    for record in records:
        assert record["institutional_context"] == {}


def test_save_and_memory_ingestion_are_deterministic() -> None:
    base_path = runtime_dir("memory_ingestion")
    lessons_path = base_path / "lessons.csv"
    summary_path = base_path / "summary.json"
    memory_path = base_path / "memory.json"
    write_lessons(lessons_path)

    aggregator = LessonSummaryAggregator(
        LessonSummaryConfig(
            lessons_path=lessons_path,
            output_path=summary_path,
            memory_path=memory_path,
            institutional_context=(),
        )
    )

    first = aggregator.build_save_and_ingest_memory()
    second = aggregator.build_save_and_ingest_memory()
    saved_summary = json.loads(summary_path.read_text())
    memory = json.loads(memory_path.read_text())

    assert first == second
    assert saved_summary == first
    assert memory["cpi_gold_summary_v1"] == first
