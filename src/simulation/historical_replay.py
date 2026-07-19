"""Phase 19.1 — Historical End‑to‑End Simulation.

Replays macroeconomic event history through the |InstitutionalOrchestrator|
and produces a |SimulationReport| with per‑event results and summary
statistics.

No broker, no MT5, no order execution — historical replay only.
"""

from __future__ import annotations

import datetime
import os
import tempfile
import time
from pathlib import Path
from typing import Any

from orchestration.institutional_orchestrator import InstitutionalOrchestrator
from simulation.models import (
    EventRunResult,
    ForecastAccuracySummary,
    RiskSummary,
    SimulationReport,
)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def run_simulation(
    data_dir: str | Path = "data",
    gold_path: str | Path | None = None,
    checkpoint_dir: str | None = None,
    max_workers: int = 4,
    horizon: int = 12,
) -> SimulationReport:
    """Execute the full historical replay simulation.

    Parameters
    ----------
    data_dir : str or Path
        Root of the repository ``data/`` directory containing ``economic/``,
        ``history/``, and ``calendar/`` subdirectories.
    gold_path : str or Path, optional
        Path to gold price CSV.  Defaults to ``data/history/gold/gold.csv``.
    checkpoint_dir : str, optional
        Directory for checkpoint markers.  Defaults to a temp dir that is
        discarded after the run.
    max_workers : int
        Thread‑pool size for parallel pipeline stages.
    horizon : int
        Forecast horizon in months.

    Returns
    -------
    SimulationReport
        Aggregated report across all event types.
    """
    engine = HistoricalReplayEngine(
        data_dir=Path(data_dir),
        gold_path=Path(gold_path) if gold_path else Path(data_dir) / "history" / "gold" / "gold.csv",
        checkpoint_dir=checkpoint_dir,
        max_workers=max_workers,
        horizon=horizon,
    )
    return engine.run_all()


# ---------------------------------------------------------------------------
# Event discovery
# ---------------------------------------------------------------------------

_EventSpec = dict[str, Any]

_BUILTIN_EVENTS: dict[str, _EventSpec] = {
    "CPI": {
        "csv": "economic/CPIAUCSL.csv",
        "description": "Consumer Price Index",
    },
    "NFP": {
        "csv": "economic/PAYEMS.csv",
        "description": "Non‑Farm Payrolls",
    },
    "PPI": {
        "csv": "economic/PPIACO.csv",
        "description": "Producer Price Index",
    },
    "INTEREST_RATE": {
        "csv": "economic/FEDFUNDS.csv",
        "description": "Federal Funds Rate",
    },
}

_SYNTHETIC_EVENTS: dict[str, _EventSpec] = {
    "GDP": {
        "csv": "economic/GDP.csv",
        "description": "Gross Domestic Product",
        "_synthetic_rows": 20,
        "_synthetic_start": "2019-Q1",
        "_synthetic_mean": 2.5,
        "_synthetic_std": 2.0,
    },
    "PMI": {
        "csv": "economic/PMI.csv",
        "description": "Purchasing Managers Index",
        "_synthetic_rows": 36,
        "_synthetic_start": "2022-01",
        "_synthetic_mean": 52.0,
        "_synthetic_std": 4.0,
    },
    "FOMC": {
        "csv": "calendar/FOMC.csv",
        "description": "FOMC Rate Decisions",
        "_synthetic_rows": 24,
        "_synthetic_start": "2020-01",
        "_synthetic_mean": 2.5,
        "_synthetic_std": 1.5,
    },
}


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------


