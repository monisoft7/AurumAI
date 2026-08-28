"""Sprint 058 -- News Intelligence Pipeline tests.

Covers the 18 required verification points for the news path repair:
silent-loss elimination, news->evidence wiring with provenance,
gold-relevance/directional semantics, determinism, no-lookahead, DAG
integration and non-regression of decision/confidence, the Technical
Desk, the 057 reference-price flow and outcome tracking.
"""

from __future__ import annotations

import datetime as _dt
import json
import sys
import types
from dataclasses import replace
from unittest.mock import MagicMock

import pytest

from news.intelligence import (
    DIRECTION_BEARISH,
    DIRECTION_BULLISH,
    DIRECTION_UNKNOWN,
    EVENT_CB_GOLD_DEMAND,
    EVENT_CPI_INFLATION,
    EVENT_FED_FOMC,
    EVENT_GEOPOLITICAL,
    EVENT_GENERIC_MACRO,
    GOLD_RELEVANCE_HIGH,
    GOLD_RELEVANCE_MEDIUM,
    STATUS_EMPTY,
    STATUS_OK,
    STATUS_UNAVAILABLE,
    article_id,
    classify_article,
    content_hash,
    run_news_intelligence,
)
from news.models import NewsArticle
from orchestration.dag import _topological_levels
from orchestration.orchestrator import InstitutionalOrchestrator
from orchestration.stages import (
    _ingest_news,
    _pre_market_scan,
    _signal_assessment,
)
from pre_market.contracts import NewsItem, OvernightPriceChange, PreMarketBriefing
from pre_market.risk_reporter import RiskReportGenerator
from pre_market.positioning import PositioningDataFetcher


NOW = _dt.datetime(2026, 8, 25, 12, 0, tzinfo=_dt.timezone.utc)
AS_OF = "2026-08-25T00:00:00+00:00"
# Base publication time safely BEFORE as_of so offsets stay inside the window.
PAST = _dt.datetime(2026, 8, 24, 12, 0, tzinfo=_dt.timezone.utc)


def _article(
    title: str,
    *,
    source: str = "TestWire",
    url: str | None = None,
    published: _dt.datetime | None = None,
    summary: str = "",
):
    from news.models import Topic

    return NewsArticle(
        title=title,
        source=source,
        url=url or f"https://example.com/{content_hash(title)[:12]}",
        published=published or PAST,
        summary=summary,
        topics=(Topic.GOLD,),
    )


def _payload(articles, **kwargs):
    return run_news_intelligence(
        data_source=lambda: articles,
        as_of=kwargs.pop("as_of", AS_OF),
        now=kwargs.pop("now", NOW),
        **kwargs,
    )


# ===========================================================================
# 1-3. Availability semantics (ok / empty / NLP dependency missing)
# ===========================================================================


class TestAvailabilitySemantics:
    def test_1_news_available_status_ok_with_items(self) -> None:
        payload = _payload([_article("Fed holds rates steady")])
        assert payload["status"] == STATUS_OK
        assert payload["reason"] == ""
        assert len(payload["items"]) >= 1

    def test_2_news_genuinely_empty_is_distinct_from_unavailable(self) -> None:
        empty = _payload([])
        assert empty["status"] == STATUS_EMPTY
        assert empty["reason"] == "no_articles_returned"
        assert empty["items"] == []

        def _boom() -> list:
            raise ConnectionError("network down")

        unavailable = run_news_intelligence(data_source=_boom, now=NOW)
        assert unavailable["status"] == STATUS_UNAVAILABLE
        assert "data_source_failed" in unavailable["reason"]
        # The two states must never be conflated.
        assert empty["status"] != unavailable["status"]

    def test_3_nlp_dependency_missing_keeps_articles_unknown_sentiment(self) -> None:
        analyzer = MagicMock()
        analyzer.analyze_batch.side_effect = ImportError(
            "transformers is required for NewsSentimentAnalyzer"
        )
        payload = _payload([_article("Gold rallies on inflation data")], sentiment_analyzer=analyzer)
        assert payload["status"] == STATUS_OK
        assert payload["sentiment_status"] == "unavailable_dependency_missing"
        item = payload["items"][0]
        assert item["sentiment_label"] == "unknown"
        assert item["sentiment_confidence"] == 0.0
        assert item["sentiment_available"] is False

    def test_no_sentiment_analyzer_never_invents_polarity(self) -> None:
        payload = _payload([_article("Dollar slides versus majors")])
        assert payload["sentiment_status"] == "skipped_none"
        assert all(it["sentiment_available"] is False for it in payload["items"])
        assert all(it["sentiment_label"] == "unknown" for it in payload["items"])


