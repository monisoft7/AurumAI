from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from knowledge.regime.constants import (
    NORMAL_GROWTH,
    INFLATIONARY,
    STAGFLATIONARY,
    DEFLATIONARY_CRISIS,
    GEOPOLITICAL_STRESS,
    STRUCTURAL_REGIME_CHANGE,
)


class RegimeTransitionDetector:
    """Detects and characterizes regime transitions.

    Computes transition probabilities between consecutive periods,
    identifies transition windows (confidence < threshold), and
    characterizes the transition type.
    """

    def __init__(self, confidence_threshold: float = 0.5) -> None:
        self._threshold = confidence_threshold

    def detect(
        self,
        regime_labels: pd.Series,
        regime_probabilities: pd.DataFrame | None = None,
    ) -> pd.DataFrame:
        if regime_probabilities is not None:
            return self._detect_from_probs(regime_labels, regime_probabilities)
        return self._detect_from_labels(regime_labels)

    def _detect_from_probs(
        self,
        regime_labels: pd.Series,
        regime_probabilities: pd.DataFrame,
    ) -> pd.DataFrame:
        records: list[dict[str, Any]] = []
        dates = regime_labels.index
        prev_regime: str | None = None

        for i, date in enumerate(dates):
            current = str(regime_labels.iloc[i])
            probs = regime_probabilities.loc[date].to_dict() if date in regime_probabilities.index else {}
            max_prob = max(probs.values()) if probs else 0.0
            in_transition = max_prob < self._threshold

            prob_values = np.array(list(probs.values())) if probs else np.array([0.0])
            entropy = float(-np.sum(prob_values * np.log(prob_values + 1e-12)))

            regime_changed = (prev_regime is not None and current != prev_regime)

            records.append({
                "date": str(date),
                "regime": current,
                "max_probability": round(max_prob, 4),
                "in_transition": in_transition,
                "entropy": round(entropy, 4),
                "regime_changed": regime_changed,
                "prev_regime": prev_regime or "",
                "transition_type": self._classify_transition(
                    prev_regime or "", current,
                ),
            })
            prev_regime = current

        return pd.DataFrame(records)

    def _detect_from_labels(self, regime_labels: pd.Series) -> pd.DataFrame:
        records: list[dict[str, Any]] = []
        dates = regime_labels.index
        prev_regime: str | None = None

        for i, date in enumerate(dates):
            current = str(regime_labels.iloc[i])
            regime_changed = (prev_regime is not None and current != prev_regime)

            records.append({
                "date": str(date),
                "regime": current,
                "max_probability": 0.0,
                "in_transition": False,
                "entropy": 0.0,
                "regime_changed": regime_changed,
                "prev_regime": prev_regime or "",
                "transition_type": self._classify_transition(
                    prev_regime or "", current,
                ),
            })
            prev_regime = current

        return pd.DataFrame(records)

    def _classify_transition(self, prev: str, current: str) -> str:
        if prev == current or not prev or not current:
            return "none"
        deterioration = {
            (NORMAL_GROWTH, INFLATIONARY),
            (NORMAL_GROWTH, STAGFLATIONARY),
            (NORMAL_GROWTH, DEFLATIONARY_CRISIS),
            (INFLATIONARY, STAGFLATIONARY),
            (INFLATIONARY, DEFLATIONARY_CRISIS),
            (STAGFLATIONARY, DEFLATIONARY_CRISIS),
            (NORMAL_GROWTH, GEOPOLITICAL_STRESS),
            (INFLATIONARY, GEOPOLITICAL_STRESS),
            (STAGFLATIONARY, GEOPOLITICAL_STRESS),
            (DEFLATIONARY_CRISIS, GEOPOLITICAL_STRESS),
        }
        improvement = {
            (DEFLATIONARY_CRISIS, STAGFLATIONARY),
            (DEFLATIONARY_CRISIS, INFLATIONARY),
            (DEFLATIONARY_CRISIS, NORMAL_GROWTH),
            (STAGFLATIONARY, INFLATIONARY),
            (STAGFLATIONARY, NORMAL_GROWTH),
            (INFLATIONARY, NORMAL_GROWTH),
            (GEOPOLITICAL_STRESS, NORMAL_GROWTH),
            (GEOPOLITICAL_STRESS, INFLATIONARY),
            (GEOPOLITICAL_STRESS, STAGFLATIONARY),
            (GEOPOLITICAL_STRESS, DEFLATIONARY_CRISIS),
        }
        if (prev, current) in deterioration:
            return "deterioration"
        if (prev, current) in improvement:
            return "improvement"
        if current == STRUCTURAL_REGIME_CHANGE:
            return "regime_break"
        if prev == STRUCTURAL_REGIME_CHANGE and current != STRUCTURAL_REGIME_CHANGE:
            return "recovery_from_break"
        return "other"

    def get_transition_windows(
        self, transition_df: pd.DataFrame,
    ) -> list[dict[str, Any]]:
        windows: list[dict[str, Any]] = []
        in_window = False
        start_date = ""
        window_regimes: list[str] = []

        for _, row in transition_df.iterrows():
            if row["in_transition"]:
                if not in_window:
                    in_window = True
                    start_date = str(row["date"])
                    window_regimes = [str(row["regime"])]
                else:
                    if str(row["regime"]) not in window_regimes:
                        window_regimes.append(str(row["regime"]))
            else:
                if in_window:
                    windows.append({
                        "start_date": start_date,
                        "end_date": str(row["date"]),
                        "regimes_in_window": window_regimes,
                        "duration_days": len(window_regimes),
                        "final_regime": str(row["regime"]),
                    })
                in_window = False
                window_regimes = []

        return windows