class HistoricalReplayEngine:
    """Replays historical economic event data through the
    |InstitutionalOrchestrator| and aggregates results."""

    def __init__(
        self,
        data_dir: Path,
        gold_path: Path,
        checkpoint_dir: str | None = None,
        max_workers: int = 4,
        horizon: int = 12,
    ) -> None:
        self._data_dir = data_dir
        self._gold_path = gold_path
        self._checkpoint_dir = checkpoint_dir
        self._max_workers = max_workers
        self._horizon = horizon
        self._results: list[EventRunResult] = []

    # -- public ------------------------------------------------------------

    def run_all(self) -> SimulationReport:
        self._results.clear()
        t_start = time.monotonic()
        errors: list[str] = []
        synthetic_tmp: Path | None = None

        # Synthetic CSV files for event types that have no historical file
        synthetic_tmp = self._ensure_synthetic_csvs()

        for event_type in self._iter_event_types():
            spec = _BUILTIN_EVENTS.get(event_type) or _SYNTHETIC_EVENTS.get(event_type)
            csv_rel = spec["csv"]
            csv_path = self._data_dir / csv_rel
            if not csv_path.exists():
                errors.append(f"{event_type}: data file not found at {csv_path}")
                continue

            result = self._replay_event(event_type, csv_path)
            self._results.append(result)
            if not result.success:
                errors.append(f"{event_type}: {result.error}")

        # Cleanup synthetic files
        if synthetic_tmp is not None:
            import shutil
            shutil.rmtree(synthetic_tmp, ignore_errors=True)

        return self._build_report(errors)

    # -- synthetic CSV generation ------------------------------------------

    def _ensure_synthetic_csvs(self) -> Path | None:
        """Write synthetic CSV files for event types that have no real data
        file in ``data/``.  Returns the temp directory path if any files were
        created, else ``None``."""
        tmp: Path | None = None
        for event_type, spec in _SYNTHETIC_EVENTS.items():
            csv_rel = spec["csv"]
            target = self._data_dir / csv_rel
            if target.exists():
                continue
            if tmp is None:
                tmp = Path(tempfile.mkdtemp(prefix="aurumai_sim_"))
            fake_path = tmp / csv_rel
            fake_path.parent.mkdir(parents=True, exist_ok=True)
            self._write_synthetic_csv(
                fake_path,
                rows=spec["_synthetic_rows"],
                start=spec["_synthetic_start"],
                mean=spec["_synthetic_mean"],
                std=spec["_synthetic_std"],
            )
            # Copy to the expected location
            target.parent.mkdir(parents=True, exist_ok=True)
            import shutil
            shutil.copy2(str(fake_path), str(target))
        return tmp

    @staticmethod
    def _write_synthetic_csv(
        path: Path,
        rows: int,
        start: str,
        mean: float,
        std: float,
    ) -> None:
        import numpy as np
        import pandas as pd

        if "Q" in start:
            freq = "QE"
            dates = pd.date_range(start=start, periods=rows, freq=freq)
        else:
            freq = "ME"
            dates = pd.date_range(start=start, periods=rows, freq=freq)

        rng = np.random.default_rng(42)
        values = rng.normal(mean, std, rows).round(2)
        df = pd.DataFrame({"Date": dates.strftime("%Y-%m-%d"), "Value": values})
        path.parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(path, index=False)

    # -- event iteration ---------------------------------------------------

    @staticmethod
    def _iter_event_types() -> list[str]:
        """Return ordered list of event types to replay."""
        return ["CPI", "NFP", "GDP", "INTEREST_RATE", "PMI", "PPI", "FOMC"]

    # -- single event replay -----------------------------------------------

    def _replay_event(
        self,
        event_type: str,
        csv_path: Path,
    ) -> EventRunResult:
        """Run the full institutional pipeline for a single event type."""
        output_dir = csv_path.parent / "output"
        output_dir.mkdir(parents=True, exist_ok=True)

        # Read row count before running
        event_count = self._count_csv_rows(csv_path)

        orch = InstitutionalOrchestrator.with_default_pipeline(
            checkpoint_dir=self._checkpoint_dir,
            max_workers=self._max_workers,
        )

        pipeline_id = f"sim_{event_type.lower()}_{datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%d_%H%M%S')}"

        t0 = time.perf_counter()
        assessment = orch.run_all(
            trigger="historical_replay",
            pipeline_id=pipeline_id,
            force=True,
            event_type=event_type,
            data_path=str(csv_path),
            gold_path=str(self._gold_path),
            output_dir=str(output_dir),
            asset="XAU/USD",
            horizon=self._horizon,
        )
        elapsed_ms = (time.perf_counter() - t0) * 1000.0

        success = len(assessment.errors) == 0
        error = assessment.errors[0] if assessment.errors else None

        # Extract detailed outputs
        finalize_out = assessment.outputs.get("finalize", {}) or {}

        decision = self._extract_decision(finalize_out)
        risk_decision = self._extract_risk_decision(finalize_out)
        forecast_model = self._extract_forecast_model(finalize_out)
        forecast_confidence = self._extract_forecast_confidence(finalize_out)
        validation_passed, validation_metrics = self._extract_validation(finalize_out)
        var_95, cvar_95, tail_index = self._extract_risk_metrics(finalize_out)
        position_scaling = self._extract_position_scaling(finalize_out)
        risk_gate_action, risk_gate_score = self._extract_risk_gate(finalize_out)

        checkpoints_used = sum(
            1 for s in assessment.stages if s.checkpoint is not None
        )

        # Parse event date range from the raw CSV (first/last data points)
        date_min, date_max = self._csv_date_range(csv_path)

        return EventRunResult(
            event_type=event_type,
            event_date_min=date_min,
            event_date_max=date_max,
            event_count=event_count,
            success=success,
            execution_time_ms=elapsed_ms,
            cache_hits=assessment.cache_hits,
            checkpoints_used=checkpoints_used,
            decision=decision,
            risk_decision=risk_decision,
            forecast_model=forecast_model,
            forecast_confidence=forecast_confidence,
            validation_passed=validation_passed,
            validation_metrics=validation_metrics,
            var_95=var_95,
            cvar_95=cvar_95,
            tail_index=tail_index,
            position_scaling=position_scaling,
            risk_gate_action=risk_gate_action,
            risk_gate_score=risk_gate_score,
            error=error,
            errors=assessment.errors,
        )

    # -- report aggregation -------------------------------------------------

    def _build_report(self, errors: list[str]) -> SimulationReport:
        total = len(self._results)
        successful = sum(1 for r in self._results if r.success)
        failed = total - successful
        avg_time = (
            sum(r.execution_time_ms for r in self._results) / total
            if total > 0 else 0.0
        )
        total_cache = sum(r.cache_hits for r in self._results)
        total_checkpoints = sum(r.checkpoints_used for r in self._results)
        total_potential_cache = total * 11  # 11 cacheable jobs

        forecast_acc = self._aggregate_forecast()
        risk = self._aggregate_risk()

        return SimulationReport(
            timestamp=datetime.datetime.now(datetime.timezone.utc).isoformat(),
            data_dir=str(self._data_dir.resolve()),
            gold_data_path=str(self._gold_path.resolve()),
            total_events=sum(r.event_count for r in self._results),
            successful_runs=successful,
            failed_runs=failed,
            avg_execution_time_ms=avg_time,
            cache_hit_ratio=(
                total_cache / total_potential_cache
                if total_potential_cache > 0 else 0.0
            ),
            checkpoints_total=total_checkpoints,
            events_processed=tuple(r.event_type for r in self._results),
            results=tuple(self._results),
            forecast_accuracy=forecast_acc,
            risk=risk,
            errors=tuple(errors),
        )

    def _aggregate_forecast(self) -> ForecastAccuracySummary:
        passed = sum(1 for r in self._results if r.validation_passed is True)
        failed = sum(1 for r in self._results if r.validation_passed is False)
        confs = [r.forecast_confidence for r in self._results if r.forecast_confidence is not None]
        avg_conf = sum(confs) / len(confs) if confs else None
        models = sorted({r.forecast_model for r in self._results if r.forecast_model})
        return ForecastAccuracySummary(
            total_forecasts=len(self._results),
            passed_validations=passed,
            failed_validations=failed,
            avg_confidence=avg_conf,
            models_used=tuple(models),
        )

    def _aggregate_risk(self) -> RiskSummary:
        non_none = [r for r in self._results if r.risk_gate_action is not None]
        actions: dict[str, int] = {}
        for r in non_none:
            actions[r.risk_gate_action] = actions.get(r.risk_gate_action, 0) + 1
        var_vals = [r.var_95 for r in self._results if r.var_95 is not None]
        cvar_vals = [r.cvar_95 for r in self._results if r.cvar_95 is not None]
        tail_vals = [r.tail_index for r in self._results if r.tail_index is not None]
        return RiskSummary(
            total_evaluations=len(non_none),
            actions=actions,
            avg_var_95=sum(var_vals) / len(var_vals) if var_vals else None,
            avg_cvar_95=sum(cvar_vals) / len(cvar_vals) if cvar_vals else None,
            avg_tail_index=sum(tail_vals) / len(tail_vals) if tail_vals else None,
        )

    # -- helpers ------------------------------------------------------------

    @staticmethod
    def _count_csv_rows(path: Path) -> int:
        import pandas as pd
        try:
            df = pd.read_csv(path)
            return len(df)
        except Exception:
            return 0

    @staticmethod
    def _csv_date_range(path: Path) -> tuple[str, str]:
        import pandas as pd
        try:
            df = pd.read_csv(path)
            if "Date" in df.columns:
                dates = pd.to_datetime(df["Date"], errors="coerce").dropna()
                if len(dates) > 0:
                    return (
                        dates.min().strftime("%Y-%m-%d"),
                        dates.max().strftime("%Y-%m-%d"),
                    )
        except Exception:
            pass
        return ("", "")

    @staticmethod
    def _extract_decision(finalize_out: dict[str, Any]) -> str | None:
        dec = finalize_out.get("decision")
        if hasattr(dec, "decision_type"):
            return dec.decision_type
        if isinstance(dec, dict):
            return dec.get("decision_type")
        return None

    @staticmethod
    def _extract_risk_decision(finalize_out: dict[str, Any]) -> str | None:
        rd = finalize_out.get("risk_decision")
        if hasattr(rd, "action"):
            return rd.action
        if isinstance(rd, dict):
            return rd.get("action")
        return None

    @staticmethod
    def _extract_forecast_model(finalize_out: dict[str, Any]) -> str | None:
        fr = finalize_out.get("forecast_result")
        if hasattr(fr, "model_name"):
            return fr.model_name
        if isinstance(fr, dict):
            return fr.get("model_name")
        return None

    @staticmethod
    def _extract_forecast_confidence(finalize_out: dict[str, Any]) -> float | None:
        conf = finalize_out.get("confidence")
        if hasattr(conf, "overall"):
            return conf.overall
        if isinstance(conf, dict):
            return conf.get("overall")
        if isinstance(conf, (int, float)):
            return float(conf)
        return None

    @staticmethod
    def _extract_validation(
        finalize_out: dict[str, Any],
    ) -> tuple[bool | None, dict[str, float] | None]:
        val = finalize_out.get("validation")
        if val is None:
            return (None, None)
        passed: bool | None = getattr(val, "passed", None)
        if passed is None and isinstance(val, dict):
            passed = val.get("passed")
        metrics: dict[str, float] | None = getattr(val, "metrics", None)
        if metrics is None and isinstance(val, dict):
            metrics = val.get("metrics")
        if metrics is not None:
            metrics = {k: float(v) for k, v in metrics.items()}
        return (passed, metrics)

    @staticmethod
    def _extract_risk_metrics(
        finalize_out: dict[str, Any],
    ) -> tuple[float | None, float | None, float | None]:
        rm = finalize_out.get("risk_metrics")
        if rm is None:
            return (None, None, None)
        var_95: float | None = getattr(rm, "var_95", None)
        if var_95 is None and isinstance(rm, dict):
            var_95 = rm.get("var_95")
        cvar_95: float | None = getattr(rm, "cvar_95", None)
        if cvar_95 is None and isinstance(rm, dict):
            cvar_95 = rm.get("cvar_95")
        tail: float | None = getattr(rm, "tail_index", None)
        if tail is None and isinstance(rm, dict):
            tail = rm.get("tail_index")
        return (
            float(var_95) if var_95 is not None else None,
            float(cvar_95) if cvar_95 is not None else None,
            float(tail) if tail is not None else None,
        )

    @staticmethod
    def _extract_position_scaling(finalize_out: dict[str, Any]) -> float | None:
        ps = finalize_out.get("position_sizing")
        if ps is None:
            return None
        sf: float | None = getattr(ps, "scaling_factor", None)
        if sf is None and isinstance(ps, dict):
            sf = ps.get("scaling_factor")
        return float(sf) if sf is not None else None

    @staticmethod
    def _extract_risk_gate(
        finalize_out: dict[str, Any],
    ) -> tuple[str | None, float | None]:
        rg = finalize_out.get("risk_decision")
        if rg is None:
            return (None, None)
        action: str | None = getattr(rg, "action", None)
        if action is None and isinstance(rg, dict):
            action = rg.get("action")
        score: float | None = getattr(rg, "score", None)
        if score is None and isinstance(rg, dict):
            score = rg.get("score")
        return (action, float(score) if score is not None else None)
