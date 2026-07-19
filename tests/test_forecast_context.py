from __future__ import annotations

import datetime
from typing import Any

import pandas as pd
import pytest

from forecasting.context import EventSummary, ForecastContext, ForecastContextBuilder

_PINNED_TS = "2026-07-18T12:00:00+00:00"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def sample_data() -> pd.DataFrame:
    return pd.DataFrame({
        "ds": pd.date_range("2020-01-01", periods=12, freq="ME"),
        "y": [100.0] * 12,
    })


@pytest.fixture
def sample_events() -> list[EventSummary]:
    return [
        EventSummary("CPI", "2026-06-10", "cpi_pressure=high", "UP", 1.5),
        EventSummary("NFP", "2026-06-05", "nfp_surprise=positive", "DOWN", -0.8),
    ]


@pytest.fixture
def full_context() -> ForecastContext:
    return ForecastContext(
        current_regime="EXPANSION",
        regime_confidence=0.85,
        recent_events=(
            EventSummary("CPI", "2026-06-10", "cpi_pressure=high", "UP", 1.5),
            EventSummary("NFP", "2026-06-05", "nfp_surprise=positive", "DOWN", -0.8),
        ),
        news_mood="positive",
        news_confidence=0.72,
        fomc_mood="hawkish",
        fomc_confidence=0.65,
        context_timestamp="2026-07-18T12:00:00+00:00",
        source_variable="CPI",
        data_date_range=("2020-01-01", "2026-06-30"),
    )


# ---------------------------------------------------------------------------
# EventSummary
# ---------------------------------------------------------------------------


class TestEventSummary:

    def test_frozen_dataclass(self) -> None:
        e = EventSummary("CPI", "2026-01-01", "high", "UP", 1.5)
        with pytest.raises(AttributeError):
            e.event_type = "NFP"  # type: ignore[misc]

    def test_all_fields(self) -> None:
        e = EventSummary("CPI", "2026-01-01", "cpi_pressure=high", "UP", 1.5)
        assert e.event_type == "CPI"
        assert e.date == "2026-01-01"
        assert e.condition == "cpi_pressure=high"
        assert e.gold_direction == "UP"
        assert e.gold_return_pct == 1.5


# ---------------------------------------------------------------------------
# ForecastContext
# ---------------------------------------------------------------------------


class TestForecastContext:

    def test_frozen_dataclass(self, full_context: ForecastContext) -> None:
        with pytest.raises(AttributeError):
            full_context.current_regime = "CONTRACTION"  # type: ignore[misc]

    def test_all_fields(self, full_context: ForecastContext) -> None:
        assert full_context.current_regime == "EXPANSION"
        assert full_context.regime_confidence == 0.85
        assert len(full_context.recent_events) == 2
        assert full_context.news_mood == "positive"
        assert full_context.news_confidence == 0.72
        assert full_context.fomc_mood == "hawkish"
        assert full_context.fomc_confidence == 0.65
        assert full_context.context_timestamp == "2026-07-18T12:00:00+00:00"
        assert full_context.source_variable == "CPI"
        assert full_context.data_date_range == ("2020-01-01", "2026-06-30")

    def test_fields_default_to_none(self) -> None:
        ctx = ForecastContext(
            current_regime=None,
            regime_confidence=0.0,
            recent_events=(),
            news_mood=None,
            news_confidence=0.0,
            fomc_mood=None,
            fomc_confidence=0.0,
            context_timestamp="",
            source_variable="",
            data_date_range=("", ""),
        )
        assert ctx.current_regime is None
        assert ctx.news_mood is None
        assert ctx.fomc_mood is None
        assert ctx.recent_events == ()
        assert ctx.regime_confidence == 0.0

    def test_recent_events_is_tuple(self) -> None:
        events = (EventSummary("CPI", "2026-01-01", "high", "UP", 1.0),)
        ctx = ForecastContext(
            current_regime=None,
            regime_confidence=0.0,
            recent_events=events,
            news_mood=None,
            news_confidence=0.0,
            fomc_mood=None,
            fomc_confidence=0.0,
            context_timestamp="",
            source_variable="",
            data_date_range=("", ""),
        )
        assert isinstance(ctx.recent_events, tuple)
        assert len(ctx.recent_events) == 1


