"""Run-003 repair: desk-produced evidence through the existing W5 abstraction.

Two independent research desks join the institutional evidence stream as
first-class Evidence items built with the EXISTING Evidence contract, the
EXISTING composite-weight formula and the EXISTING canonical-fact identity
machinery:

* TechnicalResearchDesk (Phase 9) -- one evidence item when the desk
  produces a directional reading.  Bias reuses the desk's own deterministic
  net-direction vote (``TechnicalResearchDesk._net_direction`` over its
  trend / momentum / structure interpretations); base_confidence reuses the
  desk's own ``technical_confidence``.  A degraded or non-directional
  assessment produces NO evidence item -- the unavailability is explicit.

* Historical memory (Phase 8) -- one evidence item derived from the
  existing explanation-only analogue adjudication (Correction 028).  Bias
  reuses the established status vocabulary (uniform positive history ->
  bullish, uniform negative history -> bearish, anything else ->
  uninformative); base_confidence reuses the existing retrieval similarity
  of the matched analogues (analogue transfer strength).  The item is ONE
  estimator regardless of the number of matched episodes, carries the
  matched lesson ids as provenance, and never fabricates a number.

Both builders are pure: no wall clock, no randomness, no I/O.
"""

from __future__ import annotations

from typing import Any

from evidence_collection.contracts import Evidence
from knowledge.facts.contracts import (
    DESK_HISTORICAL,
    DESK_TECHNICAL,
    primitive_fact_id,
)
from knowledge.integrity.provenance import Provenance

# Desk evidence channels are distinct event types so each desk contributes
# as its own independent EvidenceSet in W6/W7 (principle E: independent
# desks contribute as independent evidence).
TECHNICAL_EVENT_TYPE = "TECHNICAL"
HISTORICAL_MEMORY_EVENT_TYPE = "HISTORICAL_MEMORY"

_BIAS_BY_DIRECTION = {
    "bullish": "bullish",
    "bearish": "bearish",
}


def canonical_fact_identity(
    instrument: str,
    event_type: str,
    as_of_date: str,
) -> str:
    """Deterministic cross-item identity of one observed market primitive.

    Reuses the existing ``primitive_fact_id`` machinery: two evidence items
    derived from the same instrument observation on the same as-of date
    share one fact id, so same-fact repetition cannot manufacture consensus.
    """
    return primitive_fact_id(
        asset=str(instrument or "unknown"),
        topic=str(event_type or "GENERAL"),
        as_of=str(as_of_date or "unknown"),
    )


def _assessment_date(as_of: str) -> str:
    """Date part of an ISO timestamp / date string (verbatim, no invention)."""
    text = str(as_of or "").strip()
    return text[:10] if text else "unknown"


def _field(assessment: Any, name: str, default: Any = None) -> Any:
    """Read a field from either a live TechnicalAssessment object or its
    serialized stage payload dict (the production stage boundary carries the
    dict form)."""
    if isinstance(assessment, dict):
        return assessment.get(name, default)
    return getattr(assessment, name, default)


def build_technical_evidence(assessment: Any) -> Evidence | None:
    """Project a TechnicalAssessment (object or serialized stage payload)
    onto one Evidence item.

    Returns None (no evidence, explicitly) when the assessment is missing,
    failed, degraded, or carries no directional reading -- the desk then
    remains observability-only for this run rather than voting with an
    invented direction.
    """
    if assessment is None:
        return None
    if isinstance(assessment, dict) and "error" in assessment:
        return None
    trend = _field(assessment, "trend_direction")
    momentum = _field(assessment, "momentum_direction")
    structure_state = _field(assessment, "structure_state")
    confidence_raw = _field(assessment, "technical_confidence", 0.0)
    try:
        confidence = float(confidence_raw or 0.0)
    except (TypeError, ValueError):
        return None
    if not trend or not momentum:
        return None

    # Reuse the desk's own deterministic directional vote and structure
    # mapping -- no second interpretation is implemented here.
    from technical.desk import TechnicalResearchDesk

    structure_direction = TechnicalResearchDesk._structure_direction(
        structure_state
    )
    net = TechnicalResearchDesk._net_direction(trend, momentum, structure_direction)
    bias = _BIAS_BY_DIRECTION.get(net)
    if bias is None:
        return None
    if not 0.0 <= confidence <= 1.0:
        return None

    assessment_id = str(_field(assessment, "assessment_id", "") or "technical_desk")
    as_of = _assessment_date(_field(assessment, "as_of", ""))
    asset = str(_field(assessment, "asset", "") or "XAU/USD")
    prov_entries = _field(assessment, "provenance_chain", ()) or ()
    entry = prov_entries[0] if prov_entries else {}
    provenance = Provenance(
        created_at=str(entry.get("created_at", "") or ""),
        created_by=str(entry.get("created_by", "") or "TechnicalResearchDesk"),
        entity_version=str(entry.get("entity_version", "") or "1.0.0"),
        metadata={
            "desk_id": DESK_TECHNICAL,
            "assessment_id": assessment_id,
            "as_of": str(_field(assessment, "as_of", "") or ""),
            "source_data_hash": str(
                _field(assessment, "source_data_hash", "") or ""
            ),
        },
    )

    metadata: dict[str, Any] = {
        "desk_id": DESK_TECHNICAL,
        "technical_assessment_id": assessment_id,
        "as_of": str(_field(assessment, "as_of", "") or ""),
        "timeframe": str(_field(assessment, "timeframe", "") or ""),
        "trend_direction": trend,
        "momentum_direction": momentum,
        "structure_state": structure_state,
        "supporting_indicators": list(
            _field(assessment, "supporting_indicators", ()) or ()
        ),
        "conflicting_indicators": list(
            _field(assessment, "conflicting_indicators", ()) or ()
        ),
        "source_data_hash": str(_field(assessment, "source_data_hash", "") or ""),
    }
    notes = (_field(assessment, "metadata", {}) or {}).get("notes")
    if notes:
        metadata["notes"] = list(notes)

    return Evidence(
        evidence_id=f"ev_{assessment_id}",
        source_kr_id=assessment_id,
        source_kr_node_id=assessment_id,
        event_type=TECHNICAL_EVENT_TYPE,
        condition={"instrument": asset},
        bias=bias,
        base_confidence=round(confidence, 4),
        regime_weight=0.8,
        composite_weight=round(confidence * 0.8, 4),
        explanation=(
            f"TechnicalResearchDesk net direction {bias} "
            f"(trend={trend}, momentum={momentum}, structure={structure_state}) "
            f"as of {as_of}"
        ),
        regime="",
        source_label="technical_research_desk",
        mechanism="Price-based trend/momentum/structure second opinion on gold",
        provenance=provenance,
        metadata=metadata,
    )


