"""Sprint 061 -- Read-only adapters: existing desk artifacts -> canonical facts.

Every builder here is a **pure function** over artifacts that already exist
(news payload dicts, TechnicalAssessment dicts, RegimeDiagnosis dicts,
lesson rows, ReferencePrice values, risk validations).  They never mutate
their inputs, never re-classify, never re-score, and never feed anything
downstream of the producing artifact.  They only *declare* which canonical
primitives an artifact refers to so cross-desk identity becomes possible.

Mapping policy (deliberately conservative):

* Only unambiguous primitives get references.  A news headline whose event
  type has no clean market primitive stays unmapped -- an honest gap beats
  an invented fact.
* News facts describe *what the article refers to* (e.g. ``DXY state``),
  never a direction: directional semantics remain governed by
  Correction-051 inside the 058 classifier, untouched.
* Derived facts (technical stance) always declare ``derived_from`` pointing
  at the primitive facts they were computed from, satisfying the lineage
  requirement ``TechnicalAssessment -> derived_from -> primitive facts``.
"""

from __future__ import annotations

from typing import Any

from knowledge.facts.contracts import (
    DESK_HISTORICAL,
    DESK_MACRO_REGIME,
    DESK_NEWS,
    DESK_RISK_REWARD,
    DESK_TECHNICAL,
    CanonicalFact,
    DeskProvenance,
    primitive_fact_id,
)


def _to_assessment_dict(assessment: Any) -> dict[str, Any]:
    if isinstance(assessment, dict):
        return assessment
    return assessment.to_dict()


# ---------------------------------------------------------------------------
# Technical Research Desk (056-T) -- observability references only
# ---------------------------------------------------------------------------


def technical_fact_references(assessment: Any) -> dict[str, Any]:
    """Canonical facts for one TechnicalAssessment dict/dataclass.

    Primitive facts: last close, EMA-200 trend state, RSI-14 state and (when
    present) the BOS event.  The assessment-level stance is registered as a
    *derived* fact referencing those primitives.
    """
    payload = _to_assessment_dict(assessment)
    as_of = str(payload.get("as_of", ""))
    asset = str(payload.get("asset", "")) or "XAU/USD"
    timeframe = str(payload.get("timeframe", ""))
    snapshot = dict(payload.get("metadata", {}).get("indicator_snapshot", {}))
    structure = dict(payload.get("metadata", {}).get("structure", {}))
    base_metadata = {"timeframe": timeframe} if timeframe else {}

    def _fact(
        topic: str,
        value: str | None,
        *,
        unit: str = "state",
        derived: tuple[str, ...] = (),
        confidence: float = 1.0,
        extra_metadata: dict[str, Any] | None = None,
    ) -> CanonicalFact:
        meta = dict(base_metadata)
        if extra_metadata:
            meta.update(extra_metadata)
        return CanonicalFact(
            fact_id=primitive_fact_id(asset, topic, as_of),
            asset=asset,
            topic=topic,
            as_of=as_of,
            observed_at=as_of,
            value=value,
            unit=unit,
            source="gold_ohlcv",
            source_artifact_id=str(payload.get("assessment_id", "")),
            source_hash=str(payload.get("source_data_hash", "")),
            producer=DESK_TECHNICAL,
            derived_from=derived,
            confidence=float(confidence),
            valid_from=as_of,
            metadata=meta,
        )

    facts: list[CanonicalFact] = []
    close_value = snapshot.get("close")
    close_fact = None
    if close_value is not None:
        close_fact = _fact(
            "close", _format_number(close_value), unit="usd"
        )
        facts.append(close_fact)

    ema200_value = snapshot.get("ema_200")
    trend = str(payload.get("trend_direction", ""))
    derived_refs: list[str] = []
    if ema200_value is not None and trend:
        ema_fact = _fact(
            "ema200_trend_state",
            trend,
            derived=(close_fact.fact_id,) if close_fact else (),
        )
        facts.append(ema_fact)
        derived_refs.append(ema_fact.fact_id)

    rsi_value = snapshot.get("rsi_14")
    obos = str(payload.get("overbought_oversold_state", ""))
    rsi_fact = None
    if rsi_value is not None and obos:
        rsi_fact = _fact(
            "rsi14_state",
            obos,
            derived=(close_fact.fact_id,) if close_fact else (),
            extra_metadata={"rsi_14": _format_number(rsi_value)},
        )
        facts.append(rsi_fact)

    bos_flag = structure.get("bos_flag")
    if bos_flag:
        bos_fact = _fact(
            "structure_bos_event",
            str(bos_flag),
            derived=(close_fact.fact_id,) if close_fact else (),
        )
        facts.append(bos_fact)
        derived_refs.append(bos_fact.fact_id)

    if trend and trend != "unknown":
        stance_refs = list(derived_refs)
        if rsi_fact is not None:
            stance_refs.append(rsi_fact.fact_id)
        facts.append(
            _fact(
                "net_technical_stance",
                trend,
                derived=tuple(dict.fromkeys(stance_refs)),
                confidence=float(payload.get("technical_confidence", 0.0)),
                extra_metadata={
                    "momentum_direction": str(
                        payload.get("momentum_direction", "")
                    ),
                    "structure_state": str(
                        payload.get("structure_state") or ""
                    ),
                },
            )
        )

    declaration = DeskProvenance(
        desk_id=DESK_TECHNICAL,
        assessment_id=str(payload.get("assessment_id", "")),
        facts_used=tuple(f.fact_id for f in facts if f.topic != "net_technical_stance"),
        derived_facts=tuple(
            f.fact_id for f in facts if f.topic == "net_technical_stance"
        ),
        source_artifacts=(
            (
                f"gold_ohlcv#{str(payload.get('source_data_hash', ''))[:16]}"
                if payload.get("source_data_hash")
                else ""
            ),
        ),
        as_of=as_of,
        horizon_scope="technical",
        confidence=float(payload.get("technical_confidence", 0.0)),
    )

    return {
        "status": "ok",
        "facts": [f.to_dict() for f in facts],
        "desk_provenance": declaration.to_dict(),
    }


