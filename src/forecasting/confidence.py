from __future__ import annotations

import statistics
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from forecasting.context import ForecastContext
    from forecasting.knowledge import ForecastPackage

_EPSILON = 1e-8


@dataclass(frozen=True)
class ForecastConfidence:
    spread_score: float
    agreement_score: float
    context_coherence: float
    overall: float

    def to_dict(self) -> dict[str, float]:
        return {
            "spread_score": self.spread_score,
            "agreement_score": self.agreement_score,
            "context_coherence": self.context_coherence,
            "overall": self.overall,
        }


class ForecastConfidenceComputer:

    def compute(
        self,
        package: "ForecastPackage",
        context: "ForecastContext",
    ) -> ForecastConfidence:
        spread = self._compute_spread_score(package)
        agreement = self._compute_agreement_score(package)
        coherence = self._compute_context_coherence(context)
        overall = 0.30 * spread + 0.40 * agreement + 0.30 * coherence
        overall = max(0.0, min(1.0, overall))
        return ForecastConfidence(
            spread_score=spread,
            agreement_score=agreement,
            context_coherence=coherence,
            overall=overall,
        )

    @staticmethod
    def _compute_spread_score(package: "ForecastPackage") -> float:
        results = package.results
        if not results:
            return 0.0

        widths: list[float] = []
        for result in results.values():
            for pt in result.points:
                y_abs = abs(pt.y) if abs(pt.y) > _EPSILON else _EPSILON
                rel_width = (pt.y_hi - pt.y_lo) / y_abs
                widths.append(rel_width)

        if not widths:
            return 0.0

        avg_width = sum(widths) / len(widths)
        return max(0.0, 1.0 - min(avg_width, 1.0))

    @staticmethod
    def _compute_agreement_score(package: "ForecastPackage") -> float:
        results = package.results
        if not results:
            return 0.0

        model_names = list(results.keys())
        if len(model_names) == 1:
            return 1.0

        n_points = len(results[model_names[0]].points)
        if n_points == 0:
            return 0.0

        point_scores: list[float] = []
        for i in range(n_points):
            y_values = []
            for name in model_names:
                pts = results[name].points
                if i < len(pts):
                    y_values.append(pts[i].y)

            if len(y_values) < 2:
                point_scores.append(1.0)
                continue

            mean_y = sum(y_values) / len(y_values)
            mean_abs = sum(abs(v) for v in y_values) / len(y_values)
            denom = mean_abs if mean_abs > _EPSILON else _EPSILON
            variance = sum((v - mean_y) ** 2 for v in y_values) / len(y_values)
            std_y = variance ** 0.5
            cv = std_y / denom
            score = max(0.0, min(1.0, 1.0 - cv))
            point_scores.append(score)

        return sum(point_scores) / len(point_scores) if point_scores else 0.0

    @staticmethod
    def _compute_context_coherence(context: "ForecastContext") -> float:
        scores: list[float] = [
            context.regime_confidence,
            context.news_confidence,
            context.fomc_confidence,
        ]
        return sum(scores) / len(scores) if scores else 0.0
