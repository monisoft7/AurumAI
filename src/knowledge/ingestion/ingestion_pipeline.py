from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from knowledge.graph.builder import GraphBuilder
from knowledge.graph.graph import KnowledgeGraph
from knowledge.ingestion.adapter_dispatch import (
    create_causal_relations,
    create_graph_node,
    create_regime_relations,
    to_evidence,
)
from knowledge.ingestion.kr_parser import parse_kb_document
from knowledge.integrity.knowledge_record import KnowledgeRecord
from knowledge.integrity.lineage import LineageRegistry, LineageRelationType
from knowledge.integrity.provenance import Provenance, serialize_provenance

MISSING_FIELDS = {
    "mechanism",
    "preconditions",
    "trigger",
    "expected_impact",
    "failure_conditions",
    "counter_examples",
    "regime_dependence",
    "references",
}


class IngestionReport:
    def __init__(self) -> None:
        self.total_krs: int = 0
        self.parsed: int = 0
        self.graph_nodes: int = 0
        self.graph_relations: int = 0
        self.lineage_records: int = 0
        self.evidence_count: int = 0
        self.validation_errors: list[dict[str, Any]] = []
        self.missing_fields: dict[str, list[str]] = {}

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_krs": self.total_krs,
            "parsed": self.parsed,
            "graph_nodes": self.graph_nodes,
            "graph_relations": self.graph_relations,
            "lineage_records": self.lineage_records,
            "evidence_count": self.evidence_count,
            "validation_errors": self.validation_errors,
            "missing_fields": {k: len(v) for k, v in self.missing_fields.items()},
        }


def validate_kr(record: KnowledgeRecord) -> list[str]:
    errors: list[str] = []
    if not record.knowledge_id:
        errors.append("missing knowledge_id")
    if not record.event_type:
        errors.append("missing event_type")
    if not record.asset:
        errors.append("missing asset")
    for field in MISSING_FIELDS:
        if not getattr(record, field, ""):
            errors.append(f"missing {field}")
    return errors


class KrIngestionPipeline:
    def __init__(self, kb_path: str, methodology_version: str = "1.0") -> None:
        self._kb_path = kb_path
        self._methodology_version = methodology_version
        self._lineage = LineageRegistry()

    def run(self) -> tuple[KnowledgeGraph, IngestionReport]:
        report = IngestionReport()

        kr_dicts = parse_kb_document(self._kb_path)
        report.total_krs = len(kr_dicts)

        records: list[KnowledgeRecord] = []
        for kr_dict in kr_dicts:
            kr_dict["methodology_version"] = self._methodology_version
            provenance = Provenance(
                created_at=datetime.now(timezone.utc).isoformat(),
                created_by="KrIngestionPipeline",
                entity_version=self._methodology_version,
            )
            kr_dict["provenance"] = serialize_provenance(provenance)
            record = KnowledgeRecord.from_dict(kr_dict)
            records.append(record)
            self._lineage.add(
                source_id=record.knowledge_id,
                source_type="institutional_kr",
                target_id="Institutional_Gold_Knowledge_Base.md",
                target_type="kb_document",
                relation_type=LineageRelationType.DERIVES_FROM,
                metadata={
                    "kb_version": self._methodology_version,
                    "section": f"Category {kr_dict.get('category', 'unknown')}",
                },
            )
            report.parsed += 1

        nodes = [create_graph_node(r) for r in records]

        graph = KnowledgeGraph()
        for node in nodes:
            graph.add_node(node)
            report.graph_nodes += 1

        regime_relations = create_regime_relations(nodes)
        causal_relations = create_causal_relations(nodes)
        all_relations = regime_relations + causal_relations
        for rel in all_relations:
            graph.add_relation(rel)
            report.graph_relations += 1

        for record in records:
            evidence = to_evidence(record)
            if evidence is not None:
                report.evidence_count += 1

        report.lineage_records = len(self._lineage.all_records())

        missing_counts: dict[str, list[str]] = {}
        for record in records:
            errors = validate_kr(record)
            if errors:
                report.validation_errors.append({
                    "knowledge_id": record.knowledge_id,
                    "errors": errors,
                })
                for err in errors:
                    missing_counts.setdefault(err, []).append(record.knowledge_id)
        report.missing_fields = missing_counts

        return graph, report

    @property
    def lineage(self) -> LineageRegistry:
        return self._lineage
