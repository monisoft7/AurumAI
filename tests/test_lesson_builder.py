from pathlib import Path
import shutil

import pandas as pd

from knowledge.builders.lesson_builder import LessonBuilder, LessonBuilderConfig


def runtime_dir(name: str) -> Path:
    path = Path(__file__).resolve().parent / "_runtime" / name
    if path.exists():
        shutil.rmtree(path)
    path.mkdir(parents=True)
    return path


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(path, index=False)


def build_fixture(base_path: Path) -> LessonBuilder:
    cpi_path = base_path / "economic" / "CPIAUCSL.csv"
    gold_path = base_path / "history" / "gold.csv"
    output_path = base_path / "lessons" / "cpi_gold_lessons.csv"

    write_csv(
        cpi_path,
        [
            {"Date": "2020-01-01", "Value": 100.0},
            {"Date": "2020-02-01", "Value": 101.0},
            {"Date": "2020-03-01", "Value": 99.0},
        ],
    )
    write_csv(
        gold_path,
        [
            {"Date": "2020-01-31", "Close": 1000.0},
            {"Date": "2020-02-03", "Close": 1010.0},
            {"Date": "2020-02-04", "Close": 1020.0},
            {"Date": "2020-02-05", "Close": 1030.0},
            {"Date": "2020-02-06", "Close": 1040.0},
            {"Date": "2020-02-07", "Close": 1050.0},
            {"Date": "2020-02-10", "Close": 1060.0},
            {"Date": "2020-02-11", "Close": 1070.0},
            {"Date": "2020-02-12", "Close": 1080.0},
            {"Date": "2020-02-13", "Close": 1090.0},
            {"Date": "2020-02-14", "Close": 1100.0},
            {"Date": "2020-02-17", "Close": 1110.0},
            {"Date": "2020-02-18", "Close": 1120.0},
            {"Date": "2020-02-19", "Close": 1130.0},
            {"Date": "2020-02-20", "Close": 1140.0},
            {"Date": "2020-02-21", "Close": 1150.0},
            {"Date": "2020-02-24", "Close": 1160.0},
            {"Date": "2020-02-25", "Close": 1170.0},
            {"Date": "2020-02-26", "Close": 1180.0},
            {"Date": "2020-02-27", "Close": 1190.0},
            {"Date": "2020-02-28", "Close": 1200.0},
            {"Date": "2020-03-02", "Close": 900.0},
            {"Date": "2020-03-03", "Close": 890.0},
            {"Date": "2020-03-04", "Close": 880.0},
            {"Date": "2020-03-05", "Close": 870.0},
            {"Date": "2020-03-06", "Close": 860.0},
            {"Date": "2020-03-09", "Close": 850.0},
            {"Date": "2020-03-10", "Close": 840.0},
            {"Date": "2020-03-11", "Close": 830.0},
            {"Date": "2020-03-12", "Close": 820.0},
            {"Date": "2020-03-13", "Close": 810.0},
            {"Date": "2020-03-16", "Close": 800.0},
            {"Date": "2020-03-17", "Close": 790.0},
            {"Date": "2020-03-18", "Close": 780.0},
            {"Date": "2020-03-19", "Close": 770.0},
            {"Date": "2020-03-20", "Close": 760.0},
            {"Date": "2020-03-23", "Close": 750.0},
            {"Date": "2020-03-24", "Close": 740.0},
            {"Date": "2020-03-25", "Close": 730.0},
            {"Date": "2020-03-26", "Close": 720.0},
            {"Date": "2020-03-27", "Close": 710.0},
            {"Date": "2020-03-30", "Close": 700.0},
        ],
    )

    config = LessonBuilderConfig(
        event_data_path=cpi_path,
        gold_path=gold_path,
        output_path=output_path,
    )
    return LessonBuilder(config)


def test_builds_explainable_cpi_gold_lesson_schema() -> None:
    builder = build_fixture(runtime_dir("schema"))

    lessons = builder.build()

    assert list(lessons["lesson_id"]) == [
        "CPI_GOLD_2020-02-01",
        "CPI_GOLD_2020-03-01",
    ]
    assert lessons.iloc[0]["lesson_version"] == "cpi_gold_v1"
    assert lessons.iloc[0]["event_type"] == "CPI"
    assert lessons.iloc[0]["anchor_gold_date"] == "2020-02-03"
    assert lessons.iloc[0]["alignment_method"] == "first_gold_session_on_or_after_event_date"
    assert lessons.iloc[0]["cpi_pressure"] == "inflation_pressure_up"
    assert lessons.iloc[0]["gold_return_1d_pct"] == 0.990099
    assert lessons.iloc[0]["gold_return_5d_pct"] == 4.950495
    assert lessons.iloc[0]["gold_return_20d_pct"] == -10.891089
    assert lessons.iloc[0]["gold_direction_20d"] == "DOWN"
    assert lessons.iloc[0]["primary_horizon_days"] == 20
    assert "After CPI changed by" in lessons.iloc[0]["lesson_text"]
    assert lessons.iloc[1]["cpi_pressure"] == "inflation_pressure_down"
    assert lessons.iloc[1]["gold_direction_20d"] == "DOWN"


def test_build_and_save_writes_deterministic_lessons() -> None:
    builder = build_fixture(runtime_dir("deterministic"))

    first = builder.build_and_save()
    second = builder.build_and_save()
    saved = pd.read_csv(builder.config.output_path)

    pd.testing.assert_frame_equal(first, second)
    pd.testing.assert_frame_equal(first, saved)


def test_missing_required_columns_fail_fast() -> None:
    base_path = runtime_dir("missing_columns")
    cpi_path = base_path / "economic" / "CPIAUCSL.csv"
    gold_path = base_path / "history" / "gold.csv"
    write_csv(cpi_path, [{"Date": "2020-01-01", "Value": 100.0}])
    write_csv(gold_path, [{"Date": "2020-01-01", "Open": 1000.0}])

    builder = LessonBuilder(
        LessonBuilderConfig(event_data_path=cpi_path, gold_path=gold_path)
    )

    try:
        builder.build()
    except ValueError as exc:
        assert "missing required columns: Close" in str(exc)
    else:
        raise AssertionError("Expected a missing-column ValueError.")
