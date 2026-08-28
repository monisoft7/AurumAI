"""Focused tests for Trace 045-B -- Historical SignalAssessment replay adapter.

Covers: as-of cutoff for every series, no network calls, positioning=None,
news_items=(), unavailable breadth instruments not fabricated, regime from
ValidationSnapshot, reuse of the existing pure SignalAssessmentAssembler,
deterministic repeated execution, contract validity, production files
unchanged, forbidden runtime paths unreachable, and a valid historical
SignalAssessment for the first cohort case.
"""

from __future__ import annotations

import ast
import hashlib
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from historical_validation.briefing import (
    INSTRUMENT_SOURCES,
    UNAVAILABLE_HISTORICAL_SOURCES,
    build_historical_briefing,
    build_historical_signal_assessment,
)
from historical_validation.cases import build_validation_cases
from historical_validation.snapshot import build_snapshot


@pytest.fixture(scope="module")
def case():
    cases = build_validation_cases(path=ROOT / "data" / "lessons" / "cpi_gold_lessons.csv")
    return cases[0]


@pytest.fixture(scope="module")
def case_snapshot(case):
    return build_snapshot(case)


@pytest.fixture(scope="module")
def result_a(case, case_snapshot):
    return build_historical_signal_assessment(case, case_snapshot)


@pytest.fixture(scope="module")
def result_b(case, case_snapshot):
    return build_historical_signal_assessment(case, case_snapshot)


# ---------------------------------------------------------------------------
# 1. As-of cutoff for every historical series
# ---------------------------------------------------------------------------


def test_asof_cutoff_for_every_series(result_a, case) -> None:
    checks = result_a["asof_verification"]
    assert checks["all_series_max_date_le_D"] is True
    d_iso = case.evaluation_date.isoformat()
    max_dates = result_a["briefing"]["metadata"]["series_max_dates"]
    assert set(max_dates) == {name for name, _, _ in INSTRUMENT_SOURCES}
    assert all(date <= d_iso for date in max_dates.values())


# ---------------------------------------------------------------------------
# 2. No network calls (socket blocked; adapter must still complete)
# ---------------------------------------------------------------------------


def test_no_network_calls(case, case_snapshot, monkeypatch) -> None:
    import socket

    def _blocked(*args, **kwargs):
        raise AssertionError("network socket was opened")

    monkeypatch.setattr(socket, "socket", _blocked)
    monkeypatch.setattr(socket, "create_connection", _blocked)
    result = build_historical_signal_assessment(case, case_snapshot)
    assert result["signal_assessment"]["observations"] is not None


# ---------------------------------------------------------------------------
# 3/4/5. Explicitly degraded sources are never fabricated
# ---------------------------------------------------------------------------


def test_positioning_is_none_and_news_empty(result_a) -> None:
    briefing = result_a["briefing"]
    assert briefing["positioning_snapshot"] is None
    assert briefing["news_items"] == []
    assert result_a["degraded_source_checks"]["positioning_snapshot_is_None"] is True
    assert result_a["degraded_source_checks"]["news_items_empty"] is True
    # The limitation stays explicit in the payload metadata.
    assert briefing["metadata"]["unavailable_sources"] == list(
        UNAVAILABLE_HISTORICAL_SOURCES
    )


def test_unavailable_breadth_instruments_not_fabricated(result_a) -> None:
    unavailable = {"S&P 500 Futures", "Brent Crude", "EUR/USD", "USD/JPY"}
    instruments = [o["instrument"] for o in result_a["observation_classifications"]]
    change_instruments = [
        c["instrument"] for c in result_a["briefing"]["overnight_changes"]
    ]
    assert not (unavailable & set(instruments))
    assert not (unavailable & set(change_instruments))
    assert result_a["degraded_source_checks"][
        "unavailable_breadth_instruments_absent"
    ] is True
    # CORE instruments ARE present.
    core = {name for name, _, _ in INSTRUMENT_SOURCES}
    assert core <= set(change_instruments)


# ---------------------------------------------------------------------------
# 6. Regime comes from ValidationSnapshot
# ---------------------------------------------------------------------------


def test_regime_from_validation_snapshot(result_a, case_snapshot) -> None:
    assert result_a["briefing"]["regime"] == case_snapshot.institutional_regime
    assert result_a["asof_verification"]["regime_from_snapshot"] is True
    sa = result_a["signal_assessment"]
    assert sa["regime"] == case_snapshot.institutional_regime


# ---------------------------------------------------------------------------
# 7. Existing SignalAssessmentAssembler is reused
# ---------------------------------------------------------------------------


def test_existing_assembler_reused(result_a) -> None:
    provenance = result_a["provenance"]["reused_components"]
    assert "SignalAssessmentAssembler.assemble" in provenance
    # Observation shape matches the assembler's five-criteria output.
    for obs in result_a["observation_classifications"]:
        criteria = {c["criterion"] for c in obs["criteria"]}
        assert criteria == {
            "persistence",
            "breadth",
            "magnitude",
            "narrative_fit",
            "volume_flow",
        }