# ---------------------------------------------------------------------------
# Serialization
# ---------------------------------------------------------------------------


class TestSerialization:

    def test_to_dict_keys(self, full_context: ForecastContext) -> None:
        d = full_context.to_dict()
        expected = {
            "current_regime", "regime_confidence", "recent_events",
            "news_mood", "news_confidence", "fomc_mood", "fomc_confidence",
            "context_timestamp", "source_variable", "data_date_range",
        }
        assert set(d) == expected

    def test_to_dict_event_structure(self, full_context: ForecastContext) -> None:
        d = full_context.to_dict()
        assert len(d["recent_events"]) == 2
        for e in d["recent_events"]:
            assert "event_type" in e
            assert "date" in e
            assert "condition" in e
            assert "gold_direction" in e
            assert "gold_return_pct" in e

    def test_round_trip(self, full_context: ForecastContext) -> None:
        d = full_context.to_dict()
        restored = ForecastContext.from_dict(d)
        assert restored == full_context

    def test_round_trip_empty_events(self) -> None:
        ctx = ForecastContext(
            current_regime=None,
            regime_confidence=0.0,
            recent_events=(),
            news_mood=None,
            news_confidence=0.0,
            fomc_mood=None,
            fomc_confidence=0.0,
            context_timestamp="2026-01-01T00:00:00Z",
            source_variable="GOLD",
            data_date_range=("2020-01-01", "2025-12-31"),
        )
        d = ctx.to_dict()
        restored = ForecastContext.from_dict(d)
        assert restored == ctx

    def test_from_dict_coercion(self) -> None:
        data: dict[str, Any] = {
            "current_regime": None,
            "regime_confidence": "0.5",
            "recent_events": [],
            "news_mood": None,
            "news_confidence": "0.3",
            "fomc_mood": None,
            "fomc_confidence": 0.0,
            "context_timestamp": 12345,
            "source_variable": 42,
            "data_date_range": ["2020-01", "2026-06"],
        }
        ctx = ForecastContext.from_dict(data)
        assert ctx.regime_confidence == 0.5
        assert ctx.news_confidence == 0.3
        assert ctx.context_timestamp == "12345"
        assert ctx.source_variable == "42"
        assert ctx.data_date_range == ("2020-01", "2026-06")


# ---------------------------------------------------------------------------
# ForecastContextBuilder — with all components
# ---------------------------------------------------------------------------


class _MockRegimeDetector:
    def __init__(self, label: str = "EXPANSION") -> None:
        self._label = label
        self._labels = pd.Series([label] * 10, index=pd.date_range("2025-01-01", periods=10, freq="ME"))

    @property
    def regime_labels(self) -> pd.Series:
        return self._labels


class _MockNewsSentimentAnalyzer:
    def __init__(self, label: str = "positive", confidence: float = 0.8) -> None:
        self._label = label
        self._confidence = confidence

    def analyze_batch(self, texts: list[str]) -> list[Any]:
        class _Result:
            label = self._label
            confidence = self._confidence
        return [_Result() for _ in texts]


class _MockFOMCSentimentAnalyzer:
    def __init__(self, label: str = "hawkish", confidence: float = 0.7) -> None:
        self._label = label
        self._confidence = confidence

    def analyze(self, text: str) -> Any:
        class _Result:
            label = self._label
            confidence = self._confidence
        return _Result()


