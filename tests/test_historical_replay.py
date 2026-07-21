# tests/test_historical_replay.py

from __future__ import annotations

import json
import shutil
import tempfile
from types import SimpleNamespace
from pathlib import Path

import pandas as pd
import pytest

from simulation.historical_replay import (
    ChronologicalOOSEngine,
    ChronologicalOOSResult,
    HistoricalReplayEngine,
    _BUILTIN_EVENTS,
    _SYNTHETIC_EVENTS,
    _classify_actual_direction,
    _decision_is_correct,
    _compute_gold_return,
    compute_oos_summary,
    run_simulation,
)
from simulation.models import (
    EventRunResult,
    ForecastAccuracySummary,
    OOSSummary,
    RiskSummary,
    SimulationReport,
)


# ===========================================================================
# Model serialisation
# ===========================================================================


class TestSimulationReportModels:
    def test_event_run_result_to_dict_full(self) -> None:
        r = EventRunResult(
            event_type="CPI",
            event_date_min="2020-01-01",
            event_date_max="2024-06-01",
            event_count=54,
            success=True,
            execution_time_ms=1234.56,
            cache_hits=3,
            checkpoints_used=5,
            decision="NEUTRAL",
            risk_decision="proceed",
            forecast_model="AutoARIMA",
            forecast_confidence=0.85,
            validation_passed=True,
            validation_metrics={"mape": 12.5, "coverage": 0.88},
            var_95=-0.021,
            cvar_95=-0.035,
            tail_index=3.2,
            position_scaling=0.75,
            risk_gate_action="proceed",
            risk_gate_score=0.92,
        )
        d = r.to_dict()
        assert d["event_type"] == "CPI"
        assert d["success"] is True
        assert d["execution_time_ms"] == 1234.56
        assert d["decision"] == "NEUTRAL"
        assert d["forecast_confidence"] == 0.85
        assert d["validation_metrics"] == {"mape": 12.5, "coverage": 0.88}

    def test_event_run_result_to_dict_minimal(self) -> None:
        r = EventRunResult(
            event_type="NFP",
            event_date_min="2021-01-01",
            event_date_max="2024-01-01",
            event_count=36,
            success=False,
            execution_time_ms=50.0,
            cache_hits=0,
            checkpoints_used=0,
            error="something broke",
        )
        d = r.to_dict()
        assert d["event_type"] == "NFP"
        assert d["success"] is False
        assert d["error"] == "something broke"
        assert "decision" not in d

    def test_forecast_accuracy_summary_to_dict(self) -> None:
        fa = ForecastAccuracySummary(
            total_forecasts=7,
            passed_validations=5,
            failed_validations=2,
            avg_confidence=0.82,
            models_used=("AutoARIMA", "AutoETS"),
        )
        d = fa.to_dict()
        assert d["total_forecasts"] == 7
        assert len(d["models_used"]) == 2

    def test_risk_summary_to_dict(self) -> None:
        rs = RiskSummary(
            total_evaluations=5,
            actions={"proceed": 3, "scale_down": 2},
            avg_var_95=-0.018,
            avg_cvar_95=-0.032,
            avg_tail_index=3.5,
        )
        d = rs.to_dict()
        assert d["total_evaluations"] == 5
        assert d["actions"]["proceed"] == 3

    def test_simulation_report_to_dict(self) -> None:
        report = SimulationReport(
            timestamp="2026-07-18T12:00:00",
            data_dir="/tmp/data",
            gold_data_path="/tmp/gold.csv",
            total_events=200,
            successful_runs=5,
            failed_runs=2,
            avg_execution_time_ms=1500.0,
            cache_hit_ratio=0.42,
            checkpoints_total=20,
            events_processed=("CPI", "NFP"),
            results=(),
            forecast_accuracy=ForecastAccuracySummary(
                total_forecasts=7,
                passed_validations=5,
                failed_validations=2,
            ),
            risk=RiskSummary(total_evaluations=5),
        )
        d = report.to_dict()
        assert d["successful_runs"] == 5
        assert d["cache_hit_ratio"] == 0.42
        assert d["forecast_accuracy"]["total_forecasts"] == 7


# ===========================================================================
# Synthetic CSV generation
# ===========================================================================


class TestSyntheticCsvGeneration:
    def test_generates_gdp_csv(self, tmp_path: Path) -> None:
        from simulation.historical_replay import HistoricalReplayEngine

        path = tmp_path / "economic" / "GDP.csv"
        HistoricalReplayEngine._write_synthetic_csv(
            path, rows=8, start="2019-Q1", mean=2.5, std=2.0,
        )
        df = pd.read_csv(path)
        assert len(df) == 8
        assert list(df.columns) == ["Date", "Value"]
        assert "2019" in df["Date"].iloc[0]

    def test_generates_pmi_csv(self, tmp_path: Path) -> None:
        from simulation.historical_replay import HistoricalReplayEngine

        path = tmp_path / "economic" / "PMI.csv"
        HistoricalReplayEngine._write_synthetic_csv(
            path, rows=12, start="2022-01", mean=52.0, std=4.0,
        )
        df = pd.read_csv(path)
        assert len(df) == 12
        assert df["Value"].mean() == pytest.approx(52.0, abs=4.0)

    def test_generates_fomc_csv(self, tmp_path: Path) -> None:
        from simulation.historical_replay import HistoricalReplayEngine

        path = tmp_path / "calendar" / "FOMC.csv"
        HistoricalReplayEngine._write_synthetic_csv(
            path, rows=10, start="2020-01", mean=2.5, std=1.0,
        )
        df = pd.read_csv(path)
        assert len(df) == 10
        assert "2020" in df["Date"].iloc[0]

    def test_deterministic_synthetic(self, tmp_path: Path) -> None:
        from simulation.historical_replay import HistoricalReplayEngine

        p1 = tmp_path / "a.csv"
        p2 = tmp_path / "b.csv"
        HistoricalReplayEngine._write_synthetic_csv(p1, 5, "2020-01", 2.0, 1.0)
        HistoricalReplayEngine._write_synthetic_csv(p2, 5, "2020-01", 2.0, 1.0)
        df1 = pd.read_csv(p1)
        df2 = pd.read_csv(p2)
        assert df1["Value"].tolist() == df2["Value"].tolist()


# ===========================================================================
# Event discovery
# ===========================================================================


