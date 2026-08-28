"""Focused tests for Historical Validation Run 001 -- Step 2 as-of snapshot.

Covers: US10Y/DXY as-of cutoffs, 30-day anchor correctness, trend_state_at
integration, regime fit cutoff, knowledge eligibility cutoff, same-event
analogue exclusion, future gold outcome isolation, deterministic repeated
snapshot, explicit failure on missing inputs, and snapshot immutability.
"""

from __future__ import annotations

import dataclasses
import sys
from datetime import date, timedelta
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from historical_validation.cases import build_validation_cases
from historical_validation.snapshot import (
    SnapshotConfig,
    ValidationError,
    ValidationSnapshot,
    build_snapshot,
    knowledge_eligible_records,
)

EVAL_DATE = date(2021, 3, 1)  # CPI_GOLD_2021-03-01 (cohort position 74)


@pytest.fixture(scope="module")
def case_2021() -> object:
    cases = build_validation_cases(path=ROOT / "data" / "lessons" / "cpi_gold_lessons.csv")
    return next(c for c in cases if c.lesson_id == "CPI_GOLD_2021-03-01")


@pytest.fixture(scope="module")
def snapshot_2021(case_2021) -> ValidationSnapshot:
    return build_snapshot(case_2021)


@pytest.fixture(scope="module")
def dfii10() -> pd.DataFrame:
    df = pd.read_csv(ROOT / "data" / "economic" / "DFII10.csv", parse_dates=["Date"])
    df["Value"] = pd.to_numeric(df["Value"], errors="coerce")
    return df.dropna(subset=["Value"]).sort_values("Date")


@pytest.fixture(scope="module")
def dxy() -> pd.DataFrame:
    df = pd.read_csv(ROOT / "data" / "context" / "dxy" / "dxy.csv", parse_dates=["Date"])
    df["Value"] = pd.to_numeric(df["Value"], errors="coerce")
    return df.dropna(subset=["Value"]).sort_values("Date")


def _latest_on_or_before(df: pd.DataFrame, day: date) -> float:
    pos = df["Date"].searchsorted(pd.Timestamp(day), side="right")
    assert pos > 0
    return float(df["Value"].iloc[pos - 1])


# ---------------------------------------------------------------------------
# 1/2. US10Y and DXY as-of cutoff
# ---------------------------------------------------------------------------


def test_us10y_as_of_cutoff(snapshot_2021: ValidationSnapshot, case_2021, dfii10) -> None:
    snap = snapshot_2021
    assert snap.us10y_observation_date <= case_2021.evaluation_date
    assert snap.us10y_anchor_date is None or snap.us10y_anchor_date <= case_2021.evaluation_date
    assert snap.us10y_value == round(_latest_on_or_before(dfii10, case_2021.evaluation_date), 6)


def test_dxy_as_of_cutoff(snapshot_2021: ValidationSnapshot, case_2021, dxy) -> None:
    snap = snapshot_2021
    assert snap.dxy_observation_date <= case_2021.evaluation_date
    assert snap.dxy_anchor_date is None or snap.dxy_anchor_date <= case_2021.evaluation_date
    assert snap.dxy_value == round(_latest_on_or_before(dxy, case_2021.evaluation_date), 6)


# ---------------------------------------------------------------------------
# 3. 30-day anchor correctness
# ---------------------------------------------------------------------------


def test_thirty_day_anchor_correctness(
    snapshot_2021: ValidationSnapshot, case_2021, dfii10, dxy
) -> None:
    d = case_2021.evaluation_date
    anchor_day = d - timedelta(days=30)
    assert snapshot_2021.us10y_anchor_value == round(_latest_on_or_before(dfii10, anchor_day), 6)
    assert snapshot_2021.dxy_anchor_value == round(_latest_on_or_before(dxy, anchor_day), 6)
    assert snapshot_2021.us10y_change == round(
        (snapshot_2021.us10y_value - snapshot_2021.us10y_anchor_value) * 100.0, 6
    )
    assert snapshot_2021.dxy_change == round(
        snapshot_2021.dxy_value - snapshot_2021.dxy_anchor_value, 6
    )
    assert snapshot_2021.us10y_anchor_date <= anchor_day
    assert snapshot_2021.dxy_anchor_date <= anchor_day


# ---------------------------------------------------------------------------
# 4. trend_state_at integration
# ---------------------------------------------------------------------------


