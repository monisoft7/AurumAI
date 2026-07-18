from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from knowledge.integrity.provenance import Provenance


@dataclass(frozen=True)
class SourceData:
    source_id: str
    source_path: str
    source_type: str
    file_hash: str | None = None
    record_count: int = 0
    description: str = ""
    provenance: Provenance | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
