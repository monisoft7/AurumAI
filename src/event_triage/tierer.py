"""Deterministic, explainable institutional tier classifier implementing the
gold-specific priority ranking and the official W4 tier thresholds. Pure
rules: no machine learning, no randomness.
"""

from __future__ import annotations

from event_triage.contracts import SignalTiering, TierAssignment
from signal_assessment.contracts import (
    ClassificationLabel,
    ClassifiedObservation,
    SignalAssessment,
)


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, value))


def _round4(value: float) -> float:
    return round(value, 4)


# Gold-specific priority ranking (Methodology section 2, items 1-9).
# The first category whose keyword matches the observation wins, so rank
# order encodes relative importance. Items 1-2 dominate gold; 8-9 are
# secondary. Unmatched observations fall back to rank 10 (other).
GOLD_PRIORITY_RANKING: tuple[tuple[str, float, frozenset[str]], ...] = (
    ("FED/RATES", 1.00, frozenset({"fed", "fomc", "dot plot", "dotplot", "rate decision", "real yield", "treasury"})),
    ("USD", 0.90, frozenset({"dxy", "dollar", "usd"})),
    ("CENTRAL BANK GOLD", 0.85, frozenset({"central bank", "wgc", "imf", "swiss customs", "gold purchase", "reserve"})),
    ("GEOPOLITICAL", 0.80, frozenset({"geopolitical", "gpr", "sanction", "war", "conflict", "escalation"})),
    ("INFLATION", 0.75, frozenset({"inflation", "breakeven", "bei", "cpi", "pce"})),
    ("ETF FLOWS", 0.65, frozenset({"etf", "flow", "inflow", "outflow"})),
    ("POSITIONING", 0.55, frozenset({"comex", "cot", "positioning", "open interest", "futures"})),
    ("FISCAL", 0.45, frozenset({"fiscal", "debt", "deficit", "reserve currency"})),
    ("SUPPLY/COSTS", 0.30, frozenset({"mining", "supply", "cost", "production", "ore"})),
    ("OTHER", 0.20, frozenset()),
)

# Regime dominance: when the matched category is the current regime's
# dominant driver (Methodology section 2 evidence), relevance is boosted.
# Tokens are substrings of the upper-cased regime identifier.
REGIME_DRIVERS: tuple[tuple[str, frozenset[str]], ...] = (
    ("INFLATION", frozenset({"inflation", "breakeven", "bei", "cpi", "pce"})),
    ("CRISIS", frozenset({"geopolitical", "gpr", "dollar", "funding", "vix", "sanction", "war"})),
    ("RISK_OFF", frozenset({"geopolitical", "gpr", "dollar", "funding", "vix", "sanction", "war"})),
    ("LIQUIDITY", frozenset({"dollar", "funding", "fed", "fomc"})),
    ("NORMAL_GROWTH", frozenset({"fed", "fomc", "rate", "cpi"})),
    ("RECESSION", frozenset({"fed", "fomc", "rate", "cpi", "gdp"})),
)

# Portfolio-impact weights per signal classification (signal/noise criteria).
CLASSIFICATION_WEIGHTS: dict[str, float] = {
    ClassificationLabel.SIGNAL.value: 1.0,
    ClassificationLabel.WEAK_SIGNAL.value: 0.6,
    ClassificationLabel.WATCH.value: 0.35,
    ClassificationLabel.NOISE.value: 0.15,
    ClassificationLabel.IGNORE.value: 0.05,
}

# Official W4 tier thresholds (IMPLEMENTATION_WORKFLOWS W4, stage 5).
TIER_1_IMPACT = 0.7
TIER_1_RELEVANCE = 0.8
TIER_1_PRICE = 0.9
TIER_2_IMPACT = 0.3
TIER_2_RELEVANCE = 0.5
TIER_2_PRICE = 0.5

MONITORING_FREQUENCY = {
    "Tier 1": "continuous",
    "Tier 2": "intraday",
    "Tier 3": "daily",
    "Tier 4": "weekly",
}

FILTERED_LABELS = {ClassificationLabel.NOISE.value, ClassificationLabel.IGNORE.value}


