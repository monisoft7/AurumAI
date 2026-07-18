from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

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
    metadata: dict[str, Any] = field(default_factory=dict)
