from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional


class Topic(str, Enum):
    FED = "fed"
    INFLATION = "inflation"
    INTEREST_RATES = "interest_rates"
    GOLD = "gold"
    USD = "usd"
    TREASURY = "treasury"
    GEOPOLITICS = "geopolitics"


@dataclass(frozen=True)
class NewsArticle:
    title: str
    source: str
    url: str
    published: Optional[datetime] = None
    summary: str = ""
    topics: tuple[Topic, ...] = field(default_factory=tuple)


DEFAULT_RSS_FEEDS: dict[Topic, list[str]] = {
    Topic.FED: [
        "https://www.federalreserve.gov/feeds/press_all.xml",
    ],
    Topic.INFLATION: [
        "https://news.google.com/rss/search?q=inflation+CPI&hl=en-US&gl=US&ceid=US:en",
    ],
    Topic.INTEREST_RATES: [
        "https://news.google.com/rss/search?q=interest+rates+Federal+Reserve&hl=en-US&gl=US&ceid=US:en",
    ],
    Topic.GOLD: [
        "https://news.google.com/rss/search?q=gold+price+market&hl=en-US&gl=US&ceid=US:en",
    ],
    Topic.USD: [
        "https://news.google.com/rss/search?q=US+dollar+currency+market&hl=en-US&gl=US&ceid=US:en",
    ],
    Topic.TREASURY: [
        "https://news.google.com/rss/search?q=treasury+bond+yield+market&hl=en-US&gl=US&ceid=US:en",
    ],
    Topic.GEOPOLITICS: [
        "https://news.google.com/rss/search?q=geopolitics+global+trade+conflict&hl=en-US&gl=US&ceid=US:en",
    ],
}