class SignalTierer:
    """Rule-based W4 tier classifier, created for institutional workflows."""

    created_by = "W4 SignalTierer"

    def tier(self, assessment: SignalAssessment) -> SignalTiering:
        assignments = tuple(
            self.tier_observation(observation, assessment.regime)
            for observation in assessment.observations
        )
        return SignalTiering(
            tiering_id=f"tiering-{assessment.assessment_id}",
            assessment_id=assessment.assessment_id,
            timestamp=assessment.timestamp,
            regime=assessment.regime,
            assignments=assignments,
            metadata={
                "created_by": self.created_by,
                "classifier": "deterministic-rule-based",
            },
        )

    def tier_observation(
        self,
        observation: ClassifiedObservation,
        regime: str,
    ) -> TierAssignment:
        classification = observation.classification
        weight = CLASSIFICATION_WEIGHTS.get(classification, 0.0)

        category, score, keywords = self._match_category(observation)
        relevance, boosted = self._regime_relevance(regime, score, keywords)

        impact = _round4(weight * (0.5 + 0.5 * observation.confidence))
        price, price_source = self._price_impact(observation, weight)

        tier, rule, extra = self._classify(classification, impact, relevance, price)

        reason = (
            f"Category {category!r} (rank {score:.2f}) from gold priority ranking; "
            f"portfolio_impact={impact:.4f} (classification weight {weight} "
            f"x confidence blend {0.5 + 0.5 * observation.confidence:.4f}); "
            f"regime_relevance={relevance:.4f}"
            f"{' (boosted by regime dominance)' if boosted else ''}; "
            f"price_impact={price:.4f} ({price_source}); "
            f"tier={tier} ({rule}){extra}"
        )
        return TierAssignment(
            observation_id=observation.observation_id,
            tier=tier,
            classification=classification,
            confidence=observation.confidence,
            instrument=observation.instrument,
            portfolio_impact=impact,
            regime_relevance=relevance,
            price_impact=price,
            reason=reason,
            trigger_level=self._trigger_level(observation, tier),
            monitoring_frequency=MONITORING_FREQUENCY.get(tier, "weekly"),
        )

    def _match_category(
        self, observation: ClassifiedObservation
    ) -> tuple[str, float, frozenset[str]]:
        text = " ".join(
            [
                observation.instrument,
                observation.source,
                observation.reason,
            ]
        ).lower()
        for category, score, keywords in GOLD_PRIORITY_RANKING:
            if not keywords:
                continue
            if any(keyword in text for keyword in keywords):
                return category, score, keywords
        return "OTHER", 0.20, frozenset()

    def _regime_relevance(
        self,
        regime: str,
        score: float,
        keywords: frozenset[str],
    ) -> tuple[float, bool]:
        relevance = score
        normalized_regime = regime.upper()
        for token, drivers in REGIME_DRIVERS:
            if token in normalized_regime and keywords & drivers:
                relevance = min(1.0, relevance + 0.1)
                return _round4(relevance), True
        return _round4(relevance), False

    def _price_impact(
        self, observation: ClassifiedObservation, weight: float
    ) -> tuple[float, str]:
        if observation.change_sigma > 0.0 or observation.change_pct != 0.0:
            sigma_part = 0.6 * _clamp01(observation.change_sigma)
            move_part = 0.4 * _clamp01(abs(observation.change_pct) / 3.0)
            return _round4(sigma_part + move_part), "magnitude data (change_sigma/change_pct)"
        return _round4(_clamp01(weight)), "no magnitude data; proxy from classification"

    def _classify(
        self,
        classification: str,
        impact: float,
        relevance: float,
        price: float,
    ) -> tuple[str, str, str]:
        if classification in FILTERED_LABELS:
            return (
                "Tier 4",
                "filtered by signal classification",
                "; watchlist item: monitor only, no front-running",
            )
        if impact > TIER_1_IMPACT or relevance > TIER_1_RELEVANCE or price > TIER_1_PRICE:
            return (
                "Tier 1",
                self._tier1_rule(impact, relevance, price),
                "; overriding: can change the macro regime or invalidate positioning",
            )
        if impact > TIER_2_IMPACT or relevance > TIER_2_RELEVANCE or price > TIER_2_PRICE:
            return (
                "Tier 2",
                self._tier2_rule(impact, relevance, price),
                "; important: affects individual positions or sector-level views",
            )
        return (
            "Tier 3",
            "routine: no triplet threshold exceeded",
            "; scheduled data consistent with the current regime, check outcome only",
        )

    def _tier1_rule(self, impact: float, relevance: float, price: float) -> str:
        fired = []
        if impact > TIER_1_IMPACT:
            fired.append("portfolio_impact>0.7")
        if relevance > TIER_1_RELEVANCE:
            fired.append("regime_relevance>0.8")
        if price > TIER_1_PRICE:
            fired.append("price_impact>0.9")
        return " or ".join(fired)

    def _tier2_rule(self, impact: float, relevance: float, price: float) -> str:
        fired = []
        if impact > TIER_2_IMPACT:
            fired.append("portfolio_impact>0.3")
        if relevance > TIER_2_RELEVANCE:
            fired.append("regime_relevance>0.5")
        if price > TIER_2_PRICE:
            fired.append("price_impact>0.5")
        return " or ".join(fired)

    def _trigger_level(self, observation: ClassifiedObservation, tier: str) -> str:
        if tier not in ("Tier 1", "Tier 2"):
            return ""
        if observation.change_sigma > 0.0:
            return (
                f"If the move exceeds {observation.change_sigma:.2f} standard "
                "deviations, then reassess the gold view"
            )
        if observation.change_pct != 0.0:
            return (
                f"If the move exceeds |{observation.change_pct:.2f}%|, then "
                "reassess the gold view"
            )
        return "Monitor the next release for confirmation"

    def __repr__(self) -> str:
        return f"SignalTierer(created_by={self.created_by!r})"
