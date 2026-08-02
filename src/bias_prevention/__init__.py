"""W13: Bias Prevention and Decision Review.

Rule-based detection of institutional reasoning biases (confirmation bias,
anchoring, recency bias, narrative bias, overconfidence, single-source bias,
regime blindness) over the updated thesis, the counter-evidence assessment,
and the institutional confidence output.

Produces a BiasReview with per-bias severity, confidence impact, required
actions, and a human review flag. Before a final decision is emitted, the
review is consumed by the decision output: a human-review-required review
blocks directional decisions.
"""

from bias_prevention.contracts import (
    VALID_SEVERITIES,
    BiasFinding,
    BiasReview,
    apply_bias_review,
)
from bias_prevention.detector import BiasReviewer

__all__ = [
    "BiasFinding",
    "BiasReview",
    "BiasReviewer",
    "VALID_SEVERITIES",
    "apply_bias_review",
]
