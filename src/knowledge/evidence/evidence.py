from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from knowledge._compat import FrozenDict, freeze_dict
from knowledge.integrity.provenance import Provenance


@dataclass(frozen=True)
class Evidence:
    evidence_id: str
    source_node_id: str
    event_type: str
    condition: dict[str, str]
    horizon_days: int
    sample_count: int
    average_return_pct: float
    confidence: float
    bias: str
    explanation: str
    provenance: Provenance | None = None
    metadata: dict[str, Any] = field(default_factory=lambda: FrozenDict())

    def __post_init__(self) -> None:
        object.__setattr__(self, "condition", freeze_dict(self.condition))
        object.__setattr__(self, "metadata", freeze_dict(self.metadata))