# ===========================================================================
# 4/6/10. Malformed, deterministic ids, duplicates
# ===========================================================================


class TestNormalizationAndIdentity:
    def test_4_malformed_article_skipped_and_counted(self) -> None:
        malformed = NewsArticle(title="", source="X", url="https://ex.com/m")
        whitespace = NewsArticle(title="   ", source="X", url="https://ex.com/w")
        good = _article("Valid gold headline")
        payload = _payload([malformed, whitespace, good])
        assert payload["status"] == STATUS_OK
        assert payload["malformed_count"] == 2
        assert len(payload["items"]) == 1

    def test_6_deterministic_content_id_stable_and_discriminating(self) -> None:
        a1 = article_id("Reuters", "Fed cuts rates", "2026-08-20T00:00:00+00:00")
        a2 = article_id("Reuters", "Fed cuts rates", "2026-08-20T00:00:00+00:00")
        other = article_id("Reuters", "Fed holds rates", "2026-08-20T00:00:00+00:00")
        other_time = article_id("Reuters", "Fed cuts rates", "2026-08-21T00:00:00+00:00")
        assert a1 == a2
        assert a1 != other
        assert a1 != other_time
        assert a1.startswith("nws_")
        # content hash independent of process randomization
        assert content_hash("A b", "c") == content_hash("A b", "c")

    def test_10_duplicate_article_handling(self) -> None:
        first = _article("Central bank gold buying hits record", url="https://a.com/1")
        dup = _article(
            "Central bank gold buying hits record",
            source="Mirror",
            url="https://b.com/2",
            published=PAST + _dt.timedelta(hours=1),
        )
        payload = _payload([first, dup])
        assert payload["status"] == STATUS_OK
        assert payload["duplicate_count"] == 1
        original = next(i for i in payload["items"] if not i["duplicate_of"])
        duplicate = next(i for i in payload["items"] if i["duplicate_of"])
        assert duplicate["duplicate_of"] == original["article_id"]
        assert original["novelty"] == 1.0
        assert duplicate["novelty"] == 0.0
        assert duplicate["content_hash"] == original["content_hash"]


# ===========================================================================
# 5/7/8. Semantics + provenance payloads
# ===========================================================================


class TestClassificationSemantics:
    def test_7_directional_semantics_no_name_based_gold_bias(self) -> None:
        # Correction 051: an asset name in a headline never resolves a gold
        # direction on its own.
        cls = classify_article("USD strengthened after hawkish Fed remarks")
        assert cls["directional_implication"] == DIRECTION_UNKNOWN
        cls = classify_article("Dollar strengthens as yields climb")
        assert cls["directional_implication"] == DIRECTION_UNKNOWN
        # Unambiguous event semantics only.
        cls = classify_article("Central bank gold purchases increase reserves")
        assert cls["directional_implication"] == DIRECTION_BULLISH
        assert cls["direction_basis"] == "cb_gold_demand_increase"
        cls = classify_article("Conflict escalates as sanctions expand")
        assert cls["directional_implication"] == DIRECTION_BULLISH
        assert cls["direction_basis"] == "safe_haven_escalation"
        cls = classify_article("Ceasefire agreed; peace deal signed")
        assert cls["directional_implication"] == DIRECTION_BEARISH
        # Generic macro stays unknown.
        cls = classify_article("Retail sales miss expectations slightly")
        assert cls["event_type"] == EVENT_GENERIC_MACRO
        assert cls["directional_implication"] == DIRECTION_UNKNOWN

    def test_event_family_classification(self) -> None:
        assert classify_article("FOMC minutes reveal rate debate")["event_type"] == EVENT_FED_FOMC
        assert (
            classify_article("CPI inflation cooled to 2.4 percent")["event_type"]
            == EVENT_CPI_INFLATION
        )
        assert classify_article("War escalates in region")["event_type"] == EVENT_GEOPOLITICAL
        assert (
            classify_article("Central bank gold buying accelerates")["event_type"]
            == EVENT_CB_GOLD_DEMAND
        )

    def test_8_gold_relevance_mapping(self) -> None:
        assert classify_article("Central bank gold buying")["gold_relevance"] == GOLD_RELEVANCE_HIGH
        assert classify_article("Gold price jumps to record")["gold_relevance"] == GOLD_RELEVANCE_HIGH
        assert classify_article("FOMC statement parsed by markets")["gold_relevance"] == GOLD_RELEVANCE_MEDIUM
        assert classify_article("CPI print beats forecast")["gold_relevance"] == GOLD_RELEVANCE_MEDIUM
        low = classify_article("Risk-off tone dominates Asian session")
        assert low["gold_relevance"] in ("low", "medium")
        generic = classify_article("Corporate earnings season begins")
        assert generic["gold_relevance"] == "low"

    def test_classification_confidence_bounded_and_deterministic(self) -> None:
        one = classify_article("FOMC minutes released today")
        two = classify_article("FOMC minutes released; fed funds path debated today")
        assert 0.0 <= one["confidence"] <= 0.9
        assert two["confidence"] > one["confidence"]
        assert one == classify_article("FOMC minutes released today")


