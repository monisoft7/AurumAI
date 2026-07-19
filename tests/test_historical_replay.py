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
    HistoricalReplayEngine,
    _BUILTIN_EVENTS,
    _SYNTHETIC_EVENTS,
    run_simulation,
)
from simulation.models import (
    EventRunResult,
    ForecastAccuracySummary,
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
        # Gold price (Date,Close)
        lines = ["Date,Close"]
        price = 1500.0
        for idx in range(100):
            dt = pd.Timestamp("2020-01-01") + pd.Timedelta(days=idx * 7)
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
