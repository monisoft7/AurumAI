from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from knowledge._compat import FrozenDict, freeze_dict


@dataclass(frozen=True)
class OvernightPriceChange:
    instrument: str
    previous_close: float
    current_price: float
    change_pct: float
    change_sigma: float
    session: str = ""
    persistence_days: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "instrument": self.instrument,
            "previous_close": self.previous_close,
            "current_price": self.current_price,
            "change_pct": self.change_pct,
            "change_sigma": self.change_sigma,
            "session": self.session,
            "persistence_days": self.persistence_days,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> OvernightPriceChange:
        return cls(
            instrument=str(data.get("instrument", "")),
            previous_close=float(data.get("previous_close", 0.0)),
            current_price=float(data.get("current_price", 0.0)),
            change_pct=float(data.get("change_pct", 0.0)),
            change_sigma=float(data.get("change_sigma", 0.0)),
            session=str(data.get("session", "")),
            persistence_days=float(data.get("persistence_days", 0.0)),
        )


@dataclass(frozen=True)
class NewsItem:
    headline: str
    source: str
    published: str
    sentiment_label: str
    sentiment_confidence: float
    relevance_score: float
    topics: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "headline": self.headline,
            "source": self.source,
            "published": self.published,
            "sentiment_label": self.sentiment_label,
            "sentiment_confidence": self.sentiment_confidence,
            "relevance_score": self.relevance_score,
            "topics": list(self.topics),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> NewsItem:
        return cls(
            headline=str(data.get("headline", "")),
            source=str(data.get("source", "")),
            published=str(data.get("published", "")),
            sentiment_label=str(data.get("sentiment_label", "")),
            sentiment_confidence=float(data.get("sentiment_confidence", 0.0)),
            relevance_score=float(data.get("relevance_score", 0.0)),
            topics=tuple(data.get("topics", ())),
        )


@dataclass(frozen=True)
class RiskSnapshot:
    pnl_daily: float
    pnl_unrealized: float
    var_95: float
    var_99: float
    cvar_95: float
    tail_index: float | None
    drawdown_pct: float
    drawdown_state: str
    var_utilization_pct: float
    exposure: float
    timestamp: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "pnl_daily": self.pnl_daily,
            "pnl_unrealized": self.pnl_unrealized,
            "var_95": self.var_95,
            "var_99": self.var_99,
            "cvar_95": self.cvar_95,
            "tail_index": self.tail_index,
            "drawdown_pct": self.drawdown_pct,
            "drawdown_state": self.drawdown_state,
            "var_utilization_pct": self.var_utilization_pct,
            "exposure": self.exposure,
            "timestamp": self.timestamp,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> RiskSnapshot:
        return cls(
            pnl_daily=float(data.get("pnl_daily", 0.0)),
            pnl_unrealized=float(data.get("pnl_unrealized", 0.0)),
            var_95=float(data.get("var_95", 0.0)),
            var_99=float(data.get("var_99", 0.0)),
            cvar_95=float(data.get("cvar_95", 0.0)),
            tail_index=data.get("tail_index"),
            drawdown_pct=float(data.get("drawdown_pct", 0.0)),
            drawdown_state=str(data.get("drawdown_state", "normal")),
            var_utilization_pct=float(data.get("var_utilization_pct", 0.0)),
            exposure=float(data.get("exposure", 0.0)),
            timestamp=str(data.get("timestamp", "")),
        )


@dataclass(frozen=True)
class PositioningSnapshot:
    cot_z_score: float
    cot_regime: str
    etf_flow_momentum: str
    etf_flow_change_pct: float
    open_interest_change_pct: float
    gofo_rate: float
    timestamp: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "cot_z_score": self.cot_z_score,
            "cot_regime": self.cot_regime,
            "etf_flow_momentum": self.etf_flow_momentum,
            "etf_flow_change_pct": self.etf_flow_change_pct,
            "open_interest_change_pct": self.open_interest_change_pct,
            "gofo_rate": self.gofo_rate,
            "timestamp": self.timestamp,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PositioningSnapshot:
        return cls(
            cot_z_score=float(data.get("cot_z_score", 0.0)),
            cot_regime=str(data.get("cot_regime", "neutral")),
            etf_flow_momentum=str(data.get("etf_flow_momentum", "stable")),
            etf_flow_change_pct=float(data.get("etf_flow_change_pct", 0.0)),
            open_interest_change_pct=float(data.get("open_interest_change_pct", 0.0)),
            gofo_rate=float(data.get("gofo_rate", 0.0)),
            timestamp=str(data.get("timestamp", "")),
        )