class TestProvenancePayload:
    def test_5_provenance_fields_present_on_every_item(self) -> None:
        payload = _payload(
            [
                _article(
                    "Fed signals pause",
                    url="https://wire.example/fed",
                    published=PAST + _dt.timedelta(hours=2),
                )
            ]
        )
        item = payload["items"][0]
        for field in (
            "article_id",
            "content_hash",
            "source",
            "url",
            "published_at",
            "ingested_at",
            "event_type",
            "gold_relevance",
            "directional_implication",
            "confidence",
            "novelty",
            "sentiment_label",
        ):
            assert field in item, field
        assert item["url"] == "https://wire.example/fed"
        assert item["published_at"] == "2026-08-24T14:00:00+00:00"
        assert item["ingested_at"] == NOW.isoformat()


# ===========================================================================
# No lookahead / historical as-of
# ===========================================================================


class TestNoLookahead:
    def test_11_future_articles_excluded_and_counted(self) -> None:
        past = _article("Past gold headline", published=NOW - _dt.timedelta(days=1))
        future = _article("Future gold headline", published=NOW + _dt.timedelta(days=1))
        payload = _payload([past, future], as_of=AS_OF)
        headlines = [i["headline"] for i in payload["items"]]
        assert "Past gold headline" in headlines
        assert "Future gold headline" not in headlines
        assert payload["excluded_after_asof_count"] == 1

    def test_12_historical_as_of_window_respected(self) -> None:
        inside = _article(
            "Inside window headline", published=PAST - _dt.timedelta(hours=6)
        )
        also_inside = _article(
            "Older but valid headline", published=PAST - _dt.timedelta(days=2)
        )
        payload = _payload([inside, also_inside], as_of=AS_OF)
        headlines = [i["headline"] for i in payload["items"]]
        assert set(headlines) == {"Inside window headline", "Older but valid headline"}
        # items are ordered newest-first (undated last)
        assert headlines[0] == "Inside window headline"

    def test_publication_after_decision_time_never_enters_payload(self) -> None:
        decision_time = "2026-08-24T14:00:00+00:00"
        late = _article(
            "Post-decision leak", published=PAST + _dt.timedelta(hours=6)
        )
        early = _article(
            "Pre-decision context", published=PAST - _dt.timedelta(days=1)
        )
        payload = _payload([late, early], as_of=decision_time)
        headlines = [i["headline"] for i in payload["items"]]
        assert "Post-decision leak" not in headlines
        assert payload["excluded_after_asof_count"] == 1


# ===========================================================================
# Stage + W3/W5/W6 wiring
# ===========================================================================


def _stage_ingest(params_overrides=None) -> dict:
    params = {
        "_news_data_source": lambda: [
            _article(
                "Central bank gold buying hits record",
                url="https://wgc.example/record",
                published=PAST,
            ),
            _article("USD strengthened against basket", url="https://fx.example/usd"),
        ],
        "_news_now": NOW,
        "news_as_of": AS_OF,
    }
    params.update(params_overrides or {})
    return _ingest_news(params, {})


