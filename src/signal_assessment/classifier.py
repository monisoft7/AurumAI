from __future__ import annotations

from typing import Any

from signal_assessment.contracts import (
    ClassificationLabel,
    ClassifiedObservation,
    CriterionScore,
)

CRITERION_NAMES = ["persistence", "breadth", "magnitude", "narrative_fit", "volume_flow"]


class NoiseSignalClassifier:
    """Integrates the 5 Meth. §7 criteria into a single classification.

    Classification rules (per Meth. §7 and user requirements):
      - Signal: >= 3 of 5 criteria positive, or >= 2 positive with persistence confirmed
      - Weak Signal: >= 2 criteria positive but < 3, or persistence borderline
      - Watch: 1 criterion positive, or magnitude alone > 2sigma without other confirmation
      - Noise: <= 1 criterion positive, or magnitude < 1sigma with no narrative/volume
      - Ignore: zero criteria positive, magnitude < 0.5sigma, no relevance
    """

    def __init__(self, regime: str = "", knowledge_graph=None) -> None:
        self._regime = regime
        self._kg = knowledge_graph

    def classify(
        self,
        criteria_scores: dict[str, CriterionScore],
    ) -> tuple[str, float, str]:
        # Final Hardening (Group G): the legacy positional-arguments branch
        # (persistence/breadth/magnitude_z/narrative/volume) was removed --
        # every production and test caller passes ``criteria_scores``.
        scores = list(criteria_scores.values())
        magnitude_z = 0.0
        if criteria_scores and "magnitude" in criteria_scores:
            mag = criteria_scores["magnitude"]
            magnitude_z = mag.score * 3.0
            if mag.detail and "z-score=" in mag.detail:
                try:
                    magnitude_z = float(mag.detail.split("z-score=")[1].split(")")[0])
                except (ValueError, IndexError):
                    pass

        positive_count = sum(1 for s in scores if s.passed)
        persistence_passed = next(
            (s.passed for s in scores if s.criterion == "persistence"), False
        )
        magnitude_passed = abs(magnitude_z) >= 2.0

        if positive_count >= 3 or (positive_count >= 2 and persistence_passed):
            label = ClassificationLabel.SIGNAL
            confidence = min(0.5 + 0.1 * positive_count, 0.95)
            reason = self._build_reason("Signal", positive_count, scores)
        elif positive_count >= 2:
            label = ClassificationLabel.WEAK_SIGNAL
            confidence = min(0.3 + 0.1 * positive_count, 0.6)
            reason = self._build_reason("Weak Signal", positive_count, scores)
        elif positive_count == 1 or magnitude_passed:
            label = ClassificationLabel.WATCH
            confidence = min(0.2 + 0.1 * positive_count, 0.4)
            reason = self._build_reason("Watch", positive_count, scores)
        elif positive_count == 0 and abs(magnitude_z) < 0.5:
            label = ClassificationLabel.IGNORE
            confidence = 0.9
            reason = "no criteria met and negligible move magnitude"
        else:
            label = ClassificationLabel.NOISE
            confidence = min(0.5 + 0.1 * (3 - positive_count), 0.85)
            reason = self._build_reason("Noise", positive_count, scores)

        return label.value, round(confidence, 4), reason

    @staticmethod
    def _build_reason(label: str, positive_count: int, scores: list[CriterionScore]) -> str:
        passed = [s.criterion for s in scores if s.passed]
        failed = [s.criterion for s in scores if not s.passed]
        parts = [f"{label}: {positive_count}/{len(scores)} criteria met"]
        if passed:
            parts.append(f"passed={passed}")
        if failed:
            parts.append(f"failed={failed}")
        return " | ".join(parts)
