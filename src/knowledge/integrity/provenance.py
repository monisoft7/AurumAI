from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class Provenance:
    created_at: str
    created_by: str
    entity_version: str
    previous_version_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


def serialize_provenance(p: Provenance | None) -> dict | None:
    if p is None:
        return None
    return {
        "created_at": p.created_at,
        "created_by": p.created_by,
        "entity_version": p.entity_version,
        "previous_version_id": p.previous_version_id,
        "metadata": p.metadata,
    }


def deserialize_provenance(data: dict | None) -> Provenance | None:
    if data is None:
        return None
    return Provenance(
        created_at=data["created_at"],
        created_by=data["created_by"],
        entity_version=data["entity_version"],
        previous_version_id=data.get("previous_version_id"),
        metadata=data.get("metadata", {}),
    )
