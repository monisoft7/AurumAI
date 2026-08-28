"""Correction 028: explanation-only adjudication of historical gold analogues.

Reuses the existing ``knowledge.reasoning.engine.LegacyReasoningEngine`` to
interpret the outcomes attached to the explanation-only historical analogue
payload (Correction 025-B) across three independent horizon groups
(1d / 5d / 20d).

The analogue matches are projected onto ``knowledge.evidence.Evidence`` ONLY
as a temporary adapter structure consumed by the reasoning call.  These
temporary items:

* never enter the institutional EvidenceCollection / W7-W13 path,
* feed no score, weight, confidence, counter-evidence, risk/reward or
  decision value (numeric invariance), and
* carry a neutral confidence constant (1.0) that mirrors the existing
  TemporalEvidenceAdapter episode semantics (the analogue payload aggregate
  already reports ``avg_confidence: 1.0``); it is NOT a new reliability
  formula and is never combined with institutional evidence.

Provenance carries no synthetic timestamps (``created_at`` is empty), so the
engine's recency factor is fixed at its neutral 0.5 and every run is fully
deterministic.  Per-match identity, historical condition, regime and gold
outcome are preserved verbatim from the analogue records.

The output is stored at ``reasoning.metadata["historical_adjudication"]`` as:

    {
      "horizon_results": {
        "1d": {status, direction_summary, engine_conclusion, ...},
        "5d": {...},
        "20d": {...},
      },
      "overall_interpretation": "...",   # deterministic, derived from results
      "evidence_ids": [...],             # lesson_ids, no synthetic ids
      "query": {...},                    # preserved analogue query context
    }
"""

from __future__ import annotations

from typing import Any

from knowledge.evidence.collection import EvidenceCollection
from knowledge.evidence.evidence import Evidence
from knowledge.integrity.provenance import Provenance
from knowledge.reasoning.context import ReasoningContext
from knowledge.reasoning.engine import ReasoningEngine
from knowledge.reasoning.step import STEP_AGGREGATION

HORIZON_KEYS: tuple[str, ...] = ("1d", "5d", "20d")

_HORIZON_RETURN_FIELDS: dict[str, str] = {
    "1d": "gold_return_1d_pct",
    "5d": "gold_return_5d_pct",
    "20d": "gold_return_20d_pct",
}

_HORIZON_DIRECTION_FIELDS: dict[str, str] = {
    "1d": "gold_direction_1d",
    "5d": "gold_direction_5d",
    "20d": "gold_direction_20d",
}

_DIRECTION_LABELS: dict[str, str] = {
    "UP": "positive",
    "DOWN": "negative",
    "FLAT": "flat",
}

_NEUTRAL_ADAPTER_CONFIDENCE = 1.0

_HORIZON_LABELS: dict[str, str] = {
    "1d": "1 day",
    "5d": "5 days",
    "20d": "20 days",
}


def build_historical_adjudication(payload: dict[str, Any] | None) -> dict[str, Any] | None:
    """Adjudicate the historical analogue payload with the existing engine.

    Returns ``None`` (no adjudication) when the payload is missing, empty or
    carries no matches, or when no horizon group has at least two analysable
    episodes (the engine's comparison semantics require >= 2 items).
    """
    if not isinstance(payload, dict):
        return None
    matches = payload.get("matches") or []
    if not isinstance(matches, list) or not matches:
        return None

    results: dict[str, Any] = {}
    for hk in HORIZON_KEYS:
        result = _adjudicate_horizon(payload, matches, hk)
        if result is not None:
            results[hk] = result
    if not results:
        return None

    evidence_ids: list[str] = []
    for m in matches:
        lesson_id = m.get("lesson_id")
        if lesson_id is not None and str(lesson_id) not in evidence_ids:
            evidence_ids.append(str(lesson_id))

    return {
        "horizon_results": results,
        "overall_interpretation": _overall_interpretation(results),
        "evidence_ids": evidence_ids,
        "query": payload.get("query") or {},
    }


def _adjudicate_horizon(
    payload: dict[str, Any],
    matches: list[dict[str, Any]],
    hk: str,
) -> dict[str, Any] | None:
    items = [_temporary_evidence(m, hk) for m in matches]
    items = [ev for ev in items if ev is not None]
    if len(items) < 2:
        return None

    chain = ReasoningEngine().reason(
        EvidenceCollection(items=tuple(items)),
        _reasoning_context(payload, hk),
    )

    directions: list[str] = []
    inputs: list[dict[str, Any]] = []
    for m in matches:
        outcome = m.get("gold_outcome") or {}
        ret = outcome.get(_HORIZON_RETURN_FIELDS[hk])
        if ret is None:
            continue
        raw_direction = outcome.get(_HORIZON_DIRECTION_FIELDS[hk], "FLAT")
        directions.append(_DIRECTION_LABELS.get(raw_direction, "flat"))
        prov = m.get("provenance") or {}
        inputs.append(
            {
                "lesson_id": m.get("lesson_id"),
                "event_date": m.get("event_date"),
                "horizon": hk,
                "gold_return_pct": round(float(ret), 6),
                "gold_direction": raw_direction,
                "source_artifact_path": prov.get("source_artifact_path"),
                "source_artifact_sha256": prov.get("source_artifact_sha256"),
            }
        )

    agg = _aggregation_details(chain)
    return {
        "count": len(inputs),
        "returns_pct": [i["gold_return_pct"] for i in inputs],
        "directions": directions,
        "direction_summary": _direction_summary(directions),
        "status": _status(agg, directions),
        "engine_conclusion": chain.final_conclusion,
        "engine_confidence": chain.overall_confidence,
        "aggregation": agg,
        "inputs": inputs,
    }