# ---------------------------------------------------------------------------
# News Intelligence (058) -- publication-event primitives only
# ---------------------------------------------------------------------------

_NEWS_PRIMITIVE_BY_EVENT_TYPE: dict[str, tuple[str, str]] = {
    # event_type -> (asset, topic)
    "cpi_inflation": ("US_CPI", "cpi_release_reference"),
    "fed_fomc": ("FED", "fomc_event_reference"),
    "usd_dollar": ("DXY", "usd_state_reference"),
    "yields": ("US10Y", "yield_state_reference"),
    "cb_gold_demand": ("XAU/USD", "cb_gold_demand_report"),
}


def news_fact_references(news_payload: dict[str, Any]) -> dict[str, Any]:
    """Canonical publication-event facts for a Sprint-058 news payload.

    Identity binds ``(asset, topic, publication date)``; the article's own
    ``article_id``/``content_hash`` ride along as source provenance, so two
    desks can discover that macro context and news context touch the same
    underlying primitive (DXY, CPI, FOMC, US10Y, CB gold demand).
    """
    items = news_payload.get("items") or []
    references: list[dict[str, Any]] = []
    unmapped: list[str] = []
    all_facts: list[CanonicalFact] = []

    for item in items:
        event_type = str(item.get("event_type", ""))
        mapping = _NEWS_PRIMITIVE_BY_EVENT_TYPE.get(event_type)
        article_id = str(item.get("article_id", ""))
        if mapping is None:
            if article_id:
                unmapped.append(article_id)
            continue
        asset, topic = mapping
        published_at = str(item.get("published_at", "") or "")
        as_of = published_at[:10] if published_at else ""
        fact = CanonicalFact(
            fact_id=primitive_fact_id(asset, topic, as_of),
            asset=asset,
            topic=topic,
            as_of=as_of,
            observed_at=published_at,
            value=None,
            unit="state",
            source=str(item.get("source", "")),
            source_artifact_id=article_id,
            source_hash=str(item.get("content_hash", "")),
            producer=DESK_NEWS,
            derived_from=(),
            confidence=float(item.get("confidence", 0.0)),
            valid_from=as_of,
            metadata={
                "headline_hash_source": "news_intelligence",
                "directional_implication": str(
                    item.get("directional_implication", "")
                ),
            },
        )
        all_facts.append(fact)
        references.append(
            {
                "article_id": article_id,
                "event_type": event_type,
                "facts": [fact.to_dict()],
            }
        )

    status = "ok" if all_facts else "empty"
    declaration = DeskProvenance(
        desk_id=DESK_NEWS,
        assessment_id=news_payload_fingerprint(news_payload),
        facts_used=tuple(sorted({f.fact_id for f in all_facts})),
        derived_facts=(),
        source_artifacts=tuple(
            item.get("article_id", "")
            for item in items
            if item.get("article_id")
        ),
        as_of=str(news_payload.get("as_of") or ""),
        horizon_scope="news",
        confidence=0.0,
    )
    return {
        "status": status,
        "references": references,
        "unmapped_article_ids": unmapped,
        "facts": [f.to_dict() for f in all_facts],
        "desk_provenance": declaration.to_dict(),
    }


