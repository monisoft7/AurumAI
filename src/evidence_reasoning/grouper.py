from __future__ import annotations

from collections import defaultdict
from typing import Any

from evidence_collection.contracts import Evidence
from evidence_reasoning.contracts import EvidenceSet


class EvidenceGrouper:
    """Groups Evidence items into EvidenceSets by event_type.

    Each event_type yields one EvidenceSet. Items with the same
    source_kr_id AND same event_type are flagged as potential duplicates
    (same KR cannot produce two evidence items in the same channel).
    """

    def group(self, evidence_items: list[Evidence]) -> tuple[list[list[Evidence]], list[str]]:
        """Partition evidence by event_type. Returns (groups, duplicate_ids)."""
        groups: dict[str, list[Evidence]] = defaultdict(list)
        seen_per_type: dict[str, dict[str, Evidence]] = defaultdict(dict)
        duplicates: list[str] = []

        for ev in evidence_items:
            event_type = ev.event_type
            src_key = ev.source_kr_id
            seen = seen_per_type[event_type]

            if src_key in seen:
                existing = seen[src_key]
                if ev.composite_weight > existing.composite_weight:
                    duplicates.append(existing.evidence_id)
                    seen[src_key] = ev
                    groups[event_type].remove(existing)
                    groups[event_type].append(ev)
                else:
                    duplicates.append(ev.evidence_id)
                continue

            seen[src_key] = ev
            groups[event_type].append(ev)

        return list(groups.values()), duplicates

    @staticmethod
    def assign_set_id(event_type: str) -> str:
        return f"es_{event_type.lower()}"
