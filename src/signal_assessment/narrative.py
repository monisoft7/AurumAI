from __future__ import annotations

from typing import Any

from signal_assessment.contracts import CriterionScore

NARRATIVE_KEYWORDS: dict[str, list[str]] = {
    "gold": ["gold", "xau", "bullion", "precious metal"],
    "inflation": ["inflation", "cpi", "ppi", "price pressure", "core"],
    "fed": ["fed", "federal reserve", "interest rate", "monetary policy", "tightening", "easing"],
    "dxy": ["dollar", "dxy", "usd", "greenback", "fx"],
    "geopolitics": ["geopolitical", "sanctions", "war", "conflict", "tariff", "trade war"],
    "recession": ["recession", "slowdown", "contraction", "gdp"],
    "yield": ["yield", "treasury", "bond", "real yield", "nominal"],
    "etf": ["etf", "flow", "holding", "gld", "iaum"],
}

NARRATIVE_THRESHOLD: float = 0.3


class NarrativeFitScorer:
    """Evaluates criterion 4 (narrative fit) from Meth. §7.

    Checks whether current news headlines provide a credible
    narrative explanation for the observed price move.
    """

    @staticmethod
    def evaluate(
        instrument: str,
        change_pct: float,
        news_headlines: list[str],
    ) -> CriterionScore:
        if not news_headlines:
            return CriterionScore(
                criterion="narrative_fit",
                score=0.0,
                threshold=NARRATIVE_THRESHOLD,
                passed=False,
                detail="no news headlines available",
            )

        if abs(change_pct) < 0.1:
            return CriterionScore(
                criterion="narrative_fit",
                score=0.5,
                threshold=NARRATIVE_THRESHOLD,
                passed=True,
                detail="negligible move, narrative not required",
            )

        instrument_topics = NarrativeFitScorer._instrument_topics(instrument)
        matched_scores: list[float] = []

        for headline in news_headlines:
            hl = headline.lower()
            score = 0.0
            for topic, keywords in instrument_topics.items():
                for kw in keywords:
                    if kw in hl:
                        score += 0.25
                        break
            if score > 0:
                matched_scores.append(min(score, 1.0))

        if not matched_scores:
            return CriterionScore(
                criterion="narrative_fit",
                score=0.0,
                threshold=NARRATIVE_THRESHOLD,
                passed=False,
                detail="no narrative matches found in news headlines",
            )

        score = min(sum(matched_scores) / len(matched_scores), 1.0)
        passed = score >= NARRATIVE_THRESHOLD
        return CriterionScore(
            criterion="narrative_fit",
            score=round(score, 4),
            threshold=NARRATIVE_THRESHOLD,
            passed=passed,
            detail=f"matched {len(matched_scores)} headlines with narrative keywords",
        )

    @staticmethod
    def _instrument_topics(instrument: str) -> dict[str, list[str]]:
        inst_lower = instrument.lower()
        topics: dict[str, list[str]] = {}
        if "gold" in inst_lower or "xau" in inst_lower:
            topics["gold"] = NARRATIVE_KEYWORDS["gold"]
            topics["inflation"] = NARRATIVE_KEYWORDS["inflation"]
            topics["fed"] = NARRATIVE_KEYWORDS["fed"]
            topics["geopolitics"] = NARRATIVE_KEYWORDS["geopolitics"]
        elif "dxy" in inst_lower or "dollar" in inst_lower:
            topics["dxy"] = NARRATIVE_KEYWORDS["dxy"]
            topics["fed"] = NARRATIVE_KEYWORDS["fed"]
        elif "yield" in inst_lower or "real yield" in inst_lower:
            topics["yield"] = NARRATIVE_KEYWORDS["yield"]
            topics["fed"] = NARRATIVE_KEYWORDS["fed"]
        else:
            topics["gold"] = NARRATIVE_KEYWORDS["gold"]
            topics["fed"] = NARRATIVE_KEYWORDS["fed"]
        return topics
