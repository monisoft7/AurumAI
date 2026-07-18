import shutil
from pathlib import Path

import pandas as pd

from knowledge.context.dxy import DXYContextConfig, DXYContextEnricher


def _runtime_dir(name: str) -> Path:
    path = Path(__file__).resolve().parent / "_runtime" / name
    if path.exists():
        shutil.rmtree(path)
    path.mkdir(parents=True)
    return path


def _write_csv(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(path, index=False)


DXY_ROWS = [
    {"Date": "2019-11-01", "Value": 97.5},
    {"Date": "2019-12-01", "Value": 96.8},
    {"Date": "2020-01-01", "Value": 97.2},
    {"Date": "2020-02-01", "Value": 98.5},
    {"Date": "2020-03-01", "Value": 99.1},
    {"Date": "2020-04-01", "Value": 99.8},
    {"Date": "2020-05-01", "Value": 98.2},
]


def test_dxy_enricher_adds_columns() -> None:
    base = _runtime_dir("dxy_adds_columns")
    dxy_path = base / "dxy.csv"
    _write_csv(dxy_path, DXY_ROWS)

    lessons = pd.DataFrame({
        "event_date": ["2020-01-01", "2020-02-01", "2020-03-01"],
        "cpi_value": [100.0, 101.0, 99.0],
    })

    config = DXYContextConfig(dxy_path=dxy_path)
    enricher = DXYContextEnricher(config)
    enriched = enricher.enrich(lessons)

    expected_cols = {"dxy_value_at_event", "dxy_value_lookback", "dxy_change", "dxy_level", "dxy_trend"}
    assert expected_cols.issubset(enriched.columns), f"Missing columns: {expected_cols - set(enriched.columns)}"
    assert len(enriched) == 3


def test_dxy_enricher_classifies_level() -> None:
    base = _runtime_dir("dxy_classifies_level")
    dxy_path = base / "dxy.csv"
    _write_csv(dxy_path, DXY_ROWS)

    # Use a low, normal, and high DXY value
    low_rows = [{"Date": "2020-01-01", "Value": 92.0}]
    low_path = base / "dxy_low.csv"
    _write_csv(low_path, low_rows)

    normal_rows = [{"Date": "2020-01-01", "Value": 100.0}]
    normal_path = base / "dxy_normal.csv"
    _write_csv(normal_path, normal_rows)

    high_rows = [{"Date": "2020-01-01", "Value": 108.0}]
    high_path = base / "dxy_high.csv"
    _write_csv(high_path, high_rows)

    lessons = pd.DataFrame({"event_date": ["2020-01-01"]})

    for dxy_path_opt, expected in [
        (low_path, "low_dxy_regime"),
        (normal_path, "normal_dxy_regime"),
        (high_path, "high_dxy_regime"),
    ]:
        config = DXYContextConfig(dxy_path=dxy_path_opt)
        enriched = DXYContextEnricher(config).enrich(lessons)
        assert enriched["dxy_level"].iloc[0] == expected, f"Expected {expected} for value"


def test_dxy_enricher_classifies_trend() -> None:
    base = _runtime_dir("dxy_classifies_trend")
    dxy_path = base / "dxy.csv"

    # rising: change > 1.0
    _write_csv(dxy_path, [
        {"Date": "2019-12-01", "Value": 97.0},
        {"Date": "2020-01-01", "Value": 98.5},
    ])
    lessons = pd.DataFrame({"event_date": ["2020-01-01"]})
    enriched = DXYContextEnricher(DXYContextConfig(dxy_path=dxy_path)).enrich(lessons)
    assert enriched["dxy_trend"].iloc[0] == "dxy_rising"

    # falling: change < -1.0
    _write_csv(dxy_path, [
        {"Date": "2019-12-01", "Value": 100.0},
        {"Date": "2020-01-01", "Value": 98.5},
    ])
    enriched = DXYContextEnricher(DXYContextConfig(dxy_path=dxy_path)).enrich(lessons)
    assert enriched["dxy_trend"].iloc[0] == "dxy_falling"

    # flat: |change| <= 1.0
    _write_csv(dxy_path, [
        {"Date": "2019-12-01", "Value": 99.0},
        {"Date": "2020-01-01", "Value": 99.5},
    ])
    enriched = DXYContextEnricher(DXYContextConfig(dxy_path=dxy_path)).enrich(lessons)
    assert enriched["dxy_trend"].iloc[0] == "dxy_flat"


def test_dxy_enricher_missing_context() -> None:
    base = _runtime_dir("dxy_missing_context")
    dxy_path = base / "dxy.csv"
    _write_csv(dxy_path, [{"Date": "2020-06-01", "Value": 97.0}])

    # Event date before first DXY observation
    lessons = pd.DataFrame({"event_date": ["2019-01-01"]})
    enriched = DXYContextEnricher(DXYContextConfig(dxy_path=dxy_path)).enrich(lessons)
    assert enriched["dxy_level"].iloc[0] == "missing_dxy_context"
    assert enriched["dxy_trend"].iloc[0] == "missing_dxy_context"
    assert enriched["dxy_value_at_event"].iloc[0] is None


def test_dxy_enricher_missing_lookback() -> None:
    base = _runtime_dir("dxy_missing_lookback")
    dxy_path = base / "dxy.csv"
    _write_csv(dxy_path, [{"Date": "2020-01-01", "Value": 97.0}])

    lessons = pd.DataFrame({"event_date": ["2020-01-01"]})
    enriched = DXYContextEnricher(DXYContextConfig(dxy_path=dxy_path)).enrich(lessons)
    assert enriched["dxy_level"].iloc[0] == "normal_dxy_regime"
    assert enriched["dxy_trend"].iloc[0] == "missing_dxy_lookback"
    assert enriched["dxy_value_at_event"].iloc[0] == 97.0
    assert enriched["dxy_value_lookback"].iloc[0] is None


def test_dxy_enricher_standalone_csv() -> None:
    base = _runtime_dir("dxy_standalone_csv")
    in_path = base / "in" / "lessons.csv"
    out_path = base / "out" / "lessons.csv"
    dxy_path = base / "dxy.csv"

    _write_csv(dxy_path, DXY_ROWS)
    _write_csv(in_path, [
        {"event_date": "2020-01-01", "cpi_value": 100.0},
        {"event_date": "2020-02-01", "cpi_value": 101.0},
    ])

    config = DXYContextConfig(dxy_path=dxy_path)
    enricher = DXYContextEnricher(config)
    result = enricher.enrich_csv(in_path, out_path)

    assert out_path.exists()
    assert len(result) == 2
    for col in ["dxy_value_at_event", "dxy_level", "dxy_trend"]:
        assert col in result.columns

    # Verify CSV file content
    loaded = pd.read_csv(out_path)
    assert len(loaded) == 2
    assert "dxy_value_at_event" in loaded.columns


def test_dxy_enricher_handles_nan_in_source() -> None:
    base = _runtime_dir("dxy_handles_nan")
    dxy_path = base / "dxy.csv"
    _write_csv(dxy_path, [
        {"Date": "2019-12-01", "Value": 97.0},
        {"Date": "2020-01-01", "Value": None},
        {"Date": "2020-01-02", "Value": 98.0},
    ])

    lessons = pd.DataFrame({"event_date": ["2020-01-01"]})
    enriched = DXYContextEnricher(DXYContextConfig(dxy_path=dxy_path)).enrich(lessons)
    # NaN row is dropped; latest on/before 2020-01-01 is 2019-12-01
    assert enriched["dxy_value_at_event"].iloc[0] == 97.0
    assert enriched["dxy_level"].iloc[0] == "normal_dxy_regime"


def test_dxy_enricher_preserves_existing_columns() -> None:
    base = _runtime_dir("dxy_preserves_cols")
    dxy_path = base / "dxy.csv"
    _write_csv(dxy_path, DXY_ROWS)

    lessons = pd.DataFrame({
        "event_date": ["2020-01-01"],
        "lesson_id": ["CPI_GOLD_2020-01-01"],
        "cpi_pressure": ["inflation_pressure_up"],
        "gold_return_20d_pct": [0.5],
    })

    enriched = DXYContextEnricher(DXYContextConfig(dxy_path=dxy_path)).enrich(lessons)
    assert "lesson_id" in enriched.columns
    assert "cpi_pressure" in enriched.columns
    assert "gold_return_20d_pct" in enriched.columns
    assert enriched["lesson_id"].iloc[0] == "CPI_GOLD_2020-01-01"