def _temporary_evidence(match: dict[str, Any], hk: str) -> Evidence | None:
    """Temporary adapter projection of one analogue match onto one horizon."""
    lesson_id = match.get("lesson_id")
    outcome = match.get("gold_outcome") or {}
    return_pct = outcome.get(_HORIZON_RETURN_FIELDS[hk])
    if lesson_id is None or return_pct is None:
        return None
    provenance = match.get("provenance") or {}
    regime = dict(match.get("historical_regime") or {})
    prov = Provenance(
        created_at="",
        created_by="historical-analogue-adjudication",
        entity_version="1.0",
        metadata={
            "lesson_id": str(lesson_id),
            "event_date": match.get("event_date"),
            "source_artifact_path": provenance.get("source_artifact_path"),
            "source_artifact_sha256": provenance.get("source_artifact_sha256"),
        },
    )
    return Evidence(
        evidence_id=str(lesson_id),
        source_node_id=str(lesson_id),
        event_type="CPI",
        condition=dict(match.get("historical_condition") or {}),
        horizon_days=int(hk[:-1]),
        sample_count=1,
        average_return_pct=float(return_pct),
        confidence=_NEUTRAL_ADAPTER_CONFIDENCE,
        bias="",
        explanation=f"temporary adapter projection of a historical analogue match onto the {hk} horizon",
        provenance=prov,
        metadata={"institutional_context": regime, "horizon": hk},
    )


def _reasoning_context(payload: dict[str, Any], hk: str) -> ReasoningContext:
    query = payload.get("query") or {}
    return ReasoningContext(
        event_type=query.get("event_type") or "CPI",
        condition=dict(query.get("condition") or {}),
        horizon_days=int(hk[:-1]),
        institutional_context=dict(query.get("institutional_context") or {}),
    )


def _aggregation_details(chain: Any) -> dict[str, Any]:
    for step in chain.steps:
        if step.step_type == STEP_AGGREGATION:
            return dict(step.details)
    return {}


def _status(agg: dict[str, Any], directions: list[str]) -> str:
    """Adjudicated status: engine conflict resolution first, else record labels.

    ``direction_conflict`` / ``dominant_direction`` / ``neutralized`` are
    produced only by the existing engine's dominance machinery (requires >= 2
    distinct (condition | horizon) groups); with exact-match cohorts the
    status is derived from the existing ``gold_direction_*`` record labels.
    """
    if agg.get("direction_conflict"):
        dom = agg.get("dominant_direction")
        return "neutralized" if dom in (None, "neutral") else str(dom)
    return _direction_summary(directions)


def _direction_summary(directions: list[str]) -> str:
    present = set(directions)
    if "positive" in present and "negative" in present:
        return "mixed"
    if present == {"positive"}:
        return "positive"
    if present == {"negative"}:
        return "negative"
    if present == {"flat"}:
        return "flat"
    if "positive" in present:
        return "positive"
    if "negative" in present:
        return "negative"
    return "flat"


def _overall_interpretation(results: dict[str, Any]) -> str:
    """Deterministic interpretation text derived from the horizon results."""
    order = [k for k in HORIZON_KEYS if k in results]
    statuses = {k: str(results[k]["status"]) for k in order}
    unique = set(statuses.values())
    labels = [_HORIZON_LABELS[k] for k in order]

    if len(unique) == 1:
        return (
            f"Historical analogues are consistently {next(iter(unique))} across "
            f"{', '.join(labels)}, indicating a uniform rather than "
            f"horizon-dependent relationship."
        )

    desc = (
        ", ".join(f"{statuses[k]} at {_HORIZON_LABELS[k]}" for k in order[:-1])
        + f" and {statuses[order[-1]]} at {_HORIZON_LABELS[order[-1]]}"
    )
    if "positive" in unique:
        uniform = "bullish"
    elif "negative" in unique:
        uniform = "bearish"
    else:
        uniform = "directional"
    return (
        f"Historical analogues are {desc}, indicating a horizon-dependent "
        f"rather than uniformly {uniform} relationship."
    )