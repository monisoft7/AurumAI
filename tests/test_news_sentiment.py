"""Tests for the news sentiment analyzer adapter."""

from unittest.mock import MagicMock, patch

import pytest

from nlp.news_sentiment import NewsSentimentAnalyzer, SentimentResult


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_pipeline() -> MagicMock:
    return MagicMock()


def _make_analyzer(pipe: MagicMock) -> NewsSentimentAnalyzer:
    analyzer = NewsSentimentAnalyzer()
    analyzer._pipeline = pipe
    return analyzer


# ---------------------------------------------------------------------------
# SentimentResult dataclass
# ---------------------------------------------------------------------------


class TestSentimentResult:

    def test_is_frozen(self) -> None:
        r = SentimentResult(text="test", label="positive", confidence=0.95)
        with pytest.raises((AttributeError, TypeError)):
            r.label = "negative"


# ---------------------------------------------------------------------------
# Label mapping
# ---------------------------------------------------------------------------


class TestLabelMapping:

    def test_positive_label(self, mock_pipeline: MagicMock) -> None:
        mock_pipeline.return_value = [{"label": "POSITIVE", "score": 0.92}]
        analyzer = _make_analyzer(mock_pipeline)
        result = analyzer.analyze("Strong earnings growth.")
        assert result.label == "positive"
        assert result.confidence == 0.92

    def test_negative_label(self, mock_pipeline: MagicMock) -> None:
        mock_pipeline.return_value = [{"label": "NEGATIVE", "score": 0.88}]
        analyzer = _make_analyzer(mock_pipeline)
        result = analyzer.analyze("Profits declined sharply.")
        assert result.label == "negative"

    def test_neutral_label(self, mock_pipeline: MagicMock) -> None:
        mock_pipeline.return_value = [{"label": "NEUTRAL", "score": 0.75}]
        analyzer = _make_analyzer(mock_pipeline)
        result = analyzer.analyze("The economy is stable.")
        assert result.label == "neutral"


# ---------------------------------------------------------------------------
# analyze()
# ---------------------------------------------------------------------------


class TestAnalyze:

    def test_returns_sentiment_result(self, mock_pipeline: MagicMock) -> None:
        mock_pipeline.return_value = [{"label": "NEUTRAL", "score": 0.65}]
        analyzer = _make_analyzer(mock_pipeline)
        result = analyzer.analyze("Inflation is moderate.")
        assert isinstance(result, SentimentResult)
        assert result.text == "Inflation is moderate."

    def test_empty_text_returns_neutral(self, mock_pipeline: MagicMock) -> None:
        analyzer = _make_analyzer(mock_pipeline)
        result = analyzer.analyze("")
        assert result.label == "neutral"
        assert result.confidence == 0.0
        mock_pipeline.assert_not_called()

    def test_whitespace_text_returns_neutral(self, mock_pipeline: MagicMock) -> None:
        analyzer = _make_analyzer(mock_pipeline)
        result = analyzer.analyze("   ")
        assert result.label == "neutral"
        assert result.confidence == 0.0
        mock_pipeline.assert_not_called()

    def test_passes_truncation_flag(self, mock_pipeline: MagicMock) -> None:
        mock_pipeline.return_value = [{"label": "NEUTRAL", "score": 0.5}]
        analyzer = _make_analyzer(mock_pipeline)
        analyzer.analyze("Some text.")
        mock_pipeline.assert_called_once_with("Some text.", truncation=True)


# ---------------------------------------------------------------------------
# analyze_batch()
# ---------------------------------------------------------------------------


class TestAnalyzeBatch:

    def test_returns_list(self, mock_pipeline: MagicMock) -> None:
        mock_pipeline.return_value = [
            {"label": "POSITIVE", "score": 0.9},
            {"label": "NEGATIVE", "score": 0.8},
        ]
        analyzer = _make_analyzer(mock_pipeline)
        results = analyzer.analyze_batch(["Good news.", "Bad news."])
        assert len(results) == 2
        assert results[0].label == "positive"
        assert results[1].label == "negative"

    def test_empty_batch(self, mock_pipeline: MagicMock) -> None:
        analyzer = _make_analyzer(mock_pipeline)
        results = analyzer.analyze_batch([])
        assert results == []
        mock_pipeline.assert_not_called()

    def test_passes_batch_size(self, mock_pipeline: MagicMock) -> None:
        mock_pipeline.return_value = [
            {"label": "NEUTRAL", "score": 0.5},
        ]
        analyzer = _make_analyzer(mock_pipeline)
        analyzer.analyze_batch(["Text."])
        mock_pipeline.assert_called_once_with(
            ["Text."], truncation=True, batch_size=32
        )


# ---------------------------------------------------------------------------
# Deterministic behavior
# ---------------------------------------------------------------------------


class TestDeterministic:

    def test_same_input_same_output(self, mock_pipeline: MagicMock) -> None:
        mock_pipeline.return_value = [{"label": "POSITIVE", "score": 0.90}]
        analyzer = _make_analyzer(mock_pipeline)
        r1 = analyzer.analyze("Strong revenue growth.")
        r2 = analyzer.analyze("Strong revenue growth.")
        assert r1.label == r2.label
        assert r1.confidence == r2.confidence


# ---------------------------------------------------------------------------
# Model loading
# ---------------------------------------------------------------------------


class TestModelLoading:

    def test_raises_import_error_without_transformers(self) -> None:
        analyzer = NewsSentimentAnalyzer()
        with patch.object(analyzer, "_load_pipeline") as mock_load:
            mock_load.side_effect = ImportError(
                "The 'transformers' library is required"
            )
            with pytest.raises(ImportError, match="transformers"):
                analyzer.pipeline

    def test_pipeline_is_lazy(self) -> None:
        analyzer = NewsSentimentAnalyzer()
        assert analyzer._pipeline is None

    def test_custom_model_name(self) -> None:
        analyzer = NewsSentimentAnalyzer(model_name="ProsusAI/finbert")
        assert analyzer._model_name == "ProsusAI/finbert"
