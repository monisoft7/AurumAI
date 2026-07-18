"""Tests for the NewsCollector and news models."""

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from news.models import DEFAULT_RSS_FEEDS, NewsArticle, Topic
from news.news_collector import NewsCollector


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------


class TestNewsArticle:

    def test_is_frozen(self) -> None:
        a = NewsArticle(title="t", source="s", url="u")
        with pytest.raises((AttributeError, TypeError)):
            a.title = "x"

    def test_defaults(self) -> None:
        a = NewsArticle(title="t", source="s", url="u")
        assert a.summary == ""
        assert a.topics == ()
        assert a.published is None

    def test_with_all_fields(self) -> None:
        dt = datetime(2024, 1, 10, tzinfo=timezone.utc)
        a = NewsArticle(
            title="Fed Hikes",
            source="Reuters",
            url="https://example.com/fed",
            published=dt,
            summary="The Fed raised rates.",
            topics=(Topic.FED, Topic.INTEREST_RATES),
        )
        assert a.title == "Fed Hikes"
        assert a.published == dt


# ---------------------------------------------------------------------------
# Topic enum
# ---------------------------------------------------------------------------


class TestTopicEnum:

    def test_has_expected_values(self) -> None:
        assert Topic.FED.value == "fed"
        assert Topic.INFLATION.value == "inflation"
        assert Topic.INTEREST_RATES.value == "interest_rates"
        assert Topic.GOLD.value == "gold"
        assert Topic.USD.value == "usd"
        assert Topic.TREASURY.value == "treasury"
        assert Topic.GEOPOLITICS.value == "geopolitics"


class TestDefaultRSSFeeds:

    def test_all_topics_have_feeds(self) -> None:
        for topic in Topic:
            feeds = DEFAULT_RSS_FEEDS.get(topic)
            assert feeds is not None
            assert len(feeds) >= 1
            for url in feeds:
                assert url.startswith("https://")


# ---------------------------------------------------------------------------
# Deterministic collection via data_source
# ---------------------------------------------------------------------------


class TestCollectWithDataSource:

    def test_returns_articles_from_data_source(self) -> None:
        expected = [
            NewsArticle(title="A", source="S", url="https://example.com/a"),
            NewsArticle(title="B", source="S", url="https://example.com/b"),
        ]
        collector = NewsCollector(data_source=lambda: expected)
        results = collector.collect()
        assert results == expected

    def test_empty_data_source(self) -> None:
        collector = NewsCollector(data_source=lambda: [])
        results = collector.collect()
        assert results == []


# ---------------------------------------------------------------------------
# Deduplication
# ---------------------------------------------------------------------------


class TestDeduplication:

    def test_deduplicates_by_url(self) -> None:
        articles = [
            NewsArticle(title="A", source="S", url="https://example.com/a"),
            NewsArticle(title="B", source="S", url="https://example.com/a"),
        ]
        collector = NewsCollector(data_source=lambda: articles)
        results = collector.collect()
        assert len(results) == 1
        assert results[0].title == "A"

    def test_different_urls_no_dedup(self) -> None:
        articles = [
            NewsArticle(title="A", source="S", url="https://example.com/a"),
            NewsArticle(title="B", source="S", url="https://example.com/b"),
        ]
        collector = NewsCollector(data_source=lambda: articles)
        results = collector.collect()
        assert len(results) == 2


# ---------------------------------------------------------------------------
# URL normalization
# ---------------------------------------------------------------------------


class TestURLNormalization:

    def test_strips_query_params(self) -> None:
        result = NewsCollector._normalize_url(
            "https://example.com/path?q=1&r=2#frag"
        )
        assert result == "https://example.com/path"

    def test_returns_empty_for_invalid(self) -> None:
        assert NewsCollector._normalize_url("") == ""
        assert NewsCollector._normalize_url("not-a-url") == ""


# ---------------------------------------------------------------------------
# Entry to article conversion
# ---------------------------------------------------------------------------


class TestEntryToArticle:

    def test_converts_feed_entry(self) -> None:
        entry = {
            "title": "Test Article",
            "link": "https://example.com/article",
            "summary": "Summary text",
            "source": {"title": "TestSource"},
            "published_parsed": (2024, 1, 10, 12, 0, 0, 2, 10, 0),
        }
        article = NewsCollector._entry_to_article(entry, Topic.FED)
        assert article.title == "Test Article"
        assert article.url == "https://example.com/article"
        assert article.topics == (Topic.FED,)
        assert article.published is not None
        assert article.published.year == 2024

    def test_handles_missing_published(self) -> None:
        entry = {
            "title": "No Date",
            "link": "https://example.com/no-date",
            "summary": "",
            "source": {},
            "published_parsed": None,
        }
        article = NewsCollector._entry_to_article(entry, Topic.GOLD)
        assert article.published is None

    def test_handles_missing_source(self) -> None:
        entry = {
            "title": "No Source",
            "link": "https://example.com/no-source",
            "summary": "",
            "published_parsed": None,
        }
        article = NewsCollector._entry_to_article(entry, Topic.USD)
        assert article.source == ""


# ---------------------------------------------------------------------------
# Topics filtering
# ---------------------------------------------------------------------------


class TestTopicsFiltering:

    def test_filters_to_specified_topics(self) -> None:
        collector = NewsCollector(
            topics=[Topic.FED, Topic.GOLD],
            data_source=lambda: [
                NewsArticle(title="F", source="S", url="https://ex.com/fed"),
                NewsArticle(title="G", source="S", url="https://ex.com/gold"),
            ],
        )
        results = collector.collect()
        assert len(results) == 2


# ---------------------------------------------------------------------------
# Sorting
# ---------------------------------------------------------------------------


class TestSorting:

    def test_most_recent_first(self) -> None:
        articles = [
            NewsArticle(
                title="Old",
                source="S",
                url="https://ex.com/1",
                published=datetime(2024, 1, 1, tzinfo=timezone.utc),
            ),
            NewsArticle(
                title="New",
                source="S",
                url="https://ex.com/2",
                published=datetime(2024, 6, 1, tzinfo=timezone.utc),
            ),
        ]
        collector = NewsCollector(data_source=lambda: articles)
        results = collector.collect()
        assert results[0].title == "New"
        assert results[1].title == "Old"

    def test_none_published_goes_last(self) -> None:
        articles = [
            NewsArticle(
                title="With Date",
                source="S",
                url="https://ex.com/1",
                published=datetime(2024, 1, 1, tzinfo=timezone.utc),
            ),
            NewsArticle(
                title="No Date", source="S", url="https://ex.com/2"
            ),
        ]
        collector = NewsCollector(data_source=lambda: articles)
        results = collector.collect()
        assert results[0].title == "With Date"
