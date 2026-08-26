"""Sprint 058 -- deterministic news intelligence pipeline.

Producer-side normalization/classification for the news path:

    News Sources -> News Ingestion -> Normalization -> Event Classification
    -> Gold Relevance -> Directional Impact -> Confidence -> provenance payload

Design rules enforced here:

* No silent loss.  Every terminal state carries an explicit ``status``
  (``ok`` / ``empty`` / ``unavailable``) plus a machine-readable ``reason``
  so ``news_unavailable`` (dependency/fetch failure) is distinguishable
  from ``news_empty`` (sources genuinely returned nothing).
* Article existence never implies known sentiment.  When the optional
  NLP stack (transformers/torch) is missing, ``sentiment_label`` stays
  ``unknown`` with ``sentiment_available=False`` -- no invented polarity.
* Classification is rule-based and deterministic: no LLM/NLP call, no
  wall-clock reads, no random UUIDs inside semantic content.  Content ids
  are sha256-derived.
* Directional implications follow Correction-051 semantics: a headline
  naming an asset (e.g. "USD strengthened") never maps to a gold
  direction by name alone.  Only unambiguous event semantics (central
  bank gold buying/selling, documented safe-haven channels) resolve to a
  direction; everything else stays ``unknown``.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Iterable

# ---------------------------------------------------------------------------
# Contracts
# ---------------------------------------------------------------------------

STATUS_OK = "ok"
STATUS_EMPTY = "empty"
STATUS_UNAVAILABLE = "unavailable"

SENTIMENT_UNKNOWN_LABEL = "unknown"

EVENT_FED_FOMC = "fed_fomc"
EVENT_CPI_INFLATION = "cpi_inflation"
EVENT_YIELDS = "yields"
EVENT_USD = "usd_dollar"
EVENT_GEOPOLITICAL = "geopolitical"
EVENT_CB_GOLD_DEMAND = "cb_gold_demand"
EVENT_RISK_SENTIMENT = "risk_sentiment"
EVENT_GOLD_MARKET = "gold_market"
EVENT_GENERIC_MACRO = "generic_macro"

GOLD_RELEVANCE_HIGH = "high"
GOLD_RELEVANCE_MEDIUM = "medium"
GOLD_RELEVANCE_LOW = "low"
GOLD_RELEVANCE_NONE = "none"

DIRECTION_BULLISH = "bullish"
DIRECTION_BEARISH = "bearish"
DIRECTION_NEUTRAL = "neutral"
DIRECTION_UNKNOWN = "unknown"

_GOLD_RELEVANCE_SCORES: dict[str, float] = {
    GOLD_RELEVANCE_HIGH: 1.0,
    GOLD_RELEVANCE_MEDIUM: 0.6,
    GOLD_RELEVANCE_LOW: 0.3,
    GOLD_RELEVANCE_NONE: 0.0,
}


@dataclass(frozen=True)
class ClassifiedNewsItem:
    """Normalized, classified news article with full provenance."""

    article_id: str
    content_hash: str
    headline: str
    source: str
    url: str
    published_at: str
    ingested_at: str
    event_type: str
    gold_relevance: str
    gold_relevance_score: float
    directional_implication: str
    direction_basis: str
    confidence: float
    novelty: float
    duplicate_of: str
    sentiment_label: str
    sentiment_confidence: float
    sentiment_available: bool
    topics: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "article_id": self.article_id,
            "content_hash": self.content_hash,
            "headline": self.headline,
            "source": self.source,
            "url": self.url,
            "published_at": self.published_at,
            "ingested_at": self.ingested_at,
            "event_type": self.event_type,
            "gold_relevance": self.gold_relevance,
            "gold_relevance_score": self.gold_relevance_score,
            "directional_implication": self.directional_implication,
            "direction_basis": self.direction_basis,
            "confidence": self.confidence,
            "novelty": self.novelty,
            "duplicate_of": self.duplicate_of,
            "sentiment_label": self.sentiment_label,
            "sentiment_confidence": self.sentiment_confidence,
            "sentiment_available": self.sentiment_available,
            "topics": list(self.topics),
        }


# ---------------------------------------------------------------------------
# Deterministic identity
# ---------------------------------------------------------------------------


def content_hash(headline: str, summary: str = "") -> str:
    """Deterministic sha256 over normalized headline+summary."""
    normalized = " ".join(f"{headline}\n{summary}".split()).lower()
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def article_id(source: str, headline: str, published_at: str, summary: str = "") -> str:
    """Deterministic content id (no randomness, no wall clock).

    Identity binds source+publication time+content so two ingests of the
    same article collide intentionally while distinct articles never do.
    """
    digest = hashlib.sha256(
        f"{source.strip().lower()}|{published_at}|{content_hash(headline, summary)}".encode("utf-8")
    ).hexdigest()[:16]
    return f"nws_{digest}"


def headline_hash(headline: str) -> str:
    return hashlib.sha256(headline.encode("utf-8")).hexdigest()[:16]


# ---------------------------------------------------------------------------
# Rule-based classification (deterministic; Correction-051 compliant)
# ---------------------------------------------------------------------------

_EVENT_RULES: tuple[tuple[str, tuple[str, ...]], ...] = (
    (
        EVENT_CB_GOLD_DEMAND,
        (
            "central bank gold", "central-bank gold", "cb gold",
            "gold reserves", "gold purchases", "gold buying program",
            "world gold council",
        ),
    ),
    (
        EVENT_FED_FOMC,
        (
            "fomc", "federal reserve", "the fed ", "fed officials", "powell",
            "interest rate decision", "rate decision", "fomc minutes",
            "dot plot", "fed funds",
        ),
    ),
    (
        EVENT_CPI_INFLATION,
        (
            "cpi", "inflation rate", "consumer price", "pce ", "pce price",
            "core inflation", "inflation data", "nfp", "nonfarm payrolls",
            "non-farm payrolls", "ppi ",
        ),
    ),
    (
        EVENT_YIELDS,
        (
            "treasury yield", "bond yield", "10-year", "2-year", "30-year",
            "yield curve", "real yield", "tips ",
        ),
    ),
    (
        EVENT_USD,
        (
            "dollar index", "usd ", "dollar strengthens", "dollar weakens",
            "greenback", "dxy", "dollar rallies", "dollar slides",
        ),
    ),
    (
        EVENT_GEOPOLITICAL,
        (
            "war", "sanctions", "military strike", "conflict escalat",
            "invasion", "missile", "ceasefire", "peace deal", "trade war",
            "tariff",
        ),
    ),
    (
        EVENT_RISK_SENTIMENT,
        (
            "risk-off", "risk off", "risk-on", "risk appetite",
            "safe haven", "safe-haven", "market selloff", "flight to safety",
        ),
    ),
    (
        EVENT_GOLD_MARKET,
        ("gold price", "gold rises", "gold falls", "gold jumps", "gold drops", "bullion", "xau"),
    ),
)

_RELEVANCE_BY_EVENT: dict[str, str] = {
    EVENT_CB_GOLD_DEMAND: GOLD_RELEVANCE_HIGH,
    EVENT_GOLD_MARKET: GOLD_RELEVANCE_HIGH,
    EVENT_FED_FOMC: GOLD_RELEVANCE_MEDIUM,
    EVENT_CPI_INFLATION: GOLD_RELEVANCE_MEDIUM,
    EVENT_YIELDS: GOLD_RELEVANCE_MEDIUM,
    EVENT_USD: GOLD_RELEVANCE_MEDIUM,
    EVENT_GEOPOLITICAL: GOLD_RELEVANCE_MEDIUM,
    EVENT_RISK_SENTIMENT: GOLD_RELEVANCE_LOW,
    EVENT_GENERIC_MACRO: GOLD_RELEVANCE_LOW,
}

_CB_DEMAND_UP = ("buy", "purchase", "increase", "boost", "accumulate", "add")
_CB_DEMAND_DOWN = ("sell", "reduce", "trim", "cut", "dump", "decrease")
_ESCALATION = ("war", "sanction", "strike", "conflict escalat", "invasion", "missile", "escalat")
_DEESCALATION = ("ceasefire", "peace deal", "truce", "de-escalat")


def classify_event(text_lower: str) -> tuple[str, int]:
    """Return (event_type, matched_rule_count). First matching family wins;
    families are ordered most-specific first."""
    for event_type, needles in _EVENT_RULES:
        hits = sum(1 for n in needles if n in text_lower)
        if hits > 0:
            return event_type, hits
    return EVENT_GENERIC_MACRO, 0


def _direction_for(event_type: str, text_lower: str) -> tuple[str, str]:
    """Resolve directional implication from event semantics only.

    Correction 051: asset-name polarity ("USD strengthened") is never a
    gold direction.  Only documented, unambiguous channels resolve:
    central-bank gold demand (flow channel) and geopolitical escalation /
    de-escalation (safe-haven channel, Institutional KB GPR evidence).
    """
    if event_type == EVENT_CB_GOLD_DEMAND:
        if any(k in text_lower for k in _CB_DEMAND_UP):
            return DIRECTION_BULLISH, "cb_gold_demand_increase"
        if any(k in text_lower for k in _CB_DEMAND_DOWN):
            return DIRECTION_BEARISH, "cb_gold_demand_decrease"
        return DIRECTION_UNKNOWN, "cb_gold_demand_no_flow_direction"
    if event_type == EVENT_GEOPOLITICAL:
        if any(k in text_lower for k in _ESCALATION):
            return DIRECTION_BULLISH, "safe_haven_escalation"
        if any(k in text_lower for k in _DEESCALATION):
            return DIRECTION_BEARISH, "safe_haven_deescalation"
        return DIRECTION_UNKNOWN, "geopolitical_no_channel_direction"
    return DIRECTION_UNKNOWN, "no_unambiguous_event_semantics"


def _confidence_for(hits: int, relevance: str) -> float:
    base = {1: 0.4, 2: 0.6}.get(hits, 0.8 if hits >= 3 else 0.3)
    bump = {GOLD_RELEVANCE_HIGH: 0.1, GOLD_RELEVANCE_MEDIUM: 0.05}.get(relevance, 0.0)
    return round(min(base + bump, 0.9), 4)


def classify_article(headline: str, summary: str = "") -> dict[str, Any]:
    """Deterministic rule-based classification of one article's text."""
    text_lower = " ".join(f"{headline} {summary}".split()).lower()
    event_type, hits = classify_event(text_lower)
    relevance = _RELEVANCE_BY_EVENT[event_type]
    direction, basis = _direction_for(event_type, text_lower)
    return {
        "event_type": event_type,
        "gold_relevance": relevance,
        "gold_relevance_score": _GOLD_RELEVANCE_SCORES[relevance],
        "directional_implication": direction,
        "direction_basis": basis,
        "confidence": _confidence_for(hits, relevance),
    }


