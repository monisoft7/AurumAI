"""Sprint 061 -- Canonical Fact identity and cross-desk provenance contracts.

A CanonicalFact is the smallest addressable unit of market reality that more
than one research desk can refer to (``DXY close on 2026-08-25``, ``CPI
release for reference month M``, ``RSI-14 state as of D``, ...).

Design rules enforced here:

* Deterministic identity.  ``primitive_fact_id`` is a pure function of
  ``(asset, topic, as_of)`` -- no wall clock, no randomness, no UUIDs.
  Two desks observing the same primitive therefore derive the *same*
  ``fact_id`` even when they phrase the value differently.  This is what
  makes same-fact detection possible without any shared mutable store.
* Content-addressable assertions.  ``record_hash`` is a sha256 over the
  semantic content of one producer's assertion of a primitive.  Re-registering
  an identical assertion is idempotent; a changed value under the same
  primitive produces a different record, never a mutation.
* As-of safety.  Every fact carries ``as_of`` (state time), ``observed_at``
  (release/publication time) and explicit validity boundaries.
  :func:`assert_no_lookahead` rejects facts whose state or release time is
  after an evaluation date, transitively over the derivation closure,
  fail-closed on unparseable temporal fields.
* Read/reference only.  Nothing in this module reads or writes decisions,
  weights, confidence semantics or outcome records.  It is provenance and
  identity plumbing for future institutional adjudication.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any, Callable

from knowledge._compat import FrozenDict, freeze_dict

FACT_SCHEMA_VERSION = "1.0"
FACT_ID_PREFIX = "fct_"
FACT_ID_VERSION_TAG = "v1"

# Research desk identifiers (Phase 5).  Outcome tracking is deliberately not
# a research desk and must never appear here.
DESK_MACRO_REGIME = "macro_regime"
DESK_NEWS = "news_intelligence"
DESK_TECHNICAL = "technical_research"
DESK_HISTORICAL = "historical_research"
DESK_RISK_REWARD = "risk_reward"

POLARITY_BULLISH = "bullish"
POLARITY_BEARISH = "bearish"
POLARITY_NEUTRAL = "neutral"
POLARITY_UNKNOWN = "unknown"


class FactLookaheadError(ValueError):
    """Raised when a fact (or its lineage) violates an as-of boundary."""


def canonical_json(payload: Any) -> str:
    """Stable JSON serialization used by every hash in this package."""
    return json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    )


def _digest(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def normalize_identity_component(value: str) -> str:
    """Light normalization for identity inputs: trim + lowercase.

    Values are NOT normalized away into oblivion: only identity components
    (asset/topic) are case-insensitive; ``value`` stays verbatim so distinct
    phrasings remain distinguishable observations of one primitive.
    """
    return " ".join(str(value or "").split()).strip().lower()


def primitive_fact_id(asset: str, topic: str, as_of: str) -> str:
    """Deterministic cross-desk identity of one underlying market primitive.

    Same primitive observed by different desks -> same id (this is the
    property that lets a future adjudicator collapse double counting).
    Changed asset/topic/as-of -> different id.
    """
    key = "|".join(
        [
            FACT_ID_VERSION_TAG,
            normalize_identity_component(asset),
            normalize_identity_component(topic),
            str(as_of or "").strip(),
        ]
    )
    return FACT_ID_PREFIX + _digest(key)[:16]


def parse_temporal(value: str) -> date:
    """Parse an ISO date/datetime strictly; return a calendar date.

    Raises ``ValueError`` for anything unparseable -- temporal identity is
    fail-closed, mirroring historical_validation semantics.
    """
    text = str(value or "").strip()
    if not text:
        raise ValueError("empty temporal field")
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        return parsed.date()
    except ValueError:
        pass
    return date.fromisoformat(text[:10])


@dataclass(frozen=True)
class CanonicalFact:
    """One producer's immutable assertion of one canonical market primitive."""

    fact_id: str
    asset: str
    topic: str
    as_of: str
    observed_at: str = ""
    value: str | None = None
    unit: str = ""
    source: str = ""
    source_artifact_id: str = ""
    source_hash: str = ""
    producer: str = ""
    derived_from: tuple[str, ...] = ()
    confidence: float = 0.0
    valid_from: str = ""
    valid_until: str = ""
    schema_version: str = FACT_SCHEMA_VERSION
    metadata: dict[str, Any] = field(default_factory=lambda: FrozenDict())

    def __post_init__(self) -> None:
        object.__setattr__(self, "derived_from", tuple(self.derived_from))
        object.__setattr__(self, "metadata", freeze_dict(self.metadata))

    # ------------------------------------------------------------------
    # Content addressing
    # ------------------------------------------------------------------

    def content_payload(self) -> dict[str, Any]:
        """Semantic assertion content covered by ``record_hash``.

        Free-form ``metadata`` is deliberately excluded: it may carry
        wall-clock observability fields and is not part of identity.
        """
        return {
            "schema_version": self.schema_version,
            "fact_id": self.fact_id,
            "asset": normalize_identity_component(self.asset),
            "topic": normalize_identity_component(self.topic),
            "as_of": self.as_of,
            "observed_at": self.observed_at,
            "value": self.value,
            "unit": self.unit,
            "source": self.source,
            "source_artifact_id": self.source_artifact_id,
            "source_hash": self.source_hash,
            "producer": self.producer,
            "derived_from": list(self.derived_from),
            "confidence": round(float(self.confidence), 6),
            "valid_from": self.valid_from,
            "valid_until": self.valid_until,
        }

    def record_hash(self) -> str:
        """Content hash of this specific assertion (full hex digest)."""
        return _digest(canonical_json(self.content_payload()))

    # ------------------------------------------------------------------
    # Serialization / validation
    # ------------------------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "fact_id": self.fact_id,
            "record_hash": self.record_hash(),
            "asset": self.asset,
            "topic": self.topic,
            "as_of": self.as_of,
            "observed_at": self.observed_at,
            "value": self.value,
            "unit": self.unit,
            "source": self.source,
            "source_artifact_id": self.source_artifact_id,
            "source_hash": self.source_hash,
            "producer": self.producer,
            "derived_from": list(self.derived_from),
            "confidence": float(self.confidence),
            "valid_from": self.valid_from,
            "valid_until": self.valid_until,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CanonicalFact":
        return cls(
            fact_id=str(data.get("fact_id", "")),
            asset=str(data.get("asset", "")),
            topic=str(data.get("topic", "")),
            as_of=str(data.get("as_of", "")),
            observed_at=str(data.get("observed_at", "")),
            value=(None if data.get("value") is None else str(data.get("value"))),
            unit=str(data.get("unit", "")),
            source=str(data.get("source", "")),
            source_artifact_id=str(data.get("source_artifact_id", "")),
            source_hash=str(data.get("source_hash", "")),
            producer=str(data.get("producer", "")),
            derived_from=tuple(data.get("derived_from", ())),
            confidence=float(data.get("confidence", 0.0)),
            valid_from=str(data.get("valid_from", "")),
            valid_until=str(data.get("valid_until", "")),
            schema_version=str(data.get("schema_version", FACT_SCHEMA_VERSION)),
            metadata=dict(data.get("metadata", {})),
        )

    def validate(self) -> list[str]:
        errors: list[str] = []
        if not self.fact_id.startswith(FACT_ID_PREFIX):
            errors.append(f"fact_id must start with {FACT_ID_PREFIX}")
        expected = primitive_fact_id(self.asset, self.topic, self.as_of)
        if self.fact_id != expected:
            errors.append(f"fact_id mismatch: {self.fact_id} != {expected}")
        if not self.asset:
            errors.append("asset is required")
        if not self.topic:
            errors.append("topic is required")
        if not self.as_of:
            errors.append("as_of is required")
        if not self.producer:
            errors.append("producer is required")
        if not 0.0 <= float(self.confidence) <= 1.0:
            errors.append(f"confidence out of range: {self.confidence}")
        for upstream in self.derived_from:
            if not upstream.startswith(FACT_ID_PREFIX):
                errors.append(f"derived_from entry is not a fact id: {upstream}")
        effective_valid_from = self.valid_from or self.as_of
        try:
            if parse_temporal(effective_valid_from) > parse_temporal(self.as_of):
                errors.append("valid_from after as_of")
            if self.valid_until:
                vf = parse_temporal(effective_valid_from)
                vu = parse_temporal(self.valid_until)
                if vu < vf:
                    errors.append("valid_until before valid_from")
        except ValueError as exc:
            errors.append(f"unparseable validity boundary: {exc}")
        return errors

    # ------------------------------------------------------------------
    # Historical safety
    # ------------------------------------------------------------------

    def assert_not_after(self, evaluation_date: str | date) -> None:
        """Reject this single fact if it lies beyond ``evaluation_date``.

        Both the state time (``as_of``/``valid_from``) and the release time
        (``observed_at``, when present) are checked; unparseable fields fail
        closed.  Mirrors ``ValidationSnapshot.assert_no_lookahead`` semantics
        without touching that module.
        """
        cutoff = evaluation_date if isinstance(evaluation_date, date) else None
        if cutoff is None:
            cutoff = parse_temporal(str(evaluation_date))
        if parse_temporal(self.as_of) > cutoff:
            raise FactLookaheadError(
                f"fact {self.fact_id} as_of={self.as_of} is after "
                f"evaluation_date={cutoff.isoformat()}"
            )
        if parse_temporal(self.valid_from or self.as_of) > cutoff:
            raise FactLookaheadError(
                f"fact {self.fact_id} valid_from={self.valid_from} is after "
                f"evaluation_date={cutoff.isoformat()}"
            )
        if self.observed_at and parse_temporal(self.observed_at) > cutoff:
            raise FactLookaheadError(
                f"fact {self.fact_id} observed_at={self.observed_at} is after "
                f"evaluation_date={cutoff.isoformat()}"
            )


