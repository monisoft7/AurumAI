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
from dataclasses import dataclass

from simulation.models import (
    EventRunResult,
    ForecastAccuracySummary,
    OOSSummary,
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
# OOS correctness helpers
# ---------------------------------------------------------------------------


def _classify_actual_direction(
    actual_return_pct: float,
    dead_zone: float = 0.10,
) -> str:
    """Classify actual gold return as UP (>dead_zone), DOWN (<-dead_zone),
    or FLAT (|return| <= dead_zone)."""
    if actual_return_pct > dead_zone:
        return "UP"
    elif actual_return_pct < -dead_zone:
        return "DOWN"
    else:
        return "FLAT"


def _decision_is_correct(
    decision: str,
    actual_direction: str,
) -> bool | None:
    """Return True/False for a directional bet, or None for abstention.

    POSITIVE / STRONG_POSITIVE → correct if actual is UP.
    NEGATIVE / STRONG_NEGATIVE → correct if actual is DOWN.
    NEUTRAL                   → correct if actual is FLAT.
    INSUFFICIENT_EVIDENCE     → None (not scored).
    """
    decision_upper = decision.upper()
    if decision_upper == "INSUFFICIENT_EVIDENCE":
        return None
    if decision_upper in ("POSITIVE", "STRONG_POSITIVE"):
        return actual_direction == "UP"
    if decision_upper in ("NEGATIVE", "STRONG_NEGATIVE"):
        return actual_direction == "DOWN"
    if decision_upper == "NEUTRAL":
        return actual_direction == "FLAT"
    return None


def _compute_gold_return(
    gold: "pd.DataFrame",
    entry_date: datetime.datetime,
    horizon_days: int = 5,
) -> float | None:
    """Forward percentage return of gold from *entry_date* over *horizon_days*
    calendar days.  Uses the nearest price at-or-before entry and the nearest
    price at-or-after entry+horizon."""
    target_date = entry_date + datetime.timedelta(days=horizon_days)

    entry_mask = gold["Date"] <= entry_date
    entry_rows = gold.loc[entry_mask, "Close"]
    if entry_rows.empty:
        return None
    entry_price = entry_rows.iloc[-1]

    future_mask = gold["Date"] >= target_date
    future_rows = gold.loc[future_mask, "Close"]
    if future_rows.empty:
        return None
    future_price = future_rows.iloc[0]

    if entry_price == 0:
        return None

    return float((future_price - entry_price) / entry_price * 100.0)


# ---------------------------------------------------------------------------
# OOS aggregation (pure functions)
# ---------------------------------------------------------------------------


def _safe_div(numerator: float, denominator: float) -> float | None:
    """Return ``numerator / denominator`` or ``None`` if denominator is zero."""
    if denominator == 0:
        return None
    return numerator / denominator


def _predicted_direction(decision: str) -> str | None:
    """Map a decision string to the predicted direction.

    POSITIVE / STRONG_POSITIVE  →  ``"UP"``
    NEGATIVE / STRONG_NEGATIVE  →  ``"DOWN"``
    NEUTRAL                     →  ``"FLAT"``
    INSUFFICIENT_EVIDENCE       →  ``None``
    """
    d = decision.upper()
    if d in ("POSITIVE", "STRONG_POSITIVE"):
        return "UP"
    if d in ("NEGATIVE", "STRONG_NEGATIVE"):
        return "DOWN"
    if d == "NEUTRAL":
        return "FLAT"
    return None


def _confusion_matrix_counts(
    scored: list[EventRunResult],
) -> dict[str, int]:
    """Build a 3×3 confusion matrix from scored events.

    Returns a dict with nine keys of the form ``pred_{dir}_act_{dir}``
    where ``{dir}`` is ``up``, ``down``, or ``flat``.
    """
    counts: dict[str, int] = {
        "pred_up_act_up": 0,
        "pred_up_act_down": 0,
        "pred_up_act_flat": 0,
        "pred_down_act_up": 0,
        "pred_down_act_down": 0,
        "pred_down_act_flat": 0,
        "pred_flat_act_up": 0,
        "pred_flat_act_down": 0,
        "pred_flat_act_flat": 0,
    }
    for r in scored:
        pred = _predicted_direction(r.decision)
        if pred is None or r.decision_actual_return_pct is None:
            continue
        actual = _classify_actual_direction(r.decision_actual_return_pct)
        key = f"pred_{pred.lower()}_act_{actual.lower()}"
        if key in counts:
            counts[key] += 1
    return counts


def _strong_error_rate(scored: list[EventRunResult]) -> float | None:
    """Fraction of STRONG_POSITIVE / STRONG_NEGATIVE bets that were wrong."""
    strong_total = 0
    strong_wrong = 0
    for r in scored:
        d = r.decision.upper() if r.decision else ""
        if d in ("STRONG_POSITIVE", "STRONG_NEGATIVE"):
            strong_total += 1
            if r.decision_correct is False:
                strong_wrong += 1
    return _safe_div(float(strong_wrong), float(strong_total))


def _ece(scored: list[EventRunResult], n_bins: int = 5) -> float | None:
    """Expected Calibration Error with *n_bins* equal-width bins over [0, 1].

    Only includes scored events that also have a non-``None``
    ``forecast_confidence``.
    """
    confidences: list[float] = []
    corrects: list[bool] = []
    for r in scored:
        if r.forecast_confidence is not None:
            confidences.append(r.forecast_confidence)
            corrects.append(r.decision_correct is True)

    n = len(confidences)
    if n == 0:
        return None

    bin_edges = [i / n_bins for i in range(n_bins + 1)]
    bin_edges[-1] = 1.0 + 1e-9  # ensure the last bin is inclusive

    ece_value = 0.0
    for b in range(n_bins):
        lo = bin_edges[b]
        hi = bin_edges[b + 1]
        mask = [lo <= c < hi for c in confidences]
        bin_size = sum(mask)
        if bin_size == 0:
            continue
        bin_correct = sum(c for c, m in zip(corrects, mask) if m)
        bin_accuracy = bin_correct / bin_size
        bin_conf = sum(c for c, m in zip(confidences, mask) if m) / bin_size
        ece_value += (bin_size / n) * abs(bin_accuracy - bin_conf)

    return ece_value


def compute_oos_summary(results: tuple[EventRunResult, ...]) -> OOSSummary:
    """Aggregate per-event |EventRunResult| objects into an |OOSSummary|.

    Pure function — no side effects, deterministic.

    Metrics
    -------
    *Decision Distribution* — count of each decision type across all events.
    *Directional Accuracy* — correct UP or DOWN bets / total UP or DOWN bets.
    *Precision / Recall* — per-class (UP, DOWN, FLAT) and macro average.
    *Coverage* — scored events / events-with-a-decision.
    *Abstention Rate* — INSUFFICIENT_EVIDENCE / events-with-a-decision.
    *Strong Error Rate* — wrong STRONG bets / total STRONG bets.
    *ECE* — Expected Calibration Error (5 equal-width bins).
    """
    total_events = len(results)

    scored = [r for r in results if r.decision_correct is not None]
    abstained = [
        r for r in results
        if r.decision_correct is None and r.decision is not None
    ]
    no_decision = [r for r in results if r.decision is None]

    scored_events = len(scored)
    abstained_events = len(abstained)
    total_with_decision = scored_events + abstained_events

    coverage = (
        _safe_div(float(scored_events), float(total_with_decision))
        if total_with_decision > 0 else None
    )
    abstention_rate = (
        _safe_div(float(abstained_events), float(total_with_decision))
        if total_with_decision > 0 else None
    )

    # Decision distribution
    dist: dict[str, int] = {}
    for r in results:
        d = r.decision if r.decision else "NO_DECISION"
        dist[d] = dist.get(d, 0) + 1

    # Confusion matrix
    cm = _confusion_matrix_counts(scored)

    # Directional accuracy (directional bets = predict UP or DOWN, not FLAT)
    total_directional = (
        cm["pred_up_act_up"] + cm["pred_up_act_down"] + cm["pred_up_act_flat"]
        + cm["pred_down_act_up"] + cm["pred_down_act_down"] + cm["pred_down_act_flat"]
    )
    correct_directional = cm["pred_up_act_up"] + cm["pred_down_act_down"]
    directional_accuracy = (
        _safe_div(float(correct_directional), float(total_directional))
        if total_directional > 0 else None
    )

    # Per-class precision
    precision_up = _safe_div(
        float(cm["pred_up_act_up"]),
        float(cm["pred_up_act_up"] + cm["pred_up_act_down"] + cm["pred_up_act_flat"]),
    )
    precision_down = _safe_div(
        float(cm["pred_down_act_down"]),
        float(cm["pred_down_act_up"] + cm["pred_down_act_down"] + cm["pred_down_act_flat"]),
    )
    precision_flat = _safe_div(
        float(cm["pred_flat_act_flat"]),
        float(cm["pred_flat_act_up"] + cm["pred_flat_act_down"] + cm["pred_flat_act_flat"]),
    )

    # Per-class recall
    recall_up = _safe_div(
        float(cm["pred_up_act_up"]),
        float(cm["pred_up_act_up"] + cm["pred_down_act_up"] + cm["pred_flat_act_up"]),
    )
    recall_down = _safe_div(
        float(cm["pred_down_act_down"]),
        float(cm["pred_up_act_down"] + cm["pred_down_act_down"] + cm["pred_flat_act_down"]),
    )
    recall_flat = _safe_div(
        float(cm["pred_flat_act_flat"]),
        float(cm["pred_up_act_flat"] + cm["pred_down_act_flat"] + cm["pred_flat_act_flat"]),
    )

    # Macro averages
    prec_vals = [v for v in (precision_up, precision_down, precision_flat) if v is not None]
    rec_vals = [v for v in (recall_up, recall_down, recall_flat) if v is not None]
    macro_precision = sum(prec_vals) / len(prec_vals) if prec_vals else None
    macro_recall = sum(rec_vals) / len(rec_vals) if rec_vals else None

    strong_err = _strong_error_rate(scored)

    cal_error = _ece(scored)

    return OOSSummary(
        total_events=total_events,
        scored_events=scored_events,
        abstained_events=abstained_events,
        directional_accuracy=directional_accuracy,
        macro_precision=macro_precision,
        macro_recall=macro_recall,
        precision_up=precision_up,
        precision_down=precision_down,
        precision_flat=precision_flat,
        recall_up=recall_up,
        recall_down=recall_down,
        recall_flat=recall_flat,
        coverage=coverage,
        abstention_rate=abstention_rate,
        strong_error_rate=strong_err,
        ece=cal_error,
        decision_distribution=dist,
    )


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
        synthetic_tmp = HistoricalReplayEngine._ensure_synthetic_csvs(self._data_dir)

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

    @staticmethod
    def _ensure_synthetic_csvs(data_dir: Path) -> Path | None:
        """Write synthetic CSV files for event types that have no real data
        file in ``data/``.  Returns the temp directory path if any files were
        created, else ``None``."""
        import shutil
        import tempfile

        tmp: Path | None = None
        for event_type, spec in _SYNTHETIC_EVENTS.items():
            csv_rel = spec["csv"]
            target = data_dir / csv_rel
            if target.exists():
                continue
            if tmp is None:
                tmp = Path(tempfile.mkdtemp(prefix="aurumai_sim_"))
            fake_path = tmp / csv_rel
            fake_path.parent.mkdir(parents=True, exist_ok=True)
            HistoricalReplayEngine._write_synthetic_csv(
                fake_path,
                rows=spec["_synthetic_rows"],
                start=spec["_synthetic_start"],
                mean=spec["_synthetic_mean"],
                std=spec["_synthetic_std"],
            )
            target.parent.mkdir(parents=True, exist_ok=True)
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
        """Run the full institutional pipeline for a single event type.

        Event types with a supported release calendar are replayed release by
        release to enforce point-in-time data boundaries.  All others use the
        legacy single-run path.
        """
        release_csv = HistoricalReplayEngine._release_calendar_path_for(event_type, self._data_dir)
        if release_csv is not None and release_csv.exists():
            return self._replay_event_release_by_release(event_type, csv_path, release_csv)
        return self._replay_event_legacy(event_type, csv_path)

    @staticmethod
    def _release_calendar_path_for(event_type: str, data_dir: Path) -> Path | None:
        cal = {
            "CPI": "cpi_releases.csv",
        }.get(event_type)
        if cal is None:
            return None
        return data_dir / "calendar" / cal

    def _replay_event_legacy(
        self,
        event_type: str,
        csv_path: Path,
    ) -> EventRunResult:
        """Original single-run replay path (no per-release iteration)."""
        output_dir = csv_path.parent / "output"
        output_dir.mkdir(parents=True, exist_ok=True)

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

        return self._assessment_to_result(
            event_type=event_type,
            csv_path=csv_path,
            assessment=assessment,
            event_count=event_count,
            elapsed_ms=elapsed_ms,
        )

    # -- release-by-release replay -----------------------------------------

    def _replay_event_release_by_release(
        self,
        event_type: str,
        csv_path: Path,
        calendar_path: Path,
    ) -> EventRunResult:
        """Replay one event type one release at a time.

        For each release in the calendar (chronological order):

        1. Build a snapshot CPI CSV containing all CPI observations whose
           ``release_timestamp`` is at-or-before the current release.
        2. Build a snapshot gold CSV filtered to rows at-or-before the
           current release timestamp.
        3. Run the full institutional pipeline on the snapshot.
        4. Aggregate per-release results into a single |EventRunResult|.

        Extra column ``release_timestamp`` survives ``load_and_extract()``
        because ``FeatureExtractionEngine`` / ``FeatureSet`` pass through
        all columns.  The ``LessonBuilder._build_lessons()`` method detects
        the column and uses it for anchoring.
        """
        import shutil
        import tempfile

        import pandas as pd

        output_dir = csv_path.parent / "output"
        output_dir.mkdir(parents=True, exist_ok=True)

        # ---- load & prepare data -----------------------------------------

        calendar = pd.read_csv(calendar_path)
        if "release_timestamp" not in calendar.columns:
            calendar["release_timestamp"] = (
                calendar["release_date"] + " " + calendar["release_time"]
            )
        calendar["reference_period"] = pd.to_datetime(calendar["reference_period"], errors="coerce")
        calendar["release_timestamp"] = pd.to_datetime(calendar["release_timestamp"], errors="coerce")
        calendar = calendar.dropna(subset=["reference_period", "release_timestamp"])
        calendar = calendar.sort_values("release_timestamp")
        calendar = calendar[calendar["reference_period"] <= calendar["release_timestamp"]]

        cpi_raw = pd.read_csv(csv_path)
        cpi_raw["Date"] = pd.to_datetime(cpi_raw["Date"], errors="coerce")
        cpi_raw = cpi_raw.dropna(subset=["Date"])
        cpi_raw = cpi_raw.sort_values("Date")

        cpi_merged = cpi_raw.merge(
            calendar,
            left_on="Date",
            right_on="reference_period",
            how="inner",
        )
        cpi_merged["release_timestamp"] = pd.to_datetime(cpi_merged["release_timestamp"])
        cpi_merged = cpi_merged.sort_values("release_timestamp")

        if len(cpi_merged) == 0:
            return EventRunResult(
                event_type=event_type,
                event_date_min="",
                event_date_max="",
                event_count=0,
                success=False,
                execution_time_ms=0.0,
                cache_hits=0,
                checkpoints_used=0,
                decision=None,
                risk_decision=None,
                forecast_model=None,
                forecast_confidence=None,
                validation_passed=None,
                validation_metrics=None,
                var_95=None,
                cvar_95=None,
                tail_index=None,
                position_scaling=None,
                risk_gate_action=None,
                risk_gate_score=None,
                error="No CPI rows matched release calendar; cannot replay release by release",
                errors=("No CPI rows matched release calendar",),
            )

        gold = self._load_gold_data()
        gold["Date"] = pd.to_datetime(gold["Date"], errors="coerce")
        gold = gold.dropna(subset=["Date"]).sort_values("Date")

        # ---- per-release loop --------------------------------------------

        total_elapsed_ms = 0.0
        total_cache_hits = 0
        total_checkpoints = 0
        release_count = 0
        errors: list[str] = []
        all_outputs: list[dict[str, Any]] = []
        n_releases = len(cpi_merged)

        for idx, (_cal_idx, release_row) in enumerate(cpi_merged.iterrows()):
            as_of = release_row["release_timestamp"]

            cpi_snapshot = cpi_merged[
                cpi_merged["release_timestamp"] <= as_of
            ].copy()
            cpi_snapshot = cpi_snapshot[["Date", "Value", "release_timestamp"]]
            cpi_snapshot["Date"] = cpi_snapshot["Date"].dt.strftime("%Y-%m-%d")
            cpi_snapshot["release_timestamp"] = cpi_snapshot["release_timestamp"].dt.strftime("%Y-%m-%d %H:%M:%S")

            tmp = Path(tempfile.mkdtemp(prefix="aurumai_release_"))
            try:
                tmp_cpi = tmp / "cpi.csv"
                tmp_gold = tmp / "gold.csv"
                tmp_gold_lessons = tmp / "gold_lessons.csv"
                cpi_snapshot.to_csv(tmp_cpi, index=False)
                # Filtered gold for forecast stages (point-in-time).
                gold[gold["Date"] <= as_of].to_csv(tmp_gold, index=False)
                # Full gold for lesson building (needs future returns as labels).
                gold.to_csv(tmp_gold_lessons, index=False)

                orch = InstitutionalOrchestrator.with_default_pipeline(
                    checkpoint_dir=self._checkpoint_dir,
                    max_workers=self._max_workers,
                )

                pipeline_id = (
                    f"sim_{event_type.lower()}_{as_of.strftime('%Y%m%d_%H%M%S')}"
                )

                t0 = time.perf_counter()
                assessment = orch.run_all(
                    trigger="historical_replay",
                    pipeline_id=pipeline_id,
                    force=True,
                    event_type=event_type,
                    data_path=str(tmp_cpi),
                    gold_path=str(tmp_gold),
                    gold_lessons_path=str(tmp_gold_lessons),
                    output_dir=str(output_dir),
                    asset="XAU/USD",
                    horizon=self._horizon,
                    release_calendar_path=str(calendar_path),
                )
                release_elapsed = (time.perf_counter() - t0) * 1000.0

                total_elapsed_ms += release_elapsed
                total_cache_hits += assessment.cache_hits
                total_checkpoints += sum(
                    1 for s in assessment.stages if s.checkpoint is not None
                )
                release_count += 1

                if assessment.errors:
                    errors.extend(
                        f"[release {idx + 1}/{n_releases} as_of={as_of}] {e}"
                        for e in assessment.errors
                    )

                finalize_out = assessment.outputs.get("finalize", {}) or {}
                all_outputs.append(finalize_out)

            finally:
                shutil.rmtree(tmp, ignore_errors=True)

        # ---- aggregate per-release result ---------------------------------

        success = len(errors) == 0

        date_min = cpi_merged["Date"].min().strftime("%Y-%m-%d")
        date_max = cpi_merged["Date"].max().strftime("%Y-%m-%d")

        final_finalize = all_outputs[-1] if all_outputs else {}
        decision = self._extract_decision(final_finalize)
        risk_decision = self._extract_risk_decision(final_finalize)
        forecast_model = self._extract_forecast_model(final_finalize)
        forecast_confidence = self._extract_forecast_confidence(final_finalize)
        validation_passed, validation_metrics = self._extract_validation(final_finalize)
        var_95, cvar_95, tail_index = self._extract_risk_metrics(final_finalize)
        position_scaling = self._extract_position_scaling(final_finalize)
        risk_gate_action, risk_gate_score = self._extract_risk_gate(final_finalize)

        # ---- OOS correctness --------------------------------------------
        decision_correct: bool | None = None
        decision_actual_return_pct: float | None = None
        if decision is not None and gold is not None and all_outputs:
            last_as_of = cpi_merged.iloc[-1]["release_timestamp"]
            gold_return = _compute_gold_return(gold, last_as_of)
            if gold_return is not None:
                decision_actual_return_pct = gold_return
                actual_dir = _classify_actual_direction(gold_return)
                decision_correct = _decision_is_correct(decision, actual_dir)

        return EventRunResult(
            event_type=event_type,
            event_date_min=date_min,
            event_date_max=date_max,
            event_count=release_count,
            success=success,
            execution_time_ms=total_elapsed_ms,
            cache_hits=total_cache_hits,
            checkpoints_used=total_checkpoints,
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
            decision_correct=decision_correct,
            decision_actual_return_pct=decision_actual_return_pct,
            error=errors[0] if errors else None,
            errors=tuple(errors),
        )

    # -- common result builder ---------------------------------------------

    @staticmethod
    def _assessment_to_result(
        event_type: str,
        csv_path: Path,
        assessment: Any,
        event_count: int,
        elapsed_ms: float,
    ) -> EventRunResult:
        """Convert a single |InstitutionalAssessment| into an |EventRunResult|."""
        finalize_out = assessment.outputs.get("finalize", {}) or {}

        decision = HistoricalReplayEngine._extract_decision(finalize_out)
        risk_decision = HistoricalReplayEngine._extract_risk_decision(finalize_out)
        forecast_model = HistoricalReplayEngine._extract_forecast_model(finalize_out)
        forecast_confidence = HistoricalReplayEngine._extract_forecast_confidence(finalize_out)
        validation_passed, validation_metrics = HistoricalReplayEngine._extract_validation(finalize_out)
        var_95, cvar_95, tail_index = HistoricalReplayEngine._extract_risk_metrics(finalize_out)
        position_scaling = HistoricalReplayEngine._extract_position_scaling(finalize_out)
        risk_gate_action, risk_gate_score = HistoricalReplayEngine._extract_risk_gate(finalize_out)

        checkpoints_used = sum(
            1 for s in assessment.stages if s.checkpoint is not None
        )

        date_min, date_max = HistoricalReplayEngine._csv_date_range(csv_path)

        return EventRunResult(
            event_type=event_type,
            event_date_min=date_min,
            event_date_max=date_max,
            event_count=event_count,
            success=len(assessment.errors) == 0,
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
            error=assessment.errors[0] if assessment.errors else None,
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

    def _load_gold_data(self) -> pd.DataFrame:
        import pandas as pd
        df = pd.read_csv(self._gold_path)
        return df

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


# ===========================================================================
# Chronological OOS Engine
# ===========================================================================


@dataclass(frozen=True)
class ChronologicalOOSResult:
    """Result of a chronological out-of-sample evaluation run.

    .. py:attribute:: cutoff_date

        The chronological split point (ISO date string).

    .. py:attribute:: training_results

        |EventRunResult| objects from the training (knowledge-building)
        phase.  These are **not** included in OOS metrics.

    .. py:attribute:: evaluation_results

        |EventRunResult| objects from the evaluation (unseen-event) phase.
        These are the events on or after *cutoff_date*.

    .. py:attribute:: summary

        |OOSSummary| computed from *evaluation_results* only.

    .. py:attribute:: errors

        Any errors captured during the run.
    """

    cutoff_date: str
    training_results: tuple[EventRunResult, ...] = ()
    evaluation_results: tuple[EventRunResult, ...] = ()
    summary: OOSSummary | None = None
    errors: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "cutoff_date": self.cutoff_date,
            "training_events": len(self.training_results),
            "evaluation_events": len(self.evaluation_results),
        }
        if self.summary is not None:
            d["summary"] = self.summary.to_dict()
        if self.errors:
            d["errors"] = list(self.errors)
        return d


class ChronologicalOOSEngine:
    """Chronological Out-of-Sample evaluation engine.

    Splits historical event data at a configurable cutoff date:

    **Training phase** — all events strictly before *cutoff_date* are
    replayed and their lessons (knowledge) are saved to a dedicated
    knowledge directory.

    **Evaluation phase** — all events on or after *cutoff_date* are
    replayed **using only the pre-built training knowledge**.  No
    evaluation-period lesson enters the knowledge graph, guaranteeing
    strict chronological separation.

    The final |OOSSummary| is computed from the *evaluation* results
    only.
    """

    def __init__(
        self,
        cutoff_date: str | datetime.date | datetime.datetime,
        data_dir: str | Path,
        gold_path: str | Path,
        checkpoint_dir: str | None = None,
        max_workers: int = 4,
        horizon: int = 12,
        knowledge_dir: str | Path | None = None,
    ):
        import pandas as pd

        self._cutoff = pd.Timestamp(cutoff_date)
        self._data_dir = Path(data_dir)
        self._gold_path = Path(gold_path)
        self._checkpoint_dir = checkpoint_dir
        self._max_workers = max_workers
        self._horizon = horizon
        self._knowledge_dir = (
            Path(knowledge_dir) if knowledge_dir
            else self._data_dir / "oos_knowledge"
        )

    # -- public API ---------------------------------------------------------

    def run(
        self,
    ) -> ChronologicalOOSResult:
        """Execute the chronological OOS evaluation.

        Returns a |ChronologicalOOSResult| with training results,
        evaluation results, and OOS summary.
        """
        self._knowledge_dir.mkdir(parents=True, exist_ok=True)
        errors: list[str] = []

        # Ensure synthetic CSV files exist for event types without real data
        HistoricalReplayEngine._ensure_synthetic_csvs(self._data_dir)

        # Phase 1 — build training knowledge for each event type
        for event_type in HistoricalReplayEngine._iter_event_types():
            try:
                self._build_training_knowledge(event_type)
            except Exception as exc:
                errors.append(f"[train/{event_type}] {exc}")

        # Phase 2 — evaluate unseen events using pre-built knowledge
        eval_results: list[EventRunResult] = []
        for event_type in HistoricalReplayEngine._iter_event_types():
            try:
                result = self._run_evaluation(event_type)
                eval_results.append(result)
            except Exception as exc:
                errors.append(f"[eval/{event_type}] {exc}")

        summary = compute_oos_summary(tuple(eval_results))

        return ChronologicalOOSResult(
            cutoff_date=self._cutoff.date().isoformat(),
            evaluation_results=tuple(eval_results),
            summary=summary,
            errors=tuple(errors),
        )

    # -- training knowledge ------------------------------------------------
    def _build_training_knowledge(self, event_type: str) -> None:
        """Run the full pipeline on all pre-cutoff data to build lessons.

        Loads ALL event data strictly before *cutoff_date*, runs the
        institutional pipeline once (not release-by-release), and saves
        the resulting ``lessons.csv`` to the knowledge directory.

        This guarantees the evaluation phase uses only pre-cutoff knowledge.
        """
        import shutil
        import tempfile

        import pandas as pd

        spec = _BUILTIN_EVENTS.get(event_type) or _SYNTHETIC_EVENTS.get(event_type)
        csv_path = self._data_dir / spec["csv"]
        event_knowledge_dir = self._knowledge_dir / event_type
        event_knowledge_dir.mkdir(parents=True, exist_ok=True)

        df = pd.read_csv(csv_path)
        df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
        df = df.dropna(subset=["Date"])
        train_df = df[df["Date"] < self._cutoff].copy()
        if train_df.empty:
            return

        tmp_dir = Path(tempfile.mkdtemp(prefix="aurumai_oos_train_"))
        try:
            train_df["Date"] = train_df["Date"].dt.strftime("%Y-%m-%d")
            tmp_csv = tmp_dir / f"{event_type.lower()}.csv"
            train_df.to_csv(tmp_csv, index=False)

            gold_df = self._load_gold_data()
            gold_df["Date"] = pd.to_datetime(gold_df["Date"], errors="coerce")
            gold_df = gold_df.dropna(subset=["Date"]).sort_values("Date")

            release_csv = HistoricalReplayEngine._release_calendar_path_for(event_type, self._data_dir)
            if release_csv is not None and release_csv.exists():
                orch = InstitutionalOrchestrator.with_default_pipeline(
                    checkpoint_dir=self._checkpoint_dir,
                    max_workers=self._max_workers,
                )
                orch.run_all(
                    trigger="oos_train",
                    pipeline_id=f"oos_train_{event_type.lower()}_release",
                    force=True,
                    event_type=event_type,
                    data_path=str(tmp_csv),
                    gold_path=str(self._gold_path),
                    gold_lessons_path=str(self._gold_path),
                    output_dir=str(tmp_dir),
                    asset="XAU/USD",
                    horizon=self._horizon,
                    release_calendar_path=str(release_csv),
                )
            else:
                orch = InstitutionalOrchestrator.with_default_pipeline(
                    checkpoint_dir=self._checkpoint_dir,
                    max_workers=self._max_workers,
                )
                orch.run_all(
                    trigger="oos_train",
                    pipeline_id=f"oos_train_{event_type.lower()}_legacy",
                    force=True,
                    event_type=event_type,
                    data_path=str(tmp_csv),
                    gold_path=str(self._gold_path),
                    gold_lessons_path=str(self._gold_path),
                    output_dir=str(tmp_dir),
                    asset="XAU/USD",
                    horizon=self._horizon,
                )

            src = tmp_dir / "lessons.csv"
            if src.exists():
                shutil.copy2(src, event_knowledge_dir / "lessons.csv")
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

    # -- evaluation --------------------------------------------------------

    def _run_evaluation(self, event_type: str) -> EventRunResult:
        """Replay post-cutoff events using pre-built training knowledge."""
        import shutil

        import pandas as pd

        spec = _BUILTIN_EVENTS.get(event_type) or _SYNTHETIC_EVENTS.get(event_type)
        csv_path = self._data_dir / spec["csv"]
        release_csv = HistoricalReplayEngine._release_calendar_path_for(event_type, self._data_dir)

        prebuilt = self._knowledge_dir / event_type / "lessons.csv"
        prebuilt_str = str(prebuilt)

        if release_csv is not None and release_csv.exists():
            return self._eval_release_event(event_type, csv_path, release_csv, prebuilt_str)
        return self._eval_legacy_event(event_type, csv_path, prebuilt_str)

    def _eval_release_event(
        self,
        event_type: str,
        csv_path: Path,
        calendar_path: Path,
        prebuilt_lessons_path: str,
    ) -> EventRunResult:
        import pandas as pd
        import tempfile

        calendar = pd.read_csv(calendar_path)
        if "release_timestamp" not in calendar.columns:
            calendar["release_timestamp"] = (
                calendar["release_date"] + " " + calendar["release_time"]
            )
        calendar["release_timestamp"] = pd.to_datetime(calendar["release_timestamp"])
        eval_cal = calendar[calendar["release_timestamp"] >= self._cutoff].copy()
        if eval_cal.empty:
            return EventRunResult(
                event_type=event_type,
                event_date_min="",
                event_date_max="",
                event_count=0,
                success=True,
                execution_time_ms=0.0,
                cache_hits=0,
                checkpoints_used=0,
                error=f"No evaluation events on or after {self._cutoff.date()}",
                errors=(f"No evaluation events on or after {self._cutoff.date()}",),
            )

        eval_cal["reference_period"] = pd.to_datetime(eval_cal["reference_period"], errors="coerce")
        eval_cal = eval_cal.dropna(subset=["reference_period"])

        cpi_raw = pd.read_csv(csv_path)
        cpi_raw["Date"] = pd.to_datetime(cpi_raw["Date"], errors="coerce")
        cpi_raw = cpi_raw.dropna(subset=["Date"]).sort_values("Date")

        cpi_merged = cpi_raw.merge(
            eval_cal, left_on="Date", right_on="reference_period", how="inner"
        )
        cpi_merged["release_timestamp"] = pd.to_datetime(cpi_merged["release_timestamp"])
        cpi_merged = cpi_merged.sort_values("release_timestamp")

        if cpi_merged.empty:
            return EventRunResult(
                event_type=event_type,
                event_date_min="",
                event_date_max="",
                event_count=0,
                success=True,
                execution_time_ms=0.0,
                cache_hits=0,
                checkpoints_used=0,
                decision=None,
                error=f"No CPI data matching evaluation calendar on or after {self._cutoff.date()}",
                errors=(f"No CPI data matching evaluation calendar on or after {self._cutoff.date()}",),
            )

        gold_df = self._load_gold_data()
        gold_df["Date"] = pd.to_datetime(gold_df["Date"], errors="coerce")
        gold_df = gold_df.dropna(subset=["Date"]).sort_values("Date")

        # Reuse the release-by-release replay with pre-built knowledge
        engine = _EvalReplayEngine(
            gold_df=gold_df,
            checkpoint_dir=self._checkpoint_dir,
            max_workers=self._max_workers,
            horizon=self._horizon,
            data_dir=self._data_dir,
            gold_path=self._gold_path,
            prebuilt_lessons_path=prebuilt_lessons_path,
        )
        return engine.run(event_type, csv_path, calendar_path, cpi_merged)

    def _eval_legacy_event(
        self,
        event_type: str,
        csv_path: Path,
        prebuilt_lessons_path: str,
    ) -> EventRunResult:
        import shutil
        import tempfile

        import pandas as pd

        df = pd.read_csv(csv_path)
        df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
        df = df.dropna(subset=["Date"])
        eval_df = df[df["Date"] >= self._cutoff].copy()
        if eval_df.empty:
            return EventRunResult(
                event_type=event_type,
                event_date_min="",
                event_date_max="",
                event_count=0,
                success=True,
                execution_time_ms=0.0,
                cache_hits=0,
                checkpoints_used=0,
                error=f"No evaluation events on or after {self._cutoff.date()}",
                errors=(f"No evaluation events on or after {self._cutoff.date()}",),
            )

        output_dir = csv_path.parent / "output"
        output_dir.mkdir(parents=True, exist_ok=True)

        tmp_dir = Path(tempfile.mkdtemp(prefix="aurumai_oos_eval_"))
        try:
            tmp_csv = tmp_dir / f"{event_type.lower()}.csv"
            eval_df["Date"] = eval_df["Date"].dt.strftime("%Y-%m-%d")
            eval_df.to_csv(tmp_csv, index=False)

            orch = InstitutionalOrchestrator.with_default_pipeline(
                checkpoint_dir=self._checkpoint_dir,
                max_workers=self._max_workers,
            )
            t0 = time.perf_counter()
            assessment = orch.run_all(
                trigger="oos_eval",
                pipeline_id=f"oos_eval_{event_type.lower()}_legacy",
                force=True,
                event_type=event_type,
                data_path=str(tmp_csv),
                gold_path=str(self._gold_path),
                gold_lessons_path=str(self._gold_path),
                output_dir=str(output_dir),
                asset="XAU/USD",
                horizon=self._horizon,
                prebuilt_lessons_path=prebuilt_lessons_path,
            )
            elapsed_ms = (time.perf_counter() - t0) * 1000.0

            event_count = len(eval_df)
            date_min = eval_df["Date"].min().strftime("%Y-%m-%d")
            date_max = eval_df["Date"].max().strftime("%Y-%m-%d")

            return HistoricalReplayEngine._assessment_to_result(
                event_type=event_type,
                csv_path=csv_path,
                assessment=assessment,
                event_count=event_count,
                elapsed_ms=elapsed_ms,
            )
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

    def _load_gold_data(self) -> pd.DataFrame:
        import pandas as pd
        df = pd.read_csv(self._gold_path)
        return df


class _EvalReplayEngine:
    """Minimal release-by-release replay for the evaluation phase.

    Mirrors the structure of ``HistoricalReplayEngine._replay_event_release_by_release``
    but injects ``prebuilt_lessons_path`` into every pipeline invocation so that
    knowledge is always sourced from training-period lessons.
    """

    def __init__(
        self,
        gold_df: pd.DataFrame,
        checkpoint_dir: str | None,
        max_workers: int,
        horizon: int,
        data_dir: Path,
        gold_path: Path,
        prebuilt_lessons_path: str,
    ):
        self._gold_df = gold_df
        self._checkpoint_dir = checkpoint_dir
        self._max_workers = max_workers
        self._horizon = horizon
        self._data_dir = data_dir
        self._gold_path = gold_path
        self._prebuilt_lessons_path = prebuilt_lessons_path

    def run(
        self,
        event_type: str,
        csv_path: Path,
        calendar_path: Path,
        cpi_merged: pd.DataFrame,
    ) -> EventRunResult:
        import shutil
        import tempfile

        import pandas as pd

        output_dir = csv_path.parent / "output"
        output_dir.mkdir(parents=True, exist_ok=True)

        gold = self._gold_df

        total_elapsed_ms = 0.0
        total_cache_hits = 0
        total_checkpoints = 0
        release_count = 0
        errors: list[str] = []
        all_outputs: list[dict[str, Any]] = []
        n_releases = len(cpi_merged)

        for idx, (_cal_idx, release_row) in enumerate(cpi_merged.iterrows()):
            as_of = release_row["release_timestamp"]

            cpi_snapshot = cpi_merged[
                cpi_merged["release_timestamp"] <= as_of
            ].copy()
            cpi_snapshot = cpi_snapshot[["Date", "Value", "release_timestamp"]]
            cpi_snapshot["Date"] = cpi_snapshot["Date"].dt.strftime("%Y-%m-%d")
            cpi_snapshot["release_timestamp"] = cpi_snapshot["release_timestamp"].dt.strftime(
                "%Y-%m-%d %H:%M:%S"
            )

            tmp = Path(tempfile.mkdtemp(prefix="aurumai_eval_release_"))
            try:
                tmp_cpi = tmp / "cpi.csv"
                tmp_gold = tmp / "gold.csv"
                tmp_gold_lessons = tmp / "gold_lessons.csv"
                cpi_snapshot.to_csv(tmp_cpi, index=False)
                gold[gold["Date"] <= as_of].to_csv(tmp_gold, index=False)
                gold.to_csv(tmp_gold_lessons, index=False)

                orch = InstitutionalOrchestrator.with_default_pipeline(
                    checkpoint_dir=self._checkpoint_dir,
                    max_workers=self._max_workers,
                )

                pipeline_id = (
                    f"oos_eval_{event_type.lower()}_{as_of.strftime('%Y%m%d_%H%M%S')}"
                )

                t0 = time.perf_counter()
                assessment = orch.run_all(
                    trigger="oos_eval",
                    pipeline_id=pipeline_id,
                    force=True,
                    event_type=event_type,
                    data_path=str(tmp_cpi),
                    gold_path=str(tmp_gold),
                    gold_lessons_path=str(tmp_gold_lessons),
                    output_dir=str(output_dir),
                    asset="XAU/USD",
                    horizon=self._horizon,
                    release_calendar_path=str(calendar_path),
                    prebuilt_lessons_path=self._prebuilt_lessons_path,
                )
                release_elapsed = (time.perf_counter() - t0) * 1000.0

                total_elapsed_ms += release_elapsed
                total_cache_hits += assessment.cache_hits
                total_checkpoints += sum(
                    1 for s in assessment.stages if s.checkpoint is not None
                )
                release_count += 1

                if assessment.errors:
                    errors.extend(
                        f"[release {idx + 1}/{n_releases} as_of={as_of}] {e}"
                        for e in assessment.errors
                    )

                finalize_out = assessment.outputs.get("finalize", {}) or {}
                all_outputs.append(finalize_out)

            finally:
                shutil.rmtree(tmp, ignore_errors=True)

        success = len(errors) == 0
        date_min = cpi_merged["Date"].min().strftime("%Y-%m-%d")
        date_max = cpi_merged["Date"].max().strftime("%Y-%m-%d")

        final_finalize = all_outputs[-1] if all_outputs else {}
        decision = HistoricalReplayEngine._extract_decision(final_finalize)
        risk_decision = HistoricalReplayEngine._extract_risk_decision(final_finalize)
        forecast_model = HistoricalReplayEngine._extract_forecast_model(final_finalize)
        forecast_confidence = HistoricalReplayEngine._extract_forecast_confidence(final_finalize)
        validation_passed, validation_metrics = HistoricalReplayEngine._extract_validation(final_finalize)
        var_95, cvar_95, tail_index = HistoricalReplayEngine._extract_risk_metrics(final_finalize)
        position_scaling = HistoricalReplayEngine._extract_position_scaling(final_finalize)
        risk_gate_action, risk_gate_score = HistoricalReplayEngine._extract_risk_gate(final_finalize)

        # OOS correctness (same logic as HistoricalReplayEngine)
        decision_correct: bool | None = None
        decision_actual_return_pct: float | None = None
        if decision is not None and gold is not None and all_outputs:
            last_as_of = cpi_merged.iloc[-1]["release_timestamp"]
            gold_return = _compute_gold_return(gold, last_as_of)
            if gold_return is not None:
                decision_actual_return_pct = gold_return
                actual_dir = _classify_actual_direction(gold_return)
                decision_correct = _decision_is_correct(decision, actual_dir)

        return EventRunResult(
            event_type=event_type,
            event_date_min=date_min,
            event_date_max=date_max,
            event_count=release_count,
            success=success,
            execution_time_ms=total_elapsed_ms,
            cache_hits=total_cache_hits,
            checkpoints_used=total_checkpoints,
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
            decision_correct=decision_correct,
            decision_actual_return_pct=decision_actual_return_pct,
            error=errors[0] if errors else None,
            errors=tuple(errors),
        )
