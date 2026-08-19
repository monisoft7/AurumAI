"""Correction 030: explanation-only contextual historical adjudication.

Joins the three existing explanation-only metadata payloads produced by
``EvidenceReasoner.reason`` — the current ``query`` (CPI condition / US10Y
trend / DXY trend / regime), ``historical_adjudication`` (horizon
adjudication of the exact analogue cohort) and ``factor_rationale``
(gold_rule_001 composite + regime precedence) — into ONE deterministic
contextual interpretation.

The result is stored at ``reasoning.metadata["contextual_historical_adjudication"]``
and composed into the thesis explanation as a new
``contextual_historical_adjudication:`` suffix after the
``historical_adjudication:`` chunk (W8 ThesisBuilder), preserved by
ThesisUpdater (W10).

Strictly explanatory, like every payload in this family:

* feeds no score, weight, confidence, counter-evidence, risk/reward or
  decision value (numeric invariance: only metadata/explanation differs);
* invents no numeric weights or thresholds — the context effect uses only
  the existing adjudication statuses (positive / negative / mixed /
  neutralized / flat) and the existing gold_rule_001 composite bias
  (strong_bullish / strong_bearish / mixed);
* preserves mixed and horizon-dependent history verbatim instead of
  converting it into a single directional label;
* explicitly distinguishes contextual support from causal proof;
* degrades to ``None`` (chunk omitted, outputs byte-identical to before)
  when the adjudication or the factor rationale is absent.

The current CPI condition is the historical query condition: the analogue
cohort was retrieved under exactly this query, so the historical tendency is
always read through the current query, never asserted as causality.
"""

from __future__ import annotations

from typing import Any

from knowledge.reasoning.rules.gold_rule_001 import (
    ASSESSMENT_MIXED,
    ASSESSMENT_STRONG_BEARISH,
    ASSESSMENT_STRONG_BULLISH,
)

HORIZON_ORDER: tuple[str, ...] = ("1d", "5d", "20d")

EFFECT_SUPPORTIVE = "supportive"
EFFECT_WEAKENING = "weakening"
EFFECT_CONTRADICTORY = "contradictory"
EFFECT_NEUTRAL = "neutral"

_CREATED_BY = "evidence_reasoning.contextual_historical_adjudication"

_NO_CAUSALITY_SENTENCE = (
    "Historical correlation does not establish causality; this is contextual "
    "support, not causal proof."
)


def build_contextual_historical_adjudication(
    historical_adjudication: dict[str, Any] | None,
    factor_rationale: dict[str, Any] | None,
    query: dict[str, Any] | None,
) -> dict[str, Any] | None:
    """Join adjudication + factor rationale + query into one interpretation.

    Returns ``None`` (chunk omitted, no change to outputs) when the
    historical adjudication or the factor rationale is missing or empty, or
    when the adjudication carries no horizon results.  Every output field is
    derived from the existing inputs; nothing is fabricated.
    """
    if not isinstance(historical_adjudication, dict) or not historical_adjudication:
        return None
    if not isinstance(factor_rationale, dict) or not factor_rationale:
        return None
    results = historical_adjudication.get("horizon_results")
    if not isinstance(results, dict) or not results:
        return None

    statuses = _horizon_statuses(results)
    tendency = _historical_tendency(statuses)
    composite_bias = _composite_bias(factor_rationale)
    effect = _context_effect(tendency, composite_bias)
    horizon_dependent = len(set(statuses.values())) > 1
    regime_context = _regime_context(factor_rationale)

    return {
        "historical_tendency": {
            "tendency": tendency,
            "statuses": dict(statuses),
            "horizon_dependent": horizon_dependent,
            "overall_interpretation": _overall_interpretation(
                tendency, composite_bias, effect, regime_context, horizon_dependent
            ),
            "adjudication_interpretation": str(
                historical_adjudication.get("overall_interpretation") or ""
            ),
            "evidence_ids": list(historical_adjudication.get("evidence_ids") or []),
        },
        "current_context": _current_context(factor_rationale, query),
        "context_effect": effect,
        "context_reason": _context_reason(
            tendency, composite_bias, effect, regime_context
        ),
        "horizon_assessment": _horizon_assessment(results, horizon_dependent),
        "regime_context": regime_context,
        "invalidation_conditions": _invalidation_conditions(
            historical_adjudication,
            factor_rationale,
            query,
            tendency,
            statuses,
            effect,
        ),
        "provenance": _provenance(factor_rationale, historical_adjudication, query),
        "overall_interpretation": _overall_interpretation(
            tendency, composite_bias, effect, regime_context, horizon_dependent
        ),
    }


