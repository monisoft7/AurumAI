from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

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
    metadata: dict[str, Any] = field(default_factory=dict)
