"""Correction 029: derived, prefix-deterministic trend-state hysteresis.

Pins the state machine semantics shared by the yield (US10Y), DXY, and
breakeven (T5YIE) context enrichers:
- entry above the existing threshold only
- release to flat only at a zero crossing
- no direct rising <-> falling transition
- state derived by chronological prefix fold, never restored from disk
"""

from pathlib import Path

import pandas as pd
import pytest

from knowledge.context.breakeven import (
    BreakevenContextConfig,
    BreakevenContextEnricher,
)
from knowledge.context.dxy import DXYContextConfig, DXYContextEnricher
from knowledge.context.trend_state import derive_trend_states, trend_state_at
from knowledge.context.yields import YieldContextConfig, YieldContextEnricher

from evidence_reasoning.historical_analogue import current_context_trends

MONTHLY = [
    "2020-01-01",
    "2020-02-01",
    "2020-03-01",
    "2020-04-01",
    "2020-05-01",
]

LOOKBACK = 28


def write_csv(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(path, index=False)


def yield_series(values: list[float]) -> list[dict]:
    return [{"Date": d, "Value": v} for d, v in zip(MONTHLY, values)]


def enrich_yields(path: Path, lessons: pd.DataFrame) -> pd.DataFrame:
    return YieldContextEnricher(
        YieldContextConfig(yield_path=path, lookback_days=LOOKBACK)
    ).enrich(lessons)


@pytest.mark.parametrize(
    "rows,lesson_dates,expected",
    [
        (
            # flat -> rising only above +10 bps
            yield_series([2.00, 2.08, 2.20]),
            ["2020-02-01", "2020-03-01"],
            ["yields_flat", "yields_rising"],
        ),
        (
            # flat -> falling only below -10 bps
            yield_series([2.00, 1.92, 1.80]),
            ["2020-02-01", "2020-03-01"],
            ["yields_flat", "yields_falling"],
        ),
        (
            # rising persists inside the positive deadband
            yield_series([2.00, 2.15, 2.18]),
            ["2020-03-01"],
            ["yields_rising"],
        ),
        (
            # falling persists inside the negative deadband
            yield_series([2.00, 1.85, 1.82]),
            ["2020-03-01"],
            ["yields_falling"],
        ),
        (
            # rising -> flat at the zero crossing
            yield_series([2.00, 2.15, 2.15]),
            ["2020-03-01"],
            ["yields_flat"],
        ),
        (
            # falling -> flat at the zero crossing
            yield_series([2.00, 1.85, 1.85]),
            ["2020-03-01"],
            ["yields_flat"],
        ),
        (
            # no direct rising -> falling
            yield_series([2.00, 2.15, 1.85, 1.60]),
            ["2020-03-01", "2020-04-01"],
            ["yields_flat", "yields_falling"],
        ),
        (
            # no direct falling -> rising
            yield_series([2.00, 1.85, 2.15, 2.40]),
            ["2020-03-01", "2020-04-01"],
            ["yields_flat", "yields_rising"],
        ),
    ],
)
def test_yield_state_machine(
    tmp_path: Path,
    rows: list[dict],
    lesson_dates: list[str],
    expected: list[str],
) -> None:
    path = tmp_path / "yields.csv"
    write_csv(path, rows)
    lessons = pd.DataFrame(
        {"event_date": lesson_dates, "lesson_id": [f"L_{d}" for d in lesson_dates]}
    )
    enriched = enrich_yields(path, lessons)
    assert list(enriched["us10y_trend"]) == expected


def test_exact_threshold_behavior_stays_flat(tmp_path: Path) -> None:
    path = tmp_path / "yields.csv"
    write_csv(path, yield_series([2.00, 2.10]))
    lessons = pd.DataFrame({"event_date": ["2020-02-01"]})
    enriched = enrich_yields(path, lessons)
    assert enriched["us10y_change_bps"].iloc[0] == 10.0
    assert enriched["us10y_trend"].iloc[0] == "yields_flat"

    write_csv(path, yield_series([2.00, 1.90]))
    enriched = enrich_yields(path, lessons)
    assert enriched["us10y_change_bps"].iloc[0] == -10.0
    assert enriched["us10y_trend"].iloc[0] == "yields_flat"

    dxy_path = tmp_path / "dxy.csv"
    write_csv(dxy_path, [
        {"Date": "2019-12-01", "Value": 97.0},
        {"Date": "2020-01-01", "Value": 98.0},
    ])
    dxy = DXYContextEnricher(
        DXYContextConfig(dxy_path=dxy_path, lookback_days=28)
    ).enrich(pd.DataFrame({"event_date": ["2020-01-01"]}))
    assert dxy["dxy_change"].iloc[0] == 1.0
    assert dxy["dxy_trend"].iloc[0] == "dxy_flat"


def test_floating_point_boundary_around_threshold(tmp_path: Path) -> None:
    path = tmp_path / "yields.csv"
    lessons = pd.DataFrame({"event_date": ["2020-02-01"]})

    write_csv(path, yield_series([2.00, 2.0999]))
    assert enrich_yields(path, lessons)["us10y_trend"].iloc[0] == "yields_flat"

    write_csv(path, yield_series([2.00, 2.1001]))
    assert enrich_yields(path, lessons)["us10y_trend"].iloc[0] == "yields_rising"

    write_csv(path, yield_series([2.00, 2.15, 2.1499]))
    assert (
        enrich_yields(path, pd.DataFrame({"event_date": ["2020-03-01"]}))[
            "us10y_trend"
        ].iloc[0]
        == "yields_flat"
    )

    write_csv(path, yield_series([2.00, 1.85, 1.8501]))
    assert (
        enrich_yields(path, pd.DataFrame({"event_date": ["2020-03-01"]}))[
            "us10y_trend"
        ].iloc[0]
        == "yields_flat"
    )


def test_prefix_determinism_truncated_equals_full(tmp_path: Path) -> None:
    rows = yield_series([2.00, 2.15, 2.05, 1.85, 2.10])
    full = tmp_path / "yields_full.csv"
    truncated = tmp_path / "yields_truncated.csv"
    write_csv(full, rows)
    write_csv(truncated, rows[:3])

    lessons = pd.DataFrame({"event_date": ["2020-02-01", "2020-03-01"]})

    full_enriched = enrich_yields(full, lessons)
    truncated_enriched = enrich_yields(truncated, lessons)

    assert list(full_enriched["us10y_trend"]) == list(
        truncated_enriched["us10y_trend"]
    )
    for lesson_date in lessons["event_date"]:
        state = trend_state_at(
            pd.to_datetime(pd.Series([r["Date"] for r in rows[:3]])),
            pd.Series([r["Value"] for r in rows[:3]]),
            pd.Timestamp(lesson_date),
            LOOKBACK,
            10.0,
        )
        assert state in ("flat", "rising", "falling")


def test_historical_replay_independent_of_later_observations(tmp_path: Path) -> None:
    rows = yield_series([2.00, 2.15, 2.18, 2.18, 2.03])
    dates = pd.to_datetime(pd.Series([r["Date"] for r in rows]))
    values = pd.Series([r["Value"] for r in rows])

    past = pd.Timestamp("2020-03-01")
    state_without_future = trend_state_at(dates, values, past, LOOKBACK, 10.0)
    state_with_future = trend_state_at(dates, values, pd.Timestamp("2020-05-01"), LOOKBACK, 10.0)
    state_at_past_on_full = trend_state_at(dates, values, past, LOOKBACK, 10.0)

    assert state_without_future == state_with_future == state_at_past_on_full


def test_current_as_of_behavior(tmp_path: Path) -> None:
    rows = yield_series([2.00, 2.15, 2.05])
    path = tmp_path / "yields.csv"
    write_csv(path, rows)
    dates = pd.to_datetime(pd.Series([r["Date"] for r in rows]))
    values = pd.Series([r["Value"] for r in rows])

    as_of = pd.Timestamp("2020-03-01")
    enriched = enrich_yields(path, pd.DataFrame({"event_date": [str(as_of.date())]}))
    assert enriched["us10y_trend"].iloc[0] == "yields_flat"

    state = trend_state_at(dates, values, as_of, LOOKBACK, 10.0)
    assert state == "flat"

    weekend = pd.Timestamp("2020-03-15")
    friday = pd.Timestamp("2020-03-01")
    assert trend_state_at(dates, values, weekend, LOOKBACK, 10.0) == trend_state_at(
        dates, values, friday, LOOKBACK, 10.0
    )


def test_restart_independence(tmp_path: Path) -> None:
    rows = yield_series([2.00, 2.15, 2.05, 1.85, 2.10])
    path = tmp_path / "yields.csv"
    write_csv(path, rows)
    dates = pd.to_datetime(pd.Series([r["Date"] for r in rows]))
    values = pd.Series([r["Value"] for r in rows])

    first = derive_trend_states(dates, values, LOOKBACK, 10.0)
    second = derive_trend_states(dates, values, LOOKBACK, 10.0)
    assert first == second

    lessons = pd.DataFrame({"event_date": [str(r["Date"]) for r in rows]})
    enriched_once = enrich_yields(path, lessons)
    enriched_twice = enrich_yields(path, lessons)
    assert list(enriched_once["us10y_trend"]) == list(enriched_twice["us10y_trend"])


def test_missing_and_short_history(tmp_path: Path) -> None:
    path = tmp_path / "yields.csv"
    write_csv(path, [{"Date": "2020-01-01", "Value": 2.00}])

    enriched = enrich_yields(path, pd.DataFrame({"event_date": ["2020-01-01"]}))
    assert enriched["us10y_trend"].iloc[0] == "missing_yield_lookback"
    assert enriched["us10y_change_bps"].iloc[0] is None

    early = enrich_yields(path, pd.DataFrame({"event_date": ["2019-01-01"]}))
    assert early["us10y_trend"].iloc[0] == "missing_yield_context"

    dates = pd.Series(pd.to_datetime(["2020-01-01"]))
    values = pd.Series([2.00])
    assert trend_state_at(dates, values, pd.Timestamp("2020-01-01"), LOOKBACK, 10.0) == "flat"
    assert trend_state_at(dates, values, pd.Timestamp("2020-02-01"), LOOKBACK, 10.0) == "flat"
    assert trend_state_at(dates, values, pd.Timestamp("2019-12-01"), LOOKBACK, 10.0) == "flat"


def test_dxy_same_contract(tmp_path: Path) -> None:
    rows = [
        {"Date": "2019-11-01", "Value": 97.00},
        {"Date": "2019-12-01", "Value": 98.50},
        {"Date": "2020-01-01", "Value": 98.80},
        {"Date": "2020-02-01", "Value": 98.80},
        {"Date": "2020-03-01", "Value": 97.30},
    ]
    path = tmp_path / "dxy.csv"
    write_csv(path, rows)
    lessons = pd.DataFrame({"event_date": [str(r["Date"]) for r in rows]})
    enriched = DXYContextEnricher(
        DXYContextConfig(dxy_path=path, lookback_days=28)
    ).enrich(lessons)

    assert list(enriched["dxy_trend"]) == [
        "missing_dxy_lookback",
        "dxy_rising",
        "dxy_rising",
        "dxy_flat",
        "dxy_falling",
    ]
    assert list(enriched["dxy_change"])[0] is None or pd.isna(
        enriched["dxy_change"].iloc[0]
    )
    assert list(enriched["dxy_change"])[1:] == [1.5, 0.3, 0.0, -1.5]

    missing = DXYContextEnricher(
        DXYContextConfig(dxy_path=path, lookback_days=28)
    ).enrich(pd.DataFrame({"event_date": ["2019-01-01"]}))
    assert missing["dxy_trend"].iloc[0] == "missing_dxy_context"


def test_breakeven_same_contract(tmp_path: Path) -> None:
    rows = [
        {"Date": "2020-01-01", "Value": 2.00},
        {"Date": "2020-02-01", "Value": 2.15},
        {"Date": "2020-03-01", "Value": 2.18},
        {"Date": "2020-04-01", "Value": 2.18},
        {"Date": "2020-05-01", "Value": 2.03},
    ]
    path = tmp_path / "t5yie.csv"
    write_csv(path, rows)
    lessons = pd.DataFrame({"event_date": [str(r["Date"]) for r in rows]})
    enriched = BreakevenContextEnricher(
        BreakevenContextConfig(breakeven_path=path, lookback_days=28)
    ).enrich(lessons)

    assert list(enriched["t5yie_trend"]) == [
        "missing_breakeven_lookback",
        "breakeven_rising",
        "breakeven_rising",
        "breakeven_flat",
        "breakeven_falling",
    ]
    assert list(enriched["t5yie_change"])[0] is None or pd.isna(
        enriched["t5yie_change"].iloc[0]
    )
    assert list(enriched["t5yie_change"])[1:] == [0.15, 0.03, 0.0, -0.15]


def test_shared_contract_identical_transition_pattern(tmp_path: Path) -> None:
    cases = [
        (
            "us10y_trend",
            YieldContextEnricher,
            YieldContextConfig,
            {"yield_path": tmp_path / "yields_shared.csv"},
            ["2019-12-01", *MONTHLY],
            [2.00, 2.00, 2.15, 2.18, 2.18, 2.03],
        ),
        (
            "dxy_trend",
            DXYContextEnricher,
            DXYContextConfig,
            {"dxy_path": tmp_path / "dxy_shared.csv"},
            ["2019-11-01", *MONTHLY],
            [97.00, 97.00, 98.50, 98.80, 98.80, 97.30],
        ),
        (
            "t5yie_trend",
            BreakevenContextEnricher,
            BreakevenContextConfig,
            {"breakeven_path": tmp_path / "t5yie_shared.csv"},
            ["2019-12-01", *MONTHLY],
            [2.00, 2.00, 2.15, 2.18, 2.18, 2.03],
        ),
    ]

    for column, enricher_cls, config_cls, paths, dates, values in cases:
        rows = [{"Date": d, "Value": v} for d, v in zip(dates, values)]
        path = next(iter(paths.values()))
        write_csv(path, rows)
        lessons = pd.DataFrame({"event_date": [str(r["Date"]) for r in rows]})

        config = config_cls(**paths, lookback_days=LOOKBACK)
        enriched = enricher_cls(config).enrich(lessons)
        states = [str(v) for v in enriched[column]]
        flat = {"yields_flat", "dxy_flat", "breakeven_flat"}
        rising = {"yields_rising", "dxy_rising", "breakeven_rising"}
        falling = {"yields_falling", "dxy_falling", "breakeven_falling"}
        assert states[1] in flat
        assert states[2] in rising
        assert states[3] in rising
        assert states[4] in flat
        assert states[5] in falling


def test_live_wrapper_consistent_across_calls() -> None:
    first = current_context_trends(as_of_date="2020-02-01")
    second = current_context_trends(as_of_date="2020-02-01")
    assert first == second
    for key, values in first.items():
        assert values in ("yields_rising", "yields_falling", "yields_flat",
                          "dxy_rising", "dxy_falling", "dxy_flat")


def test_exact_threshold_dxy_stays_flat(tmp_path: Path) -> None:
    path = tmp_path / "dxy.csv"
    write_csv(path, [
        {"Date": "2019-12-01", "Value": 97.0},
        {"Date": "2020-01-01", "Value": 96.0},
    ])
    enriched = DXYContextEnricher(
        DXYContextConfig(dxy_path=path, lookback_days=28)
    ).enrich(pd.DataFrame({"event_date": ["2020-01-01"]}))
    assert enriched["dxy_change"].iloc[0] == -1.0
    assert enriched["dxy_trend"].iloc[0] == "dxy_flat"
