from __future__ import annotations

from collections import defaultdict
from typing import Any

from evidence_collection.contracts import Evidence
from evidence_reasoning.contracts import EvidenceSet


def evidence_dedup_key(ev: Evidence) -> str:
    """Identity used to recognize same-fact repetition inside one group.

    Run-003 repair (Phase 3): when the producer stamped the deterministic
    canonical fact identity (existing ``primitive_fact_id`` machinery), that
    identity is the dedup key -- two items asserting the same market
    primitive on the same as-of date are the same fact regardless of which
    knowledge record or desk phrased them.  Items without a stamped
    identity fall back to the existing ``source_kr_id`` semantics.
    """
    fact_id = ev.metadata.get("canonical_fact_id")
    if isinstance(fact_id, str) and fact_id:
        return fact_id
    return ev.source_kr_id


class EvidenceGrouper:
    """Groups Evidence items into EvidenceSets by event_type.

    Each event_type yields one EvidenceSet. Items asserting the SAME
    canonical fact (or, lacking a stamped identity, the same
    ``source_kr_id``) within one event_type are flagged as duplicates and
    only the highest-composite-weight assertion is retained, so same-fact
    repetition can never manufacture consensus or confidence.
    """

    def group(self, evidence_items: list[Evidence]) -> tuple[list[list[Evidence]], list[str]]:
        """Partition evidence by event_type. Returns (groups, duplicate_ids)."""
        groups: dict[str, list[Evidence]] = defaultdict(list)
        seen_per_type: dict[str, dict[str, Evidence]] = defaultdict(dict)
        duplicates: list[str] = []

        for ev in evidence_items:
            event_type = ev.event_type
            src_key = evidence_dedup_key(ev)
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