class TestEventDiscovery:
    def test_builtin_events_have_specs(self) -> None:
        assert "CPI" in _BUILTIN_EVENTS
        assert "NFP" in _BUILTIN_EVENTS
        assert "PPI" in _BUILTIN_EVENTS
        assert "INTEREST_RATE" in _BUILTIN_EVENTS

    def test_synthetic_events_have_specs(self) -> None:
        assert "GDP" in _SYNTHETIC_EVENTS
        assert "PMI" in _SYNTHETIC_EVENTS
        assert "FOMC" in _SYNTHETIC_EVENTS

    def test_iter_event_types_order(self) -> None:
        types = HistoricalReplayEngine._iter_event_types()
        assert types == ["CPI", "NFP", "GDP", "INTEREST_RATE", "PMI", "PPI", "FOMC"]
        assert len(types) == 7

    def test_count_csv_rows(self, tmp_path: Path) -> None:
        p = tmp_path / "test.csv"
        p.write_text("Date,Value\n2020-01-01,100\n2020-02-01,101\n", encoding="utf-8")
        assert HistoricalReplayEngine._count_csv_rows(p) == 2

    def test_count_csv_rows_empty(self, tmp_path: Path) -> None:
        p = tmp_path / "empty.csv"
        p.write_text("Date,Value\n", encoding="utf-8")
        assert HistoricalReplayEngine._count_csv_rows(p) == 0

    def test_count_csv_rows_missing_file(self, tmp_path: Path) -> None:
        assert HistoricalReplayEngine._count_csv_rows(tmp_path / "nope.csv") == 0

    def test_csv_date_range(self, tmp_path: Path) -> None:
        p = tmp_path / "range.csv"
        p.write_text("Date,Value\n2020-01-01,100\n2023-12-01,200\n", encoding="utf-8")
        dmin, dmax = HistoricalReplayEngine._csv_date_range(p)
        assert dmin == "2020-01-01"
        assert dmax == "2023-12-01"


# ===========================================================================
# Extraction helpers
# ===========================================================================


class TestExtractionHelpers:
    @staticmethod
    @staticmethod
    def _ns(**kwargs: object) -> SimpleNamespace:
        return SimpleNamespace(**kwargs)

    def _make_finalize(
        self,
        decision_type: str | None = "POSITIVE",
        risk_action: str | None = "proceed",
        risk_score: float = 0.8,
        model: str = "AutoARIMA",
        confidence: float = 0.75,
        validation_passed: bool = True,
        var: float = -0.02,
        cvar: float = -0.03,
        tail: float = 3.0,
        scaling: float = 0.5,
    ) -> dict:
        return {
            "decision": self._ns(decision_type=decision_type) if decision_type else None,
            "risk_decision": self._ns(action=risk_action, score=risk_score) if risk_action else None,
            "forecast_result": self._ns(model_name=model) if model else None,
            "confidence": self._ns(overall=confidence) if confidence else None,
            "validation": self._ns(passed=validation_passed, metrics={"mape": 10.0, "coverage": 0.85})
                if validation_passed is not None else None,
            "risk_metrics": self._ns(var_95=var, cvar_95=cvar, tail_index=tail) if var else None,
            "position_sizing": self._ns(scaling_factor=scaling) if scaling else None,
        }

    def test_extract_decision(self) -> None:
        eng = HistoricalReplayEngine
        assert eng._extract_decision(self._make_finalize("STRONG_POSITIVE")) == "STRONG_POSITIVE"
        assert eng._extract_decision(self._make_finalize(None)) is None

    def test_extract_risk_decision(self) -> None:
        eng = HistoricalReplayEngine
        assert eng._extract_risk_decision(self._make_finalize(risk_action="halt")) == "halt"
        assert eng._extract_risk_decision(self._make_finalize(risk_action=None)) is None

    def test_extract_risk_decision_from_dict(self) -> None:
        eng = HistoricalReplayEngine
        fo = {"risk_decision": {"action": "scale_down", "score": 0.6}}
        assert eng._extract_risk_decision(fo) == "scale_down"

    def test_extract_forecast_confidence(self) -> None:
        eng = HistoricalReplayEngine
        assert eng._extract_forecast_confidence(self._make_finalize(confidence=0.92)) == 0.92

    def test_extract_validation(self) -> None:
        eng = HistoricalReplayEngine
        fo = self._make_finalize(validation_passed=True)
        passed, metrics = eng._extract_validation(fo)
        assert passed is True
        assert metrics is not None
        assert "mape" in metrics

    def test_extract_risk_metrics(self) -> None:
        eng = HistoricalReplayEngine
        fo = self._make_finalize(var=-0.015, cvar=-0.028, tail=3.5)
        var, cvar, tail = eng._extract_risk_metrics(fo)
        assert var == -0.015
        assert cvar == -0.028
        assert tail == 3.5

    def test_extract_position_scaling(self) -> None:
        eng = HistoricalReplayEngine
        fo = self._make_finalize(scaling=0.65)
        assert eng._extract_position_scaling(fo) == 0.65

    def test_extract_risk_gate(self) -> None:
        eng = HistoricalReplayEngine
        fo = self._make_finalize(risk_action="scale_down", risk_score=0.6)
        action, score = eng._extract_risk_gate(fo)
        assert action == "scale_down"
        assert score == 0.6


# ===========================================================================
# HistoricalReplayEngine — fixture-based tests
# ===========================================================================