def test_trend_state_at_integration(
    snapshot_2021: ValidationSnapshot, case_2021, dfii10, dxy
) -> None:
    from knowledge.context.trend_state import trend_state_at

    d = case_2021.evaluation_date

    yield_series = dfii10[dfii10["Date"] <= pd.Timestamp(d)]
    yield_state = trend_state_at(
        yield_series["Date"],
        yield_series["Value"] * 100.0,
        pd.Timestamp(d),
        30,
        10.0,
    )
    assert snapshot_2021.us10y_trend == {"flat": "yields_flat", "rising": "yields_rising", "falling": "yields_falling"}[yield_state]

    dxy_series = dxy[dxy["Date"] <= pd.Timestamp(d)]
    dxy_state = trend_state_at(
        dxy_series["Date"],
        dxy_series["Value"],
        pd.Timestamp(d),
        30,
        1.0,
    )
    assert snapshot_2021.dxy_trend == {"flat": "dxy_flat", "rising": "dxy_rising", "falling": "dxy_falling"}[dxy_state]


# ---------------------------------------------------------------------------
# 5. Regime fit cutoff
# ---------------------------------------------------------------------------


def test_regime_fit_cutoff(snapshot_2021: ValidationSnapshot, case_2021) -> None:
    from knowledge.regime.constants import INSTITUTIONAL_REGIMES

    snap = snapshot_2021
    assert snap.regime_source_max_date <= case_2021.evaluation_date
    assert snap.institutional_regime in INSTITUTIONAL_REGIMES


# ---------------------------------------------------------------------------
# 6. Knowledge eligibility cutoff
# ---------------------------------------------------------------------------


def test_knowledge_eligibility_cutoff(case_2021, snapshot_2021: ValidationSnapshot) -> None:
    snap = snapshot_2021
    assert snap.knowledge_cutoff == case_2021.evaluation_date
    if snap.knowledge_source_max_lesson_date is not None:
        assert snap.knowledge_source_max_lesson_date <= case_2021.evaluation_date

    # Contract under review: the AS-OF knowledge view is DERIVED from the
    # canonical lesson artifact restricted to event_date <= D, so no record
    # can ever depend on a post-D lesson.  Verify the derivation law.
    from historical_validation.cases import load_lessons as _load
    from historical_validation.snapshot import asof_knowledge_records

    early = date(2015, 3, 1)
    later = date(2015, 7, 1)

    dates_by_id = {
        row["lesson_id"]: row["event_date"] for row in _load()
    }
    for d in (early, later):
        iso = d.isoformat()
        for rec in asof_knowledge_records(d):
            assert rec["source_lesson_ids"], rec["knowledge_id"]
            assert all(
                dates_by_id[i] <= iso for i in rec["source_lesson_ids"]
            ), (d, rec["knowledge_id"])

    # Monotonicity: knowledge cannot be forgotten as D advances.
    ids_early = {r["knowledge_id"] for r in asof_knowledge_records(early)}
    ids_later = {r["knowledge_id"] for r in asof_knowledge_records(later)}
    assert ids_early <= ids_later

    # Boundary law: before the first lesson exists there is NO knowledge,
    # and the first episode's aggregate appears exactly on its own date
    # (as-of is inclusive of D itself).
    first_date = min(dates_by_id.values())
    pre_first = date.fromisoformat(first_date) - timedelta(days=1)
    assert asof_knowledge_records(pre_first) == []
    first_ids = {
        r["knowledge_id"] for r in asof_knowledge_records(date.fromisoformat(first_date))
    }
    assert first_ids and first_ids <= ids_early


# ---------------------------------------------------------------------------
# 7. Same-event analogue exclusion
# ---------------------------------------------------------------------------


def test_same_event_analogue_exclusion(
    snapshot_2021: ValidationSnapshot, case_2021
) -> None:
    snap = snapshot_2021
    assert snap.analogue_cutoff is None or snap.analogue_cutoff < case_2021.evaluation_date
    assert case_2021.lesson_id not in snap.analogue_eligible_lesson_ids
    assert case_2021.lesson_id in snap.excluded_lesson_ids


# ---------------------------------------------------------------------------
# 8. Future gold outcome isolation
# ---------------------------------------------------------------------------