class TestStageIngestNews:
    def test_stage_returns_explicit_payload(self) -> None:
        payload = _stage_ingest()
        assert payload["status"] == STATUS_OK
        assert len(payload["items"]) == 2
        assert payload["fomc_status"] in ("ok", "unavailable")
        assert isinstance(payload["fomc_events"], list)

    def test_stage_failure_is_explicit_not_empty(self) -> None:
        def boom():
            raise RuntimeError("collector exploded")

        payload = _stage_ingest({"_news_data_source": boom})
        assert payload["status"] == STATUS_UNAVAILABLE
        assert "data_source_failed" in payload["reason"]
        assert payload["items"] == []

    def test_fomc_channel_separate_from_news_items(self) -> None:
        payload = _stage_ingest()
        for event in payload["fomc_events"]:
            assert event["event_type"] == "FOMC"
            assert set(event) <= {
                "event_type", "start_date", "end_date", "is_two_day",
                "has_press_conference", "statement_time", "minutes_release_date",
            }
        assert all(i["article_id"].startswith("nws_") for i in payload["items"])
        # fomc events never leak into news items
        assert all("start_date" not in i for i in payload["items"])


def _only_narrative_changed(old, new) -> bool:
    """True when two observations differ only through the pre-existing
    narrative_fit channel (news headlines feed the narrative scorer)."""
    old_map = {c.criterion: c for c in old.evidence}
    new_map = {c.criterion: c for c in new.evidence}
    if set(old_map) != set(new_map):
        return False
    for name, c_old in old_map.items():
        c_new = new_map[name]
        if name == "narrative_fit":
            continue
        if c_new.to_dict() != c_old.to_dict():
            return False
    return True


def _briefing(news_items, metadata_extra=None) -> PreMarketBriefing:
    return PreMarketBriefing(
        briefing_id="premarket_test058",
        timestamp=NOW.isoformat(),
        regime="EXPANSION",
        regime_confidence=0.7,
        overnight_changes=(
            OvernightPriceChange(
                instrument="DXY",
                previous_close=103.0,
                current_price=103.5,
                change_pct=0.485,
                change_sigma=1.0,
            ),
        ),
        news_items=tuple(news_items),
        risk_snapshot=RiskReportGenerator().generate(),
        positioning_snapshot=PositioningDataFetcher().fetch(),
        anomaly_flags=(),
        watchlist=(),
        metadata={"news_source_path": "ingest_news_stage", **(metadata_extra or {})},
    )


class TestNewsToEvidenceWiring:
    def test_9_evidence_propagation_with_provenance(self) -> None:
        from evidence_collection.collector import EvidenceCollector
        from signal_assessment.assembler import SignalAssessmentAssembler

        stage_payload = _stage_ingest()
        from news.intelligence import to_pre_market_news_items

        items = to_pre_market_news_items(stage_payload)
        briefing = _briefing(items)
        assessment = SignalAssessmentAssembler(regime="EXPANSION").assemble(briefing)

        news_obs = [o for o in assessment.observations if o.source == "news"]
        assert len(news_obs) == len(items)
        registry = assessment.metadata["news_provenance"]
        assert set(registry) == {o.observation_id for o in news_obs}

        collection = EvidenceCollector().collect(assessment, regime_weight=0.8)
        news_evidence = [e for e in collection.items if e.source_label == "news"]
        assert news_evidence, "news observations must reach EvidenceCollection"
        for ev in news_evidence:
            prov = ev.metadata["news"]
            assert prov["article_id"].startswith("nws_")
            assert "content_hash" in prov
            assert "published_at" in prov
            assert "ingested_at" in prov
            assert "event_type" in prov
            assert "gold_relevance" in prov
            assert "directional_implication" in prov
            assert "confidence" in prov
        assert collection.metadata["news_intelligence"]["article_count"] == len(items)

    def test_news_evidence_traceable_to_thesis_support_sets(self) -> None:
        """News provenance survives into W7 reasoning inputs via evidence."""
        from collections import Counter

        from evidence_collection.collector import EvidenceCollector
        from signal_assessment.assembler import SignalAssessmentAssembler

        stage_payload = _stage_ingest({"news_max_articles": 20})
        from news.intelligence import to_pre_market_news_items

        items = to_pre_market_news_items(stage_payload)
        briefing = _briefing(items * 6)  # enough breadth for non-noise labels
        assessment = SignalAssessmentAssembler(regime="EXPANSION").assemble(briefing)
        collection = EvidenceCollector().collect(assessment, regime_weight=0.8)
        news_ids = {e.evidence_id for e in collection.items if e.source_label == "news"}
        assert news_ids
        # every news evidence carries its source article id
        for e in collection.items:
            if e.evidence_id in news_ids:
                assert e.metadata["news"]["article_id"].startswith("nws_")

    def test_deterministic_observation_ids_across_calls(self) -> None:
        from signal_assessment.assembler import SignalAssessmentAssembler

        item = NewsItem(
            headline="Fed holds rates",
            source="R",
            published="2026-08-25T08:00:00+00:00",
            sentiment_label="unknown",
            sentiment_confidence=0.0,
            relevance_score=0.35,
        )
        b1 = _briefing([item])
        b2 = _briefing([item])
        a1 = SignalAssessmentAssembler(regime="E").assemble(b1)
        a2 = SignalAssessmentAssembler(regime="E").assemble(b2)
        id1 = [o.observation_id for o in a1.observations if o.source == "news"][0]
        id2 = [o.observation_id for o in a2.observations if o.source == "news"][0]
        assert id1 == id2
        assert id1.startswith("obs_news_")