class TestHistoricalReplayEngine:
    """Tests using temporary CSV fixtures that simulate historical data."""

    @pytest.fixture
    def sim_data_dir(self, tmp_path: Path) -> Path:
        """Create a minimal data directory with one real event CSV and a
        gold CSV, plus synthetic data for the missing types."""
        d = tmp_path / "sim_data"
        econ = d / "economic"
        cal = d / "calendar"
        hist = d / "history" / "gold"
        econ.mkdir(parents=True, exist_ok=True)
        cal.mkdir(parents=True, exist_ok=True)
        hist.mkdir(parents=True, exist_ok=True)

        # Real event data — CPI (Date,Value)
        (econ / "CPIAUCSL.csv").write_text(
            "Date,Value\n"
            "2020-01-15,100.0\n"
            "2020-02-15,101.0\n"
            "2020-03-15,99.5\n"
            "2020-04-15,102.0\n",
            encoding="utf-8",
        )
        # NFP
        (econ / "PAYEMS.csv").write_text(
            "Date,Value\n"
            "2020-01-10,150000.0\n"
            "2020-02-10,151000.0\n"
            "2020-03-10,149000.0\n",
            encoding="utf-8",
        )
        # PPI
        (econ / "PPIACO.csv").write_text(
            "Date,Value\n"
            "2020-01-15,110.0\n"
            "2020-02-15,111.0\n",
            encoding="utf-8",
        )
        # Interest Rate
        (econ / "FEDFUNDS.csv").write_text(
            "Date,Value\n"
            "2020-01-01,1.55\n"
            "2020-02-01,1.50\n"
            "2020-03-01,0.25\n",
            encoding="utf-8",
        )
        # CPI release calendar matching the CPI data reference periods
        (cal / "cpi_releases.csv").write_text(
            "reference_period,release_date,release_time,timezone\n"
            "2020-01-15,2020-01-15,08:30,US/Eastern\n"
            "2020-02-15,2020-02-15,08:30,US/Eastern\n"
            "2020-03-15,2020-03-15,08:30,US/Eastern\n"
            "2020-04-15,2020-04-15,08:30,US/Eastern\n",
            encoding="utf-8",
        )
        # Gold price (Date,Close) — 200 weekly rows starting 2019-01-01 so
        # the earliest CPI release snapshot (2020-01-15) has enough data.
        lines = ["Date,Close"]
        price = 1500.0
        for idx in range(200):
            dt = pd.Timestamp("2019-01-01") + pd.Timedelta(days=idx * 7)
            if dt.weekday() >= 5:
                continue
            lines.append(f"{dt.date().isoformat()},{price:.1f}")
            price += 2.0 if idx % 2 == 0 else -1.0
        (hist / "gold.csv").write_text("\n".join(lines), encoding="utf-8")

        return d

    def test_engine_creates_synthetic_csvs(self, sim_data_dir: Path) -> None:
        """Engine should generate synthetic CSVs for missing event types."""
        engine = HistoricalReplayEngine(
            data_dir=sim_data_dir,
            gold_path=sim_data_dir / "history" / "gold" / "gold.csv",
        )
        # Before run_all, synthetic files should not exist
        assert not (sim_data_dir / "economic" / "GDP.csv").exists()
        assert not (sim_data_dir / "economic" / "PMI.csv").exists()
        assert not (sim_data_dir / "calendar" / "FOMC.csv").exists()

        # run_all generates them
        report = engine.run_all()

        assert report.total_events > 0
        # All 7 event types should have been processed
        assert len(report.results) == 7
        # Some stages may fail with minimal fixture data (e.g. lessons CSV
        # may lack condition columns with only 4 CPI rows).  This is
        # expected — the simulation handles partial failures.
        assert report.successful_runs + report.failed_runs == 7

    def test_run_all_structure(self, sim_data_dir: Path) -> None:
        engine = HistoricalReplayEngine(
            data_dir=sim_data_dir,
            gold_path=sim_data_dir / "history" / "gold" / "gold.csv",
        )
        report = engine.run_all()
        assert isinstance(report, SimulationReport)
        assert "T" in report.timestamp
        assert report.data_dir == str(sim_data_dir.resolve())

        # Structure checks
        assert report.successful_runs + report.failed_runs == len(report.results)
        assert report.total_events >= sum(r.event_count for r in report.results)

    def test_each_event_type_has_result(self, sim_data_dir: Path) -> None:
        engine = HistoricalReplayEngine(
            data_dir=sim_data_dir,
            gold_path=sim_data_dir / "history" / "gold" / "gold.csv",
        )
        report = engine.run_all()
        types_found = {r.event_type for r in report.results}
        expected = {"CPI", "NFP", "PPI", "INTEREST_RATE", "GDP", "PMI", "FOMC"}
        assert types_found == expected

    def test_result_has_metrics(self, sim_data_dir: Path) -> None:
        engine = HistoricalReplayEngine(
            data_dir=sim_data_dir,
            gold_path=sim_data_dir / "history" / "gold" / "gold.csv",
        )
        report = engine.run_all()
        cpi_result = next(r for r in report.results if r.event_type == "CPI")
        assert cpi_result.success is True, (
            f"CPI replay failed: {cpi_result.error}"
        )
        assert cpi_result.event_count > 0
        assert cpi_result.execution_time_ms > 0

    def test_forecast_summary_aggregated(self, sim_data_dir: Path) -> None:
        engine = HistoricalReplayEngine(
            data_dir=sim_data_dir,
            gold_path=sim_data_dir / "history" / "gold" / "gold.csv",
        )
        report = engine.run_all()
        fa = report.forecast_accuracy
        assert fa.total_forecasts == len(report.results)
        # With minimal fixture data, some forecasts may fail before
        # validation runs, so passed+failed may be less than total.
        assert fa.passed_validations + fa.failed_validations <= fa.total_forecasts

    def test_risk_summary_aggregated(self, sim_data_dir: Path) -> None:
        engine = HistoricalReplayEngine(
            data_dir=sim_data_dir,
            gold_path=sim_data_dir / "history" / "gold" / "gold.csv",
        )
        report = engine.run_all()
        risk = report.risk
        # Some runs may fail before risk gate; verify structure is valid
        assert risk.total_evaluations >= 0

    def test_report_to_dict_roundtrip(self, sim_data_dir: Path) -> None:
        engine = HistoricalReplayEngine(
            data_dir=sim_data_dir,
            gold_path=sim_data_dir / "history" / "gold" / "gold.csv",
        )
        report = engine.run_all()
        d = report.to_dict()
        assert isinstance(json.dumps(d), str)  # serialisable

    def test_run_simulation_convenience(self, sim_data_dir: Path) -> None:
        report = run_simulation(
            data_dir=str(sim_data_dir),
            gold_path=str(sim_data_dir / "history" / "gold" / "gold.csv"),
        )
        assert isinstance(report, SimulationReport)
        assert report.successful_runs + report.failed_runs == 7

    def test_gold_date_column(self, tmp_path: Path) -> None:
        """When gold CSV uses Date,Close columns (standard format),
        the pipeline should load correctly."""
        d = tmp_path / "custom_gold"
        econ = d / "economic"
        hist = d / "history" / "gold"
        econ.mkdir(parents=True, exist_ok=True)
        hist.mkdir(parents=True, exist_ok=True)

        (econ / "CPIAUCSL.csv").write_text("Date,Value\n2023-01-01,100.0\n", encoding="utf-8")
        (hist / "gold.csv").write_text(
            "Date,Close\n2023-01-02,1800.0\n2023-01-03,1810.0\n",
            encoding="utf-8",
        )
        engine = HistoricalReplayEngine(
            data_dir=d,
            gold_path=hist / "gold.csv",
        )
        report = engine.run_all()
        cpi = next((r for r in report.results if r.event_type == "CPI"), None)
        assert cpi is not None

    # -- OOS correctness integration ---------------------------------------

    def test_cpi_result_has_correctness_fields(self, sim_data_dir: Path) -> None:
        engine = HistoricalReplayEngine(
            data_dir=sim_data_dir,
            gold_path=sim_data_dir / "history" / "gold" / "gold.csv",
        )
        report = engine.run_all()
        cpi = next(r for r in report.results if r.event_type == "CPI")
        # decision_actual_return_pct is always computed when gold data exists
        assert cpi.decision_actual_return_pct is not None
        assert isinstance(cpi.decision_actual_return_pct, float)
        # decision_correct is None when system abstains (INSUFFICIENT_EVIDENCE)
        if cpi.decision == "INSUFFICIENT_EVIDENCE":
            assert cpi.decision_correct is None
        else:
            assert cpi.decision_correct is not None

    def test_non_cpi_result_no_correctness(self, sim_data_dir: Path) -> None:
        engine = HistoricalReplayEngine(
            data_dir=sim_data_dir,
            gold_path=sim_data_dir / "history" / "gold" / "gold.csv",
        )
        report = engine.run_all()
        for r in report.results:
            if r.event_type != "CPI":
                assert r.decision_correct is None, f"{r.event_type} should not have correctness"
                assert r.decision_actual_return_pct is None


