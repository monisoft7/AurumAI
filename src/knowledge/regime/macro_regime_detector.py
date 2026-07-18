from __future__ import annotations

import numpy as np
import pandas as pd
from statsmodels.tsa.regime_switching.markov_regression import MarkovRegression

EXPANSION = "EXPANSION"
LATE_CYCLE = "LATE_CYCLE"
CONTRACTION = "CONTRACTION"
RECOVERY = "RECOVERY"

REGIMES = [EXPANSION, LATE_CYCLE, CONTRACTION, RECOVERY]


class MacroRegimeDetector:
    """Thin adapter around statsmodels MarkovRegression.

    Fits a 4-regime Markov switching model on a composite macro indicator
    and labels each period as EXPANSION, LATE_CYCLE, CONTRACTION, or RECOVERY.

    Deterministic when constructed with the same random_state.
    """

    def __init__(self, random_state: int = 42) -> None:
        self._random_state = random_state
        self._results: MarkovRegression | None = None
        self._regime_labels: pd.Series | None = None

    def fit(self, data: pd.DataFrame) -> MacroRegimeDetector:
        df = data.copy()
        date_col = "Date" if "Date" in df.columns else df.index.name
        if date_col and date_col in df.columns:
            df = df.set_index(date_col)

        if "composite_score" not in df.columns:
            raise ValueError("Data must contain a 'composite_score' column")

        np.random.seed(self._random_state)

        model = MarkovRegression(
            df["composite_score"],
            k_regimes=4,
            trend="c",
            switching_variance=True,
        )
        try:
            self._results = model.fit(
                search_reps=20, search_iter=10, disp=False
            )
        except (ValueError, np.linalg.LinAlgError):
            self._results = model.fit(disp=False)

        probs = self._results.smoothed_marginal_probabilities
        if isinstance(probs, pd.DataFrame):
            self._regime_labels = pd.Series(
                probs.values.argmax(axis=1),
                index=probs.index,
            )
        else:
            self._regime_labels = pd.Series(
                probs.argmax(axis=1),
                index=df.index,
            )

        self._relabel_regimes(df)
        return self

    def _relabel_regimes(self, data: pd.DataFrame) -> None:
        state_means: dict[int, float] = {}
        for state in range(4):
            mask = self._regime_labels.values == state
            if mask.any():
                state_means[state] = float(
                    data.loc[mask, "composite_score"].mean()
                )
            else:
                state_means[state] = -999.0

        sorted_states = sorted(state_means, key=state_means.get, reverse=True)

        label_map = {
            sorted_states[0]: EXPANSION,
            sorted_states[1]: LATE_CYCLE,
            sorted_states[2]: RECOVERY,
            sorted_states[3]: CONTRACTION,
        }

        self._regime_labels = self._regime_labels.map(label_map)

    def get_regime_data(self) -> pd.DataFrame:
        if self._regime_labels is None:
            raise RuntimeError("Must call fit() before get_regime_data()")
        return pd.DataFrame({
            "Date": self._regime_labels.index,
            "macro_regime": self._regime_labels.values,
        }).reset_index(drop=True)

    @property
    def regime_labels(self) -> pd.Series | None:
        return self._regime_labels
