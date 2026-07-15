from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class GraphNode:
    node_id: str
    node_type: str
    properties: dict[str, Any] = field(default_factory=dict)
