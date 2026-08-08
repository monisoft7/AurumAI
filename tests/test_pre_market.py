"""Unit + integration tests for W3 Pre-Market Intelligence Scan."""

import json
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import numpy as np
import pandas as pd
import pytest

from pre_market.anomaly_detector import AnomalyDetectionEngine
from pre_market.briefing_assembler import PreMarketBriefingAssembler
from pre_market.contracts import (
    AnomalyFlag,
    NewsItem,
    OvernightPriceChange,
    PositioningSnapshot,
    PreMarketBriefing,
    RiskSnapshot,
    WatchlistItem,
)
from pre_market.news_ingestion import OvernightNewsIngestion
from pre_market.overnight_fetcher import OvernightDataFetcher
from pre_market.positioning import PositioningDataFetcher
from pre_market.risk_reporter import RiskReportGenerator
from pre_market.watchlist_builder import WatchlistBuilder


# =========================================================================
# Contract tests
# =========================================================================


class TestOvernightPriceChange:
    def test_to_dict_from_dict_roundtrip(self):
        obj = OvernightPriceChange(
            instrument="XAU/USD",
            previous_close=1900.0,
            current_price=1910.0,
            change_pct=0.53,
            change_sigma=1.2,
            session="APAC",
        )
        d = obj.to_dict()
        restored = OvernightPriceChange.from_dict(d)
        assert restored.instrument == obj.instrument
        assert restored.change_pct == obj.change_pct
        assert restored.session == obj.session

    def test_from_dict_defaults(self):
        restored = OvernightPriceChange.from_dict({})
        assert restored.instrument == ""
        assert restored.change_pct == 0.0

    def test_persistence_days_roundtrip(self):
        obj = OvernightPriceChange(
            instrument="XAU/USD",
            previous_close=1900.0,
            current_price=1912.0,
            change_pct=0.63,
            change_sigma=2.1,
            session="APAC",
            persistence_days=4.0,
        )
        restored = OvernightPriceChange.from_dict(obj.to_dict())
        assert restored.persistence_days == 4.0

    def test_persistence_days_defaults_zero(self):
        restored = OvernightPriceChange.from_dict({})
        assert restored.persistence_days == 0.0


class TestNewsItem:
    def test_to_dict_from_dict_roundtrip(self):
        obj = NewsItem(
            headline="Fed holds rates steady",
            source="Reuters",
            published="2026-07-29T06:00:00",
            sentiment_label="positive",
            sentiment_confidence=0.85,
            relevance_score=0.9,
            topics=("fed", "interest_rates"),
        )
        d = obj.to_dict()
        restored = NewsItem.from_dict(d)
        assert restored.headline == obj.headline
        assert restored.relevance_score == obj.relevance_score


class TestRiskSnapshot:
    def test_to_dict_from_dict_roundtrip(self):
        obj = RiskSnapshot(
            pnl_daily=1500.0,
            pnl_unrealized=-200.0,
            var_95=-0.023,
            var_99=-0.045,
            cvar_95=-0.035,
            tail_index=3.5,
            drawdown_pct=0.05,
            drawdown_state="normal",
            var_utilization_pct=45.0,
            exposure=50000.0,
            timestamp="2026-07-29T06:00:00",
        )
        d = obj.to_dict()
        restored = RiskSnapshot.from_dict(d)
        assert restored.pnl_daily == obj.pnl_daily
        assert restored.drawdown_state == obj.drawdown_state


class TestPositioningSnapshot:
    def test_to_dict_from_dict_roundtrip(self):
        obj = PositioningSnapshot(
            cot_z_score=1.5,
            cot_regime="bullish",
            etf_flow_momentum="accumulating",
            etf_flow_change_pct=2.3,
            open_interest_change_pct=-0.5,
            gofo_rate=0.12,
        )
        d = obj.to_dict()
        restored = PositioningSnapshot.from_dict(d)
        assert restored.cot_z_score == obj.cot_z_score
        assert restored.etf_flow_momentum == obj.etf_flow_momentum


