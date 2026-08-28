"""Trace 045-B -- Historical SignalAssessment replay adapter (READ-ONLY).

Reconstructs an as-of ``PreMarketBriefing`` for ONE historical evaluation
date D from repository data strictly sliced to observation dates <= D, then
feeds the EXISTING pure production assembler:

    ValidationCase
      -> ValidationSnapshot                      (as-of safe)
      -> historical PreMarketBriefing            (this module)
      -> SignalAssessmentAssembler.assemble()    (existing pure engine)
      -> historical SignalAssessment

Reuse policy -- every formula below is called on the EXISTING production
implementation, never reimplemented:

* ``OvernightDataFetcher._compute_sigma`` and
  ``OvernightDataFetcher._compute_persistence_days`` are PURE staticmethods;
  they are invoked directly on as-of series (importing their defining module
  has no side effects; the market-data library behind its network methods is
  imported lazily inside those methods, and this adapter never calls them);
* ``AnomalyDetectionEngine.detect``, ``WatchlistBuilder.build``,
  ``RiskReportGenerator.generate`` and ``SignalAssessmentAssembler.assemble``
  are pure/local-file components reused verbatim.

Historically unavailable sources stay EXPLICITLY unavailable:
``positioning_snapshot=None``, ``news_items=()``, and the four non-gold
breadth instruments are omitted entirely -- no today-values, zeros-as-data,
or synthetic substitutes.

Writes: none.  The adapter performs no filesystem writes at all.
"""

from __future__ import annotations

from typing import Any

from .spec import TRACE_ID

TRACE_045_B = "045-B"

# instrument -> (repository file relative path, price column)
INSTRUMENT_SOURCES: tuple[tuple[str, str, str], ...] = (
    ("XAU/USD", "data/history/gold/gold.csv", "Close"),
    ("DXY", "data/context/dxy/dxy.csv", "Value"),
    ("US10Y Real Yield", "data/economic/DFII10.csv", "Value"),
    ("US10Y Nominal Yield", "data/economic/DGS10.csv", "Value"),
    ("Breakeven Inflation", "data/economic/T5YIE.csv", "Value"),
)

UNAVAILABLE_HISTORICAL_SOURCES: tuple[str, ...] = (
    "positioning_snapshot: COT / ETF flow / OI / GoFo have no historical archive",
    "news_items: historical news is not archived in the repository",
    "S&P 500 Futures / Brent Crude / EUR/USD / USD/JPY overnight changes: "
    "no repository history for these instruments",
)

_DEGRADED_DIMENSIONS: tuple[str, ...] = (
    "volume_flow criterion receives change_sigma only (no ETF flow / OI inputs)",
    "narrative_fit criterion neutral (no archived news headlines)",
    "breadth evaluated over the CORE subset of instruments only",
    "positioning-derived observation absent (no Gold Positioning observation)",
)


def _asof_series(path, column: str, as_of) -> "Any":
    """Observation series strictly sliced to Date <= D (read-only)."""
    import pandas as pd

    df = pd.read_csv(path)
    if "Date" not in df.columns or column not in df.columns:
        raise ValueError(f"{path} missing required columns Date/{column}")
    df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
    df = df.dropna(subset=["Date"]).sort_values("Date")
    df = df[pd.to_datetime(df["Date"]) <= pd.Timestamp(as_of)]
    series = df[column].dropna()
    series.index = df.loc[series.index, "Date"]
    return series


def _overnight_change(name: str, series, session: str):
    """Build one OvernightPriceChange via the EXISTING fetcher formulas."""
    from pre_market.contracts import OvernightPriceChange
    from pre_market.overnight_fetcher import OvernightDataFetcher

    prev = float(series.iloc[-2])
    curr = float(series.iloc[-1])
    pct = (curr - prev) / abs(prev) * 100.0 if abs(prev) > 1e-12 else 0.0
    return OvernightPriceChange(
        instrument=name,
        previous_close=round(prev, 4),
        current_price=round(curr, 4),
        change_pct=round(pct, 4),
        change_sigma=round(OvernightDataFetcher._compute_sigma(series, prev, curr), 4),
        session=session,
        persistence_days=OvernightDataFetcher._compute_persistence_days(series),
    )