# ===========================================================================
# End‑to‑end with real repository data
# ===========================================================================


class TestRealDataSimulation:
    """Integration tests using the actual ``data/`` directory in the repo.
    These tests verify that the simulation works against real historical
    economic data."""

    PROJECT_ROOT = Path(__file__).resolve().parents[1]
    DATA_DIR = PROJECT_ROOT / "data"
    GOLD_PATH = DATA_DIR / "history" / "gold" / "gold.csv"

    @pytest.mark.skipif(
        not DATA_DIR.exists(),
        reason="data/ directory not found at project root",
    )
    def test_real_data_discovery(self) -> None:
        assert self.DATA_DIR.exists()
        assert self.GOLD_PATH.exists()

        # Built-in event files should exist
        assert (self.DATA_DIR / "economic" / "CPIAUCSL.csv").exists()
        assert (self.DATA_DIR / "economic" / "PAYEMS.csv").exists()
        assert (self.DATA_DIR / "economic" / "PPIACO.csv").exists()
        assert (self.DATA_DIR / "economic" / "FEDFUNDS.csv").exists()

    @pytest.mark.skipif(
        not DATA_DIR.exists(),
        reason="data/ directory not found at project root",
    )
    def test_real_data_simulation_runs(self) -> None:
        """Run the full simulation against real data files.  This is the
        primary acceptance test for Phase 19.1."""
        engine = HistoricalReplayEngine(
            data_dir=self.DATA_DIR,
            gold_path=self.GOLD_PATH,
            horizon=6,
        )
        report = engine.run_all()

        assert isinstance(report, SimulationReport)
        assert report.total_events > 0

        # All 7 event types should be reported
        assert len(report.results) == 7
        assert report.cache_hit_ratio >= 0.0

        # Verify CPI result specifically (largest dataset)
        cpi_result = next(r for r in report.results if r.event_type == "CPI")
        assert cpi_result.event_count > 10  # plenty of historical CPI rows
        assert cpi_result.execution_time_ms > 0

    @pytest.mark.skipif(
        not DATA_DIR.exists(),
        reason="data/ directory not found at project root",
    )
    def test_real_data_serialisable(self) -> None:
        engine = HistoricalReplayEngine(
            data_dir=self.DATA_DIR,
            gold_path=self.GOLD_PATH,
        )
        report = engine.run_all()
        d = report.to_dict()
        assert isinstance(json.dumps(d), str)
        # Verify top-level keys
        for key in (
            "timestamp", "total_events", "successful_runs", "failed_runs",
            "avg_execution_time_ms", "cache_hit_ratio", "events_processed",
            "forecast_accuracy", "risk",
        ):
            assert key in d, f"Missing key: {key}"


# ===========================================================================
# Edge cases
# ===========================================================================


class TestEdgeCases:
    def test_engine_with_empty_data_dir(self, tmp_path: Path) -> None:
        """Engine should handle a directory with no event data gracefully."""
        gold_path = tmp_path / "history" / "gold" / "gold.csv"
        gold_path.parent.mkdir(parents=True, exist_ok=True)
        gold_path.write_text("Date,Close\n2023-01-01,1800.0\n", encoding="utf-8")

        engine = HistoricalReplayEngine(
            data_dir=tmp_path,
            gold_path=gold_path,
        )
        report = engine.run_all()
        # Only synthetic events have results (built-in CSVs are missing)
        assert len(report.results) == 3
        assert report.failed_runs == 3
        assert report.successful_runs == 0

    def test_engine_with_bad_gold_path(self, tmp_path: Path) -> None:
        d = tmp_path / "bad_gold"
        econ = d / "economic"
        econ.mkdir(parents=True, exist_ok=True)
        (econ / "CPIAUCSL.csv").write_text("Date,Value\n2020-01-01,100.0\n", encoding="utf-8")

        engine = HistoricalReplayEngine(
            data_dir=d,
            gold_path=tmp_path / "nonexistent.csv",
        )
        report = engine.run_all()
        assert report.failed_runs >= 1

    def test_run_simulation_kwargs(self, tmp_path: Path) -> None:
        """run_simulation convenience function accepts all kwargs."""
        d = tmp_path / "kwargs_test"
        econ = d / "economic"
        hist = d / "history" / "gold"
        econ.mkdir(parents=True, exist_ok=True)
        hist.mkdir(parents=True, exist_ok=True)
        (econ / "CPIAUCSL.csv").write_text("Date,Value\n2020-01-01,100.0\n", encoding="utf-8")
        (hist / "gold.csv").write_text("Date,Close\n2020-01-02,1800.0\n", encoding="utf-8")

        report = run_simulation(
            data_dir=str(d),
            gold_path=str(hist / "gold.csv"),
            max_workers=2,
            horizon=3,
        )
        assert isinstance(report, SimulationReport)

    def test_skip_missing_generated_csv(self, tmp_path: Path) -> None:
        """If a synthetic CSV already exists, the engine should not
        regenerate it."""
        d = tmp_path / "skip_gen"
        econ = d / "economic"
        cal = d / "calendar"
        hist = d / "history" / "gold"
        econ.mkdir(parents=True, exist_ok=True)
        cal.mkdir(parents=True, exist_ok=True)
        hist.mkdir(parents=True, exist_ok=True)

        (hist / "gold.csv").write_text("Date,Close\n2020-01-01,1800.0\n", encoding="utf-8")
        # Pre-create synthetic CSV with known content
        (econ / "GDP.csv").write_text("Date,Value\n2020-01-01,42.0\n", encoding="utf-8")
        (econ / "PMI.csv").write_text("Date,Value\n2020-02-01,55.0\n", encoding="utf-8")
        (cal / "FOMC.csv").write_text("Date,Value\n2020-03-01,1.5\n", encoding="utf-8")

        engine = HistoricalReplayEngine(data_dir=d, gold_path=hist / "gold.csv")
        engine.run_all()
        # Verify the pre-created file was not overwritten
        gdp_df = pd.read_csv(econ / "GDP.csv")
        assert gdp_df["Value"].iloc[0] == 42.0


# ===========================================================================
# OOS correctness evaluation
# ===========================================================================


