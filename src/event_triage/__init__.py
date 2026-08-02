"""W4: Macro Event Prioritization and Triage.

Deterministic, explainable institutional signal tiering. Classifies every
observation of the assessment stage output into Tier 1 (Overriding),
Tier 2 (Important), Tier 3 (Routine), or Tier 4 (Watchlist) using the
triplet (portfolio_impact, regime_relevance, price_impact) and assembles a
prioritized watchlist with trigger levels and monitoring frequency, per
Methodology section 2 and IMPLEMENTATION_WORKFLOWS W4.

The stage is intentionally rule-based: no machine learning, no randomness,
and every tier assignment carries an explanation of the rules that fired.
"""

from event_triage.contracts import (
    TierAssignment,
    TierLevel,
    SignalTiering,
    VALID_TIERS,
)
from event_triage.tierer import SignalTierer

__all__ = [
    "SignalTierer",
    "SignalTiering",
    "TierAssignment",
    "TierLevel",
    "VALID_TIERS",
]