def assert_no_lookahead(
    fact: CanonicalFact,
    evaluation_date: str | date,
    *,
    resolve: Callable[[str], tuple[CanonicalFact, ...]] | None = None,
) -> None:
    """Reject a fact whose derivation chain reaches beyond ``evaluation_date``.

    ``resolve`` maps an upstream fact id to its registered observations
    (pass ``registry.get``); every reachable ancestor assertion is validated
    against the cutoff.  When omitted only the fact itself is checked.
    Traversal is iterative with sorted expansion so violations surface
    deterministically.
    """
    fact.assert_not_after(evaluation_date)
    if resolve is None:
        return
    seen: set[str] = set()
    stack = sorted(set(fact.derived_from))
    while stack:
        fid = stack.pop(0)
        if fid in seen:
            continue
        seen.add(fid)
        for parent in sorted(resolve(fid)):
            parent.assert_not_after(evaluation_date)
            for grandparent in sorted(parent.derived_from):
                if grandparent not in seen:
                    stack.append(grandparent)


@dataclass(frozen=True)
class DeskProvenance:
    """Cross-desk declaration (Phase 5): what a desk assessment consumed.

    ``facts_used`` are primitives the assessment directly relied on;
    ``derived_facts`` are higher-level statements the desk itself produced
    from those primitives.  Outcome tracking never declares here.
    """

    desk_id: str
    assessment_id: str
    facts_used: tuple[str, ...] = ()
    derived_facts: tuple[str, ...] = ()
    source_artifacts: tuple[str, ...] = ()
    as_of: str = ""
    horizon_scope: str = ""
    confidence: float = 0.0
    metadata: dict[str, Any] = field(default_factory=lambda: FrozenDict())

    def __post_init__(self) -> None:
        object.__setattr__(self, "facts_used", tuple(self.facts_used))
        object.__setattr__(self, "derived_facts", tuple(self.derived_facts))
        object.__setattr__(self, "source_artifacts", tuple(self.source_artifacts))
        object.__setattr__(self, "metadata", freeze_dict(self.metadata))

    def to_dict(self) -> dict[str, Any]:
        return {
            "desk_id": self.desk_id,
            "assessment_id": self.assessment_id,
            "facts_used": list(self.facts_used),
            "derived_facts": list(self.derived_facts),
            "source_artifacts": list(self.source_artifacts),
            "as_of": self.as_of,
            "horizon_scope": self.horizon_scope,
            "confidence": float(self.confidence),
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "DeskProvenance":
        return cls(
            desk_id=str(data.get("desk_id", "")),
            assessment_id=str(data.get("assessment_id", "")),
            facts_used=tuple(data.get("facts_used", ())),
            derived_facts=tuple(data.get("derived_facts", ())),
            source_artifacts=tuple(data.get("source_artifacts", ())),
            as_of=str(data.get("as_of", "")),
            horizon_scope=str(data.get("horizon_scope", "")),
            confidence=float(data.get("confidence", 0.0)),
            metadata=dict(data.get("metadata", {})),
        )

    def validate(self) -> list[str]:
        errors: list[str] = []
        if not self.desk_id:
            errors.append("desk_id is required")
        if not self.assessment_id:
            errors.append("assessment_id is required")
        if not 0.0 <= float(self.confidence) <= 1.0:
            errors.append(f"confidence out of range: {self.confidence}")
        for fid in (*self.facts_used, *self.derived_facts):
            if not fid.startswith(FACT_ID_PREFIX):
                errors.append(f"reference is not a fact id: {fid}")
        return errors


@dataclass(frozen=True)
class FactClaim:
    """Lightweight claim handle used by duplicate recognition.

    Decouples dedup logic from the registry: callers pass claims referencing
    canonical fact ids plus an optional directional stance.
    """

    desk_id: str
    assessment_id: str
    label: str = ""
    polarity: str = POLARITY_UNKNOWN
    facts_used: tuple[str, ...] = ()
    derived_facts: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "facts_used", tuple(self.facts_used))
        object.__setattr__(self, "derived_facts", tuple(self.derived_facts))

    @property
    def referenced_facts(self) -> tuple[str, ...]:
        return tuple(sorted(set(self.facts_used) | set(self.derived_facts)))
