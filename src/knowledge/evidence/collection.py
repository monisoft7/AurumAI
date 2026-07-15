from __future__ import annotations

from typing import Any

from knowledge.evidence.evidence import Evidence


class EvidenceCollection:
    def __init__(self, items: list[Evidence] | None = None):
        self._items = list(items) if items is not None else []

    def __len__(self) -> int:
        return len(self._items)

    def __getitem__(self, index: int) -> Evidence:
        return self._items[index]

    def __iter__(self):
        return iter(self._items)

    def filter(self, **kwargs: Any) -> EvidenceCollection:
        result = self._items
        for key, value in kwargs.items():
            result = [e for e in result if getattr(e, key, None) == value]
        return EvidenceCollection(result)

    def top(self, n: int) -> EvidenceCollection:
        return EvidenceCollection(self._items[:n])

    def aggregate(self) -> dict[str, Any]:
        if not self._items:
            return {
                "count": 0,
                "avg_confidence": 0.0,
                "avg_sample_count": 0,
                "avg_return_pct": 0.0,
            }
        return {
            "count": len(self._items),
            "avg_confidence": round(
                sum(e.confidence for e in self._items) / len(self._items), 6
            ),
            "avg_sample_count": round(
                sum(e.sample_count for e in self._items) / len(self._items)
            ),
            "avg_return_pct": round(
                sum(e.average_return_pct for e in self._items) / len(self._items), 6
            ),
        }