def news_payload_fingerprint(news_payload: dict[str, Any]) -> str:
    """Deterministic fingerprint of a news payload (identity of the batch).

    Uses only semantic fields (item article ids + as_of), never wall clock,
    so repeated runs over the same articles produce the same batch id.
    """
    import hashlib

    from knowledge.facts.contracts import canonical_json

    material = canonical_json(
        {
            "as_of": str(news_payload.get("as_of") or ""),
            "articles": sorted(
                str(i.get("article_id", "")) for i in (news_payload.get("items") or [])
            ),
        }
    )
    digest = hashlib.sha256(material.encode("utf-8")).hexdigest()[:16]
    return f"news_batch_{digest}"


# ---------------------------------------------------------------------------
# Macro / Regime desk -- first durable identity for RegimeDiagnosis
# ---------------------------------------------------------------------------


def regime_fact_references(
    diagnosis: Any,
    *,
    as_of: str | None = None,
) -> dict[str, Any]:
    """Canonical regime-state facts for one RegimeDiagnosis dict/dataclass.

    ``as_of`` should be supplied by the caller for determinism (the diagnosis
    timestamp is wall-clock).  When omitted, the date portion of the
    diagnosis timestamp is used and determinism is bounded to same-day runs.
    """
    payload = _to_assessment_dict(diagnosis)
    effective_as_of = as_of or str(payload.get("timestamp", ""))[:10]
    regime = str(payload.get("regime", ""))
    confidence = float(payload.get("confidence", 0.0))

    facts: list[CanonicalFact] = []
    state_fact = CanonicalFact(
        fact_id=primitive_fact_id("GOLD", "macro_regime_state", effective_as_of),
        asset="GOLD",
        topic="macro_regime_state",
        as_of=effective_as_of,
        observed_at=str(payload.get("timestamp", ""))[:10],
        value=regime or None,
        unit="state",
        source="institutional_regime_detector",
        source_artifact_id=f"regime_diagnosis#{effective_as_of}",
        source_hash="",
        producer=DESK_MACRO_REGIME,
        derived_from=(),
        confidence=confidence,
        valid_from=effective_as_of,
    )
    facts.append(state_fact)

    if bool(payload.get("in_transition")):
        facts.append(
            CanonicalFact(
                fact_id=primitive_fact_id(
                    "GOLD", "macro_regime_transition", effective_as_of
                ),
                asset="GOLD",
                topic="macro_regime_transition",
                as_of=effective_as_of,
                observed_at=str(payload.get("timestamp", ""))[:10],
                value=str(payload.get("transition_type", "")) or None,
                unit="state",
                source="institutional_regime_detector",
                source_artifact_id=f"regime_diagnosis#{effective_as_of}",
                source_hash="",
                producer=DESK_MACRO_REGIME,
                derived_from=(state_fact.fact_id,),
                confidence=float(payload.get("transition_confidence", 0.0)),
                valid_from=effective_as_of,
            )
        )

    declaration = DeskProvenance(
        desk_id=DESK_MACRO_REGIME,
        assessment_id=f"regime_diagnosis#{effective_as_of}",
        facts_used=(state_fact.fact_id,),
        derived_facts=tuple(
            f.fact_id for f in facts if f.topic == "macro_regime_transition"
        ),
        source_artifacts=("composite_score",),
        as_of=effective_as_of,
        horizon_scope="macro_regime",
        confidence=confidence,
    )
    return {
        "status": "ok",
        "facts": [f.to_dict() for f in facts],
        "desk_provenance": declaration.to_dict(),
    }


