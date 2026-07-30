from __future__ import annotations

from signal_assessment.contracts import CriterionScore

# Gold-specific noise filters from Meth. §7:
# COMEX: 1w = noise, 3w = signal
# ETF: 1d = noise, 2w = signal
# CB purchases: 1Q = noise, 8Q = signal
# Gold/real yield: 1d divergence = noise, 1m divergence = signal
# DXY: 0.5% alone = noise, 0.5% + 5bp real yield = signal

NOISE_FILTERS: dict[str, dict[str, float]] = {
    "COMEX": {"noise_days": 7, "signal_days": 21},
    "ETF": {"noise_days": 1, "signal_days": 14},
    "CB": {"noise_days": 90, "signal_days": 560},
    "gold_real_yield": {"noise_days": 1, "signal_days": 30},
    "DXY": {"noise_days": 1, "signal_days": 5},
}

PERSISTENCE_THRESHOLDS: dict[str, float] = {
    "COMEX": 0.7,
    "ETF": 0.7,
    "CB": 0.6,
    "gold_real_yield": 0.6,
    "DXY": 0.5,
}


class PersistenceTracker:
    """Evaluates criterion 1 (persistence) from Meth. §7.

    Determines how long a deviation has persisted and compares
    against gold-specific noise/signal duration thresholds.
    """

    @staticmethod
    def evaluate(
        deviation_days: float,
        instrument_type: str = "ETF",
        change_z_score: float = 0.0,
    ) -> CriterionScore:
        filters = NOISE_FILTERS.get(instrument_type, NOISE_FILTERS["ETF"])
        threshold = PERSISTENCE_THRESHOLDS.get(instrument_type, 0.5)

        noise_days = filters["noise_days"]
        signal_days = filters["signal_days"]

        if deviation_days >= signal_days:
            score = min(deviation_days / signal_days, 1.0)
            passed = True
            detail = (
                f"persisted {deviation_days:.0f}d >= signal threshold {signal_days}d"
            )
        elif deviation_days <= noise_days:
            score = deviation_days / noise_days if noise_days > 0 else 0.0
            passed = False
            detail = (
                f"persisted only {deviation_days:.0f}d <= noise threshold {noise_days}d"
            )
        else:
            progress = (deviation_days - noise_days) / (signal_days - noise_days)
            score = noise_days / signal_days + progress * (1.0 - noise_days / signal_days)
            passed = score >= threshold
            detail = (
                f"persisted {deviation_days:.0f}d between noise({noise_days}d) "
                f"and signal({signal_days}d) thresholds"
            )

        return CriterionScore(
            criterion="persistence",
            score=round(score, 4),
            threshold=round(threshold, 4),
            passed=passed,
            detail=detail,
        )