class TestAnomalyFlag:
    def test_to_dict_from_dict_roundtrip(self):
        obj = AnomalyFlag(
            anomaly_type="two_sigma_move",
            severity="medium",
            instrument="XAU/USD",
            description="Gold moved 2.5sigma",
            value=2.5,
            threshold=2.0,
        )
        d = obj.to_dict()
        restored = AnomalyFlag.from_dict(d)
        assert restored.anomaly_type == obj.anomaly_type
        assert restored.value == obj.value


class TestWatchlistItem:
    def test_to_dict_from_dict_roundtrip(self):
        obj = WatchlistItem(
            event_type="CPI",
            release_date="2026-07-31",
            release_time="08:30",
            priority="Tier 1",
            description="Consumer Price Index",
            expected_impact="high",
        )
        d = obj.to_dict()
        restored = WatchlistItem.from_dict(d)
        assert restored.event_type == obj.event_type
        assert restored.priority == obj.priority


class TestPreMarketBriefing:
    def test_minimal_briefing(self):
        briefing = PreMarketBriefing(
            briefing_id="test_001",
            timestamp="2026-07-29T06:00:00",
            regime="NORMAL_GROWTH",
            regime_confidence=0.85,
        )
        assert briefing.briefing_id == "test_001"
        assert briefing.regime == "NORMAL_GROWTH"
        assert briefing.risk_snapshot is None

    def test_to_dict_from_dict_roundtrip(self):
        briefing = PreMarketBriefing(
            briefing_id="test_001",
            timestamp="2026-07-29T06:00:00",
            regime="NORMAL_GROWTH",
            regime_confidence=0.85,
            overnight_changes=(
                OvernightPriceChange("XAU/USD", 1900, 1910, 0.53, 1.2, "APAC"),
            ),
            news_items=(
                NewsItem("Headline", "Source", "2026-07-29", "neutral", 0.5, 0.8),
            ),
            risk_snapshot=RiskSnapshot(100, 0, -0.02, -0.04, -0.03, None, 0, "normal", 0, 0),
            positioning_snapshot=PositioningSnapshot(0, "neutral", "stable", 0, 0, 0),
            anomaly_flags=(
                AnomalyFlag("two_sigma", "medium", "XAU/USD", "test", 2.0, 2.0),
            ),
            watchlist=(
                WatchlistItem("CPI", "2026-07-31", "08:30", "Tier 1", "CPI", "high"),
            ),
        )
        d = briefing.to_dict()
        restored = PreMarketBriefing.from_dict(d)
        assert restored.briefing_id == briefing.briefing_id
        assert len(restored.overnight_changes) == 1
        assert len(restored.news_items) == 1
        assert restored.risk_snapshot is not None
        assert restored.positioning_snapshot is not None
        assert len(restored.anomaly_flags) == 1
        assert len(restored.watchlist) == 1

    def test_json_serializable(self):
        briefing = PreMarketBriefing(
            briefing_id="json_test",
            timestamp="2026-07-29T06:00:00",
            regime="INFLATIONARY",
            regime_confidence=0.72,
        )
        serialized = json.dumps(briefing.to_dict())
        restored = PreMarketBriefing.from_dict(json.loads(serialized))
        assert restored.briefing_id == "json_test"
        assert restored.regime == "INFLATIONARY"


# =========================================================================
# OvernightDataFetcher tests
# =========================================================================


