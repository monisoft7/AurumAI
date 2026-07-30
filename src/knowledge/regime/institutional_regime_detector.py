from __future__ import annotations

from datetime import datetime, timezone
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
    INSTITUTIONAL_REGIMES,
    REGIME_LABELS,
    DEFAULT_TRANSITION_THRESHOLD,
    DEFAULT_GPR_THRESHOLD,
    DEFAULT_GRAM_RESIDUAL_THRESHOLD,
)
from knowledge.regime.contracts import RegimeDiagnosis, TriggerLevel
from knowledge.regime.macro_regime_detector import (
    CONTRACTION,
    EXPANSION,
    LATE_CYCLE,
    RECOVERY,
    MacroRegimeDetector,
)


class InstitutionalRegimeDetector:
    """6-regime classifier matching Meth. §9 taxonomy.

    Uses MacroRegimeDetector (Markov 4-state) for the economic core
    (Normal Growth -> Inflationary -> Stagflationary -> Deflationary/Crisis),
    then overlays Geopolitical Stress (GPR threshold) and Structural
    Regime Change (GRAM residual trigger).
    """

    def __init__(
        self,
        gpr_threshold: float = DEFAULT_GPR_THRESHOLD,
        gram_residual_threshold: float = DEFAULT_GRAM_RESIDUAL_THRESHOLD,
        transition_threshold: float = DEFAULT_TRANSITION_THRESHOLD,
        random_state: int = 42,
    ) -> None:
        self._markov = MacroRegimeDetector(random_state=random_state)
        self._gpr_threshold = gpr_threshold
        self._gram_residual_threshold = gram_residual_threshold
        self._transition_threshold = transition_threshold
        self._results: pd.DataFrame | None = None
        self._regime_probs: pd.DataFrame | None = None
        self._last_composite_score: float = 0.0
        self._last_gpr_value: float = 0.0
        self._last_gram_value: float = 0.0
        self._last_diagnosis: RegimeDiagnosis | None = None

    def fit(
        self,
        composite_data: pd.DataFrame,
        gpr_series: pd.Series | None = None,
        gram_residual_series: pd.Series | None = None,
    ) -> InstitutionalRegimeDetector:
        self._last_diagnosis = None
        markov = self._markov.fit(composite_data)
        regime_df = markov.get_regime_data()
        regime_df = regime_df.set_index("Date")

        composite_values = regime_df.copy()
        composite_values["composite_score"] = composite_data.set_index("Date")["composite_score"]

        economic_labels: dict[str, str] = {
            EXPANSION: NORMAL_GROWTH,
            LATE_CYCLE: INFLATIONARY,
            RECOVERY: STAGFLATIONARY,
            CONTRACTION: DEFLATIONARY_CRISIS,
        }

        labels: list[str] = []
        probs_list: list[dict[str, float]] = []

        for date, row in composite_values.iterrows():
            mk_label = self._markov.regime_labels
            if mk_label is not None and date in mk_label.index:
                label = economic_labels.get(mk_label[date], DEFLATIONARY_CRISIS)
            else:
                label = NORMAL_GROWTH

            if gpr_series is not None and date in gpr_series.index:
                if gpr_series[date] > self._gpr_threshold:
                    label = GEOPOLITICAL_STRESS

            if gram_residual_series is not None and date in gram_residual_series.index:
                if abs(gram_residual_series[date]) > self._gram_residual_threshold:
                    label = STRUCTURAL_REGIME_CHANGE

            labels.append(label)

            score = float(row.get("composite_score", 0.0))
            gpr_val = float(gpr_series[date]) if gpr_series is not None and date in gpr_series.index else 0.0
            gram_val = float(gram_residual_series[date]) if gram_residual_series is not None and date in gram_residual_series.index else 0.0

            probs = self._compute_regime_probs(score, gpr_val, gram_val)
            probs_list.append(probs)

        self._results = pd.DataFrame({
            "Date": composite_values.index,
            "regime": labels,
        }).reset_index(drop=True)

        probs_df = pd.DataFrame(probs_list, index=composite_values.index)
        probs_df.index.name = "Date"
        self._regime_probs = probs_df

        self._last_composite_score = float(composite_values["composite_score"].iloc[-1])
        if gpr_series is not None and len(gpr_series) > 0:
            self._last_gpr_value = float(gpr_series.iloc[-1])
        if gram_residual_series is not None and len(gram_residual_series) > 0:
            self._last_gram_value = float(gram_residual_series.iloc[-1])

        return self

    def diagnose(
        self,
        composite_score: float,
        gpr_value: float = 0.0,
        gram_residual_value: float = 0.0,
    ) -> RegimeDiagnosis:
        probs = self._compute_regime_probs(composite_score, gpr_value, gram_residual_value)
        label = max(probs, key=probs.get)
        max_prob = probs[label]

        previous_regime = ""
        if self._results is not None and len(self._results) > 0:
            previous_regime = str(self._results["regime"].iloc[-1])
        elif self._last_diagnosis is not None:
            previous_regime = self._last_diagnosis.regime

        in_transition = max_prob < self._transition_threshold
        transition_type = "none"
        if in_transition and previous_regime and label != previous_regime:
            transition_type = "deterioration" if self._is_deterioration(previous_regime, label) else "improvement"
        if label == STRUCTURAL_REGIME_CHANGE and previous_regime and label != previous_regime:
            transition_type = "regime_break"

        diagnosis = RegimeDiagnosis(
            regime=label,
            label=REGIME_LABELS.get(label, label),
            confidence=round(max_prob, 4),
            probabilities={k: round(v, 4) for k, v in probs.items()},
            in_transition=in_transition,
            transition_type=transition_type,
            previous_regime=previous_regime,
            timestamp=datetime.now(timezone.utc).isoformat(),
            transition_confidence=round(1.0 - max_prob, 4),
            gram_residual=gram_residual_value,
            gram_trend="stable",
        )
        self._last_diagnosis = diagnosis
        return diagnosis

    def _is_deterioration(self, prev: str, current: str) -> bool:
        deterioration_pairs = {
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
        return (prev, current) in deterioration_pairs

    def _compute_regime_probs(
        self,
        score: float,
        gpr_val: float,
        gram_val: float,
    ) -> dict[str, float]:
        base = {
            NORMAL_GROWTH: 0.0,
            INFLATIONARY: 0.0,
            STAGFLATIONARY: 0.0,
            DEFLATIONARY_CRISIS: 0.0,
            GEOPOLITICAL_STRESS: 0.0,
            STRUCTURAL_REGIME_CHANGE: 0.0,
        }

        if gpr_val > self._gpr_threshold:
            gpr_excess = (gpr_val - self._gpr_threshold) / self._gpr_threshold
            base[GEOPOLITICAL_STRESS] = min(0.5 + gpr_excess * 0.3, 0.95)

        if abs(gram_val) > self._gram_residual_threshold:
            gram_excess = (abs(gram_val) - self._gram_residual_threshold) / self._gram_residual_threshold
            base[STRUCTURAL_REGIME_CHANGE] = min(0.5 + gram_excess * 0.3, 0.95)

        if base[GEOPOLITICAL_STRESS] < 0.5 and base[STRUCTURAL_REGIME_CHANGE] < 0.5:
            if score > 1.0:
                base[NORMAL_GROWTH] = 0.7
                base[INFLATIONARY] = 0.2
                base[STAGFLATIONARY] = 0.05
                base[DEFLATIONARY_CRISIS] = 0.05
            elif score > 0.0:
                base[INFLATIONARY] = 0.6
                base[NORMAL_GROWTH] = 0.3
                base[STAGFLATIONARY] = 0.05
                base[DEFLATIONARY_CRISIS] = 0.05
            elif score > -1.0:
                base[STAGFLATIONARY] = 0.6
                base[DEFLATIONARY_CRISIS] = 0.2
                base[INFLATIONARY] = 0.15
                base[NORMAL_GROWTH] = 0.05
            else:
                base[DEFLATIONARY_CRISIS] = 0.7
                base[STAGFLATIONARY] = 0.2
                base[NORMAL_GROWTH] = 0.05
                base[INFLATIONARY] = 0.05

        total = sum(base.values())
        if total > 0:
            for k in base:
                base[k] = round(base[k] / total, 4)
        return base

    def get_regime_data(self) -> pd.DataFrame:
        if self._results is None:
            raise RuntimeError("Must call fit() before get_regime_data()")
        return self._results.copy()

    def get_regime_probabilities(self) -> pd.DataFrame:
        if self._regime_probs is None:
            raise RuntimeError("Must call fit() before get_regime_probabilities()")
        return self._regime_probs.copy()

    def is_in_transition(self, date: str | None = None) -> bool:
        if self._regime_probs is None:
            return True
        if date is not None:
            if date not in self._regime_probs.index:
                return True
            pvals = self._regime_probs.loc[date].to_dict()
        else:
            pvals = self._regime_probs.iloc[-1].to_dict()
        max_prob = max(pvals.values())
        return max_prob < self._transition_threshold

    def get_current_regime(self) -> dict[str, Any]:
        if self._results is None or self._regime_probs is None:
            return {"regime": "UNKNOWN", "confidence": 0.0, "in_transition": True}
        last = self._results.iloc[-1]
        pvals = self._regime_probs.iloc[-1].to_dict()
        return {
            "regime": str(last["regime"]),
            "label": REGIME_LABELS.get(str(last["regime"]), str(last["regime"])),
            "confidence": round(max(pvals.values()), 4),
            "probabilities": {k: round(v, 4) for k, v in pvals.items()},
            "in_transition": max(pvals.values()) < self._transition_threshold,
        }

    def get_diagnosis(self) -> RegimeDiagnosis:
        if self._last_diagnosis is not None:
            return self._last_diagnosis
        current = self.get_current_regime()
        probs = current.get("probabilities", {})
        diagnosis = RegimeDiagnosis(
            regime=current["regime"],
            label=current["label"],
            confidence=current["confidence"],
            probabilities=probs,
            in_transition=current["in_transition"],
            transition_type="none",
            timestamp=datetime.now(timezone.utc).isoformat(),
        )
        self._last_diagnosis = diagnosis
        return diagnosis