# ---------------------------------------------------------------------------
# 8. Deterministic repeated execution
# ---------------------------------------------------------------------------


def test_deterministic_repeated_execution(result_a, result_b) -> None:
    def numeric(view: dict) -> dict:
        from historical_validation.compare import numeric_leaf_comparison

        return numeric_leaf_comparison({"v": view})

    assert numeric(result_a) == numeric(result_b)
    cls_a = [
        (o["instrument"], o["classification"], o["confidence"])
        for o in result_a["observation_classifications"]
    ]
    cls_b = [
        (o["instrument"], o["classification"], o["confidence"])
        for o in result_b["observation_classifications"]
    ]
    assert cls_a == cls_b
    assert (
        result_a["briefing"]["overnight_changes"]
        == result_b["briefing"]["overnight_changes"]
    )
    assert (
        result_a["briefing"]["anomaly_flags"] == result_b["briefing"]["anomaly_flags"]
    )


# ---------------------------------------------------------------------------
# 9. Output matches the existing SignalAssessment contract
# ---------------------------------------------------------------------------


def test_matches_signal_assessment_contract(result_a) -> None:
    from signal_assessment.contracts import SignalAssessment

    assessment = SignalAssessment.from_dict(result_a["signal_assessment"])
    assert isinstance(assessment, SignalAssessment)
    assert assessment.regime == result_a["briefing"]["regime"]
    assert len(assessment.observations) >= 1


# ---------------------------------------------------------------------------
# 10. Production files unchanged
# ---------------------------------------------------------------------------


def test_production_files_unchanged(case, case_snapshot, monkeypatch) -> None:
    watched = [rel for _, rel, _ in INSTRUMENT_SOURCES] + [
        "data/calendar/cpi_releases.csv",
        "data/economic/gold_oi_state.json",
        "data/lessons/cpi_gold_lessons.csv",
        "runtime/run_registry.jsonl",
    ]

    def digest(rel: str):
        p = ROOT / rel
        return hashlib.sha256(p.read_bytes()).hexdigest() if p.is_file() else "<missing>"

    before = {rel: digest(rel) for rel in watched}
    build_historical_signal_assessment(case, case_snapshot)
    after = {rel: digest(rel) for rel in watched}
    assert before == after


# ---------------------------------------------------------------------------
# 11. Forbidden runtime paths unreachable
# ---------------------------------------------------------------------------


def test_forbidden_runtime_paths_unreachable() -> None:
    pkg = ROOT / "historical_validation"
    forbidden_tokens = (
        "InstitutionalOrchestrator",
        "with_default_pipeline",
        "_pre_market_scan",
        "PreMarketBriefingAssembler",
        "PositioningDataFetcher",
        "OvernightNewsIngestion",
        "NewsCollector",
        "FOMCCalendarConnector",
        "yfinance",
        "fetch_all",
        "_fetch_yfinance_change",
        "_persist_oi_level",
        "FredClient(",
        "CheckpointManager",
        "runtime_registry",
        "run.py",
    )
    forbidden_roots = {"orchestration", "news", "runtime_registry", "simulation"}
    forbidden_modules = {
        "pre_market.briefing_assembler",
        "pre_market.positioning",
        "pre_market.news_ingestion",
    }
    for py in sorted(pkg.rglob("*.py")):
        source = py.read_text(encoding="utf-8")
        for token in forbidden_tokens:
            assert token not in source, f"forbidden runtime reference {token!r} in {py.name}"
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    root_mod = alias.name.split(".")[0]
                    assert root_mod not in forbidden_roots, (
                        f"forbidden import '{alias.name}' in {py.name}"
                    )
            elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
                root_mod = node.module.split(".")[0]
                assert root_mod not in forbidden_roots, (
                    f"forbidden import from '{node.module}' in {py.name}"
                )
                assert node.module not in forbidden_modules, (
                    f"forbidden module import '{node.module}' in {py.name}"
                )


# ---------------------------------------------------------------------------
# 12. First cohort case produces a valid historical SignalAssessment
# ---------------------------------------------------------------------------


def test_first_case_valid_historical_signal_assessment(result_a, case) -> None:
    assert result_a["lesson_id"] == case.lesson_id == "CPI_GOLD_2015-06-01"
    observations = result_a["observation_classifications"]
    assert observations, "no observations classified"
    valid_labels = {"Signal", "Weak Signal", "Watch", "Noise", "Ignore"}
    assert all(o["classification"] in valid_labels for o in observations)
    by_source = {o["source"] for o in observations}
    assert "overnight_price" in by_source
    assert "cpi_release" in by_source
    # All eight verification blocks green.
    assert all(result_a["asof_verification"].values())
    assert all(result_a["degraded_source_checks"].values())