# ===========================================================================
# 13. DAG integration
# ===========================================================================


class TestDagIntegration:
    def test_13_pre_market_scan_depends_on_ingest_news(self) -> None:
        orch = InstitutionalOrchestrator.with_default_pipeline()
        deps = orch._jobs["pre_market_scan"].dependencies
        assert "ingest_news" in deps
        levels = _topological_levels(orch._jobs)
        level_of = {jid: i for i, level in enumerate(levels) for jid in level}
        assert level_of["ingest_news"] < level_of["pre_market_scan"]

    def test_build_context_no_longer_declares_fake_dependency(self) -> None:
        orch = InstitutionalOrchestrator.with_default_pipeline()
        assert "ingest_news" not in orch._jobs["build_context"].dependencies
        assert "ingest_news" not in orch._jobs["technical_research"].dependencies

    def test_topology_remains_valid_and_level0_stable(self) -> None:
        orch = InstitutionalOrchestrator.with_default_pipeline()
        levels = _topological_levels(orch._jobs)
        all_jobs = {jid for level in levels for jid in level}
        assert all_jobs == set(orch._jobs.keys())
        level0 = set(levels[0])
        assert level0 == {"ingest_event", "ingest_news"}

    def test_stage_consumes_ingest_news_output_without_refetch(self) -> None:
        """pre_market_scan must consume stage output, not re-collect."""
        from news.intelligence import to_pre_market_news_items

        stage_payload = _stage_ingest()
        items = to_pre_market_news_items(stage_payload)
        results = {"regime_diagnosis": {"regime": "EXPANSION", "confidence": 0.7},
                   "ingest_news": stage_payload}
        params = {"briefing_id": "premarket_wired"}
        result = _pre_market_scan(params, results)
        assert result.metadata["news_source_path"] == "ingest_news_stage"
        assert [n.headline for n in result.news_items] == [n.headline for n in items]

    def test_unavailable_stage_result_not_masked_by_refetch(self) -> None:
        results = {
            "regime_diagnosis": {"regime": "EXPANSION", "confidence": 0.7},
            "ingest_news": {
                "status": STATUS_UNAVAILABLE,
                "reason": "data_source_failed: ConnectionError",
                "items": [],
            },
        }
        result = _pre_market_scan({"briefing_id": "premarket_unavail"}, results)
        assert result.metadata["news_source_path"] == "ingest_news_stage"
        assert result.news_items == ()

    def test_legacy_internal_path_only_when_no_stage_result(self) -> None:
        collector = MagicMock()
        collector.collect.return_value = []
        ingestion = MagicMock()
        ingestion.ingest_with_status.return_value = ([], "no_articles")
        from pre_market.briefing_assembler import PreMarketBriefingAssembler

        assembler = PreMarketBriefingAssembler(news_ingestion=ingestion)
        briefing = assembler.assemble(briefing_id="premarket_solo")
        assert briefing.metadata["news_source_path"].startswith("legacy_internal_ingestion:")
        ingestion.ingest_with_status.assert_called_once()


# ===========================================================================
# 14/15. Non-regression when no news / unchanged decisions
# ===========================================================================


