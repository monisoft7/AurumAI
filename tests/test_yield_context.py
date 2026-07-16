from pathlib import Path

import pandas as pd

from knowledge.context.yields import YieldContextConfig, YieldContextEnricher


def write_csv(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(path, index=False)


def test_yield_context_enriches_lessons_with_level_and_trend(tmp_path: Path) -> None:
    lessons = pd.DataFrame([
        {"lesson_id": "CPI_GOLD_2020-02-01", "event_date": "2020-02-01"},
        {"lesson_id": "CPI_GOLD_2020-03-01", "event_date": "2020-03-01"},
    ])
    yield_path = tmp_path / "dgs10.csv"
    write_csv(yield_path, [
        {"Date": "2020-01-01", "Value": 1.50},
        {"Date": "2020-02-01", "Value": 1.80},
        {"Date": "2020-03-01", "Value": 1.60},
    ])

    enriched = YieldContextEnricher(
        YieldContextConfig(yield_path=yield_path, lookback_days=28)
    ).enrich(lessons)

    assert list(enriched["us10y_level"]) == [
        "low_yield_regime",
        "low_yield_regime",
    ]
    assert list(enriched["us10y_trend"]) == ["yields_rising", "yields_falling"]
    assert list(enriched["us10y_change_bps"]) == [30.0, -20.0]


def test_yield_context_uses_latest_observation_on_or_before_event(tmp_path: Path) -> None:
    lessons = pd.DataFrame([
        {"lesson_id": "CPI_GOLD_2020-02-03", "event_date": "2020-02-03"},
    ])
    yield_path = tmp_path / "dgs10.csv"
    write_csv(yield_path, [
        {"Date": "2020-01-01", "Value": 2.50},
        {"Date": "2020-01-31", "Value": 2.75},
        {"Date": "2020-02-04", "Value": 3.25},
    ])

    enriched = YieldContextEnricher(
        YieldContextConfig(yield_path=yield_path, lookback_days=30)
    ).enrich(lessons)

    row = enriched.iloc[0]
    assert row["us10y_value_at_event"] == 2.75
    assert row["us10y_value_lookback"] == 2.5
    assert row["us10y_level"] == "normal_yield_regime"
    assert row["us10y_trend"] == "yields_rising"


def test_yield_context_raises_on_missing_yield_columns(tmp_path: Path) -> None:
    lessons = pd.DataFrame([
        {"lesson_id": "CPI_GOLD_2020-02-01", "event_date": "2020-02-01"},
    ])
    yield_path = tmp_path / "bad.csv"
    write_csv(yield_path, [{"Date": "2020-01-01"}])

    try:
        YieldContextEnricher(YieldContextConfig(yield_path=yield_path)).enrich(lessons)
    except ValueError as exc:
        assert "Value" in str(exc)
        assert "missing required columns" in str(exc)
    else:
        raise AssertionError("Expected ValueError for missing yield columns")
