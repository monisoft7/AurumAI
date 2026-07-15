from dataclasses import dataclass, field
from typing import Any


RELATION_SAME_EVENT_TYPE = "same_event_type"
RELATION_SAME_CONDITION = "same_condition"
RELATION_SAME_HORIZON = "same_horizon"


@dataclass(frozen=True)
class GraphRelation:
    source_id: str
    target_id: str
    relation_type: str
    properties: dict[str, Any] = field(default_factory=dict)