class TestBuilderWithAllComponents:

    def test_build_returns_context(self, sample_data: pd.DataFrame) -> None:
        builder = ForecastContextBuilder(
            regime_detector=_MockRegimeDetector("EXPANSION"),
            news_analyzer=_MockNewsSentimentAnalyzer("positive", 0.8),
            fomc_analyzer=_MockFOMCSentimentAnalyzer("hawkish", 0.7),
        )
        ctx = builder.build(
            source_variable="CPI",
            training_data=sample_data,
            event_summaries=[
                EventSummary("CPI", "2026-06-10", "cpi_pressure=high", "UP", 1.5),
            ],
            news_texts=["News article 1", "News article 2"],
            fomc_texts=["FOMC minutes text"],
            _timestamp=_PINNED_TS,
        )
        assert isinstance(ctx, ForecastContext)
        assert ctx.current_regime == "EXPANSION"
        assert ctx.regime_confidence == 1.0
        assert ctx.news_mood == "positive"
        assert ctx.news_confidence == 1.0
        assert ctx.fomc_mood == "hawkish"
        assert ctx.fomc_confidence == 1.0
        assert ctx.source_variable == "CPI"
        assert len(ctx.recent_events) == 1
        assert ctx.data_date_range == ("2020-01-31", "2020-12-31")

    def test_deterministic(self, sample_data: pd.DataFrame) -> None:
        builder = ForecastContextBuilder(
            regime_detector=_MockRegimeDetector("CONTRACTION"),
        )
        ctx1 = builder.build(source_variable="CPI", training_data=sample_data, _timestamp=_PINNED_TS)
        ctx2 = builder.build(source_variable="CPI", training_data=sample_data, _timestamp=_PINNED_TS)
        assert ctx1 == ctx2

    def test_timestamp_is_iso_format(self, sample_data: pd.DataFrame) -> None:
        builder = ForecastContextBuilder()
        ctx = builder.build(source_variable="CPI", training_data=sample_data)
        datetime.datetime.fromisoformat(ctx.context_timestamp)


# ---------------------------------------------------------------------------
# ForecastContextBuilder — graceful degradation
# ---------------------------------------------------------------------------


class TestBuilderGracefulDegradation:

    def test_no_components(self, sample_data: pd.DataFrame) -> None:
        builder = ForecastContextBuilder()
        ctx = builder.build(source_variable="CPI", training_data=sample_data)
        assert ctx.current_regime is None
        assert ctx.regime_confidence == 0.0
        assert ctx.news_mood is None
        assert ctx.news_confidence == 0.0
        assert ctx.fomc_mood is None
        assert ctx.fomc_confidence == 0.0

    def test_regime_only(self, sample_data: pd.DataFrame) -> None:
        builder = ForecastContextBuilder(
            regime_detector=_MockRegimeDetector("RECOVERY"),
        )
        ctx = builder.build(source_variable="CPI", training_data=sample_data)
        assert ctx.current_regime == "RECOVERY"
        assert ctx.regime_confidence > 0
        assert ctx.news_mood is None
        assert ctx.fomc_mood is None

    def test_news_only(self, sample_data: pd.DataFrame) -> None:
        builder = ForecastContextBuilder(
            news_analyzer=_MockNewsSentimentAnalyzer("negative", 0.6),
        )
        ctx = builder.build(
            source_variable="CPI",
            training_data=sample_data,
            news_texts=["Bad news"],
        )
        assert ctx.current_regime is None
        assert ctx.news_mood == "negative"
        assert ctx.fomc_mood is None

    def test_news_without_texts(self, sample_data: pd.DataFrame) -> None:
        builder = ForecastContextBuilder(
            news_analyzer=_MockNewsSentimentAnalyzer("positive", 0.9),
        )
        ctx = builder.build(source_variable="CPI", training_data=sample_data)
        assert ctx.news_mood is None
        assert ctx.news_confidence == 0.0

    def test_fomc_only(self, sample_data: pd.DataFrame) -> None:
        builder = ForecastContextBuilder(
            fomc_analyzer=_MockFOMCSentimentAnalyzer("dovish", 0.8),
        )
        ctx = builder.build(
            source_variable="CPI",
            training_data=sample_data,
            fomc_texts=["Dovish statement"],
            _timestamp=_PINNED_TS,
        )
        assert ctx.current_regime is None
        assert ctx.news_mood is None
        assert ctx.fomc_mood == "dovish"
        assert ctx.fomc_confidence == 1.0


# ---------------------------------------------------------------------------
# ForecastContextBuilder — sentiment aggregation
# ---------------------------------------------------------------------------


