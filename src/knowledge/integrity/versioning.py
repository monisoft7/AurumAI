from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Generic, TypeVar

from knowledge._compat import atomic_write_json

T = TypeVar("T")


@dataclass(frozen=True)
class VersionedEntity(Generic[T]):
    version_number: int
    entity: T
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    previous_version_file: str | None = None


class VersionedStore(Generic[T]):
    def __init__(
        self,
        store_dir: Path,
        loader: Callable[[dict[str, Any]], T] | None = None,
    ) -> None:
        self._store_dir = store_dir
        self._loader = loader

    def store_dir(self) -> Path:
        return self._store_dir

    def save(
        self,
        entity_id: str,
        entity: T,
        version_number: int | None = None,
        previous_version_file: str | None = None,
    ) -> VersionedEntity[T]:
        if version_number is None:
            current = self.latest_version(entity_id)
            version_number = (current.version_number + 1) if current else 1
        entity_dir = self._store_dir / entity_id
        entity_dir.mkdir(parents=True, exist_ok=True)
        filename = f"v{version_number:04d}.json"
        path = entity_dir / filename
        if path.exists():
            raise FileExistsError(f"Version already exists: {path}")
        payload = {
            "version_number": version_number,
            "entity": self._serialize(entity),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "previous_version_file": previous_version_file,
        }
        atomic_write_json(path, payload)
        return VersionedEntity(
            version_number=version_number,
            entity=entity,
            timestamp=payload["timestamp"],
            previous_version_file=previous_version_file,
        )

    def load_version(self, entity_id: str, version_number: int) -> VersionedEntity[T] | None:
        entity_dir = self._store_dir / entity_id
        filename = f"v{version_number:04d}.json"
        path = entity_dir / filename
        if not path.exists():
            return None
        payload = json.loads(path.read_text())
        return VersionedEntity(
            version_number=payload["version_number"],
            entity=self._deserialize(payload["entity"]),
            timestamp=payload.get("timestamp", ""),
            previous_version_file=payload.get("previous_version_file"),
        )

    def latest_version(self, entity_id: str) -> VersionedEntity[T] | None:
        entity_dir = self._store_dir / entity_id
        if not entity_dir.exists():
            return None
        version_files = sorted(
            [p for p in entity_dir.iterdir() if p.suffix == ".json"],
            key=lambda p: int(p.stem[1:]),
            reverse=True,
        )
        if not version_files:
            return None
        latest = version_files[0]
        payload = json.loads(latest.read_text())
        return VersionedEntity(
            version_number=payload["version_number"],
            entity=self._deserialize(payload["entity"]),
            timestamp=payload.get("timestamp", ""),
            previous_version_file=payload.get("previous_version_file"),
        )

    def all_versions(self, entity_id: str) -> list[VersionedEntity[T]]:
        entity_dir = self._store_dir / entity_id
        if not entity_dir.exists():
            return []
        version_files = sorted(
            [p for p in entity_dir.iterdir() if p.suffix == ".json"],
            key=lambda p: int(p.stem[1:]),
        )
        results: list[VersionedEntity[T]] = []
        for vf in version_files:
            payload = json.loads(vf.read_text())
            results.append(VersionedEntity(
                version_number=payload["version_number"],
                entity=self._deserialize(payload["entity"]),
                timestamp=payload.get("timestamp", ""),
                previous_version_file=payload.get("previous_version_file"),
            ))
        return results

    def _serialize(self, entity: T) -> dict[str, Any]:
        if hasattr(entity, "_asdict"):
            return entity._asdict()
        if isinstance(entity, dict):
            return entity
        if hasattr(entity, "__dataclass_fields__"):
            return {f.name: getattr(entity, f.name) for f in entity.__dataclass_fields__.values()}
        if isinstance(entity, (list, tuple)):
            return {"__list__": [self._serialize(e) for e in entity]}
        return {"__value__": str(entity)}

    def _deserialize(self, data: dict[str, Any]) -> T:
        if self._loader is not None:
            return self._loader(data)
        return data  # type: ignore[return-value]