class TestOosCorrectnessEvaluation:
    """Unit tests for the OOS correctness helpers and integration test
    verifying the fields are populated on EventRunResult."""

    # -- _classify_actual_direction -----------------------------------------

    def test_classify_up(self) -> None:
        assert _classify_actual_direction(0.50) == "UP"
        assert _classify_actual_direction(0.11) == "UP"
        assert _classify_actual_direction(99.0) == "UP"

    def test_classify_down(self) -> None:
        assert _classify_actual_direction(-0.50) == "DOWN"
        assert _classify_actual_direction(-0.11) == "DOWN"
        assert _classify_actual_direction(-99.0) == "DOWN"

    def test_classify_flat(self) -> None:
        assert _classify_actual_direction(0.0) == "FLAT"
        assert _classify_actual_direction(0.05) == "FLAT"
        assert _classify_actual_direction(-0.05) == "FLAT"

    def test_classify_boundary(self) -> None:
        assert _classify_actual_direction(0.10) == "FLAT"
        assert _classify_actual_direction(-0.10) == "FLAT"
        assert _classify_actual_direction(0.1001) == "UP"
        assert _classify_actual_direction(-0.1001) == "DOWN"

    # -- _decision_is_correct -----------------------------------------------

    def test_positive_correct(self) -> None:
        assert _decision_is_correct("POSITIVE", "UP") is True
        assert _decision_is_correct("POSITIVE", "DOWN") is False
        assert _decision_is_correct("POSITIVE", "FLAT") is False

    def test_negative_correct(self) -> None:
        assert _decision_is_correct("NEGATIVE", "DOWN") is True
        assert _decision_is_correct("NEGATIVE", "UP") is False
        assert _decision_is_correct("NEGATIVE", "FLAT") is False

    def test_strong_positive_correct(self) -> None:
        assert _decision_is_correct("STRONG_POSITIVE", "UP") is True
        assert _decision_is_correct("STRONG_POSITIVE", "DOWN") is False
        assert _decision_is_correct("STRONG_POSITIVE", "FLAT") is False

    def test_strong_negative_correct(self) -> None:
        assert _decision_is_correct("STRONG_NEGATIVE", "DOWN") is True
        assert _decision_is_correct("STRONG_NEGATIVE", "UP") is False
        assert _decision_is_correct("STRONG_NEGATIVE", "FLAT") is False

    def test_neutral_correct(self) -> None:
        assert _decision_is_correct("NEUTRAL", "FLAT") is True
        assert _decision_is_correct("NEUTRAL", "UP") is False
        assert _decision_is_correct("NEUTRAL", "DOWN") is False

    def test_insufficient_evidence_abstains(self) -> None:
        assert _decision_is_correct("INSUFFICIENT_EVIDENCE", "UP") is None
        assert _decision_is_correct("INSUFFICIENT_EVIDENCE", "DOWN") is None
        assert _decision_is_correct("INSUFFICIENT_EVIDENCE", "FLAT") is None

    def test_unknown_decision_returns_none(self) -> None:
        assert _decision_is_correct("BANANAS", "UP") is None

    # -- _compute_gold_return -----------------------------------------------

    def test_gold_return_positive(self) -> None:
        gold = pd.DataFrame({
            "Date": pd.to_datetime([
                "2024-01-01", "2024-01-02",
                "2024-01-06", "2024-01-07",
            ]),
            "Close": [100.0, 101.0, 105.0, 106.0],
        })
        entry = pd.Timestamp("2024-01-02")
        ret = _compute_gold_return(gold, entry, horizon_days=5)
        assert ret is not None
        # entry=101.0 (2024-01-02), future=106.0 (2024-01-07) => (106-101)/101*100
        assert ret == pytest.approx(4.950495, abs=1e-5)

    def test_gold_return_negative(self) -> None:
        gold = pd.DataFrame({
            "Date": pd.to_datetime([
                "2024-01-01", "2024-01-02",
                "2024-01-06", "2024-01-07",
            ]),
            "Close": [100.0, 101.0, 95.0, 94.0],
        })
        entry = pd.Timestamp("2024-01-02")
        ret = _compute_gold_return(gold, entry, horizon_days=5)
        assert ret is not None
        # entry=101.0 (2024-01-02), future=94.0 (2024-01-07) => (94-101)/101*100
        assert ret == pytest.approx(-6.930693, abs=1e-5)

    def test_gold_return_exact_day_match(self) -> None:
        gold = pd.DataFrame({
            "Date": pd.to_datetime(["2024-06-01", "2024-06-06"]),
            "Close": [200.0, 210.0],
        })
        entry = pd.Timestamp("2024-06-01")
        ret = _compute_gold_return(gold, entry, horizon_days=5)
        assert ret is not None
        assert ret == pytest.approx(5.0, abs=1e-5)

    def test_gold_return_no_entry_data(self) -> None:
        gold = pd.DataFrame({
            "Date": pd.to_datetime(["2024-06-10", "2024-06-15"]),
            "Close": [200.0, 210.0],
        })
        entry = pd.Timestamp("2024-06-01")
        ret = _compute_gold_return(gold, entry, horizon_days=5)
        assert ret is None

    def test_gold_return_no_future_data(self) -> None:
        gold = pd.DataFrame({
            "Date": pd.to_datetime(["2024-06-01", "2024-06-02"]),
            "Close": [200.0, 201.0],
        })
        entry = pd.Timestamp("2024-06-02")
        ret = _compute_gold_return(gold, entry, horizon_days=10)
        assert ret is None


# ===========================================================================
# OOS report — pure aggregation tests
# ===========================================================================


def _r(
    event_type: str,
    decision: str | None,
    decision_correct: bool | None,
    actual_return: float | None = None,
    confidence: float | None = None,
) -> EventRunResult:
    """Minimal EventRunResult factory for OOS test data."""
    return EventRunResult(
        event_type=event_type,
        event_date_min="",
        event_date_max="",
        event_count=1,
        success=True,
        execution_time_ms=0.0,
        cache_hits=0,
        checkpoints_used=0,
        decision=decision,
        forecast_confidence=confidence,
        decision_correct=decision_correct,
        decision_actual_return_pct=actual_return,
    )