def _horizon_statuses(results: dict[str, Any]) -> dict[str, str]:
    statuses: dict[str, str] = {}
    for hk in HORIZON_ORDER:
        result = results.get(hk)
        if isinstance(result, dict) and result.get("status"):
            statuses[hk] = str(result["status"])
    return statuses


def _historical_tendency(statuses: dict[str, str]) -> str:
    """Deterministic tendency from the existing horizon statuses.

    Any mixed status (or mixed directions across horizons) yields ``mixed`` —
    mixed history is never converted into a single bullish/bearish label.
    """
    present = list(statuses.values())
    pos = present.count("positive")
    neg = present.count("negative")
    if "mixed" in present or (pos > 0 and neg > 0):
        return "mixed"
    if pos > 0:
        return "positive"
    if neg > 0:
        return "negative"
    if "neutralized" in present:
        return "neutralized"
    if "flat" in present:
        return "flat"
    return "unknown"


def _composite_bias(factor_rationale: dict[str, Any]) -> str:
    bias = factor_rationale.get("composite_bias")
    return str(bias) if isinstance(bias, str) else ""


def _context_effect(tendency: str, composite_bias: str) -> str:
    """Map tendency x composite into the four-word effect vocabulary.

    Uses only the existing statuses; no numeric weights are invented.
    Conflicting current factors weaken (never confirm) the tendency; regime
    precedence explains the conflict but does not reweight it.
    """
    if tendency not in ("positive", "negative"):
        return EFFECT_NEUTRAL
    if composite_bias == ASSESSMENT_MIXED:
        return EFFECT_WEAKENING
    if (tendency == "positive" and composite_bias == ASSESSMENT_STRONG_BULLISH) or (
        tendency == "negative" and composite_bias == ASSESSMENT_STRONG_BEARISH
    ):
        return EFFECT_SUPPORTIVE
    if (tendency == "positive" and composite_bias == ASSESSMENT_STRONG_BEARISH) or (
        tendency == "negative" and composite_bias == ASSESSMENT_STRONG_BULLISH
    ):
        return EFFECT_CONTRADICTORY
    return EFFECT_NEUTRAL


def _current_context(
    factor_rationale: dict[str, Any],
    query: dict[str, Any] | None,
) -> dict[str, Any]:
    factors = factor_rationale.get("factors")
    if not isinstance(factors, list):
        factors = []
    return {
        "query": dict(query or {}),
        "composite_bias": factor_rationale.get("composite_bias"),
        "composite_strength": factor_rationale.get("composite_strength"),
        "composite_confidence": factor_rationale.get("composite_confidence"),
        "signal_dispersion": factor_rationale.get("signal_dispersion"),
        "factor_conflict": factor_rationale.get("composite_bias") == ASSESSMENT_MIXED,
        "factors": [
            {
                "factor_id": f.get("factor_id"),
                "influence_bias": f.get("influence_bias"),
                "influence_strength": f.get("influence_strength"),
                "confidence": f.get("confidence"),
                "status": f.get("status"),
            }
            for f in factors
            if isinstance(f, dict)
        ],
    }


def _regime_context(factor_rationale: dict[str, Any]) -> dict[str, Any]:
    return {
        "regime": factor_rationale.get("regime"),
        "dominant_factor": factor_rationale.get("dominant_factor"),
        "weaker_factor": factor_rationale.get("weaker_factor"),
        "precedence_reason": factor_rationale.get("precedence_reason"),
        "adjudicated_interpretation": factor_rationale.get(
            "adjudicated_interpretation"
        ),
    }


def _horizon_assessment(
    results: dict[str, Any], horizon_dependent: bool
) -> dict[str, Any]:
    statuses: dict[str, dict[str, Any]] = {}
    for hk in HORIZON_ORDER:
        result = results.get(hk)
        if not isinstance(result, dict):
            continue
        statuses[hk] = {
            "status": result.get("status"),
            "direction_summary": result.get("direction_summary"),
            "count": result.get("count"),
        }
    unique = {s["status"] for s in statuses.values()}
    return {
        "statuses": statuses,
        "horizon_dependent": horizon_dependent,
        "uniform": len(unique) == 1 if statuses else False,
    }


def _context_reason(
    tendency: str,
    composite_bias: str,
    effect: str,
    regime_context: dict[str, Any],
) -> str:
    parts = [
        f"Historical cohort tendency is {tendency}; the current factor composite "
        f"is {composite_bias}; the contextual effect of the historical evidence "
        f"is {effect}."
    ]
    if (
        composite_bias == ASSESSMENT_MIXED
        and regime_context.get("regime")
        and regime_context.get("dominant_factor")
        and regime_context.get("weaker_factor")
    ):
        parts.append(
            f"Under {regime_context['regime']}, factor precedence ranks "
            f"{regime_context['dominant_factor']} above "
            f"{regime_context['weaker_factor']}; the precedence explains, not "
            "reweights, the conflicting factors."
        )
    if effect == EFFECT_NEUTRAL and tendency == "mixed":
        parts.append(
            "Mixed history is preserved as mixed and is not converted into a "
            "directional label."
        )
    return " ".join(parts)


