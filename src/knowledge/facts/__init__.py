"""Sprint 061 -- Canonical Fact identity + cross-desk provenance.

Read/reference-only layer over the existing desks: deterministic primitive
identity (``fct_<sha256>``), content-addressed assertions, desk provenance
declarations, duplicate-fact recognition and the future adjudication
contract.  Nothing here participates in decisions, weights, confidence
semantics or outcome tracking.
"""

from knowledge.facts.adjudication import (
    AgreementSummary,
    DisagreementReport,
    InstitutionalAdjudicationContract,
    SharedPrimitiveReport,
    UnresolvedQuestion,
)
from knowledge.facts.contracts import (
    DESK_HISTORICAL,
    DESK_MACRO_REGIME,
    DESK_NEWS,
    DESK_RISK_REWARD,
    DESK_TECHNICAL,
    FACT_ID_PREFIX,
    FACT_SCHEMA_VERSION,
    POLARITY_BEARISH,
    POLARITY_BULLISH,
    POLARITY_NEUTRAL,
    POLARITY_UNKNOWN,
    CanonicalFact,
    DeskProvenance,
    FactClaim,
    FactLookaheadError,
    assert_no_lookahead,
    parse_temporal,
    primitive_fact_id,
)
from knowledge.facts.dedup import (
    RELATION_DERIVED_AGREEMENT,
    RELATION_GENUINE_DISAGREEMENT,
    RELATION_INDEPENDENT_AGREEMENT,
    RELATION_SAME_FACT_AGREEMENT,
    RELATION_UNKNOWN,
    classify_pair,
    vote_clusters,
)
from knowledge.facts.registry import CanonicalFactRegistry

__all__ = [
    "AgreementSummary",
    "CanonicalFact",
    "CanonicalFactRegistry",
    "DESK_HISTORICAL",
    "DESK_MACRO_REGIME",
    "DESK_NEWS",
    "DESK_RISK_REWARD",
    "DESK_TECHNICAL",
    "DeskProvenance",
    "DisagreementReport",
    "FACT_ID_PREFIX",
    "FACT_SCHEMA_VERSION",
    "FactClaim",
    "FactLookaheadError",
    "InstitutionalAdjudicationContract",
    "POLARITY_BEARISH",
    "POLARITY_BULLISH",
    "POLARITY_NEUTRAL",
    "POLARITY_UNKNOWN",
    "RELATION_DERIVED_AGREEMENT",
    "RELATION_GENUINE_DISAGREEMENT",
    "RELATION_INDEPENDENT_AGREEMENT",
    "RELATION_SAME_FACT_AGREEMENT",
    "RELATION_UNKNOWN",
    "SharedPrimitiveReport",
    "UnresolvedQuestion",
    "assert_no_lookahead",
    "classify_pair",
    "parse_temporal",
    "primitive_fact_id",
    "vote_clusters",
]