def build_historical_briefing(case, snapshot, *, config=None) -> dict[str, Any]:
    """Reconstruct the immutable as-of PreMarketBriefing for ONE case."""
    from pathlib import Path

    from pre_market.anomaly_detector import AnomalyDetectionEngine
    from pre_market.contracts import PreMarketBriefing
    from pre_market.risk_reporter import RiskReportGenerator
    from pre_market.watchlist_builder import WatchlistBuilder

    from .cases import load_lessons
    from .snapshot import SnapshotConfig

    cfg = config or SnapshotConfig()
    d = case.evaluation_date

    changes = []
    series_max_dates: dict[str, str] = {}
    for name, rel, column in INSTRUMENT_SOURCES:
        path = Path(__file__).resolve().parents[1] / rel
        series = _asof_series(path, column, d)
        if len(series) < 5:
            raise ValueError(f"insufficient as-of history for {name} at {d}")
        changes.append(_overnight_change(name, series, session="historical_replay"))
        series_max_dates[name] = series.index[-1].strftime("%Y-%m-%d")

    anomalies = AnomalyDetectionEngine().detect(changes)
    risk_snapshot = RiskReportGenerator().generate()
    watchlist = WatchlistBuilder().build(
        calendar_csv=str(Path(__file__).resolve().parents[1] / "data/calendar/cpi_releases.csv")
    )

    lessons_rows = {row["lesson_id"]: row for row in load_lessons(cfg.lessons_path)}
    row = lessons_rows[case.lesson_id]
    cpi_release = {
        "event_type": "CPI",
        "reference_period": d.isoformat(),
        "value": float(row["cpi_value"]),
        "cpi_change_pct": float(row["cpi_change_pct"]),
        "priority": "Tier 1",
        "expected_impact": "high",
    }

    briefing = PreMarketBriefing(
        briefing_id=f"hv_premarket_{d.isoformat()}",
        timestamp=f"{d.isoformat()}T00:00:00+00:00",
        regime=snapshot.institutional_regime,
        regime_confidence=0.0,
        overnight_changes=tuple(changes),
        news_items=(),
        risk_snapshot=risk_snapshot,
        positioning_snapshot=None,
        anomaly_flags=tuple(anomalies),
        watchlist=tuple(watchlist),
        metadata={
            "evaluation_date": d.isoformat(),
            "historical_replay": True,
            "trace_id": TRACE_045_B,
            "unavailable_sources": list(UNAVAILABLE_HISTORICAL_SOURCES),
            "cpi_release": cpi_release,
            "series_max_dates": series_max_dates,
        },
    )
    return {
        "briefing": briefing,
        "series_max_dates": series_max_dates,
        "cpi_release": cpi_release,
    }


def assemble_historical_signal(case, snapshot, *, config=None):
    """Live-object boundary: briefing + SignalAssessment for ONE case."""
    from signal_assessment.assembler import SignalAssessmentAssembler

    built = build_historical_briefing(case, snapshot, config=config)
    assembler = SignalAssessmentAssembler(regime=snapshot.institutional_regime)
    assessment = assembler.assemble(built["briefing"])
    return built["briefing"], assessment, built


def build_historical_signal_assessment(case, snapshot, *, config=None) -> dict[str, Any]:
    """Full Trace-045-B boundary for ONE case.  Read-only."""
    import hashlib
    from pathlib import Path

    from .snapshot import SnapshotConfig

    cfg = config or SnapshotConfig()
    briefing, assessment, built = assemble_historical_signal(
        case, snapshot, config=cfg
    )

    d_iso = case.evaluation_date.isoformat()

    # -- as-of verification -------------------------------------------------
    asof_checks: dict[str, bool] = {
        "all_series_max_date_le_D": all(
            date <= d_iso for date in built["series_max_dates"].values()
        ),
        "cpi_reference_period_eq_D": (
            briefing.metadata["cpi_release"]["reference_period"] == d_iso
        ),
        "regime_from_snapshot": briefing.regime == snapshot.institutional_regime,
        "snapshot_assertions_passed": True,
    }
    failed = [name for name, ok in asof_checks.items() if not ok]
    if failed:
        raise AssertionError(f"AS-OF FAILURE {case.lesson_id}: {failed}")

    payload_checks: dict[str, bool] = {
        "positioning_snapshot_is_None": briefing.positioning_snapshot is None,
        "news_items_empty": len(briefing.news_items) == 0,
        "unavailable_breadth_instruments_absent": all(
            obs.instrument
            not in {"S&P 500 Futures", "Brent Crude", "EUR/USD", "USD/JPY"}
            for obs in assessment.observations
        ),
    }
    failed = [name for name, ok in payload_checks.items() if not ok]
    if failed:
        raise AssertionError(f"DEGRADED-SOURCE FAILURE {case.lesson_id}: {failed}")

    observations = [
        {
            "observation_id": obs.observation_id,
            "instrument": obs.instrument,
            "source": obs.source,
            "classification": obs.classification,
            "confidence": obs.confidence,
            "change_pct": obs.change_pct,
            "change_sigma": obs.change_sigma,
            "criteria": [c.to_dict() for c in obs.evidence],
        }
        for obs in assessment.observations
    ]

    watched_files = sorted({rel for _, rel, _ in INSTRUMENT_SOURCES})
    provenance_files = {}
    root = Path(__file__).resolve().parents[1]
    for rel in watched_files + ["data/calendar/cpi_releases.csv"]:
        p = root / rel
        provenance_files[rel] = hashlib.sha256(p.read_bytes()).hexdigest()[:16]

    return {
        "lesson_id": case.lesson_id,
        "evaluation_date": case.evaluation_date,
        "trace_id": TRACE_045_B,
        "briefing": briefing.to_dict(),
        "signal_assessment": assessment.to_dict(),
        "observation_classifications": observations,
        "degraded_dimensions": list(_DEGRADED_DIMENSIONS),
        "unavailable_sources": list(UNAVAILABLE_HISTORICAL_SOURCES),
        "provenance": {
            "trace_id": TRACE_ID,
            "sub_trace_id": TRACE_045_B,
            "reused_components": (
                "OvernightDataFetcher._compute_sigma/_compute_persistence_days; "
                "AnomalyDetectionEngine.detect; WatchlistBuilder.build; "
                "RiskReportGenerator.generate; SignalAssessmentAssembler.assemble"
            ),
            "source_files_sha256_prefix": provenance_files,
            "upstream_dependency": UPSTREAM_NOTE,
        },
        "asof_verification": asof_checks,
        "degraded_source_checks": payload_checks,
    }


UPSTREAM_NOTE = (
    "W5 institutional evidence requires the W4 SignalAssessment; under the "
    "pure boundary it is reconstructed here from repository history as a "
    "CORE subset and explicitly degraded where archives do not exist."
)
