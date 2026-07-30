from __future__ import annotations

from statistics import mean
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
        criteria_scores: dict[str, CriterionScore] | None = None,
        persistence: CriterionScore | None = None,
        breadth: CriterionScore | None = None,
        magnitude_z: float = 0.0,
        narrative: CriterionScore | None = None,
        volume: CriterionScore | None = None,
    ) -> tuple[str, float, str]:
        scores = self._collect_scores(
            criteria_scores, persistence, breadth, magnitude_z, narrative, volume,
        )
        if criteria_scores is not None and "magnitude" in criteria_scores:
            mag = criteria_scores["magnitude"]
            magnitude_z = mag.score * 3.0 * (1 if mag.detail and "z-score=" in mag.detail else 1)
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
        avg_score = mean([s.score for s in scores]) if scores else 0.0

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

    def _collect_scores(
        self,
        criteria_scores: dict[str, CriterionScore] | None,
        persistence: CriterionScore | None,
        breadth: CriterionScore | None,
        magnitude_z: float,
        narrative: CriterionScore | None,
        volume: CriterionScore | None,
    ) -> list[CriterionScore]:
        if criteria_scores is not None:
            return list(criteria_scores.values())

        scores: list[CriterionScore] = []
        if persistence is not None:
            scores.append(persistence)
        if breadth is not None:
            scores.append(breadth)
        mag_passed = abs(magnitude_z) >= 2.0
        mag_score = min(abs(magnitude_z) / 3.0, 1.0) if abs(magnitude_z) > 0 else 0.0
        scores.append(CriterionScore(
            criterion="magnitude",
            score=round(mag_score, 4),
            threshold=2.0,
            passed=mag_passed,
            detail=f"z-score={magnitude_z:.2f}",
        ))
        if narrative is not None:
            scores.append(narrative)
        if volume is not None:
            scores.append(volume)
        return scores

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
