from __future__ import annotations

import datetime
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

import pandas as pd

if TYPE_CHECKING:
    from knowledge.regime.macro_regime_detector import MacroRegimeDetector
    from nlp.news_sentiment import NewsSentimentAnalyzer
    from nlp.fomc_sentiment import FOMCSentimentAnalyzer


@dataclass(frozen=True)
class EventSummary:
    event_type: str
    date: str
    condition: str
    gold_direction: str
    gold_return_pct: float


@dataclass(frozen=True)
class ForecastContext:
    current_regime: str | None
    regime_confidence: float
    recent_events: tuple[EventSummary, ...]
    news_mood: str | None
    news_confidence: float
    fomc_mood: str | None
    fomc_confidence: float
    context_timestamp: str
    source_variable: str
    data_date_range: tuple[str, str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "current_regime": self.current_regime,
            "regime_confidence": self.regime_confidence,
            "recent_events": [
                {
                    "event_type": e.event_type,
                    "date": e.date,
                    "condition": e.condition,
                    "gold_direction": e.gold_direction,
                    "gold_return_pct": e.gold_return_pct,
                }
                for e in self.recent_events
            ],
            "news_mood": self.news_mood,
            "news_confidence": self.news_confidence,
            "fomc_mood": self.fomc_mood,
            "fomc_confidence": self.fomc_confidence,
            "context_timestamp": self.context_timestamp,
            "source_variable": self.source_variable,
            "data_date_range": list(self.data_date_range),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ForecastContext:
        events = tuple(
            EventSummary(
                event_type=e["event_type"],
                date=e["date"],
                condition=e["condition"],
                gold_direction=e["gold_direction"],
                gold_return_pct=float(e["gold_return_pct"]),
            )
            for e in data.get("recent_events", [])
        )
        ddr = data.get("data_date_range", ["", ""])
        if isinstance(ddr, list):
            ddr = (str(ddr[0]) if len(ddr) > 0 else "", str(ddr[1]) if len(ddr) > 1 else "")
        return cls(
            current_regime=data.get("current_regime"),
            regime_confidence=float(data.get("regime_confidence", 0.0)),
            recent_events=events,
            news_mood=data.get("news_mood"),
            news_confidence=float(data.get("news_confidence", 0.0)),
            fomc_mood=data.get("fomc_mood"),
            fomc_confidence=float(data.get("fomc_confidence", 0.0)),
            context_timestamp=str(data.get("context_timestamp", "")),
            source_variable=str(data.get("source_variable", "")),
            data_date_range=ddr,
        )


class ForecastContextBuilder:
    """The ONLY component allowed to construct a ``ForecastContext``.

    Aggregates already-validated intelligence from existing sources.
    Never computes intelligence, never performs reasoning or forecasting.
    """

    def __init__(
        self,
        regime_detector: MacroRegimeDetector | None = None,
        news_analyzer: NewsSentimentAnalyzer | None = None,
        fomc_analyzer: FOMCSentimentAnalyzer | None = None,
    ) -> None:
        self._regime_detector = regime_detector
        self._news_analyzer = news_analyzer
        self._fomc_analyzer = fomc_analyzer

    def build(
        self,
        source_variable: str,
        training_data: pd.DataFrame,
        event_summaries: list[EventSummary] | None = None,
        news_texts: list[str] | None = None,
        fomc_texts: list[str] | None = None,
        *,
        _timestamp: str | None = None,
    ) -> ForecastContext:
        regime = self._resolve_regime()
        news = self._resolve_news_sentiment(news_texts)
        fomc = self._resolve_fomc_sentiment(fomc_texts)
        date_range = self._resolve_date_range(training_data)

        return ForecastContext(
            current_regime=regime["label"],
            regime_confidence=regime["confidence"],
            recent_events=tuple(event_summaries or []),
            news_mood=news["mood"],
            news_confidence=news["confidence"],
            fomc_mood=fomc["mood"],
            fomc_confidence=fomc["confidence"],
            context_timestamp=_timestamp or datetime.datetime.now(datetime.timezone.utc).isoformat(),
            source_variable=source_variable,
            data_date_range=date_range,
        )

    def _resolve_regime(self) -> dict[str, Any]:
        if self._regime_detector is None:
            return {"label": None, "confidence": 0.0}
        labels = self._regime_detector.regime_labels
        if labels is None or labels.empty:
            return {"label": None, "confidence": 0.0}
        latest_label = labels.iloc[-1]
        regime_counts = labels.value_counts()
        total = regime_counts.sum()
        latest_count = regime_counts.get(latest_label, 0)
        confidence = round(latest_count / total, 4) if total > 0 else 0.0
        return {"label": str(latest_label), "confidence": confidence}

    def _resolve_news_sentiment(self, texts: list[str] | None) -> dict[str, Any]:
        if self._news_analyzer is None or not texts:
            return {"mood": None, "confidence": 0.0}
        results = self._news_analyzer.analyze_batch(texts)
        if not results:
            return {"mood": None, "confidence": 0.0}
        positive = sum(1 for r in results if r.label == "positive")
        negative = sum(1 for r in results if r.label == "negative")
        neutral = sum(1 for r in results if r.label == "neutral")
        total = len(results)
        if positive > negative and positive > neutral:
            mood = "positive"
        elif negative > positive and negative > neutral:
            mood = "negative"
        else:
            mood = "neutral"
        confidence = round(max(positive, negative, neutral) / total, 4) if total > 0 else 0.0
        return {"mood": mood, "confidence": confidence}

    def _resolve_fomc_sentiment(self, texts: list[str] | None) -> dict[str, Any]:
        if self._fomc_analyzer is None or not texts:
            return {"mood": None, "confidence": 0.0}
        results = [self._fomc_analyzer.analyze(t) for t in texts]
        if not results:
            return {"mood": None, "confidence": 0.0}
        hawkish = sum(1 for r in results if r.label == "hawkish")
        dovish = sum(1 for r in results if r.label == "dovish")
        neutral = sum(1 for r in results if r.label == "neutral")
        total = len(results)
        if hawkish > dovish and hawkish > neutral:
            mood = "hawkish"
        elif dovish > hawkish and dovish > neutral:
            mood = "dovish"
        else:
            mood = "neutral"
        confidence = round(max(hawkish, dovish, neutral) / total, 4) if total > 0 else 0.0
        return {"mood": mood, "confidence": confidence}

    @staticmethod
    def _resolve_date_range(data: pd.DataFrame) -> tuple[str, str]:
        if "ds" in data.columns:
            dates = pd.to_datetime(data["ds"], errors="coerce").dropna()
        elif "Date" in data.columns:
            dates = pd.to_datetime(data["Date"], errors="coerce").dropna()
        else:
            return ("", "")
        if dates.empty:
            return ("", "")
        return (str(dates.min().date()), str(dates.max().date()))
