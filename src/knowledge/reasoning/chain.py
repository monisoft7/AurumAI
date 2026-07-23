from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from knowledge._compat import FrozenDict, freeze_dict
from knowledge.reasoning.context import ReasoningContext
from knowledge.reasoning.step import ReasoningStep
from knowledge.integrity.provenance import Provenance


@dataclass(frozen=True)
class ReasoningChain:
    chain_id: str
    context: ReasoningContext
    steps: tuple[ReasoningStep, ...]
    final_conclusion: str
    overall_confidence: float
    evidence_count: int
    provenance: Provenance | None = None
    metadata: dict[str, Any] = field(default_factory=lambda: FrozenDict())
    attribution: dict[str, float] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "metadata", freeze_dict(self.metadata))
        object.__setattr__(self, "attribution", freeze_dict(self.attribution))
