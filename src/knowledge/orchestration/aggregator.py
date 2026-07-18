from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from knowledge.evidence.evidence import Evidence
from knowledge.evidence.collection import EvidenceCollection


@dataclass
class AggregationResult:
    collection: EvidenceCollection
    layer_counts: dict[str, int] = field(default_factory=dict)
    layer_sources: dict[str, list[str]] = field(default_factory=dict)
    conflicts: list[dict[str, Any]] = field(default_factory=list)


class EvidenceAggregator:
    def merge(
        self,
        collections: dict[str, EvidenceCollection],
    ) -> AggregationResult:
        seen: dict[str, Evidence] = {}
        layer_counts: dict[str, int] = {}
        layer_sources: dict[str, list[str]] = {}
        conflicts: list[dict[str, Any]] = []

        for layer_name, coll in collections.items():
            layer_counts[layer_name] = len(coll)
            layer_sources[layer_name] = []
            for ev in coll:
                if ev.evidence_id in seen:
                    existing = seen[ev.evidence_id]
                    if existing.bias != ev.bias:
                        conflicts.append({
                            "evidence_id": ev.evidence_id,
                            "layer": layer_name,
                            "existing_bias": existing.bias,
                            "incoming_bias": ev.bias,
                            "existing_layer": existing.metadata.get("_source_layer", "unknown"),
                            "incoming_layer": layer_name,
                        })
                seen[ev.evidence_id] = ev
                layer_sources[layer_name].append(ev.evidence_id)

        merged = EvidenceCollection(list(seen.values()))
        return AggregationResult(
            collection=merged,
            layer_counts=layer_counts,
            layer_sources=layer_sources,
            conflicts=conflicts,
        )