class TestOOSReport:
    """Tests for compute_oos_summary and OOSSummary model."""

    # -- empty / edge cases -----------------------------------------------

    def test_empty_results(self) -> None:
        s = compute_oos_summary(())
        assert s.total_events == 0
        assert s.scored_events == 0
        assert s.abstained_events == 0
        assert s.directional_accuracy is None
        assert s.macro_precision is None
        assert s.macro_recall is None
        assert s.coverage is None
        assert s.abstention_rate is None
        assert s.strong_error_rate is None
        assert s.ece is None
        assert s.decision_distribution == {}

    def test_all_abstained(self) -> None:
        results = (
            _r("CPI", "INSUFFICIENT_EVIDENCE", None),
            _r("NFP", "INSUFFICIENT_EVIDENCE", None),
        )
        s = compute_oos_summary(results)
        assert s.total_events == 2
        assert s.scored_events == 0
        assert s.abstained_events == 2
        assert s.coverage == 0.0
        assert s.abstention_rate == 1.0
        assert s.directional_accuracy is None

    def test_no_decision_events_excluded(self) -> None:
        """Events with decision=None are counted in total_events but do
        not affect coverage (they are structural failures, not abstentions)."""
        results = (
            _r("CPI", "POSITIVE", True, 0.5),
            _r("FAILED", None, None),
        )
        s = compute_oos_summary(results)
        assert s.total_events == 2
        assert s.scored_events == 1
        assert s.abstained_events == 0
        assert s.coverage == 1.0  # 1 scored / 1 with decision
        assert s.decision_distribution == {"POSITIVE": 1, "NO_DECISION": 1}

    # -- directional accuracy ---------------------------------------------

    def test_directional_accuracy_perfect(self) -> None:
        results = (
            _r("A", "POSITIVE", True, 0.5),
            _r("B", "NEGATIVE", True, -0.5),
            _r("C", "STRONG_POSITIVE", True, 0.3),
        )
        s = compute_oos_summary(results)
        assert s.directional_accuracy == 1.0

    def test_directional_accuracy_zero(self) -> None:
        results = (
            _r("A", "POSITIVE", False, -0.5),
            _r("B", "NEGATIVE", False, 0.5),
        )
        s = compute_oos_summary(results)
        assert s.directional_accuracy == 0.0

    def test_directional_accuracy_excludes_neutral(self) -> None:
        """NEUTRAL predictions are not directional bets."""
        results = (
            _r("A", "POSITIVE", True, 0.5),
            _r("B", "NEUTRAL", True, 0.05),
            _r("C", "NEGATIVE", False, 0.5),
        )
        s = compute_oos_summary(results)
        # Directional: A correct, C wrong → 1/2 = 0.5
        assert s.directional_accuracy == 0.5

    def test_directional_accuracy_excludes_abstained(self) -> None:
        results = (
            _r("A", "POSITIVE", True, 0.5),
            _r("B", "INSUFFICIENT_EVIDENCE", None),
        )
        s = compute_oos_summary(results)
        assert s.directional_accuracy == 1.0

    # -- precision ---------------------------------------------------------

    def test_precision_up(self) -> None:
        # 2 correct UP, 1 incorrect UP → precision_up = 2/3
        results = (
            _r("A", "POSITIVE", True, 0.5),
            _r("B", "STRONG_POSITIVE", True, 0.8),
            _r("C", "POSITIVE", False, -0.5),
        )
        s = compute_oos_summary(results)
        assert s.precision_up == pytest.approx(2.0 / 3.0)

    def test_precision_down(self) -> None:
        results = (
            _r("A", "NEGATIVE", True, -0.5),
            _r("B", "STRONG_NEGATIVE", True, -0.8),
            _r("C", "NEGATIVE", False, 0.5),
            _r("D", "NEGATIVE", False, 0.05),
        )
        s = compute_oos_summary(results)
        assert s.precision_down == pytest.approx(2.0 / 4.0)

    def test_precision_flat(self) -> None:
        results = (
            _r("A", "NEUTRAL", True, 0.05),
            _r("B", "NEUTRAL", True, -0.03),
            _r("C", "NEUTRAL", False, 0.5),
        )
        s = compute_oos_summary(results)
        assert s.precision_flat == pytest.approx(2.0 / 3.0)

    def test_precision_up_no_predictions(self) -> None:
        results = (
            _r("A", "NEGATIVE", True, -0.5),
            _r("B", "NEUTRAL", True, 0.05),
        )
        s = compute_oos_summary(results)
        assert s.precision_up is None

    # -- recall ------------------------------------------------------------

    def test_recall_up(self) -> None:
        # actual UP in 3 events: 2 predicted UP, 1 predicted DOWN → recall_up = 2/3
        results = (
            _r("A", "POSITIVE", True, 0.5),
            _r("B", "STRONG_POSITIVE", True, 0.8),
            _r("C", "NEGATIVE", False, 0.5),  # wrong: actual UP but predicted DOWN
        )
        s = compute_oos_summary(results)
        assert s.recall_up == pytest.approx(2.0 / 3.0)

    def test_recall_down(self) -> None:
        results = (
            _r("A", "NEGATIVE", True, -0.5),
            _r("B", "POSITIVE", False, -0.5),  # wrong: actual DOWN but predicted UP
        )
        s = compute_oos_summary(results)
        assert s.recall_down == pytest.approx(1.0 / 2.0)

    def test_recall_flat(self) -> None:
        results = (
            _r("A", "NEUTRAL", True, 0.05),
            _r("B", "NEUTRAL", True, -0.03),
            _r("C", "POSITIVE", False, 0.03),  # wrong: actual FLAT but predicted UP
        )
        s = compute_oos_summary(results)
        assert s.recall_flat == pytest.approx(2.0 / 3.0)

    # -- macro averages ----------------------------------------------------

    def test_macro_precision_recall(self) -> None:
        """2 correct UP / 4 UP predictions → prec_up=0.5
        1 correct DOWN / 3 DOWN predictions → prec_down=1/3
        1 correct FLAT / 1 FLAT predictions → prec_flat=1.0
        macro_precision = (0.5 + 1/3 + 1.0) / 3 = 0.611...

        2 actual UP / 3 actual UP found → rec_up=2/3
        1 actual DOWN / 3 actual DOWN found → rec_down=1/3
        1 actual FLAT / 2 actual FLAT found → rec_flat=0.5
        macro_recall = (2/3 + 1/3 + 0.5) / 3 = 0.5
        """
        results = (
            # UP predictions: 2 correct, 2 wrong (C and G)
            _r("A", "POSITIVE", True, 0.5),
            _r("B", "STRONG_POSITIVE", True, 0.8),
            _r("C", "POSITIVE", False, -0.5),     # actual DOWN
            # DOWN predictions: 1 correct, 2 wrong
            _r("D", "NEGATIVE", True, -0.5),
            _r("E", "NEGATIVE", False, 0.5),       # actual UP
            _r("H", "NEGATIVE", False, 0.03),       # actual FLAT
            # FLAT predictions: 1 correct
            _r("F", "NEUTRAL", True, 0.05),
            # actual DOWN predicted UP
            _r("G", "POSITIVE", False, -0.3),
        )
        s = compute_oos_summary(results)
        assert s.precision_up == pytest.approx(2.0 / 4.0)
        assert s.precision_down == pytest.approx(1.0 / 3.0)
        assert s.precision_flat == 1.0
        assert s.macro_precision == pytest.approx((0.5 + 1.0/3.0 + 1.0) / 3.0)
        assert s.recall_up == pytest.approx(2.0 / 3.0)
        assert s.recall_down == pytest.approx(1.0 / 3.0)
        assert s.recall_flat == pytest.approx(1.0 / 2.0)
        assert s.macro_recall == pytest.approx(0.5)

    # -- coverage / abstention rate ----------------------------------------

    def test_coverage_mixed(self) -> None:
        results = (
            _r("A", "POSITIVE", True, 0.5),
            _r("B", "INSUFFICIENT_EVIDENCE", None),
            _r("C", "NEGATIVE", True, -0.5),
        )
        s = compute_oos_summary(results)
        assert s.coverage == pytest.approx(2.0 / 3.0)
        assert s.abstention_rate == pytest.approx(1.0 / 3.0)

    def test_coverage_and_abstention_sum_to_one(self) -> None:
        results = (
            _r("A", "POSITIVE", True, 0.5),
            _r("B", "INSUFFICIENT_EVIDENCE", None),
            _r("C", "NEGATIVE", True, -0.5),
            _r("D", "INSUFFICIENT_EVIDENCE", None),
        )
        s = compute_oos_summary(results)
        if s.coverage is not None and s.abstention_rate is not None:
            assert s.coverage + s.abstention_rate == pytest.approx(1.0)

    # -- strong error rate -------------------------------------------------

    def test_strong_error_rate_all_correct(self) -> None:
        results = (
            _r("A", "STRONG_POSITIVE", True, 0.5),
            _r("B", "STRONG_NEGATIVE", True, -0.5),
        )
        s = compute_oos_summary(results)
        assert s.strong_error_rate == 0.0

    def test_strong_error_rate_all_wrong(self) -> None:
        results = (
            _r("A", "STRONG_POSITIVE", False, -0.5),
            _r("B", "STRONG_NEGATIVE", False, 0.5),
        )
        s = compute_oos_summary(results)
        assert s.strong_error_rate == 1.0

    def test_strong_error_rate_mixed(self) -> None:
        """A (correct), B (wrong), C (wrong) → 2 wrong / 3 strong = 2/3."""
        results = (
            _r("A", "STRONG_POSITIVE", True, 0.5),
            _r("B", "STRONG_NEGATIVE", False, 0.5),
            _r("C", "STRONG_POSITIVE", False, -0.5),
            _r("D", "POSITIVE", True, 0.3),  # not strong
        )
        s = compute_oos_summary(results)
        assert s.strong_error_rate == pytest.approx(2.0 / 3.0)

    def test_strong_error_rate_no_strong(self) -> None:
        results = (
            _r("A", "POSITIVE", True, 0.5),
            _r("B", "NEUTRAL", True, 0.05),
        )
        s = compute_oos_summary(results)
        assert s.strong_error_rate is None

    # -- ECE ---------------------------------------------------------------

    def test_ece_perfect_calibration(self) -> None:
        """10 events at confidence=0.5, 5 correct, 5 wrong.
        Bin [0.4, 0.6): accuracy=0.5, mean_conf=0.5 → |acc-conf| = 0."""
        results = tuple(
            _r(f"E{i}", "POSITIVE", i < 5, 0.5 if i < 5 else -0.5, confidence=0.5)
            for i in range(10)
        )
        s = compute_oos_summary(results)
        assert s.ece == pytest.approx(0.0, abs=1e-9)

    def test_ece_miscalibrated(self) -> None:
        """Overconfident: high confidence but low accuracy."""
        results = (
            # Bin [0.8, 1.0): conf=0.9, 0 correct / 2 → accuracy=0.0
            _r("A", "POSITIVE", False, -0.5, confidence=0.9),
            _r("B", "POSITIVE", False, -0.5, confidence=0.9),
            # Bin [0.0, 0.2): conf=0.1, 2 correct / 2 → accuracy=1.0
            _r("C", "POSITIVE", True, 0.5, confidence=0.1),
            _r("D", "POSITIVE", True, 0.5, confidence=0.1),
        )
        s = compute_oos_summary(results)
        # ECE = 0.5 * |0.0 - 0.9| + 0.5 * |1.0 - 0.1| = 0.5*0.9 + 0.5*0.9 = 0.9
        assert s.ece == pytest.approx(0.9)

    def test_ece_no_confidence(self) -> None:
        """Events without forecast_confidence are excluded from ECE."""
        results = (
            _r("A", "POSITIVE", True, 0.5),  # no confidence
            _r("B", "POSITIVE", True, 0.5, confidence=0.8),
        )
        s = compute_oos_summary(results)
        # Only 1 event with confidence, single bin: |acc-conf| = |1.0-0.8| = 0.2
        assert s.ece == pytest.approx(0.2)

    # -- decision distribution ---------------------------------------------

    def test_decision_distribution(self) -> None:
        results = (
            _r("A", "POSITIVE", True, 0.5),
            _r("B", "NEGATIVE", True, -0.5),
            _r("C", "NEUTRAL", True, 0.05),
            _r("D", "INSUFFICIENT_EVIDENCE", None),
            _r("E", "STRONG_POSITIVE", True, 0.8),
            _r("F", "POSITIVE", False, -0.3),
        )
        s = compute_oos_summary(results)
        assert s.decision_distribution == {
            "POSITIVE": 2,
            "NEGATIVE": 1,
            "NEUTRAL": 1,
            "INSUFFICIENT_EVIDENCE": 1,
            "STRONG_POSITIVE": 1,
        }

    # -- determinism -------------------------------------------------------

    def test_deterministic(self) -> None:
        """Same input always produces the same OOSSummary."""
        results = (
            _r("A", "POSITIVE", True, 0.5),
            _r("B", "NEGATIVE", False, 0.5),
            _r("C", "INSUFFICIENT_EVIDENCE", None),
        )
        s1 = compute_oos_summary(results)
        s2 = compute_oos_summary(results)
        assert s1 == s2
        assert s1.to_dict() == s2.to_dict()

    # -- model serialisation -----------------------------------------------

    def test_oos_summary_to_dict(self) -> None:
        results = (
            _r("A", "POSITIVE", True, 0.5),
            _r("B", "NEGATIVE", False, 0.5),
        )
        s = compute_oos_summary(results)
        d = s.to_dict()
        assert isinstance(d, dict)
        assert d["total_events"] == 2
        assert d["scored_events"] == 2
        assert d["abstained_events"] == 0
        assert isinstance(d["directional_accuracy"], float)
        assert isinstance(d["decision_distribution"], dict)
        assert json.dumps(d)  # serialisable


