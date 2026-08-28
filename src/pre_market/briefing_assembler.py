from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import numpy as np

from pre_market.anomaly_detector import AnomalyDetectionEngine
from pre_market.contracts import PreMarketBriefing, WatchlistItem
from pre_market.news_ingestion import OvernightNewsIngestion
from pre_market.overnight_fetcher import OvernightDataFetcher
from pre_market.positioning import PositioningDataFetcher
from pre_market.risk_reporter import RiskReportGenerator
from pre_market.watchlist_builder import WatchlistBuilder


class PreMarketBriefingAssembler:
    """Composes all W3 intelligence into a single PreMarketBriefing contract.

    Orchestrates the 7 processing stages from IMPLEMENTATION_WORKFLOWS.md:
    1. Overnight market data fetch
    2. Overnight news ingestion
    3. Research report ingestion (placeholder)
    4. Risk report generation
    5. Positioning data fetch
    6. Anomaly detection
    7. Briefing assembly
    """

    def __init__(
        self,
        overnight_fetcher: OvernightDataFetcher | None = None,
        news_ingestion: OvernightNewsIngestion | None = None,
        risk_reporter: RiskReportGenerator | None = None,
        positioning_fetcher: PositioningDataFetcher | None = None,
        anomaly_detector: AnomalyDetectionEngine | None = None,
        watchlist_builder: WatchlistBuilder | None = None,
        regime: str = "",
        regime_confidence: float = 0.0,
    ) -> None:
        self._overnight = overnight_fetcher or OvernightDataFetcher()
        self._news = news_ingestion or OvernightNewsIngestion()
        self._risk = risk_reporter or RiskReportGenerator()
        self._positioning = positioning_fetcher or PositioningDataFetcher()
        self._anomaly = anomaly_detector or AnomalyDetectionEngine()
        self._watchlist = watchlist_builder or WatchlistBuilder()
        self._regime = regime
        self._regime_confidence = regime_confidence

    def assemble(
        self,
        session: str = "APAC",
        portfolio_returns: np.ndarray | None = None,
        portfolio_equity: float = 0.0,
        daily_pnl: float = 0.0,
        unrealized_pnl: float = 0.0,
        exposure: float = 0.0,
        var_utilization_pct: float = 0.0,
        calendar_csv: str | None = None,
        briefing_id: str | None = None,
        external_news_items: tuple | list | None = None,
    ) -> PreMarketBriefing:
        now = datetime.now(timezone.utc)
        bid = briefing_id or f"premarket_{now.strftime('%Y%m%d_%H%M%S')}"

        overnight_result = self._overnight.fetch_all(session=session)
        overnight_changes = overnight_result.get("overnight_changes", [])
        if not isinstance(overnight_changes, list):
            overnight_changes = []

        # Sprint 058 (W-5): when the orchestrator's ingest_news stage already
        # produced normalized news, consume it instead of re-collecting
        # (single ingestion, full provenance).  The legacy internal path is
        # kept only for standalone use where no stage output exists.
        news_source_path = "none"
        if external_news_items is not None:
            # Stage output exists: consume it verbatim (even when empty) so
            # an empty/unavailable stage result is never masked by a second
            # collection pass.
            news_items = list(external_news_items)
            news_source_path = "ingest_news_stage"
        else:
            news_items, sentiment_status = self._news.ingest_with_status()
            news_source_path = f"legacy_internal_ingestion:{sentiment_status}"

        risk_snapshot = self._risk.generate(
            portfolio_returns=portfolio_returns,
            portfolio_equity=portfolio_equity,
            daily_pnl=daily_pnl,
            unrealized_pnl=unrealized_pnl,
            exposure=exposure,
            var_utilization_pct=var_utilization_pct,
        )
        positioning_snapshot = self._positioning.fetch()
        anomaly_flags = self._anomaly.detect(overnight_changes)
        # Final Hardening (D-11): the watchlist availability status is
        # surfaced on the briefing metadata -- a default-fallback watchlist
        # (undated generic events) is never silently presented as the
        # calendar output.
        watchlist, watchlist_status = self._watchlist.build_with_status(
            calendar_csv=calendar_csv
        )

        return PreMarketBriefing(
            briefing_id=bid,
            timestamp=now.isoformat(),
            regime=self._regime,
            regime_confidence=self._regime_confidence,
            overnight_changes=tuple(overnight_changes),
            news_items=tuple(news_items),
            risk_snapshot=risk_snapshot,
            positioning_snapshot=positioning_snapshot,
            anomaly_flags=tuple(anomaly_flags),
            watchlist=tuple(watchlist),
            metadata={
                "news_source_path": news_source_path,
                "watchlist_status": watchlist_status,
            },
        )
