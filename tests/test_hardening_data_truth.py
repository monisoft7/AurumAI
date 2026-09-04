"""Final Hardening — Group B: Data Truth.

Locks the D-03 / D-11 semantics:

- synthetic rng-seeded CSV files are excluded from the macro regime
  composite on the live path AND surfaced in the regime payload;
- no fabricated random numbers anywhere in the live risk path
  (risk_measures degenerate residuals, pre-market risk report);
- an unavailable risk-metrics state reads as NOT acceptable at the
  decision gate (no silent missing-data success);
- positioning feeds carry explicit availability states;
- the replay simulator never writes synthetic files into the repo tree.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from knowledge.regime.composite_score import (  # noqa: E402
    SYNTHETIC_INDEX_FILENAME,
    CompositeScoreBuilder,
    SyntheticIndexError,
    load_synthetic_exclusions,
)


# ---------------------------------------------------------------------------
# synthetic exclusion
# ---------------------------------------------------------------------------


def test_synthetic_index_exists_and_lists_pmi():
    index_path = ROOT / "data" / "economic" / SYNTHETIC_INDEX_FILENAME
    assert index_path.is_file(), "synthetic_data_index.json must exist"
    payload = json.loads(index_path.read_text(encoding="utf-8"))
    assert "PMI.csv" in payload["files"]
    entry = payload["files"]["PMI.csv"]
    assert entry.get("excluded_from_live") is True
    assert "rng" in entry.get("generator", "").lower() or "default_rng" in entry.get("generator", "")


def test_load_synthetic_exclusions_reads_index():
    exclusions = load_synthetic_exclusions(ROOT / "data" / "economic")
    assert "PMI.csv" in exclusions
    assert "CPIAUCSL.csv" not in exclusions
    assert load_synthetic_exclusions(ROOT / "data" / "does_not_exist") == {}


def test_synthetic_index_missing_is_not_corrupt(tmp_path):
    # state 1 -- absent: explicit "no known synthetic files", not an error
    assert load_synthetic_exclusions(tmp_path) == {}


def test_synthetic_index_malformed_json_is_corrupt_not_missing(tmp_path):
    # state 3a -- exists but malformed JSON: must NOT collapse to state 1
    (tmp_path / SYNTHETIC_INDEX_FILENAME).write_text("{not json", encoding="utf-8")
    with pytest.raises(SyntheticIndexError, match="malformed JSON"):
        load_synthetic_exclusions(tmp_path)


def test_synthetic_index_invalid_schema_is_corrupt_not_missing(tmp_path):
    # state 3b -- valid JSON but no 'files' mapping: corrupt, not missing
    (tmp_path / SYNTHETIC_INDEX_FILENAME).write_text(
        json.dumps(["not", "a", "mapping"]), encoding="utf-8"
    )
    with pytest.raises(SyntheticIndexError, match="invalid schema"):
        load_synthetic_exclusions(tmp_path)


def test_synthetic_index_unreadable_is_corrupt_not_missing(tmp_path, monkeypatch):
    # state 3c -- exists but unreadable (e.g. permission failure)
    index_path = tmp_path / SYNTHETIC_INDEX_FILENAME
    index_path.write_text(json.dumps({"files": {}}), encoding="utf-8")

    def _unreadable(self, *args, **kwargs):
        raise PermissionError("simulated unreadable index")

    monkeypatch.setattr(Path, "read_text", _unreadable)
    with pytest.raises(SyntheticIndexError, match="unreadable"):
        load_synthetic_exclusions(tmp_path)


def test_composite_builder_fails_loudly_on_corrupt_index(tmp_path):
    # whole-path: a corrupt index must surface through the composite
    # builder (stage failure), never silently re-admit synthetic data
    (tmp_path / SYNTHETIC_INDEX_FILENAME).write_text("{corrupt", encoding="utf-8")
    builder = CompositeScoreBuilder(data_dir=tmp_path)
    with pytest.raises(SyntheticIndexError):
        builder.build_with_provenance()


def test_composite_builder_excludes_synthetic_indicators(tmp_path):
    # Build a tiny fake economic dir: CPI (real) + PMI (synthetic-marked).
    (tmp_path / SYNTHETIC_INDEX_FILENAME).write_text(
        json.dumps({"files": {"PMI.csv": {"reason": "test"}}}), encoding="utf-8"
    )
    cpi_rows = "\n".join(
        f"2024-{month:02d}-01,{100 + i}" for i, month in enumerate(range(1, 15))
    )
    (tmp_path / "CPIAUCSL.csv").write_text(
        "Date,Value\n" + cpi_rows + "\n", encoding="utf-8"
    )
    (tmp_path / "PMI.csv").write_text(
        "Date,Value\n2024-01-01,50\n2024-02-01,99\n2024-03-01,48\n",
        encoding="utf-8",
    )
    builder = CompositeScoreBuilder(data_dir=tmp_path)
    frame, provenance = builder.build_with_provenance()
    assert not frame.empty
    assert any(e["indicator"] == "PMI" for e in provenance["excluded_indicators"])
    # the honest CPI data still drives the composite
    assert len(frame) >= 1


def test_regime_diagnosis_payload_records_exclusions():
    from orchestration.stages import _regime_diagnosis

    payload = _regime_diagnosis(
        {"regime_as_of": "2026-01-01", "output_dir": None}, {}
    )
    assert "composite_provenance" in payload
    excluded = payload["composite_provenance"]["excluded_indicators"]
    assert any(e["indicator"] == "PMI" for e in excluded)


# ---------------------------------------------------------------------------
# no fabricated risk numbers
# ---------------------------------------------------------------------------


class _Point:
    def __init__(self, y_hi: float, y_lo: float) -> None:
        self.y_hi = y_hi
        self.y_lo = y_lo


def test_risk_measures_degenerate_residuals_not_fabricated():
    from forecasting.risk_measures import UNAVAILABLE_METHOD_PREFIX
    from orchestration.stages import _risk_measures

    class _Forecast:
        points = [_Point(100.0, 99.0), _Point(101.0, 100.0)]

    metrics = _risk_measures({}, {"forecast": _Forecast()})
    assert metrics.method.startswith(UNAVAILABLE_METHOD_PREFIX)
    assert metrics.var_95 == 0.0 and metrics.var_99 == 0.0 and metrics.cvar_95 == 0.0
    assert metrics.tail_index is None


def test_risk_gate_treats_unavailable_metrics_as_not_acceptable():
    from forecasting.risk_measures import UNAVAILABLE_METHOD_PREFIX, RiskMetrics
    from forecasting.decision_gate import RiskDecision
    from orchestration.stages import _risk_gate

    metrics = RiskMetrics(
        var_95=0.0,
        var_99=0.0,
        cvar_95=0.0,
        tail_index=None,
        method=f"{UNAVAILABLE_METHOD_PREFIX}_degenerate_forecast_intervals",
    )

    class _Ctx:
        current_regime = "EXPANSION"
        regime_confidence = 0.9

    gate = _risk_gate(
        {},
        {"risk_measures": metrics, "build_context": _Ctx(), "position_sizing": {}},
    )
    assert isinstance(gate, RiskDecision)
    assert gate.action != "proceed"
    assert "unavailable" in gate.reason.lower()


def test_risk_gate_healthy_metrics_still_proceed():
    from forecasting.risk_measures import RiskMetrics
    from orchestration.stages import _risk_gate

    metrics = RiskMetrics(
        var_95=-0.01, var_99=-0.02, cvar_95=-0.03, tail_index=0.2,
        method="historical",
    )

    class _Ctx:
        current_regime = "EXPANSION"
        regime_confidence = 0.9

    gate = _risk_gate(
        {},
        {"risk_measures": metrics, "build_context": _Ctx(), "position_sizing": {}},
    )
    assert gate.action == "proceed"


def test_risk_reporter_never_fabricates_returns():
    import numpy as np

    from pre_market.risk_reporter import RiskReportGenerator

    generator = RiskReportGenerator()
    snap = generator.generate(portfolio_returns=None)
    assert snap.status == RiskReportGenerator.UNAVAILABLE
    too_short = np.array([0.01, 0.02])
    snap2 = generator.generate(portfolio_returns=too_short)
    assert snap2.status == RiskReportGenerator.UNAVAILABLE
    # a real series is measured normally
    rng = np.random.default_rng(7)
    real = rng.normal(0.0, 0.01, 300)
    snap3 = generator.generate(portfolio_returns=real)
    assert snap3.status == "ok"
    assert snap3.var_95 < 0.0


# ---------------------------------------------------------------------------
# positioning availability
# ---------------------------------------------------------------------------


def test_positioning_snapshot_roundtrips_availability():
    from pre_market.contracts import PositioningSnapshot

    snap = PositioningSnapshot(
        cot_z_score=0.0,
        cot_regime="unavailable",
        etf_flow_momentum="unknown",
        etf_flow_change_pct=0.0,
        open_interest_change_pct=1.5,
        gofo_rate=0.0,
        timestamp="t",
        availability={
            "cot": "unavailable_no_data_source",
            "gofo": "unavailable_no_data_source",
            "etf_flow": "available",
            "open_interest": "available",
        },
    )
    restored = PositioningSnapshot.from_dict(snap.to_dict())
    assert restored.availability["cot"] == "unavailable_no_data_source"
    assert restored.availability["open_interest"] == "available"


def test_positioning_cot_and_gofo_declared_unavailable():
    from pre_market.positioning import PositioningDataFetcher

    fetcher = PositioningDataFetcher()
    assert fetcher._fetch_cot()["status"] == "unavailable_no_data_source"
    assert PositioningDataFetcher._fetch_gofo()["status"] == "unavailable_no_data_source"


# ---------------------------------------------------------------------------
# replay engine never writes synthetic files into the repo tree
# ---------------------------------------------------------------------------


def test_replay_synthetic_csvs_go_to_tmp_only(tmp_path):
    from simulation.historical_replay import HistoricalReplayEngine

    data_dir = tmp_path / "economic"
    data_dir.mkdir()
    tmp_workspace = HistoricalReplayEngine._ensure_synthetic_csvs(data_dir)
    try:
        assert tmp_workspace is not None
        # nothing was written into the (empty) repo-side data dir
        assert list(data_dir.iterdir()) == []
        generated = list(Path(tmp_workspace).rglob("*.csv"))
        assert generated, "synthetic fillers must exist in the temp workspace"
    finally:
        import shutil

        shutil.rmtree(tmp_workspace, ignore_errors=True)


# ---------------------------------------------------------------------------
# watchlist fallback is explicit
# ---------------------------------------------------------------------------


def test_watchlist_default_fallback_is_flagged(tmp_path):
    from pre_market.watchlist_builder import WatchlistBuilder

    builder = WatchlistBuilder()
    # no calendar provided at all -> explicit default fallback
    items, status = builder.build_with_status(calendar_csv=None)
    assert status == WatchlistBuilder.STATUS_DEFAULT_FALLBACK
    assert items

    # unreadable calendar path (a directory) -> explicit read-failure state
    items2, status2 = builder.build_with_status(calendar_csv=tmp_path)
    assert status2 == WatchlistBuilder.STATUS_CALENDAR_READ_FAILED


def test_briefing_metadata_carries_watchlist_status():
    from unittest.mock import Mock

    from pre_market.briefing_assembler import PreMarketBriefingAssembler

    overnight_fetcher = Mock(spec=["fetch_all"])
    overnight_fetcher.fetch_all.return_value = {"overnight_changes": []}
    positioning_fetcher = Mock(spec=["fetch"])
    positioning_fetcher.fetch.return_value = None
    assembler = PreMarketBriefingAssembler(
        overnight_fetcher=overnight_fetcher,
        positioning_fetcher=positioning_fetcher,
    )
    briefing = assembler.assemble(calendar_csv=None, external_news_items=[])
    assert briefing.metadata.get("watchlist_status") in (
        "calendar",
        "default_watchlist_fallback",
        "calendar_read_failed",
    )
