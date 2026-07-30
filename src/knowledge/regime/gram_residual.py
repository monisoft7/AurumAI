from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
from sklearn.linear_model import LinearRegression


class GramResidualAnalyzer:
    """Computes GRAM (Gold Return Attribution Model) residuals.

    Runs rolling regression of gold returns against regime-specific
    dominant indicators and tracks unexplained variance.  A growing
    residual trend signals a possible Structural Regime Change.
    """

    def __init__(
        self,
        window: int = 36,
        min_periods: int = 12,
    ) -> None:
        self._window = window
        self._min_periods = min_periods
        self._results: pd.DataFrame | None = None
        self._model: LinearRegression | None = None

    def fit(
        self,
        gold_returns: pd.Series,
        indicators: pd.DataFrame,
    ) -> GramResidualAnalyzer:
        records: list[dict[str, Any]] = []
        common_idx = gold_returns.index.intersection(indicators.index)
        y = gold_returns.loc[common_idx]
        X = indicators.loc[common_idx]

        for i in range(len(y)):
            end = i + 1
            start = max(0, end - self._window)
            if end - start < self._min_periods:
                continue

            y_window = y.iloc[start:end]
            X_window = X.iloc[start:end]
            if len(y_window) < 2 or X_window.shape[1] < 1:
                continue

            model = LinearRegression()
            try:
                model.fit(X_window, y_window)
            except (ValueError, np.linalg.LinAlgError):
                continue

            y_pred = float(model.predict(X.iloc[[i]])[0])
            y_actual = float(y.iloc[i])
            residual = y_actual - y_pred

            records.append({
                "date": str(y.index[i]),
                "actual_return": round(y_actual, 6),
                "predicted_return": round(y_pred, 6),
                "residual": round(residual, 6),
                "abs_residual": round(abs(residual), 6),
                "r_squared": round(model.score(X_window, y_window), 4),
                "n_obs": len(y_window),
            })

        df = pd.DataFrame(records)
        if not df.empty:
            df["residual_zscore"] = (df["residual"] - df["residual"].expanding().mean()) / df["residual"].expanding().std().replace(0, np.nan)
            df["residual_trend"] = self._compute_trend(df["residual"].values)

        self._results = df
        self._model = model
        return self

    def _compute_trend(self, values: np.ndarray) -> list[str]:
        if len(values) < 3:
            return ["stable"] * len(values)
        trends: list[str] = []
        for i in range(len(values)):
            if i < 2:
                trends.append("stable")
            else:
                recent = values[max(0, i - 5):i + 1]
                slope = np.polyfit(range(len(recent)), recent, 1)[0]
                if slope > 0.01:
                    trends.append("growing")
                elif slope < -0.01:
                    trends.append("shrinking")
                else:
                    trends.append("stable")
        return trends

    def get_residual_data(self) -> pd.DataFrame:
        if self._results is None:
            raise RuntimeError("Must call fit() before get_residual_data()")
        return self._results.copy()

    def get_current_status(self) -> dict[str, Any]:
        if self._results is None or self._results.empty:
            return {
                "residual": 0.0,
                "abs_residual": 0.0,
                "r_squared": 0.0,
                "residual_zscore": 0.0,
                "residual_trend": "unknown",
                "regime_break_detected": False,
            }
        last = self._results.iloc[-1]
        recent = self._results.tail(6)
        growing_count = sum(1 for t in recent["residual_trend"] if t == "growing")
        return {
            "residual": float(last["residual"]),
            "abs_residual": float(last["abs_residual"]),
            "r_squared": float(last["r_squared"]),
            "residual_zscore": float(last.get("residual_zscore", 0.0)),
            "residual_trend": str(last.get("residual_trend", "stable")),
            "regime_break_detected": growing_count >= 4,
        }

    def flag_regime_break(self, threshold: float = 2.0) -> bool:
        if self._results is None or self._results.empty:
            return False
        recent = self._results.tail(3)
        return bool((recent["abs_residual"] > threshold).any())