class TestOvernightDataFetcher:
    def test_fetch_yfinance_change_no_data_returns_none(self):
        with patch("yfinance.download", return_value=pd.DataFrame()):
            fetcher = OvernightDataFetcher()
            result = fetcher._fetch_yfinance_change("XAU/USD", "GC=F", "APAC")
            assert result is None

    def test_fetch_overnight_changes_returns_list(self):
        mock_data = pd.DataFrame({
            "Close": [1900.0, 1910.0, 1905.0, 1908.0, 1912.0],
        }, index=pd.date_range("2026-07-24", periods=5))
        with patch("yfinance.download", return_value=mock_data):
            fetcher = OvernightDataFetcher(lookback_days=5)
            changes = fetcher.fetch_overnight_changes(session="APAC")
            assert isinstance(changes, list)

    def test_compute_sigma(self):
        series = pd.Series([100.0, 101.0, 99.0, 102.0, 100.5])
        sigma = OvernightDataFetcher._compute_sigma(series, 100.0, 101.0)
        assert isinstance(sigma, float)

    def test_fetch_all_returns_dict(self):
        with patch("yfinance.download", return_value=pd.DataFrame()):
            fetcher = OvernightDataFetcher()
            result = fetcher.fetch_all(session="APAC")
            assert "overnight_changes" in result

    def test_default_lookback_is_10_days(self):
        fetcher = OvernightDataFetcher()
        assert fetcher._lookback_days == 10

    def test_lookback_override(self):
        fetcher = OvernightDataFetcher(lookback_days=5)
        assert fetcher._lookback_days == 5

    def test_real_z_score_path(self):
        series = pd.Series([100.0, 101.0, 102.5, 103.0, 105.0])
        sigma = OvernightDataFetcher._compute_sigma(series, 103.0, 105.0)
        assert sigma > 0.0

    def test_four_bar_window_sigma_still_zero(self):
        series = pd.Series([100.0, 101.0, 102.0, 103.0])
        sigma = OvernightDataFetcher._compute_sigma(series, 102.0, 103.0)
        assert sigma == 0.0

    def test_persistence_days_consecutive_direction(self):
        series = pd.Series([100.0, 101.0, 102.5, 103.0, 105.0])
        days = OvernightDataFetcher._compute_persistence_days(series)
        assert days == 4.0

    def test_persistence_days_stops_on_direction_change(self):
        series = pd.Series([100.0, 101.0, 100.5, 101.0, 102.0])
        days = OvernightDataFetcher._compute_persistence_days(series)
        assert days == 2.0

    def test_persistence_days_returns_zero_on_flat(self):
        series = pd.Series([100.0, 100.0, 100.0])
        days = OvernightDataFetcher._compute_persistence_days(series)
        assert days == 0.0


# =========================================================================
# OvernightNewsIngestion tests
# =========================================================================


class TestOvernightNewsIngestion:
    def test_default_relevance_scores_topic_matches(self):
        from news.models import NewsArticle, Topic

        article = NewsArticle(
            title="Fed signals potential rate cut amid inflation concerns",
            source="Test",
            url="http://test.com",
            topics=(Topic.FED, Topic.INFLATION),
        )
        score = OvernightNewsIngestion._default_relevance(article, OvernightNewsIngestion.W3_TOPICS)
        assert score > 0.3

    def test_default_relevance_low_for_unrelated(self):
        from news.models import NewsArticle, Topic

        article = NewsArticle(
            title="Tech stock rally continues",
            source="Test",
            url="http://test.com",
            topics=(),
        )
        score = OvernightNewsIngestion._default_relevance(article, OvernightNewsIngestion.W3_TOPICS)
        assert score == 0.0

    def test_ingest_empty_when_no_articles(self):
        collector = MagicMock()
        collector.collect.return_value = []
        ingestion = OvernightNewsIngestion(collector=collector)
        items = ingestion.ingest()
        assert items == []

    def test_ingest_returns_sorted_news_items(self):
        from news.models import NewsArticle, Topic

        articles = [
            NewsArticle(title="Gold at record high", source="R", url="http://r.com",
                        published=datetime(2026, 7, 29, 6, 0, 0), topics=(Topic.GOLD,)),
            NewsArticle(title="Fed holds rates", source="R", url="http://r.com",
                        published=datetime(2026, 7, 29, 6, 5, 0), topics=(Topic.FED,)),
        ]
        collector = MagicMock()
        collector.collect.return_value = articles
        analyzer = MagicMock()
        analyzer.analyze_batch.return_value = [
            MagicMock(label="positive", confidence=0.9),
            MagicMock(label="neutral", confidence=0.7),
        ]
        ingestion = OvernightNewsIngestion(collector=collector, sentiment_analyzer=analyzer)
        items = ingestion.ingest(max_articles=10)
        assert len(items) == 2
        assert items[0].relevance_score >= items[1].relevance_score


