from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from transformers import Pipeline

_MODEL_NAME = "gtfintechlab/FOMC-RoBERTa"
_LABEL_MAP: dict[str, str] = {
    "LABEL_0": "dovish",
    "LABEL_1": "hawkish",
    "LABEL_2": "neutral",
}


@dataclass(frozen=True)
class SentimentResult:
    text: str
    label: str
    confidence: float


class FOMCSentimentAnalyzer:
    """Thin adapter around ``gtfintechlab/FOMC-RoBERTa`` for
    hawkish / dovish / neutral classification of FOMC texts.

    Lazy-loads the model on first call.  Deterministic at inference
    (no dropout, fixed seed).
    """

    def __init__(self, device: int = -1) -> None:
        self._device = device
        self._pipeline: Pipeline | None = None

    def _load_pipeline(self) -> None:
        try:
            from transformers import pipeline
        except ImportError:
            raise ImportError(
                "The 'transformers' library is required for FOMCSentimentAnalyzer. "
                "Install it with: pip install transformers torch"
            )
        self._pipeline = pipeline(
            "text-classification",
            model=_MODEL_NAME,
            device=self._device,
        )

    @property
    def pipeline(self) -> Pipeline:
        if self._pipeline is None:
            self._load_pipeline()
        return self._pipeline

    @lru_cache(maxsize=512)
    def _classify(self, text: str) -> tuple[str, float]:
        result = self.pipeline(text, truncation=True)[0]
        label = _LABEL_MAP.get(result["label"], result["label"])
        return label, result["score"]

    def analyze(self, text: str) -> SentimentResult:
        if not text or not text.strip():
            return SentimentResult(text=text, label="neutral", confidence=0.0)
        label, confidence = self._classify(text)
        return SentimentResult(text=text, label=label, confidence=confidence)

    def analyze_batch(self, texts: list[str]) -> list[SentimentResult]:
        return [self.analyze(t) for t in texts]
