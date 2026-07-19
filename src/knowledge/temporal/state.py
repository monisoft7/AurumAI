from dataclasses import dataclass, field
from typing import Any

from knowledge._compat import FrozenDict, freeze_dict

SOURCE_TYPE_EVIDENCE = "evidence"
SOURCE_TYPE_KNOWLEDGE = "knowledge"
SOURCE_TYPE_ECONOMIC = "economic"
SOURCE_TYPE_DECISION = "decision"
SOURCE_TYPE_REASONING = "reasoning"
SOURCE_TYPE_LESSON = "lesson"
SOURCE_TYPE_FEATURE = "feature"

VALID_SOURCE_TYPES = frozenset({
    SOURCE_TYPE_EVIDENCE,
    SOURCE_TYPE_KNOWLEDGE,
    SOURCE_TYPE_ECONOMIC,
    SOURCE_TYPE_DECISION,
    SOURCE_TYPE_REASONING,
    SOURCE_TYPE_LESSON,
    SOURCE_TYPE_FEATURE,
})


@dataclass(frozen=True)
class TemporalState:
    state_id: str
    date: str
    source_type: str
    source_id: str
    tags: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=lambda: FrozenDict())

    def __post_init__(self) -> None:
        object.__setattr__(self, "metadata", freeze_dict(self.metadata))
