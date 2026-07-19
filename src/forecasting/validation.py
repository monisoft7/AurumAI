from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

import pandas as pd

from forecasting.models import ForecastPoint, ForecastResult

_MAPE_THRESHOLD = 20.0
_COVERAGE_THRESHOLD = 0.80
_DA_THRESHOLD = 0.50

_STRATEGIES = ("walk_forward", "expanding_window")


@dataclass(frozen=True)
class ForecastValidationReport:
    validation_strategy: str
    metrics: dict[str, float]
    horizon: int
    sample_size: int
    passed: bool
    notes: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "validation_strategy": self.validation_strategy,
            "metrics": dict(self.metrics),
            "horizon": self.horizon,
            "sample_size": self.sample_size,
            "passed": self.passed,
            "notes": self.notes,
        }


class ForecastValidator:

    def validate(
        self,
        actual_data: pd.DataFrame,
        forecast_results: dict[str, ForecastResult],
        strategy: str = "walk_forward",
        horizon: int = 1,
    ) -> ForecastValidationReport:
        if strategy not in _STRATEGIES:
            raise ValueError(
                f"Unknown validation strategy: {strategy!r}. "
                f"Must be one of {_STRATEGIES}"
            )
        if horizon < 1:
            raise ValueError("horizon must be >= 1")

        pairs = self._align(actual_data, forecast_results)

        if not pairs:
            return ForecastValidationReport(
                validation_strategy=strategy,
                metrics={
                    "mae": 0.0,
                    "rmse": 0.0,
                    "mape": 0.0,
                    "directional_accuracy": 0.0,
                    "coverage": 0.0,
                },
                horizon=horizon,
                sample_size=0,
                passed=False,
                notes="No aligned forecast- actual pairs available for validation",
            )

        abs_errors: list[float] = []
        sq_errors: list[float] = []
        abs_pct_errors: list[float] = []
        in_interval: list[float] = []

        for _ds, actual_y, pt in pairs:
            e = actual_y - pt.y
            abs_errors.append(abs(e))
            sq_errors.append(e * e)

            if abs(actual_y) > 1e-12:
                abs_pct_errors.append(abs(e / actual_y) * 100.0)

            in_interval.append(1.0 if pt.y_lo <= actual_y <= pt.y_hi else 0.0)

        direction_correct: list[float] = []
        if len(pairs) >= 2:
            for i in range(1, len(pairs)):
                actual_diff = pairs[i][1] - pairs[i - 1][1]
                pred_diff = pairs[i][2].y - pairs[i - 1][2].y
                if actual_diff == 0 and pred_diff == 0:
                    direction_correct.append(1.0)
                elif (actual_diff > 0 and pred_diff > 0) or (
                    actual_diff < 0 and pred_diff < 0
                ):
                    direction_correct.append(1.0)
                else:
                    direction_correct.append(0.0)

        n = len(abs_errors)
        mae = sum(abs_errors) / n if n > 0 else 0.0
        rmse = math.sqrt(sum(sq_errors) / n) if n > 0 else 0.0
        mape = (
            sum(abs_pct_errors) / len(abs_pct_errors) if abs_pct_errors else 0.0
        )
        coverage = (
            sum(in_interval) / len(in_interval) if in_interval else 0.0
        )
        da = (
            sum(direction_correct) / len(direction_correct)
            if direction_correct
            else 0.0
        )

        metrics: dict[str, float] = {
            "mae": round(mae, 4),
            "rmse": round(rmse, 4),
            "mape": round(mape, 4),
            "directional_accuracy": round(da, 4),
            "coverage": round(coverage, 4),
        }

        passed = bool(
            mape < _MAPE_THRESHOLD
            and coverage > _COVERAGE_THRESHOLD
            and da > _DA_THRESHOLD
        )

        notes = self._build_notes(metrics, n, passed)

        return ForecastValidationReport(
            validation_strategy=strategy,
            metrics=metrics,
            horizon=horizon,
            sample_size=n,
            passed=passed,
            notes=notes,
        )

    @staticmethod
    def _align(
        actual_data: pd.DataFrame,
        forecast_results: dict[str, ForecastResult],
    ) -> list[tuple[str, float, ForecastPoint]]:
        if actual_data.empty or not forecast_results:
            return []

        actual_map: dict[str, float] = {}
        for _idx, row in actual_data.iterrows():
            ds = str(row.get("ds", ""))
            if ds:
                actual_map[ds] = float(row["y"])

        if not actual_map:
            return []

        first_result = next(iter(forecast_results.values()))
        pairs: list[tuple[str, float, ForecastPoint]] = []
        for pt in first_result.points:
            if pt.ds in actual_map:
                pairs.append((pt.ds, actual_map[pt.ds], pt))

        return pairs

    @staticmethod
    def _build_notes(
        metrics: dict[str, float], n: int, passed: bool
    ) -> str:
        parts = [f"Validation over {n} aligned forecast points."]
        if passed:
            parts.append("All thresholds met.")
        else:
            parts.append("Thresholds not met.")
        return " ".join(parts)
