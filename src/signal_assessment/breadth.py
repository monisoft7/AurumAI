from __future__ import annotations

from signal_assessment.contracts import CriterionScore

EXPECTED_RELATIONSHIPS: dict[str, dict[str, str]] = {
    "XAU/USD": {"DXY": "inverse", "US10Y Real Yield": "inverse", "S&P 500 Futures": "positive"},
    "DXY": {"XAU/USD": "inverse", "US10Y Real Yield": "positive", "EUR/USD": "inverse"},
}

BREADTH_THRESHOLDS: dict[str, float] = {
    "XAU/USD": 0.6,
    "DXY": 0.5,
}


class BreadthChecker:
    """Evaluates criterion 2 (breadth) from Meth. §7.

    Determines whether a move in one instrument is confirmed
    by correlated moves in other assets.
    """

    @staticmethod
    def evaluate(
        instrument: str,
        changes: dict[str, float],
        regime: str = "",
    ) -> CriterionScore:
        relationships = EXPECTED_RELATIONSHIPS.get(instrument, {})
        threshold = BREADTH_THRESHOLDS.get(instrument, 0.5)

        if instrument not in changes:
            return CriterionScore(
                criterion="breadth",
                score=0.0,
                threshold=threshold,
                passed=False,
                detail=f"{instrument} not in change data",
            )

        instrument_change = changes[instrument]
        if abs(instrument_change) < 0.01:
            return CriterionScore(
                criterion="breadth",
                score=0.5,
                threshold=threshold,
                passed=True,
                detail="no material move, breadth check skipped",
            )

        confirms = 0
        total = 0
        details: list[str] = []

        for other, expected_rel in relationships.items():
            if other not in changes:
                continue
            total += 1
            other_change = changes[other]
            if abs(other_change) < 0.01:
                details.append(f"{other}: flat, neutral")
                confirms += 0.5
                continue
            actual_same_dir = (instrument_change > 0) == (other_change > 0)
            if expected_rel == "positive":
                confirmed = actual_same_dir
            else:
                confirmed = not actual_same_dir
            relationship_word = "confirmed" if confirmed else "disconfirmed"
            details.append(f"{other}: {relationship_word} (expected {expected_rel})")
            if confirmed:
                confirms += 1.0

        if total == 0:
            score = 0.0
            passed = False
            details = ["no correlated instruments available"]
        else:
            score = confirms / total
            passed = score >= threshold

        return CriterionScore(
            criterion="breadth",
            score=round(score, 4),
            threshold=round(threshold, 4),
            passed=passed,
            detail="; ".join(details),
        )