@dataclass(frozen=True)
class AnomalyFlag:
    anomaly_type: str
    severity: str
    instrument: str
    description: str
    value: float
    threshold: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "anomaly_type": self.anomaly_type,
            "severity": self.severity,
            "instrument": self.instrument,
            "description": self.description,
            "value": self.value,
            "threshold": self.threshold,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AnomalyFlag:
        return cls(
            anomaly_type=str(data.get("anomaly_type", "")),
            severity=str(data.get("severity", "")),
            instrument=str(data.get("instrument", "")),
            description=str(data.get("description", "")),
            value=float(data.get("value", 0.0)),
            threshold=float(data.get("threshold", 0.0)),
        )


@dataclass(frozen=True)
class WatchlistItem:
    event_type: str
    release_date: str
    release_time: str
    priority: str
    description: str
    expected_impact: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_type": self.event_type,
            "release_date": self.release_date,
            "release_time": self.release_time,
            "priority": self.priority,
            "description": self.description,
            "expected_impact": self.expected_impact,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> WatchlistItem:
        return cls(
            event_type=str(data.get("event_type", "")),
            release_date=str(data.get("release_date", "")),
            release_time=str(data.get("release_time", "")),
            priority=str(data.get("priority", "")),
            description=str(data.get("description", "")),
            expected_impact=str(data.get("expected_impact", "")),
        )


@dataclass(frozen=True)
class PreMarketBriefing:
    briefing_id: str
    timestamp: str
    regime: str
    regime_confidence: float
    overnight_changes: tuple[OvernightPriceChange, ...] = ()
    news_items: tuple[NewsItem, ...] = ()
    risk_snapshot: RiskSnapshot | None = None
    positioning_snapshot: PositioningSnapshot | None = None
    anomaly_flags: tuple[AnomalyFlag, ...] = ()
    watchlist: tuple[WatchlistItem, ...] = ()
    metadata: dict[str, Any] = field(default_factory=lambda: FrozenDict())

    def __post_init__(self) -> None:
        object.__setattr__(self, "overnight_changes", tuple(self.overnight_changes))
        object.__setattr__(self, "news_items", tuple(self.news_items))
        object.__setattr__(self, "anomaly_flags", tuple(self.anomaly_flags))
        object.__setattr__(self, "watchlist", tuple(self.watchlist))
        object.__setattr__(self, "metadata", freeze_dict(self.metadata))

    def to_dict(self) -> dict[str, Any]:
        return {
            "briefing_id": self.briefing_id,
            "timestamp": self.timestamp,
            "regime": self.regime,
            "regime_confidence": self.regime_confidence,
            "overnight_changes": [c.to_dict() for c in self.overnight_changes],
            "news_items": [n.to_dict() for n in self.news_items],
            "risk_snapshot": self.risk_snapshot.to_dict() if self.risk_snapshot else None,
            "positioning_snapshot": self.positioning_snapshot.to_dict() if self.positioning_snapshot else None,
            "anomaly_flags": [f.to_dict() for f in self.anomaly_flags],
            "watchlist": [w.to_dict() for w in self.watchlist],
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PreMarketBriefing:
        return cls(
            briefing_id=str(data.get("briefing_id", "")),
            timestamp=str(data.get("timestamp", "")),
            regime=str(data.get("regime", "")),
            regime_confidence=float(data.get("regime_confidence", 0.0)),
            overnight_changes=tuple(
                OvernightPriceChange.from_dict(c) for c in data.get("overnight_changes", [])
            ),
            news_items=tuple(
                NewsItem.from_dict(n) for n in data.get("news_items", [])
            ),
            risk_snapshot=RiskSnapshot.from_dict(data["risk_snapshot"]) if data.get("risk_snapshot") else None,
            positioning_snapshot=PositioningSnapshot.from_dict(data["positioning_snapshot"]) if data.get("positioning_snapshot") else None,
            anomaly_flags=tuple(
                AnomalyFlag.from_dict(f) for f in data.get("anomaly_flags", [])
            ),
            watchlist=tuple(
                WatchlistItem.from_dict(w) for w in data.get("watchlist", [])
            ),
            metadata=dict(data.get("metadata", {})),
        )
