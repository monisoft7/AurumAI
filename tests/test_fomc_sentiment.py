"""Tests for the FOMC sentiment analyzer adapter."""

from unittest.mock import MagicMock, patch

import pytest

from nlp.fomc_sentiment import (
    FOMCSentimentAnalyzer,
    SentimentResult,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_pipeline() -> MagicMock:
    pipe = MagicMock()
    # Single-text mode returns a list with one dict
    pipe.side_effect = None
    return pipe


def _make_analyzer(pipe: MagicMock) -> FOMCSentimentAnalyzer:
    analyzer = FOMCSentimentAnalyzer()
    analyzer._pipeline = pipe
    return analyzer


# ---------------------------------------------------------------------------
# SentimentResult dataclass
# ---------------------------------------------------------------------------


class TestSentimentResult:

    def test_is_frozen(self) -> None:
        r = SentimentResult(text="test", label="hawkish", confidence=0.95)
        with pytest.raises((AttributeError, TypeError)):
            r.label = "dovish"


# ---------------------------------------------------------------------------
# Label mapping
# ---------------------------------------------------------------------------


class TestLabelMapping:

    def test_hawkish_label(self, mock_pipeline: MagicMock) -> None:
        mock_pipeline.return_value = [{"label": "LABEL_1", "score": 0.92}]
        analyzer = _make_analyzer(mock_pipeline)
        result = analyzer.analyze("Tightening is needed.")
        assert result.label == "hawkish"
        assert result.confidence == 0.92

    def test_dovish_label(self, mock_pipeline: MagicMock) -> None:
        mock_pipeline.return_value = [{"label": "LABEL_0", "score": 0.88}]
        analyzer = _make_analyzer(mock_pipeline)
        result = analyzer.analyze("We should ease policy.")
        assert result.label == "dovish"

    def test_neutral_label(self, mock_pipeline: MagicMock) -> None:
        mock_pipeline.return_value = [{"label": "LABEL_2", "score": 0.75}]
        analyzer = _make_analyzer(mock_pipeline)
        result = analyzer.analyze("The economy is stable.")
        assert result.label == "neutral"


# ---------------------------------------------------------------------------
# analyze()
# ---------------------------------------------------------------------------


class TestAnalyze:

    def test_returns_sentiment_result(self, mock_pipeline: MagicMock) -> None:
        mock_pipeline.return_value = [{"label": "LABEL_2", "score": 0.65}]
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
        mock_pipeline.return_value = [{"label": "LABEL_2", "score": 0.5}]
        analyzer = _make_analyzer(mock_pipeline)
        analyzer.analyze("Some text.")
        mock_pipeline.assert_called_once_with("Some text.", truncation=True)


# ---------------------------------------------------------------------------
# analyze_batch()
# ---------------------------------------------------------------------------


class TestAnalyzeBatch:

    def test_returns_list(self, mock_pipeline: MagicMock) -> None:
        def side_effect(text: str, **kwargs: object) -> list[dict]:
            return [{"label": "LABEL_2", "score": 0.5}]

        mock_pipeline.side_effect = side_effect
        analyzer = _make_analyzer(mock_pipeline)
        results = analyzer.analyze_batch(["a", "b", "c"])
        assert len(results) == 3
        assert all(isinstance(r, SentimentResult) for r in results)

    def test_empty_batch(self, mock_pipeline: MagicMock) -> None:
        analyzer = _make_analyzer(mock_pipeline)
        results = analyzer.analyze_batch([])
        assert results == []


# ---------------------------------------------------------------------------
# Deterministic behavior
# ---------------------------------------------------------------------------


class TestDeterministic:

    def test_same_input_same_output(self, mock_pipeline: MagicMock) -> None:
        mock_pipeline.return_value = [{"label": "LABEL_1", "score": 0.90}]
        analyzer = _make_analyzer(mock_pipeline)
        r1 = analyzer.analyze("Rate hikes are appropriate.")
        r2 = analyzer.analyze("Rate hikes are appropriate.")
        assert r1.label == r2.label
        assert r1.confidence == r2.confidence


# ---------------------------------------------------------------------------
# Model loading
# ---------------------------------------------------------------------------


class TestModelLoading:

    def test_raises_import_error_without_transformers(self) -> None:
        analyzer = FOMCSentimentAnalyzer()
        with patch.object(analyzer, "_load_pipeline") as mock_load:
            mock_load.side_effect = ImportError(
                "The 'transformers' library is required"
            )
            with pytest.raises(ImportError, match="transformers"):
                analyzer.pipeline

    def test_pipeline_is_lazy(self) -> None:
        analyzer = FOMCSentimentAnalyzer()
        assert analyzer._pipeline is None
