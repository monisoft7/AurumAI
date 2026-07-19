from dataclasses import dataclass, field
from typing import Any

from knowledge._compat import FrozenDict, freeze_dict

HYPOTHESIS_PROPOSED = "proposed"
HYPOTHESIS_SUPPORTED = "supported"
HYPOTHESIS_CONTRADICTED = "contradicted"
HYPOTHESIS_INCONCLUSIVE = "inconclusive"

VALID_HYPOTHESIS_STATUSES = frozenset({
    HYPOTHESIS_PROPOSED,
    HYPOTHESIS_SUPPORTED,
    HYPOTHESIS_CONTRADICTED,
    HYPOTHESIS_INCONCLUSIVE,
})


@dataclass(frozen=True)
class CausalHypothesis:
    hypothesis_id: str
    name: str
    description: str
    cause_node_id: str
    effect_node_id: str
    direction: str = "cause_to_effect"
    status: str = HYPOTHESIS_PROPOSED
    supporting_evidence_ids: tuple[str, ...] = ()
    contradicting_evidence_ids: tuple[str, ...] = ()
    confidence: float = 0.0
    created_at: str = ""
    metadata: dict[str, Any] = field(default_factory=lambda: FrozenDict())

    def __post_init__(self) -> None:
        object.__setattr__(self, "metadata", freeze_dict(self.metadata))
