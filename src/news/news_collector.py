from __future__ import annotations

from datetime import datetime, timezone
from typing import Callable, Optional
from urllib.parse import urlparse

from news.models import DEFAULT_RSS_FEEDS, NewsArticle, Topic


def _default_article_sort_key(a: NewsArticle) -> str:
    if a.published is not None:
        return a.published.isoformat()
    return ""


class NewsCollector:
    """Lightweight news aggregator for macro-relevant topics.

    Default mode fetches from RSS feeds via ``feedparser``.
    For deterministic behaviour (e.g. tests), pass a *data_source*
    callable that returns ``list[NewsArticle]``.
    """

    def __init__(
        self,
        topics: Optional[list[Topic]] = None,
        feeds: Optional[dict[Topic, list[str]]] = None,
        data_source: Optional[Callable[[], list[NewsArticle]]] = None,
    ) -> None:
        self._topics = topics or list(Topic)
        self._feeds = feeds or DEFAULT_RSS_FEEDS
        self._data_source = data_source

    def collect(self) -> list[NewsArticle]:
        if self._data_source is not None:
            raw = self._data_source()
        else:
            raw = self._fetch_from_rss()
        return self._dedup_and_sort(raw)

    def _fetch_from_rss(self) -> list[NewsArticle]:
        import feedparser

        articles: list[NewsArticle] = []
        for topic in self._topics:
            urls = self._feeds.get(topic, [])
            for url in urls:
                feed = feedparser.parse(url)
                for entry in feed.entries:
                    articles.append(self._entry_to_article(entry, topic))
        return articles

    @staticmethod
    def _dedup_and_sort(
        articles: list[NewsArticle],
    ) -> list[NewsArticle]:
        seen: set[str] = set()
        result: list[NewsArticle] = []
        for a in articles:
            normalized = NewsCollector._normalize_url(a.url)
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            result.append(a)
        result.sort(key=_default_article_sort_key, reverse=True)
        return result

    @staticmethod
    def _normalize_url(url: str) -> str:
        if not url:
            return ""
        parsed = urlparse(url)
        if not parsed.netloc:
            return ""
        scheme = parsed.scheme or "https"
        return f"{scheme}://{parsed.netloc}{parsed.path}"

    @staticmethod
    def _entry_to_article(
        entry: dict, topic: Topic
    ) -> NewsArticle:
        published = None
        published_parsed = entry.get("published_parsed")
        if published_parsed:
            try:
                published = datetime(
                    *published_parsed[:6], tzinfo=timezone.utc
                )
            except (ValueError, TypeError):
                published = None

        source_data = entry.get("source", {}) or {}
        source_title = ""
        if isinstance(source_data, dict):
            source_title = source_data.get("title", "")

        return NewsArticle(
            title=entry.get("title", ""),
            source=source_title,
            url=entry.get("link", ""),
            published=published,
            summary=entry.get("summary", ""),
            topics=(topic,),
        )
