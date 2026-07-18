import json
from pathlib import Path

from knowledge.evidence.evidence import Evidence
from knowledge.evidence.collection import EvidenceCollection
from knowledge.integrity.provenance import serialize_provenance, deserialize_provenance


class EvidenceRepository:
    def save(self, collection: EvidenceCollection, path: Path) -> None:
        items = []
        for evidence in collection:
            items.append({
                "evidence_id": evidence.evidence_id,
                "source_node_id": evidence.source_node_id,
                "event_type": evidence.event_type,
                "condition": evidence.condition,
                "horizon_days": evidence.horizon_days,
                "sample_count": evidence.sample_count,
                "average_return_pct": evidence.average_return_pct,
                "confidence": evidence.confidence,
                "bias": evidence.bias,
                "explanation": evidence.explanation,
                "provenance": serialize_provenance(evidence.provenance),
                "metadata": evidence.metadata,
            })
        payload = {"evidence_count": len(items), "items": items}
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, indent=2))

    def load(self, path: Path) -> EvidenceCollection:
        payload = json.loads(path.read_text())
        items = []
        for item_data in payload.get("items", []):
            items.append(Evidence(
                evidence_id=item_data["evidence_id"],
                source_node_id=item_data["source_node_id"],
                event_type=item_data["event_type"],
                condition=item_data.get("condition", {}),
                horizon_days=item_data.get("horizon_days", 0),
                sample_count=item_data.get("sample_count", 0),
                average_return_pct=item_data.get("average_return_pct", 0.0),
                confidence=item_data.get("confidence", 0.0),
                bias=item_data.get("bias", ""),
                explanation=item_data.get("explanation", ""),
                provenance=deserialize_provenance(item_data.get("provenance")),
                metadata=item_data.get("metadata", {}),
            ))
        return EvidenceCollection(items)