def _invalidation_conditions(
    adjudication: dict[str, Any],
    rationale: dict[str, Any],
    query: dict[str, Any] | None,
    tendency: str,
    statuses: dict[str, str],
    effect: str,
) -> list[str]:
    conditions: list[str] = []
    adj_query = adjudication.get("query")
    if not isinstance(adj_query, dict):
        adj_query = {}
    q = query if isinstance(query, dict) else {}

    adj_condition = adj_query.get("condition")
    cur_condition = q.get("condition")
    if isinstance(adj_condition, dict) and isinstance(cur_condition, dict):
        if adj_condition != cur_condition:
            conditions.append(
                "Current query condition differs from the adjudicated query "
                "condition - the contextual interpretation is invalidated."
            )
    else:
        conditions.append(
            "Current query condition is unavailable - the contextual match "
            "cannot be verified."
        )

    adj_regime = _query_regime(adj_query)
    cur_regime = _query_regime(q)
    if adj_regime and cur_regime and adj_regime != cur_regime:
        conditions.append(
            "The regime in the adjudicated query differs from the current query "
            "regime - the contextual interpretation is invalidated."
        )
    rationale_regime = rationale.get("regime")
    if rationale_regime and cur_regime and rationale_regime != cur_regime:
        conditions.append(
            "The regime in the factor rationale differs from the current query "
            "regime - the regime interpretation is invalidated."
        )

    if len(statuses) < len(HORIZON_ORDER):
        conditions.append(
            f"Historical adjudication covers {len(statuses)} of "
            f"{len(HORIZON_ORDER)} horizons - the historical evidence is partial."
        )
    if tendency == "mixed":
        conditions.append(
            "Historical outcomes are mixed - the historical tendency is "
            "ambiguous, not directional."
        )
    if "neutralized" in statuses.values():
        conditions.append(
            "The historical adjudication neutralized a direction conflict - the "
            "historical tendency is neutralized."
        )
    if effect == EFFECT_CONTRADICTORY:
        conditions.append(
            "Current factor context opposes the historical tendency - the "
            "historical evidence is contradicted in the current context."
        )
    if effect == EFFECT_WEAKENING:
        conditions.append(
            "Current factors conflict with each other - the historical evidence "
            "cannot be confirmed by the current factor context."
        )
    conditions.append(
        "Historical correlation does not establish causality - the analogy can "
        "be invalidated by unobserved structural change."
    )
    return conditions


def _query_regime(q: dict[str, Any]) -> str:
    inst = q.get("institutional_context")
    if isinstance(inst, dict) and inst.get("regime"):
        return str(inst["regime"])
    if q.get("regime"):
        return str(q["regime"])
    return ""


def _provenance(
    factor_rationale: dict[str, Any],
    adjudication: dict[str, Any],
    query: dict[str, Any] | None,
) -> dict[str, Any]:
    """Deterministic provenance: no synthetic timestamps, no UUIDs."""
    return {
        "created_by": _CREATED_BY,
        "created_at": "",
        "input_sources": {
            "historical_adjudication": True,
            "factor_rationale_rule_id": factor_rationale.get("rule_id"),
            "query": dict(query or {}),
        },
        "evidence_ids": list(adjudication.get("evidence_ids") or []),
    }


def _overall_interpretation(
    tendency: str,
    composite_bias: str,
    effect: str,
    regime_context: dict[str, Any],
    horizon_dependent: bool,
) -> str:
    parts = [
        f"Historical evidence is evaluated as {effect} in the current context: "
        f"the cohort tendency is {tendency} and the current factor composite is "
        f"{composite_bias}."
    ]
    if (
        composite_bias == ASSESSMENT_MIXED
        and regime_context.get("regime")
        and regime_context.get("dominant_factor")
        and regime_context.get("weaker_factor")
    ):
        parts.append(
            f"Under {regime_context['regime']}, factor precedence ranks "
            f"{regime_context['dominant_factor']} above "
            f"{regime_context['weaker_factor']} (explanation only; no "
            "reweighting)."
        )
    if horizon_dependent:
        parts.append("The historical relationship is horizon-dependent, not uniform.")
    parts.append(_NO_CAUSALITY_SENTENCE)
    return " ".join(parts)
