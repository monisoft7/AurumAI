from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Callable

from news.news_collector import NewsCollector
from news.models import NewsArticle, Topic
from nlp.news_sentiment import NewsSentimentAnalyzer, SentimentResult
from pre_market.contracts import NewsItem


class OvernightNewsIngestion:
    """Collects and classifies overnight news headlines.

    Wraps NewsCollector + NewsSentimentAnalyzer. Assigns a relevance
    score to each headline based on topic alignment.
    """

    W3_TOPICS: list[str] = [
        "gold", "inflation", "fed", "interest_rates", "usd",
        "treasury", "geopolitics", "central_bank",
    ]

    def __init__(
        self,
        collector: NewsCollector | None = None,
        sentiment_analyzer: NewsSentimentAnalyzer | None = None,
        relevance_scorer: Callable[[NewsArticle, list[str]], float] | None = None,
    ) -> None:
        self._collector = collector or NewsCollector()
        self._analyzer = sentiment_analyzer or NewsSentimentAnalyzer()
        self._relevance_scorer = relevance_scorer or self._default_relevance

    def ingest(self, max_articles: int = 20) -> list[NewsItem]:
        articles = self._collector.collect()
        if not articles:
            return []
        articles = articles[:max_articles]
        texts = [a.title for a in articles]
        try:
            sentiments = self._analyzer.analyze_batch(texts) or []
        except (ImportError, RuntimeError):
            sentiments = []

        items: list[NewsItem] = []
        for article, sentiment in zip(articles, sentiments):
            relevance = self._relevance_scorer(article, self.W3_TOPICS)
            topic_strs = tuple(t.value if hasattr(t, "value") else str(t) for t in article.topics)
            items.append(NewsItem(
                headline=article.title,
                source=article.source,
                published=article.published.isoformat() if article.published else "",
                sentiment_label=sentiment.label if sentiment else "neutral",
                sentiment_confidence=round(sentiment.confidence, 4) if sentiment else 0.0,
                relevance_score=round(relevance, 4),
                topics=topic_strs,
            ))

        items.sort(key=lambda x: x.relevance_score, reverse=True)
        return items

    @staticmethod
    def _default_relevance(article: NewsArticle, topics: list[str]) -> float:
        score = 0.0
        title_lower = article.title.lower()
        for topic in topics:
            if topic in title_lower:
                score += 0.2
        article_topics = [t.value if hasattr(t, "value") else str(t) for t in article.topics]
        for at in article_topics:
            if at in topics:
                score += 0.15
        return min(score, 1.0)