class TestNoRegression:
    def _assessment_for(self, news_items):
        from signal_assessment.assembler import SignalAssessmentAssembler

        return SignalAssessmentAssembler(regime="EXPANSION").assemble(
            _briefing(news_items)
        )
    def test_14_no_news_identical_to_legacy_shape(self) -> None:
        baseline = self._assessment_for([])
        assert all(o.source != "news" for o in baseline.observations)
        assert "news_provenance" not in baseline.metadata
        assert baseline.metadata.get("news_source_path") == "ingest_news_stage"

    def test_15_news_presence_changes_only_legitimate_paths(self) -> None:
        from news.intelligence import to_pre_market_news_items

        stage_payload = _stage_ingest()
        items = to_pre_market_news_items(stage_payload)
        without = self._assessment_for([])
        with_news = self._assessment_for(items)

        non_news_without = [
            o for o in without.observations if o.source != "news"
        ]
        non_news_with = {
            o.observation_id: o
            for o in with_news.observations
            if o.source != "news"
        }
        # same non-news observation identities, unchanged core numbers
        assert len(non_news_without) == len(non_news_with)
        for o in non_news_without:
            twin = non_news_with[o.observation_id]
            assert twin.classification == o.classification or _only_narrative_changed(o, twin)
            assert twin.confidence == o.confidence or _only_narrative_changed(o, twin)
            # every criterion except narrative_fit must be byte-identical
            base = {c.criterion: c.to_dict() for c in o.evidence}
            new = {c.criterion: c.to_dict() for c in twin.evidence}
            assert set(base) == set(new)
            for name, d in base.items():
                if name != "narrative_fit":
                    assert new[name] == d
        added = [
            o for o in with_news.observations
            if o.source not in {"overnight_price", "positioning", "anomaly_flag"}
        ]
        assert {o.source for o in added} <= {"news"}

    def test_news_evidence_keeps_correction_051_neutral_bias(self) -> None:
        from evidence_collection.collector import EvidenceCollector

        from news.intelligence import to_pre_market_news_items
        from signal_assessment.assembler import SignalAssessmentAssembler

        items = to_pre_market_news_items(_stage_ingest())
        briefing = _briefing(items)
        assessment = SignalAssessmentAssembler(regime="EXPANSION").assemble(briefing)
        collection = EvidenceCollector().collect(assessment, regime_weight=0.8)
        for e in collection.items:
            if e.source_label == "news":
                assert e.bias == "neutral"


# ===========================================================================
# 16-18. Isolation guarantees
# ===========================================================================


class TestIsolationGuarantees:
    def test_16_technical_desk_remains_isolated_from_news(self) -> None:
        orch = InstitutionalOrchestrator.with_default_pipeline()
        tech = orch._jobs["technical_research"]
        assert tech.dependencies == ("build_legacy_pipeline",)
        consumers = [
            jid for jid, job in orch._jobs.items()
            if "technical_research" in job.dependencies
        ]
        # Final Hardening (Group F): the technical desk joined the research
        # layer via thesis_construction (non-scoring metadata context).  It
        # remains fully isolated from the NEWS path and from every
        # decision-scoring module.
        assert consumers == ["thesis_construction"]
        news_job = orch._jobs["ingest_news"]
        assert "technical_research" not in news_job.dependencies

    def test_technical_assessment_contract_has_no_news_fields(self) -> None:
        from technical.contracts import TechnicalAssessment

        fields = {f for f in TechnicalAssessment.__dataclass_fields__}
        assert not any("news" in f for f in fields)

    def test_17_reference_price_flow_unaffected(self) -> None:
        from trade_recommendation.reference_price import resolve_reference_price

        resolved, reason = resolve_reference_price(None)
        assert resolved is None
        assert reason

    def test_trade_recommendation_stage_imports_cleanly(self) -> None:
        from orchestration.stages import _trade_recommendation  # noqa: F401

        orch = InstitutionalOrchestrator.with_default_pipeline()
        assert "decision_engine" in orch._jobs["trade_recommendation"].dependencies

    def test_18_outcome_tracking_modules_unaffected(self) -> None:
        import execution.execution_engine  # noqa: F401
        import trade_recommendation.recommender  # noqa: F401

        from runtime_registry.registry import append_record  # noqa: F401

        orch = InstitutionalOrchestrator.with_default_pipeline()
        finalize_deps = orch._jobs["finalize"].dependencies
        # Final Hardening (Group D): trade_recommendation is a finalize
        # dependency -- the executable levels are part of the final artifact.
        assert set(finalize_deps) == {
            "risk_gate", "position_sizing", "forecast_confidence",
            "forecast_validation", "decision_engine",
            "trade_recommendation",
        }

    def test_finalize_attaches_news_payload_additively(self) -> None:
        from orchestration.stages import _finalize

        stage_payload = {"status": STATUS_EMPTY, "reason": "no_articles_returned",
                         "items": [], "fomc_events": []}
        results = {
            "build_context": {"current_regime": "EXPANSION"},
            "position_sizing": {},
            "ingest_news": stage_payload,
        }
        payload = _finalize({}, results)
        assert payload["news_intelligence"] == stage_payload

        legacy_results = {k: v for k, v in results.items() if k != "ingest_news"}
        legacy_payload = _finalize({}, legacy_results)
        assert "news_intelligence" not in legacy_payload


