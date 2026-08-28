"""Correction 008-B: explanation-only knowledge rationale for KR-backed evidence.

The preserved KnowledgeRecord semantics (Correction 008-A) are mirrored into
EvidenceSet metadata as a deterministic, human-readable rationale.  The
textual summary is produced by the legacy ReasoningEngine so the same
deterministic machinery that explains legacy decisions also explains the
record here.  The rationale is numerically inert: it feeds no score, weight,
confidence, consensus, or decision value.
"""

from __future__ import annotations

from typing import Any

from evidence_collection.contracts import Evidence
from knowledge.evidence.collection import EvidenceCollection
from knowledge.evidence.evidence import Evidence as KnowledgeEvidence
from knowledge.reasoning.context import ReasoningContext
from knowledge.reasoning.engine import ReasoningEngine

# Minimal condition-key -> KR family label mapping.  The preserved payload
# carries the KnowledgeRecord condition but not the record's event_type, so a
# small deterministic mapping recovers the family for evaluation phrasing.
FAMILY_FROM_CONDITION_KEY: dict[str, str] = {
    "cpi_pressure": "CPI",
}


def _family_for(semantics: dict[str, Any], fallback: str) -> str:
    condition = semantics.get("condition")
    if isinstance(condition, dict):
        for key, family in FAMILY_FROM_CONDITION_KEY.items():
            if key in condition:
                return family
    return fallback


def build_knowledge_rationale(evidence_items: list[Evidence]) -> list[dict[str, Any]]:
    """Return one deterministic rationale entry per KR-backed evidence item.

    Items without a ``knowledge_semantics`` payload are skipped entirely;
    missing numeric fields degrade to safe defaults (0.0 / 0) so the summary
    never raises.
    """
    rationale: list[dict[str, Any]] = []
    engine = ReasoningEngine()
    for ev in evidence_items:
        semantics = ev.metadata.get("knowledge_semantics")
        if not isinstance(semantics, dict) or not semantics:
            continue
        entry = _rationale_entry(ev, semantics, engine)
        if entry is not None:
            rationale.append(entry)
    return rationale


def _rationale_entry(
    ev: Evidence,
    semantics: dict[str, Any],
    engine: ReasoningEngine,
) -> dict[str, Any] | None:
    condition = semantics.get("condition")
    if not isinstance(condition, dict):
        condition = {}
    family = _family_for(semantics, ev.event_type or "GENERAL")
    horizon_days = int(semantics.get("horizon_days", 0) or 0)
    sample_count = int(semantics.get("sample_count", 0) or 0)
    average_return_pct = float(semantics.get("average_return_pct", 0.0) or 0.0)
    confidence = float(semantics.get("confidence", 0.0) or 0.0)
    positive_return_rate_pct = semantics.get("positive_return_rate_pct")

    knowledge_ev = KnowledgeEvidence(
        evidence_id=ev.evidence_id,
        source_node_id=ev.source_kr_node_id,
        event_type=family,
        condition=dict(condition),
        horizon_days=horizon_days,
        sample_count=sample_count,
        average_return_pct=average_return_pct,
        confidence=confidence,
        bias=str(semantics.get("bias") or ""),
        explanation="",
    )
    context = ReasoningContext(
        event_type=family,
        condition=dict(condition) or None,
        horizon_days=horizon_days or None,
        institutional_context=dict(semantics.get("institutional_context") or {}),
    )
    chain = engine.reason(EvidenceCollection([knowledge_ev]), context)
    summary = chain.steps[-1].conclusion if chain.steps else ""

    entry: dict[str, Any] = {
        "evidence_id": ev.evidence_id,
        "source_kr_node_id": ev.source_kr_node_id,
        "family": family,
        "condition": dict(condition),
        "horizon_days": horizon_days,
        "sample_count": sample_count,
        "average_return_pct": average_return_pct,
        "confidence": confidence,
        "engine_summary": summary,
    }
    if positive_return_rate_pct is not None:
        entry["positive_return_rate_pct"] = float(positive_return_rate_pct)
    return entry