# =========================================================================
# RiskReportGenerator tests
# =========================================================================


class TestRiskReportGenerator:
    def test_generate_returns_risk_snapshot(self):
        generator = RiskReportGenerator()
        snapshot = generator.generate(
            portfolio_returns=np.random.default_rng(42).normal(0, 0.02, 252),
            portfolio_equity=100000.0,
            daily_pnl=1500.0,
            exposure=50000.0,
            var_utilization_pct=45.0,
        )
        assert isinstance(snapshot, RiskSnapshot)
        assert snapshot.var_95 < 0
        assert snapshot.var_99 < snapshot.var_95
        assert snapshot.drawdown_state in ("normal", "caution", "halted")

    def test_generate_with_empty_returns(self):
        generator = RiskReportGenerator()
        snapshot = generator.generate()
        assert isinstance(snapshot, RiskSnapshot)
        assert snapshot.var_95 != 0.0


# =========================================================================
# PositioningDataFetcher tests
# =========================================================================


class TestPositioningDataFetcher:
    def test_fetch_returns_snapshot(self, tmp_path):
        fetcher = PositioningDataFetcher(oi_state_file=tmp_path / "oi_state.json")
        snapshot = fetcher.fetch()
        assert isinstance(snapshot, PositioningSnapshot)
        assert snapshot.cot_regime == "neutral"
        assert snapshot.etf_flow_momentum in ("accumulating", "distributing", "stable")
        assert snapshot.open_interest_change_pct == 0.0

    def test_fetch_open_interest_first_observation_returns_zero(self, tmp_path):
        state_file = tmp_path / "oi_state.json"
        fetcher = PositioningDataFetcher(oi_state_file=state_file)
        with patch("yfinance.Ticker") as mock_ticker:
            mock_ticker.return_value.get_info.return_value = {"openInterest": 298095}
            result = fetcher._fetch_open_interest()
        assert result == {"change_pct": 0.0}
        assert state_file.exists()
        saved = json.loads(state_file.read_text(encoding="utf-8"))
        assert saved["open_interest"] == 298095.0

    def test_fetch_open_interest_second_observation_returns_change_pct(self, tmp_path):
        state_file = tmp_path / "oi_state.json"
        state_file.write_text(
            json.dumps(
                {"timestamp": "2026-08-07T00:00:00+00:00", "open_interest": 290000.0}
            ),
            encoding="utf-8",
        )
        fetcher = PositioningDataFetcher(oi_state_file=state_file)
        with patch("yfinance.Ticker") as mock_ticker:
            mock_ticker.return_value.get_info.return_value = {"openInterest": 297155}
            result = fetcher._fetch_open_interest()
        expected = round((297155.0 - 290000.0) / 290000.0 * 100.0, 2)
        assert result == {"change_pct": expected}
        saved = json.loads(state_file.read_text(encoding="utf-8"))
        assert saved["open_interest"] == 297155.0

    def test_fetch_open_interest_unavailable_falls_back(self, tmp_path):
        state_file = tmp_path / "oi_state.json"
        state_file.write_text(
            json.dumps(
                {"timestamp": "2026-08-07T00:00:00+00:00", "open_interest": 290000.0}
            ),
            encoding="utf-8",
        )
        fetcher = PositioningDataFetcher(oi_state_file=state_file)
        with patch("yfinance.Ticker") as mock_ticker:
            mock_ticker.return_value.get_info.return_value = {}
            result = fetcher._fetch_open_interest()
        assert result == {"change_pct": 0.0}
        saved = json.loads(state_file.read_text(encoding="utf-8"))
        assert saved["open_interest"] == 290000.0

    def test_fetch_open_interest_exception_falls_back(self, tmp_path):
        state_file = tmp_path / "oi_state.json"
        state_file.write_text(
            json.dumps(
                {"timestamp": "2026-08-07T00:00:00+00:00", "open_interest": 290000.0}
            ),
            encoding="utf-8",
        )
        fetcher = PositioningDataFetcher(oi_state_file=state_file)
        with patch("yfinance.Ticker", side_effect=RuntimeError("network down")):
            result = fetcher._fetch_open_interest()
        assert result == {"change_pct": 0.0}
        saved = json.loads(state_file.read_text(encoding="utf-8"))
        assert saved["open_interest"] == 290000.0

    def test_fetch_open_interest_malformed_state_does_not_crash(self, tmp_path):
        state_file = tmp_path / "oi_state.json"
        state_file.write_text("{not valid json", encoding="utf-8")
        fetcher = PositioningDataFetcher(oi_state_file=state_file)
        with patch("yfinance.Ticker") as mock_ticker:
            mock_ticker.return_value.get_info.return_value = {"openInterest": 298095}
            result = fetcher._fetch_open_interest()
        assert result == {"change_pct": 0.0}
        saved = json.loads(state_file.read_text(encoding="utf-8"))
        assert saved["open_interest"] == 298095.0

    def test_fetch_open_interest_invalid_previous_state_ignored(self, tmp_path):
        state_file = tmp_path / "oi_state.json"
        state_file.write_text(
            json.dumps({"timestamp": "...", "open_interest": -10}), encoding="utf-8"
        )
        fetcher = PositioningDataFetcher(oi_state_file=state_file)
        with patch("yfinance.Ticker") as mock_ticker:
            mock_ticker.return_value.get_info.return_value = {"openInterest": 298095}
            result = fetcher._fetch_open_interest()
        assert result == {"change_pct": 0.0}

    def test_fetch_open_interest_never_uses_volume(self, tmp_path):
        state_file = tmp_path / "oi_state.json"
        state_file.write_text(
            json.dumps(
                {"timestamp": "2026-08-07T00:00:00+00:00", "open_interest": 290000.0}
            ),
            encoding="utf-8",
        )
        fetcher = PositioningDataFetcher(oi_state_file=state_file)
        with patch("yfinance.Ticker") as mock_ticker:
            mock_ticker.return_value.get_info.return_value = {
                "openInterest": 297155,
                "volume": 999999999,
            }
            result = fetcher._fetch_open_interest()
        expected = round((297155.0 - 290000.0) / 290000.0 * 100.0, 2)
        assert result == {"change_pct": expected}
        assert expected != round((999999999.0 - 290000.0) / 290000.0 * 100.0, 2)