# ---------------------------------------------------------------------------
# Normalization
# ---------------------------------------------------------------------------


def _parse_published(raw: Any) -> tuple[str, datetime | None]:
    if isinstance(raw, datetime):
        dt = raw if raw.tzinfo else raw.replace(tzinfo=timezone.utc)
        return dt.isoformat(), dt
    text = str(raw or "").strip()
    if not text:
        return "", None
    try:
        dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
        dt = dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
        return dt.isoformat(), dt
    except ValueError:
        return text, None


def normalize_articles(
    articles: Iterable[Any],
    *,
    as_of: datetime | str | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Normalize raw article-like objects into ClassifiedNewsItem dicts.

    Applies, in order: malformed filtering, no-lookahead filtering
    (``published <= as_of`` when ``as_of`` given), deterministic content
    ids, classification, within-batch duplicate/novelty marking.
    """
    ingested_dt = now or datetime.now(timezone.utc)
    if ingested_dt.tzinfo is None:
        ingested_dt = ingested_dt.replace(tzinfo=timezone.utc)
    ingested_iso = ingested_dt.isoformat()

    as_of_dt: datetime | None = None
    if isinstance(as_of, datetime):
        as_of_dt = as_of if as_of.tzinfo else as_of.replace(tzinfo=timezone.utc)
    elif isinstance(as_of, str) and as_of.strip():
        parsed, parsed_dt = _parse_published(as_of)
        as_of_dt = parsed_dt

    malformed = 0
    excluded_after_asof = 0
    drafts: list[dict[str, Any]] = []
    seen_content: dict[str, str] = {}

    for art in articles:
        headline = str(getattr(art, "title", "") or getattr(art, "headline", "") or "").strip()
        summary = str(getattr(art, "summary", "") or "").strip()
        source = str(getattr(art, "source", "") or "").strip()
        url = str(getattr(art, "url", "") or getattr(art, "link", "") or "").strip()
        published_raw = getattr(art, "published", None)
        if getattr(art, "published_at", None) is not None and published_raw is None:
            published_raw = getattr(art, "published_at")
        topics_raw = getattr(art, "topics", ()) or ()
        topics = tuple(t.value if hasattr(t, "value") else str(t) for t in topics_raw)

        if not headline and not summary:
            malformed += 1
            continue

        published_iso, published_dt = _parse_published(published_raw)
        if as_of_dt is not None and published_dt is not None and published_dt > as_of_dt:
            excluded_after_asof += 1
            continue

        chash = content_hash(headline, summary)
        aid = article_id(source, headline, published_iso, summary)
        duplicate_of = seen_content.get(chash, "")
        novelty = 0.0 if duplicate_of else 1.0
        if not duplicate_of:
            seen_content[chash] = aid

        cls = classify_article(headline, summary)
        drafts.append(
            {
                "article_id": aid,
                "content_hash": chash,
                "headline": headline,
                "source": source,
                "url": url,
                "published_at": published_iso,
                "ingested_at": ingested_iso,
                "duplicate_of": duplicate_of,
                "novelty": novelty,
                "topics": topics,
                **cls,
            }
        )

    return {
        "drafts": drafts,
        "malformed_count": malformed,
        "excluded_after_asof_count": excluded_after_asof,
    }


def attach_sentiment(
    items: list[dict[str, Any]],
    analyzer: Any | None,
) -> str:
    """Attach optional NLP sentiment in place; report explicit status.

    Returns ``ok`` / ``unavailable_dependency_missing`` / ``skipped_none``.
    Missing or failing analyzers leave ``sentiment_label='unknown'`` --
    sentiment is never invented.
    """
    if analyzer is None:
        status = "skipped_none"
    else:
        try:
            texts = [it["headline"] for it in items]
            results = analyzer.analyze_batch(texts) if texts else []
            status = "ok"
            if len(results) != len(items):
                results = []
                status = "unavailable_analyzer_error"
        except (ImportError, RuntimeError, AttributeError):
            results = []
            status = "unavailable_dependency_missing"
        except Exception:
            results = []
            status = "unavailable_analyzer_error"
        for item, res in zip(items, results):
            label = getattr(res, "label", None)
            conf = getattr(res, "confidence", None)
            if label is None or conf is None:
                item["sentiment_label"] = SENTIMENT_UNKNOWN_LABEL
                item["sentiment_confidence"] = 0.0
                item["sentiment_available"] = False
            else:
                item["sentiment_label"] = str(label)
                item["sentiment_confidence"] = round(float(conf), 4)
                item["sentiment_available"] = True
    for item in items:
        item.setdefault("sentiment_label", SENTIMENT_UNKNOWN_LABEL)
        item.setdefault("sentiment_confidence", 0.0)
        item.setdefault("sentiment_available", False)
    return status


# ---------------------------------------------------------------------------
# Pipeline entry point
# ---------------------------------------------------------------------------

NewsSource = Callable[[], list[Any]]


def run_news_intelligence(
    *,
    data_source: NewsSource | None = None,
    topics: tuple[str, ...] = ("gold", "inflation", "fed"),
    lookback_days: int = 7,
    max_articles: int = 20,
    as_of: datetime | str | None = None,
    now: datetime | None = None,
    sentiment_analyzer: Any | None = None,
) -> dict[str, Any]:
    """Run ingestion->normalization->classification end-to-end.

    Never raises for expected environment failures; every failure mode is
    reported through ``status``/``reason`` so callers cannot confuse a
    broken pipeline with an empty news day.
    """
    ingested_dt = now or datetime.now(timezone.utc)
    ingested_iso = (
        ingested_dt if ingested_dt.tzinfo else ingested_dt.replace(tzinfo=timezone.utc)
    ).isoformat()

    payload: dict[str, Any] = {
        "status": STATUS_UNAVAILABLE,
        "reason": "",
        "ingested_at": ingested_iso,
        "as_of": None,
        "items": [],
        "malformed_count": 0,
        "excluded_after_asof_count": 0,
        "duplicate_count": 0,
        "fetch_errors": [],
        "sentiment_status": "skipped_none",
    }

    if isinstance(as_of, str) and as_of.strip():
        payload["as_of"] = as_of
    elif isinstance(as_of, datetime):
        payload["as_of"] = (
            as_of if as_of.tzinfo else as_of.replace(tzinfo=timezone.utc)
        ).isoformat()

    # --- collection -----------------------------------------------------
    raw_articles: list[Any] = []
    if data_source is not None:
        try:
            raw_articles = list(data_source() or [])
        except Exception as exc:
            payload["reason"] = f"data_source_failed: {type(exc).__name__}"
            return payload
    else:
        try:
            from news.models import DEFAULT_RSS_FEEDS, Topic
            from news.news_collector import NewsCollector

            topic_map = {}
            for t in topics:
                try:
                    topic_map[Topic(t)] = DEFAULT_RSS_FEEDS.get(Topic(t), [])
                except ValueError:
                    continue
            collector = NewsCollector(topics=list(topic_map.keys()), feeds=topic_map)
            raw_articles, fetch_errors = _collect_with_error_capture(collector)
            payload["fetch_errors"] = fetch_errors
        except ImportError as exc:
            payload["reason"] = f"dependency_missing: {exc.name or 'feedparser'}"
            return payload

    # --- normalization / classification ---------------------------------
    norm = normalize_articles(raw_articles, as_of=as_of, now=now)
    drafts = norm["drafts"]
    dated = [d for d in drafts if d["published_at"]]
    undated = [d for d in drafts if not d["published_at"]]
    dated.sort(key=lambda d: d["published_at"], reverse=True)
    drafts = (dated + undated)[:max_articles]

    payload["malformed_count"] = norm["malformed_count"]
    payload["excluded_after_asof_count"] = norm["excluded_after_asof_count"]

    if not drafts:
        if raw_articles:
            payload["status"] = STATUS_EMPTY
            payload["reason"] = "all_articles_filtered"
        elif payload["fetch_errors"]:
            payload["status"] = STATUS_UNAVAILABLE
            payload["reason"] = "feed_fetch_failed"
        else:
            payload["status"] = STATUS_EMPTY
            payload["reason"] = "no_articles_returned"
        return payload

    payload["sentiment_status"] = attach_sentiment(drafts, sentiment_analyzer)

    items = [ClassifiedNewsItem(**d).to_dict() for d in drafts]
    payload["duplicate_count"] = sum(1 for it in items if it["duplicate_of"])
    payload["items"] = items
    payload["status"] = STATUS_OK
    payload["reason"] = ""
    return payload


def _collect_with_error_capture(collector: Any) -> tuple[list[Any], list[str]]:
    """Collect via feedparser-style sources capturing per-feed errors.

    The default NewsCollector hides per-feed bozo errors; we re-walk its
    feeds so a fully-failing network reports ``unavailable`` instead of a
    fake ``empty`` news day.
    """
    import feedparser

    articles: list[Any] = []
    errors: list[str] = []
    for topic, urls in collector._feeds.items():
        for url in urls:
            try:
                feed = feedparser.parse(url)
            except Exception as exc:
                errors.append(f"{url}: {type(exc).__name__}")
                continue
            if feed.bozo and not feed.entries:
                errors.append(f"{url}: {type(feed.bozo_exception).__name__}")
                continue
            for entry in feed.entries:
                articles.append(collector._entry_to_article(entry, topic))
    deduped = NewsCollector._dedup_and_sort(articles) if hasattr(collector, "_dedup_and_sort") else articles
    return deduped, errors


# ---------------------------------------------------------------------------
# Adapter: intelligence payload -> pre_market NewsItem contract
# ---------------------------------------------------------------------------


def relevance_score_for(headline: str, topics: tuple[str, ...], w3_topics: tuple[str, ...]) -> float:
    """Verbatim re-implementation of OvernightNewsIngestion._default_relevance
    so stage-supplied news scores identically to the legacy internal path
    (W5 narrative_fit thresholds stay untouched)."""
    score = 0.0
    title_lower = headline.lower()
    for topic in w3_topics:
        if topic in title_lower:
            score += 0.2
    for at in topics:
        if at in w3_topics:
            score += 0.15
    return min(score, 1.0)


def to_pre_market_news_items(payload: dict[str, Any]) -> list[Any]:
    """Adapt ingest_news payload items into pre_market.contracts.NewsItem."""
    from pre_market.contracts import NewsItem
    from pre_market.news_ingestion import OvernightNewsIngestion

    w3 = tuple(OvernightNewsIngestion.W3_TOPICS)
    out: list[Any] = []
    for it in payload.get("items", []):
        relevance = relevance_score_for(it["headline"], tuple(it.get("topics", ())), w3)
        out.append(
            NewsItem(
                headline=it["headline"],
                source=it["source"],
                published=it["published_at"],
                sentiment_label=it["sentiment_label"],
                sentiment_confidence=float(it["sentiment_confidence"]),
                relevance_score=round(relevance, 4),
                topics=tuple(it.get("topics", ())),
                provenance={
                    "article_id": it["article_id"],
                    "content_hash": it["content_hash"],
                    "url": it["url"],
                    "published_at": it["published_at"],
                    "ingested_at": it["ingested_at"],
                    "event_type": it["event_type"],
                    "gold_relevance": it["gold_relevance"],
                    "directional_implication": it["directional_implication"],
                    "direction_basis": it["direction_basis"],
                    "confidence": it["confidence"],
                    "novelty": it["novelty"],
                    "duplicate_of": it["duplicate_of"],
                    "sentiment_available": it["sentiment_available"],
                },
            )
        )
    out.sort(key=lambda n: n.relevance_score, reverse=True)
    return out