def build_memory_evidence(
    adjudication: dict[str, Any] | None,
    analogue_payload: dict[str, Any] | None,
) -> Evidence | None:
    """Project the historical analogue adjudication onto one Evidence item.

    The adjudication (existing Correction-028 engine output) is the ONE
    estimator: several matched episodes never become several votes.  Bias
    follows the established status vocabulary -- uniform ``positive``
    history supports bullish, uniform ``negative`` history supports
    bearish, and any mixed / flat / neutralized combination is
    uninformative (Correction 033 semantics).  Base confidence reuses the
    existing retrieval similarity of the matches (analogue transfer
    strength); no new statistic is invented.
    """
    if not isinstance(adjudication, dict) or not adjudication:
        return None
    results = adjudication.get("horizon_results")
    if not isinstance(results, dict) or not results:
        return None

    statuses = {
        str(hk): str((results.get(hk) or {}).get("status", ""))
        for hk in results
        if isinstance(results.get(hk), dict)
    }
    statuses = {hk: status for hk, status in statuses.items() if status}
    if not statuses:
        return None
    unique = set(statuses.values())
    if unique == {"positive"}:
        bias = "bullish"
    elif unique == {"negative"}:
        bias = "bearish"
    else:
        # Mixed / flat / neutralized history is never converted into a
        # directional label (Correction 033): the memory stays uninformative.
        bias = "neutral"

    matches = []
    if isinstance(analogue_payload, dict):
        candidates = analogue_payload.get("matches")
        if isinstance(candidates, list):
            matches = [m for m in candidates if isinstance(m, dict)]
    similarities = [
        float(m["similarity"]["overall_similarity"])
        for m in matches
        if isinstance(m.get("similarity"), dict)
        and isinstance(m["similarity"].get("overall_similarity"), (int, float))
    ]
    base_confidence = (
        round(sum(similarities) / len(similarities), 4) if similarities else 0.0
    )

    lesson_ids: list[str] = []
    for m in matches:
        lesson_id = m.get("lesson_id")
        if lesson_id is not None and str(lesson_id) not in lesson_ids:
            lesson_ids.append(str(lesson_id))
    if not lesson_ids:
        return None
    source_kr_id = "hist_" + "-".join(lesson_ids)

    query = (
        analogue_payload.get("query")
        if isinstance(analogue_payload, dict)
        else None
    )
    condition = dict(query.get("condition")) if isinstance(query, dict) else {}

    provenance_payloads = []
    for m in matches:
        prov = m.get("provenance")
        if isinstance(prov, dict) and prov:
            provenance_payloads.append(prov)
    first_prov = provenance_payloads[0] if provenance_payloads else {}
    provenance = Provenance(
        created_at="",
        created_by="W6 historical-memory desk",
        entity_version="1.0.0",
        metadata={
            "desk_id": DESK_HISTORICAL,
            "lesson_ids": lesson_ids,
            "source_artifact_path": first_prov.get("source_artifact_path"),
            "source_artifact_sha256": first_prov.get("source_artifact_sha256"),
        },
    )

    metadata: dict[str, Any] = {
        "desk_id": DESK_HISTORICAL,
        "lesson_ids": lesson_ids,
        "horizon_statuses": statuses,
        "match_count": len(lesson_ids),
        "analogue_similarity": {
            str(m.get("lesson_id")): (m.get("similarity") or {}).get(
                "overall_similarity"
            )
            for m in matches
            if isinstance(m.get("similarity"), dict)
        },
        "retrieval_methods": {
            str(m.get("lesson_id")): (m.get("similarity") or {}).get(
                "retrieval_method"
            )
            for m in matches
            if isinstance(m.get("similarity"), dict)
        },
        "evidence_ids": list(adjudication.get("evidence_ids") or []),
    }

    return Evidence(
        evidence_id=f"ev_{source_kr_id}",
        source_kr_id=source_kr_id,
        source_kr_node_id=source_kr_id,
        event_type=HISTORICAL_MEMORY_EVENT_TYPE,
        condition=condition,
        bias=bias,
        base_confidence=base_confidence,
        regime_weight=0.8,
        composite_weight=round(base_confidence * 0.8, 4),
        explanation=(
            f"Historical analogue adjudication: {len(lesson_ids)} matched "
            f"episode(s), horizon statuses {statuses}; uniform-direction "
            f"mapping -> {bias}; transfer confidence from existing "
            f"retrieval similarity"
        ),
        regime="",
        source_label="historical_memory",
        mechanism="Empirical outcome distribution of the most similar historical episodes",
        provenance=provenance,
        metadata=metadata,
    )