# =========================================================================
# AnomalyDetectionEngine tests
# =========================================================================


class TestAnomalyDetectionEngine:
    def test_no_anomalies_with_small_moves(self):
        changes = [
            OvernightPriceChange("XAU/USD", 1900, 1901, 0.05, 0.3, "APAC"),
            OvernightPriceChange("DXY", 100, 100.1, 0.1, 0.4, "APAC"),
        ]
        engine = AnomalyDetectionEngine()
        flags = engine.detect(changes)
        two_sigma = [f for f in flags if f.anomaly_type == "two_sigma_move"]
        assert len(two_sigma) == 0

    def test_detects_two_sigma_move(self):
        changes = [
            OvernightPriceChange("XAU/USD", 1900, 1950, 2.63, 2.5, "APAC"),
        ]
        engine = AnomalyDetectionEngine()
        flags = engine.detect(changes)
        assert any(f.anomaly_type == "two_sigma_move" for f in flags)

    def test_detects_high_sigma_move(self):
        changes = [
            OvernightPriceChange("XAU/USD", 1900, 2000, 5.26, 4.0, "APAC"),
        ]
        engine = AnomalyDetectionEngine()
        flags = engine.detect(changes)
        assert any(f.anomaly_type == "high_sigma_move" for f in flags)

    def test_detects_gold_dxy_template_violation(self):
        changes = [
            OvernightPriceChange("XAU/USD", 1900, 1920, 1.05, 1.0, "APAC"),
            OvernightPriceChange("DXY", 100, 101, 1.0, 0.8, "APAC"),
            OvernightPriceChange("US10Y Real Yield", 0.5, 0.55, 10.0, 1.0, "APAC"),
            OvernightPriceChange("S&P 500 Futures", 4500, 4520, 0.44, 0.5, "APAC"),
        ]
        engine = AnomalyDetectionEngine()
        flags = engine.detect(changes)
        violations = [f for f in flags if f.anomaly_type == "template_violation"]
        assert len(violations) >= 1


