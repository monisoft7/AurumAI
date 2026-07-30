from __future__ import annotations

from typing import Any

from knowledge.cai.adapter import CaiEvidenceAdapter
from knowledge.cbi.adapter import CbiEvidenceAdapter
from knowledge.cfi.adapter import CfiEvidenceAdapter
from knowledge.evidence.evidence import Evidence
from knowledge.graph.node import GraphNode
from knowledge.graph.relation import GraphRelation, RELATION_SAME_EVENT_TYPE
from knowledge.integrity.knowledge_record import KnowledgeRecord
from knowledge.regime.constants import (
    CANONICAL_REGIME_SET,
    REGIME_TEXT_PATTERNS,
    SUPPLEMENTARY_REGIME_PATTERNS,
)

_ALL_REGIME_PATTERNS: dict[str, set[str]] = {}
_ALL_REGIME_PATTERNS.update(REGIME_TEXT_PATTERNS)
_ALL_REGIME_PATTERNS.update(SUPPLEMENTARY_REGIME_PATTERNS)


def _extract_regimes(regime_dependence: str) -> list[str]:
    if not regime_dependence:
        return []
    text_lower = regime_dependence.lower()
    if text_lower in ("n/a", "none", "na", "not applicable"):
        return []
    found: list[str] = []
    for regime, patterns in _ALL_REGIME_PATTERNS.items():
        for pattern in patterns:
            if pattern in text_lower:
                found.append(regime)
                break
    if not found:
        if "all regime" in text_lower or "any regime" in text_lower or "across all" in text_lower:
            return list(CANONICAL_REGIME_SET)
    return found


def _determine_adapter_layer(category: str) -> str:
    cat_lower = category.lower()
    if "central bank" in cat_lower:
        return "cbi"
    if "etf" in cat_lower or "flow" in cat_lower:
        return "cfi"
    if "real yield" in cat_lower or "interest rate" in cat_lower or "inflation" in cat_lower or "breakeven" in cat_lower:
        return "evidence"
    if "usd" in cat_lower or "fx" in cat_lower or "dollar" in cat_lower:
        return "evidence"
    if "geopolitical" in cat_lower:
        return "evidence"
    if "cross-asset" in cat_lower or "correlation" in cat_lower:
        return "cai"
    return "evidence"


def create_graph_node(record: KnowledgeRecord) -> GraphNode:
    regimes = _extract_regimes(record.regime_dependence)
    properties = dict(record.to_dict())
    properties["regimes"] = regimes
    properties["adapter_layer"] = _determine_adapter_layer(record.metadata.get("category", ""))
    return GraphNode(
        node_id=record.knowledge_id,
        node_type="institutional_kr",
        properties=properties,
    )


def create_regime_relations(nodes: list[GraphNode]) -> list[GraphRelation]:
    relations: list[GraphRelation] = []
    regime_groups: dict[str, list[str]] = {}
    for node in nodes:
        regimes = node.properties.get("regimes", [])
        for regime in regimes:
            if regime not in CANONICAL_REGIME_SET:
                continue
            regime_groups.setdefault(regime, []).append(node.node_id)
    for regime, node_ids in regime_groups.items():
        m = len(node_ids)
        for i in range(m):
            for j in range(i + 1, m):
                relations.append(GraphRelation(
                    source_id=node_ids[i],
                    target_id=node_ids[j],
                    relation_type="same_regime",
                    properties={"regime": regime},
                ))
    return relations


def create_causal_relations(nodes: list[GraphNode]) -> list[GraphRelation]:
    relations: list[GraphRelation] = []
    event_type_groups: dict[str, list[GraphNode]] = {}
    for node in nodes:
        et = node.properties.get("event_type", "GENERAL")
        event_type_groups.setdefault(et, []).append(node)
    for event_type, group in event_type_groups.items():
        for i in range(len(group)):
            for j in range(i + 1, len(group)):
                relations.append(GraphRelation(
                    source_id=group[i].node_id,
                    target_id=group[j].node_id,
                    relation_type=RELATION_SAME_EVENT_TYPE,
                    properties={
                        "event_type": event_type,
                        "causal_direction": "undirected",
                        "confidence": 0.5,
                    },
                ))
    return relations


def to_evidence(record: KnowledgeRecord) -> Evidence | None:
    layer = _determine_adapter_layer(record.metadata.get("category", ""))
    if layer == "cbi":
        return CbiEvidenceAdapter().regime_to_evidence(
            type("obj", (), {
                "regime": "Institutional_KR",
                "regime_description": record.mechanism[:200],
                "confidence": record.confidence,
                "provenance": record.provenance,
                "valid_from": "",
                "valid_until": "",
                "time_horizon": "T0",
                "evidence_references": [],
                "cross_references": None,
                "methodology_version": record.methodology_version,
                "scenario_analysis": None,
                "aggregate_monetary_stance": 0.0,
                "synchronization_measure": 0.0,
                "transition_signals": [],
            })()
        )
    return None
