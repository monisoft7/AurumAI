from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from transformers import Pipeline

_DEFAULT_MODEL = "tabularisai/ModernFinBERT"


@dataclass(frozen=True)
class SentimentResult:
    text: str
    label: str
    confidence: float


class NewsSentimentAnalyzer:
    """Thin adapter for financial news sentiment analysis.

    Defaults to ``tabularisai/ModernFinBERT`` (Apache 2.0) which
    outperforms FinBERT by up to 48% on benchmark datasets.

    Lazy-loads the model on first call.  Batch inference uses the
    pipeline's native batching for efficiency.
    """

    def __init__(
        self, model_name: str = _DEFAULT_MODEL, device: int = -1
    ) -> None:
        self._model_name = model_name
        self._device = device
        self._pipeline: Pipeline | None = None

    def _load_pipeline(self) -> None:
        try:
            from transformers import pipeline
        except ImportError:
            raise ImportError(
                "The 'transformers' library is required for "
                "NewsSentimentAnalyzer. "
                "Install it with: pip install transformers torch"
            )
        self._pipeline = pipeline(
            "text-classification",
            model=self._model_name,
            device=self._device,
        )

    @property
    def pipeline(self) -> Pipeline:
        if self._pipeline is None:
            self._load_pipeline()
        return self._pipeline

    def analyze(self, text: str) -> SentimentResult:
        if not text or not text.strip():
            return SentimentResult(text=text, label="neutral", confidence=0.0)
        result = self.pipeline(text, truncation=True)[0]
        label = result["label"].lower()
        return SentimentResult(text=text, label=label, confidence=result["score"])

    def analyze_batch(self, texts: list[str]) -> list[SentimentResult]:
        if not texts:
            return []
        results = self.pipeline(texts, truncation=True, batch_size=32)
        return [
            SentimentResult(
                text=texts[i],
                label=r["label"].lower(),
                confidence=r["score"],
            )
            for i, r in enumerate(results)
        ]