# ===========================================================================
# Default (live) RSS collection path -- the path with no injected
# data_source.  Baseline regression: ``NewsCollector`` was referenced
# undefined inside ``_collect_with_error_capture`` and crashed every
# run_daily / historical-replay ``ingest_news`` stage.  These tests pin the
# live path end-to-end with a stubbed feedparser (no network).
# ===========================================================================


class _FakeFeed:
    def __init__(self, entries=None, bozo=False, bozo_exception=None):
        self.entries = entries or []
        self.bozo = bozo
        self.bozo_exception = bozo_exception


def _entry(title="Gold price edges higher", link="https://news.example/g1",
           summary="bullion demand", published_parsed=None):
    return {
        "title": title,
        "link": link,
        "summary": summary,
        "published_parsed": published_parsed,
    }


@pytest.fixture
def fake_feedparser(monkeypatch):
    """Install a stub ``feedparser`` module and capture parsed URLs."""
    calls: list[str] = []

    def _parse(url):
        calls.append(url)
        return _FakeFeed(entries=[_entry()])

    module = types.SimpleNamespace(parse=_parse)
    monkeypatch.setitem(sys.modules, "feedparser", module)
    return calls


class TestDefaultRssCollectionPath:
    def test_default_path_collects_articles_with_provenance(self, fake_feedparser) -> None:
        payload = run_news_intelligence(now=NOW, as_of=AS_OF)
        assert payload["status"] == STATUS_OK
        assert payload["reason"] == ""
        assert payload["fetch_errors"] == []
        assert len(payload["items"]) == 1
        item = payload["items"][0]
        assert item["article_id"].startswith("nws_")
        assert item["content_hash"]
        assert len(fake_feedparser) >= 1

    def test_default_path_never_raises_name_error(self, fake_feedparser) -> None:
        # The baseline defect raised ``NameError: NewsCollector is not
        # defined`` from the default path; the callable must complete with
        # an explicit status whatever the collection outcome is.
        for _ in range(2):
            payload = run_news_intelligence(now=NOW, as_of=AS_OF)
            assert payload["status"] in (STATUS_OK, STATUS_EMPTY, STATUS_UNAVAILABLE)

    def test_default_path_total_network_failure_is_unavailable(self, monkeypatch) -> None:
        def _parse(url):
            raise OSError("network unreachable")

        monkeypatch.setitem(
            sys.modules, "feedparser", types.SimpleNamespace(parse=_parse)
        )
        payload = run_news_intelligence(now=NOW)
        assert payload["status"] == STATUS_UNAVAILABLE
        assert payload["reason"] == "feed_fetch_failed"
        assert payload["fetch_errors"], "per-feed errors must be recorded"
        assert payload["items"] == []

    def test_default_path_collector_crash_is_explicit_unavailable(self, monkeypatch) -> None:
        import news.intelligence as news_intel

        def _boom(collector):
            raise RuntimeError("collector exploded")

        monkeypatch.setattr(news_intel, "_collect_with_error_capture", _boom)
        payload = run_news_intelligence(now=NOW)
        assert payload["status"] == STATUS_UNAVAILABLE
        assert payload["reason"] == "collector_failed: RuntimeError"
        assert payload["items"] == []


class TestStageLiveNoLookahead:
    def test_stage_without_news_as_of_excludes_future_articles(self) -> None:
        """No explicit ``news_as_of``: the stage gates on ``_news_now``."""
        params = {
            "_news_data_source": lambda: [
                _article("Past gold headline", published=NOW - _dt.timedelta(days=1)),
                _article("Future gold headline", published=NOW + _dt.timedelta(days=1)),
            ],
            "_news_now": NOW,
        }
        payload = _ingest_news(params, {})
        headlines = [i["headline"] for i in payload["items"]]
        assert "Past gold headline" in headlines
        assert "Future gold headline" not in headlines
        assert payload["excluded_after_asof_count"] == 1
        assert payload["status"] == STATUS_OK
