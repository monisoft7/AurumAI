"""W10: Thesis Update Cycle.

Versioned, immutable updating of an existing investment thesis when new
evidence arrives, following the Bridgewater four-step template: identify the
changed input, map the impact, quantify the confidence delta, and decide
(no change / scale / hedge / pause / exit).

The previous thesis is never mutated: every update produces a new thesis
version and a ThesisUpdate note that records the previous thesis id, the new
version, the updated evidence, the confidence delta, the changed assumptions,
and the change summary, preserving a full immutable history for audit.
"""

from thesis_update.contracts import (
    VALID_ACTIONS,
    VALID_TRIGGER_TYPES,
    ThesisUpdate,
)
from thesis_update.updater import ThesisUpdater

__all__ = [
    "ThesisUpdate",
    "ThesisUpdater",
    "VALID_ACTIONS",
    "VALID_TRIGGER_TYPES",
]