def test_future_gold_outcome_isolation(
    snapshot_2021: ValidationSnapshot, case_2021
) -> None:
    snap = snapshot_2021
    assert len(snap.evaluation_only_outcomes) == 3
    for item in snap.evaluation_only_outcomes:
        assert item["evaluation_only"] is True
        assert item["horizon"] in {"1d", "5d", "20d"}
    snap.assert_no_lookahead()
    outcome_values = {
        item["return_pct"] for item in snap.evaluation_only_outcomes
    } | {item["direction"] for item in snap.evaluation_only_outcomes}
    for f in dataclasses.fields(snap):
        if f.name == "evaluation_only_outcomes":
            continue
        assert getattr(snap, f.name) not in outcome_values, f"leak via {f.name}"


# ---------------------------------------------------------------------------
# 9. Deterministic repeated snapshot
# ---------------------------------------------------------------------------


def test_deterministic_repeated_snapshot(case_2021) -> None:
    first = build_snapshot(case_2021)
    second = build_snapshot(case_2021)
    assert first == second
    assert first.evaluation_date == date(2021, 3, 1)


# ---------------------------------------------------------------------------
# 10. Missing historical input fails explicitly
# ---------------------------------------------------------------------------


def test_missing_historical_input_fails_explicitly(case_2021, tmp_path) -> None:
    config = SnapshotConfig(
        lessons_path=ROOT / "data" / "lessons" / "cpi_gold_lessons.csv",
        dfii10_path=tmp_path / "missing_dfii10.csv",
        dxy_path=ROOT / "data" / "context" / "dxy" / "dxy.csv",
        economic_dir=ROOT / "data" / "economic",
        knowledge_records_path=ROOT / "data" / "economic" / "output" / "knowledge.json",
    )
    with pytest.raises(ValidationError):
        build_snapshot(case_2021, config)

    with pytest.raises(ValidationError):
        knowledge_eligible_records(
            date(2021, 3, 1),
            knowledge_records_path=tmp_path / "missing_knowledge.json",
            lessons_path=ROOT / "data" / "lessons" / "cpi_gold_lessons.csv",
        )


# ---------------------------------------------------------------------------
# 11. Snapshot is immutable / read-only
# ---------------------------------------------------------------------------


def test_snapshot_is_immutable(snapshot_2021: ValidationSnapshot) -> None:
    assert dataclasses.is_dataclass(snapshot_2021)
    assert snapshot_2021.__dataclass_params__.frozen
    with pytest.raises(dataclasses.FrozenInstanceError):
        snapshot_2021.us10y_trend = "yields_rising_new"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Regression: bool snapshot fields vs zero-valued realized returns
# ---------------------------------------------------------------------------


def test_bool_fields_do_not_collide_with_zero_return_outcomes() -> None:
    """CPI_GOLD_2019-11-01 realizes exactly 0.0% at 1d; ``False == 0.0`` in
    Python must not be reported as a future-outcome leak (Run 001 pilot,
    episode 11)."""
    cases = build_validation_cases(path=ROOT / "data" / "lessons" / "cpi_gold_lessons.csv")
    case = next(c for c in cases if c.lesson_id == "CPI_GOLD_2019-11-01")
    assert case.actual_1d.return_pct == 0.0
    snap = build_snapshot(case)
    snap.assert_no_lookahead()  # must not raise


# ---------------------------------------------------------------------------
# 12. No production files changed; layer is read-only
# ---------------------------------------------------------------------------


def test_no_production_pipeline_changes() -> None:
    snapshot_source = (ROOT / "historical_validation" / "snapshot.py").read_text(encoding="utf-8")
    for forbidden in ('"w"', '"w+"', 'to_csv', 'write_text', 'atomic_write', 'outputs/', 'runtime/'):
        assert forbidden not in snapshot_source, f"write detected in snapshot layer: {forbidden}"
    # AST-based import scan: prose references are not imports (the facts-layer
    # contracts legitimately cite historical_validation semantics by name).
    import ast as _ast

    src = ROOT / "src"
    for py in src.rglob("*.py"):
        tree = _ast.parse(py.read_text(encoding="utf-8", errors="ignore"))
        for node in _ast.walk(tree):
            if isinstance(node, _ast.Import):
                names = [alias.name for alias in node.names]
            elif isinstance(node, _ast.ImportFrom):
                names = [node.module or ""]
            else:
                continue
            for name in names:
                assert "historical_validation" not in name, (
                    f"production import: {py}: {name}"
                )