# ---------------------------------------------------------------------------
# Historical research -- analogue / episode references
# ---------------------------------------------------------------------------


def analogue_reference_fact(
    lesson_id: str,
    event_date: str,
    source_artifact_sha256: str = "",
    *,
    similarity_label: str = "",
) -> CanonicalFact:
    """Canonical reference to one historical episode (lesson-backed).

    Episode identity stays borrowed from the lesson artifact (never
    regenerated), matching the temporal-layer rule ``state_id == lesson_id``.
    """
    label = similarity_label or None
    return CanonicalFact(
        fact_id=primitive_fact_id("XAU/USD", "historical_analogue_reference", event_date),
        asset="XAU/USD",
        topic="historical_analogue_reference",
        as_of=event_date,
        observed_at=event_date,
        value=label,
        unit="label",
        source="lesson_archive",
        source_artifact_id=lesson_id,
        source_hash=source_artifact_sha256,
        producer=DESK_HISTORICAL,
        derived_from=(),
        confidence=0.0,
        valid_from=event_date,
    )


# ---------------------------------------------------------------------------
# Reference price (057) -- same primitive space as the technical close
# ---------------------------------------------------------------------------


def reference_price_fact(
    reference_price: Any,
    *,
    as_of: str | None = None,
) -> CanonicalFact:
    """Canonical close fact from a resolved ReferencePrice.

    Deliberately uses the same primitive space ``(XAU/USD, close, anchor)``
    as the technical desk's close fact.  By default the anchor is the
    resolved ``bar_date``; when a caller knows both artifacts describe the
    state as of one boundary, pass ``as_of`` explicitly so both producers
    converge onto a single identity.
    """
    data = (
        reference_price
        if isinstance(reference_price, dict)
        else reference_price.to_dict()
    )
    bar_date = str(data.get("bar_date", ""))
    effective_as_of = str(as_of or bar_date)
    value = data.get("value")
    return CanonicalFact(
        fact_id=primitive_fact_id("XAU/USD", "close", effective_as_of),
        asset="XAU/USD",
        topic="close",
        as_of=effective_as_of,
        observed_at=bar_date,
        value=_format_number(value),
        unit="usd",
        source="run_gold_csv",
        source_artifact_id=f"reference_price#{bar_date}",
        source_hash=str(data.get("source_data_hash", "")),
        producer="reference_price",
        derived_from=(),
        confidence=1.0,
        valid_from=effective_as_of,
    )


# ---------------------------------------------------------------------------
# Risk / RR desk -- lineage declaration only (W12 untouched)
# ---------------------------------------------------------------------------


def risk_desk_provenance(validation_like: Any) -> DeskProvenance:
    """Desk declaration for a RiskRewardValidation-like object.

    Reads attributes defensively and declares only upstream artifact links
    (scenario/thesis).  Per Correction-052-A the RR desk consumes conviction
    proxies, not market primitives, hence ``facts_used`` stays empty unless
    a caller explicitly extends it.
    """
    validation_id = str(getattr(validation_like, "validation_id", "") or "")
    scenario_id = str(getattr(validation_like, "scenario_id", "") or "")
    thesis_id = str(getattr(validation_like, "thesis_id", "") or "")
    chain = getattr(validation_like, "provenance_chain", ()) or ()
    artifacts = [
        item
        for item in (scenario_id, thesis_id, *(getattr(p, "created_by", "") or "" for p in chain))
        if item
    ]
    horizon = ""
    for attr in ("time_horizon_days", "horizon_days"):
        value = getattr(validation_like, attr, None)
        if value is not None:
            horizon = f"{attr}:{value}"
            break
    return DeskProvenance(
        desk_id=DESK_RISK_REWARD,
        assessment_id=validation_id,
        facts_used=(),
        derived_facts=(),
        source_artifacts=tuple(dict.fromkeys(artifacts)),
        horizon_scope=horizon or "risk_reward",
        confidence=0.0,
        metadata={"metrics_basis": "conviction_proxy"},
    )


def _format_number(value: Any) -> str | None:
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return str(value)
    return f"{number:.6f}".rstrip("0").rstrip(".")