# =========================================================================
# WatchlistBuilder tests
# =========================================================================


class TestWatchlistBuilder:
    def test_build_returns_default_events(self):
        builder = WatchlistBuilder()
        items = builder.build()
        assert len(items) > 0
        for item in items:
            assert isinstance(item, WatchlistItem)
        assert items[0].priority == "Tier 1"

    def test_build_sorts_by_priority(self):
        builder = WatchlistBuilder()
        items = builder.build()
        priorities = [i.priority for i in items]
        assert priorities.index("Tier 1") < priorities.index("Tier 2")


# =========================================================================
# PreMarketBriefingAssembler tests
# =========================================================================


class TestPreMarketBriefingAssembler:
    def test_assemble_returns_briefing(self):
        assembler = PreMarketBriefingAssembler(
            regime="NORMAL_GROWTH",
            regime_confidence=0.85,
        )
        briefing = assembler.assemble()
        assert isinstance(briefing, PreMarketBriefing)
        assert briefing.regime == "NORMAL_GROWTH"
        assert briefing.regime_confidence == 0.85
        assert briefing.briefing_id.startswith("premarket_")

    def test_assemble_includes_all_sections(self):
        assembler = PreMarketBriefingAssembler(
            regime="INFLATIONARY",
            regime_confidence=0.72,
        )
        briefing = assembler.assemble(
            daily_pnl=1500.0,
            unrealized_pnl=-200.0,
            exposure=50000.0,
            var_utilization_pct=45.0,
        )
        assert briefing.risk_snapshot is not None
        assert briefing.positioning_snapshot is not None
        assert isinstance(briefing.overnight_changes, tuple)
        assert isinstance(briefing.news_items, tuple)
        assert isinstance(briefing.anomaly_flags, tuple)
        assert isinstance(briefing.watchlist, tuple)

    def test_assemble_with_custom_briefing_id(self):
        assembler = PreMarketBriefingAssembler()
        briefing = assembler.assemble(briefing_id="custom_001")
        assert briefing.briefing_id == "custom_001"

    def test_json_roundtrip_via_assembler(self):
        assembler = PreMarketBriefingAssembler(
            regime="NORMAL_GROWTH",
            regime_confidence=0.85,
        )
        briefing = assembler.assemble()
        serialized = json.dumps(briefing.to_dict())
        restored = PreMarketBriefing.from_dict(json.loads(serialized))
        assert restored.regime == briefing.regime
        assert restored.regime_confidence == briefing.regime_confidence


# =========================================================================
# Integration test: orchestration stage
# =========================================================================


def test_pre_market_scan_stage():
    from orchestration.stages import _pre_market_scan

    params = {
        "regime": "NORMAL_GROWTH",
        "regime_confidence": 0.85,
        "pre_market_session": "APAC",
    }
    results: dict = {}
    result = _pre_market_scan(params, results)
    assert isinstance(result, PreMarketBriefing)
    assert result.regime == "NORMAL_GROWTH"
    assert result.briefing_id.startswith("premarket_")

