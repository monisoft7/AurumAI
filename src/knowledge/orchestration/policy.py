from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from knowledge.evidence.collection import EvidenceCollection
from knowledge.orchestration.context import OrchestrationContext


@dataclass(frozen=True)
class LayerPolicy:
    layer_fn: Callable[[OrchestrationContext], EvidenceCollection]
    run_if: Callable[[OrchestrationContext], bool] = lambda ctx: True
    priority: int = 0


def evaluate_policies(
    policies: list[LayerPolicy],
    ctx: OrchestrationContext,
) -> list[LayerPolicy]:
    return sorted(
        [p for p in policies if p.run_if(ctx)],
        key=lambda p: p.priority,
    )
