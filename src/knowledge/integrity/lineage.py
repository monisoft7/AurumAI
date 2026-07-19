from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from knowledge._compat import FrozenDict, freeze_dict


class LineageRelationType:
    DERIVES_FROM = "derives_from"
    UPDATES = "updates"
    REFERENCES = "references"
    GENERATES = "generates"


@dataclass(frozen=True)
class LineageRecord:
    source_id: str
    source_type: str
    target_id: str
    target_type: str
    relation_type: str
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    metadata: dict[str, Any] = field(default_factory=lambda: FrozenDict())

    def __post_init__(self) -> None:
        object.__setattr__(self, "metadata", freeze_dict(self.metadata))


class LineageRegistry:
    def __init__(self) -> None:
        self._records: list[LineageRecord] = []

    def record(self, record: LineageRecord) -> None:
        self._records.append(record)

    def add(
        self,
        source_id: str,
        source_type: str,
        target_id: str,
        target_type: str,
        relation_type: str = LineageRelationType.REFERENCES,
        metadata: dict[str, Any] | None = None,
    ) -> LineageRecord:
        rec = LineageRecord(
            source_id=source_id,
            source_type=source_type,
            target_id=target_id,
            target_type=target_type,
            relation_type=relation_type,
            metadata=metadata or {},
        )
        self._records.append(rec)
        return rec

    def query(
        self,
        entity_id: str | None = None,
        entity_type: str | None = None,
        relation_type: str | None = None,
        direction: str = "forward",
    ) -> list[LineageRecord]:
        results = list(self._records)
        if relation_type:
            results = [r for r in results if r.relation_type == relation_type]
        if entity_type:
            if direction == "forward":
                results = [r for r in results if r.source_type == entity_type]
            elif direction == "backward":
                results = [r for r in results if r.target_type == entity_type]
            else:
                results = [
                    r for r in results
                    if r.source_type == entity_type or r.target_type == entity_type
                ]
        if entity_id:
            if direction == "forward":
                results = [r for r in results if r.source_id == entity_id]
            elif direction == "backward":
                results = [r for r in results if r.target_id == entity_id]
            else:
                results = [
                    r for r in results
                    if r.source_id == entity_id or r.target_id == entity_id
                ]
        return results

    def trace(self, target_id: str, target_type: str) -> list[LineageRecord]:
        path: list[LineageRecord] = []
        seen: set[tuple[str, str]] = set()
        stack = [(target_id, target_type)]
        while stack:
            eid, etype = stack.pop()
            if (eid, etype) in seen:
                continue
            seen.add((eid, etype))
            incoming = self.query(entity_id=eid, entity_type=etype, direction="backward")
            path.extend(incoming)
            for r in incoming:
                stack.append((r.source_id, r.source_type))
        return path

    def all_records(self) -> list[LineageRecord]:
        return list(self._records)

    def clear(self) -> None:
        self._records.clear()