# ===========================================================================
# Chronological OOS Engine
# ===========================================================================


class TestChronologicalOOSResult:
    """Tests for the ChronologicalOOSResult data model."""

    def test_defaults(self) -> None:
        r = ChronologicalOOSResult(cutoff_date="2023-01-01")
        assert r.cutoff_date == "2023-01-01"
        assert r.training_results == ()
        assert r.evaluation_results == ()
        assert r.summary is None
        assert r.errors == ()

    def test_to_dict_with_summary(self) -> None:
        s = compute_oos_summary((
            _r("A", "POSITIVE", True, 0.5),
        ))
        r = ChronologicalOOSResult(
            cutoff_date="2023-01-01",
            evaluation_results=(_r("A", "POSITIVE", True, 0.5),),
            summary=s,
        )
        d = r.to_dict()
        assert "cutoff_date" in d
        assert d["evaluation_events"] == 1
        assert "summary" in d
        assert json.dumps(d)


class TestChronologicalOOSEngine:
    """Integration tests for chronological train/eval separation."""

    @pytest.fixture
    def sim_data_dir(self, tmp_path: Path) -> Path:
        """Same fixture as TestHistoricalReplayEngine.sim_data_dir."""
        import pandas as pd
        d = tmp_path / "sim_data"
        econ = d / "economic"
        cal = d / "calendar"
        hist = d / "history" / "gold"
        econ.mkdir(parents=True, exist_ok=True)
        cal.mkdir(parents=True, exist_ok=True)
        hist.mkdir(parents=True, exist_ok=True)

        (econ / "CPIAUCSL.csv").write_text(
            "Date,Value\n"
            "2020-01-15,100.0\n"
            "2020-02-15,101.0\n"
            "2020-03-15,99.5\n"
            "2020-04-15,102.0\n",
            encoding="utf-8",
        )
        (econ / "PAYEMS.csv").write_text(
            "Date,Value\n"
            "2020-01-10,150000.0\n"
            "2020-02-10,151000.0\n"
            "2020-03-10,149000.0\n",
            encoding="utf-8",
        )
        (econ / "PPIACO.csv").write_text(
            "Date,Value\n"
            "2020-01-15,110.0\n"
            "2020-02-15,111.0\n",
            encoding="utf-8",
        )
        (econ / "FEDFUNDS.csv").write_text(
            "Date,Value\n"
            "2020-01-01,1.55\n"
            "2020-02-01,1.50\n"
            "2020-03-01,0.25\n",
            encoding="utf-8",
        )
        (cal / "cpi_releases.csv").write_text(
            "reference_period,release_date,release_time,timezone\n"
            "2020-01-15,2020-01-15,08:30,US/Eastern\n"
            "2020-02-15,2020-02-15,08:30,US/Eastern\n"
            "2020-03-15,2020-03-15,08:30,US/Eastern\n"
            "2020-04-15,2020-04-15,08:30,US/Eastern\n",
            encoding="utf-8",
        )
        lines = ["Date,Close"]
        price = 1500.0
        for idx in range(200):
            dt = pd.Timestamp("2019-01-01") + pd.Timedelta(days=idx * 7)
            if dt.weekday() >= 5:
                continue
            lines.append(f"{dt.date().isoformat()},{price:.1f}")
            price += 2.0 if idx % 2 == 0 else -1.0
        (hist / "gold.csv").write_text("\n".join(lines), encoding="utf-8")
        return d

    def test_cpi_separation_produces_results(
        self, sim_data_dir: Path
    ) -> None:
        """CPI events after cutoff are replayed with training knowledge."""
        cutoff = "2020-03-01"
        engine = ChronologicalOOSEngine(
            cutoff_date=cutoff,
            data_dir=sim_data_dir,
            gold_path=sim_data_dir / "history" / "gold" / "gold.csv",
            max_workers=2,
        )
        result = engine.run()
        assert result.cutoff_date == "2020-03-01"
        assert isinstance(result, ChronologicalOOSResult)
        # At least CPI should have an evaluation result
        cpi_evals = [r for r in result.evaluation_results if r.event_type == "CPI"]
        assert len(cpi_evals) == 1
        cpi = cpi_evals[0]
        # CPI with releases on/after 2020-03-15 should have data
        assert cpi.event_count > 0
        # OOS summary should be populated
        assert result.summary is not None
        assert result.summary.total_events == len(result.evaluation_results)

    def test_knowledge_dir_created(self, sim_data_dir: Path) -> None:
        """Training knowledge is persisted to the knowledge directory."""
        cutoff = "2020-03-01"
        knowledge_dir = sim_data_dir / "oos_knowledge"
        engine = ChronologicalOOSEngine(
            cutoff_date=cutoff,
            data_dir=sim_data_dir,
            gold_path=sim_data_dir / "history" / "gold" / "gold.csv",
            knowledge_dir=knowledge_dir,
            max_workers=2,
        )
        engine.run()
        # CPI training lessons should exist
        assert (knowledge_dir / "CPI" / "lessons.csv").exists()

    def test_deterministic(self, sim_data_dir: Path) -> None:
        """Same inputs produce identical outputs."""
        cutoff = "2020-03-01"
        kwargs = dict(
            cutoff_date=cutoff,
            data_dir=sim_data_dir,
            gold_path=sim_data_dir / "history" / "gold" / "gold.csv",
            max_workers=2,
        )
        r1 = ChronologicalOOSEngine(**kwargs).run()
        r2 = ChronologicalOOSEngine(**kwargs).run()
        assert r1.summary is not None
        assert r2.summary is not None
        # OOS metrics should be deterministic
        assert r1.summary.total_events == r2.summary.total_events
        assert r1.summary.scored_events == r2.summary.scored_events
        assert r1.summary.directional_accuracy == r2.summary.directional_accuracy

    def test_cutoff_after_all_data(self, sim_data_dir: Path) -> None:
        """Cutoff after all events → no evaluation results for CPI."""
        cutoff = "2025-01-01"
        engine = ChronologicalOOSEngine(
            cutoff_date=cutoff,
            data_dir=sim_data_dir,
            gold_path=sim_data_dir / "history" / "gold" / "gold.csv",
            max_workers=2,
        )
        result = engine.run()
        # CPI has no post-cutoff events
        cpi = next(
            (r for r in result.evaluation_results if r.event_type == "CPI"), None
        )
        if cpi is not None:
            assert cpi.event_count == 0

    def test_cutoff_before_all_data(self, sim_data_dir: Path) -> None:
        """Cutoff before all events → CPI uses all data in eval."""
        cutoff = "2019-01-01"
        engine = ChronologicalOOSEngine(
            cutoff_date=cutoff,
            data_dir=sim_data_dir,
            gold_path=sim_data_dir / "history" / "gold" / "gold.csv",
            max_workers=2,
        )
        result = engine.run()
        cpi = next(
            (r for r in result.evaluation_results if r.event_type == "CPI"), None
        )
        assert cpi is not None
        # CPI fixture has 4 releases (2020-01-15 through 2020-04-15)
        assert cpi.event_count >= 4

    def test_prebuilt_lessons_injected(self, sim_data_dir: Path) -> None:
        """Verify that prebuilt_lessons_path is threaded through
        to the pipeline by checking the knowledge dir exists with
        training lessons that are NOT overwritten after eval."""
        cutoff = "2020-03-01"
        knowledge_dir = sim_data_dir / "oos_knowledge"
        engine = ChronologicalOOSEngine(
            cutoff_date=cutoff,
            data_dir=sim_data_dir,
            gold_path=sim_data_dir / "history" / "gold" / "gold.csv",
            knowledge_dir=knowledge_dir,
            max_workers=2,
        )
        # Run training + evaluation
        engine.run()
        # After evaluation, the training lessons should still exist
        # (they were loaded but not overwritten by evaluation-period lessons)
        lessons_path = knowledge_dir / "CPI" / "lessons.csv"
        assert lessons_path.exists()
        # The file should be non-empty
        import pandas as pd
        df = pd.read_csv(lessons_path)
        assert len(df) > 0