class TestSentimentAggregation:

    def test_news_majority_positive(self, sample_data: pd.DataFrame) -> None:
        builder = ForecastContextBuilder(
            news_analyzer=_MockNewsSentimentAnalyzer("positive", 0.9),
        )
        ctx = builder.build(
            source_variable="CPI",
            training_data=sample_data,
            news_texts=["a", "b", "c"],
        )
        assert ctx.news_mood == "positive"

    def test_news_tie_becomes_neutral(self, sample_data: pd.DataFrame) -> None:
        class _MixedNews:
            def analyze_batch(self, texts: list[str]) -> list[Any]:
                class _P:
                    label = "positive"
                    confidence = 0.7
                class _N:
                    label = "negative"
                    confidence = 0.7
                class _Neut:
                    label = "neutral"
                    confidence = 0.7
                return [_P(), _N(), _Neut()]
        builder = ForecastContextBuilder(
            news_analyzer=_MixedNews(),  # type: ignore[arg-type]
        )
        ctx = builder.build(
            source_variable="CPI",
            training_data=sample_data,
            news_texts=["a", "b", "c"],
        )
        assert ctx.news_mood == "neutral"

    def test_fomc_majority_hawkish(self, sample_data: pd.DataFrame) -> None:
        builder = ForecastContextBuilder(
            fomc_analyzer=_MockFOMCSentimentAnalyzer("hawkish", 0.8),
        )
        ctx = builder.build(
            source_variable="CPI",
            training_data=sample_data,
            fomc_texts=["a", "b"],
        )
        assert ctx.fomc_mood == "hawkish"

    def test_fomc_tie_becomes_neutral(self, sample_data: pd.DataFrame) -> None:
        class _MixedFOMC:
            def analyze(self, text: str) -> Any:
                class _R:
                    pass
                mapping = {"a": "hawkish", "b": "dovish", "c": "neutral"}
                _R.label = mapping.get(text, "neutral")
                _R.confidence = 0.7
                return _R()
        builder = ForecastContextBuilder(
            fomc_analyzer=_MixedFOMC(),  # type: ignore[arg-type]
        )
        ctx = builder.build(
            source_variable="CPI",
            training_data=sample_data,
            fomc_texts=["a", "b", "c"],
        )
        assert ctx.fomc_mood == "neutral"


# ---------------------------------------------------------------------------
# ForecastContextBuilder — date range
# ---------------------------------------------------------------------------


class TestDateRangeResolution:

    def test_uses_ds_column(self) -> None:
        data = pd.DataFrame({
            "ds": pd.date_range("2024-01-01", periods=5, freq="ME"),
            "y": [1.0] * 5,
        })
        builder = ForecastContextBuilder()
        ctx = builder.build(source_variable="CPI", training_data=data)
        assert ctx.data_date_range == ("2024-01-31", "2024-05-31")

    def test_uses_date_column(self) -> None:
        data = pd.DataFrame({
            "Date": pd.date_range("2023-06-01", periods=3, freq="ME"),
            "y": [1.0] * 3,
        })
        builder = ForecastContextBuilder()
        ctx = builder.build(source_variable="CPI", training_data=data)
        assert ctx.data_date_range == ("2023-06-30", "2023-08-31")

    def test_empty_when_no_date_column(self) -> None:
        data = pd.DataFrame({"a": [1, 2, 3]})
        builder = ForecastContextBuilder()
        ctx = builder.build(source_variable="CPI", training_data=data)
        assert ctx.data_date_range == ("", "")

    def test_empty_when_no_rows(self) -> None:
        data = pd.DataFrame({"ds": pd.Series(dtype="datetime64[ns]"), "y": pd.Series(dtype="float64")})
        builder = ForecastContextBuilder()
        ctx = builder.build(source_variable="CPI", training_data=data)
        assert ctx.data_date_range == ("", "")


# ---------------------------------------------------------------------------
# ForecastContextBuilder — regime confidence
# ---------------------------------------------------------------------------


class TestRegimeConfidence:

    def test_confidence_from_label_frequency(self) -> None:
        labels = pd.Series(
            ["EXPANSION"] * 8 + ["CONTRACTION"] * 2,
            index=pd.date_range("2025-01-01", periods=10, freq="ME"),
        )
        detector = _MockRegimeDetector("EXPANSION")
        detector._labels = labels  # type: ignore[assignment]
        builder = ForecastContextBuilder(regime_detector=detector)
        data = pd.DataFrame({"ds": pd.date_range("2025-01-01", periods=10, freq="ME"), "y": [1.0] * 10})
        ctx = builder.build(source_variable="CPI", training_data=data, _timestamp=_PINNED_TS)
        # Latest label is CONTRACTION; confidence is frequency of that label
        assert ctx.current_regime == "CONTRACTION"
        assert ctx.regime_confidence == 0.2
