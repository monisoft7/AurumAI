"""Sprint 061 -- Duplicate fact recognition (Phase 6 taxonomy).

The goal is *awareness*, not removal: evidence is never dropped.  These
helpers classify how two desk claims relate so a future adjudicator can
distinguish independent agreement from re-descriptions of one primitive.

Taxonomy (stable contract):

* ``independent_agreement``  -- disjoint primitives, agreeing stance
* ``same_fact_agreement``    -- both reference the same primitive directly
* ``derived_agreement``      -- no direct share, but linked through derivation
* ``genuine_disagreement``   -- direct shared primitive, conflicting stances
* ``unknown``                -- not determinable (neutral/unknown stance or
                                conflict reachable only through derived chains)

No majority vote exists anywhere in this module; the only aggregate output is
a deterministic clustering report (union-find over shared/derived primitives)
that reports how many *distinct* primitive clusters the claims reference.
"""

from __future__ import annotations

from typing import Any, Callable

from knowledge.facts.contracts import (
    POLARITY_BEARISH,
    POLARITY_BULLISH,
    FactClaim,
)

RELATION_INDEPENDENT_AGREEMENT = "independent_agreement"
RELATION_SAME_FACT_AGREEMENT = "same_fact_agreement"
RELATION_DERIVED_AGREEMENT = "derived_agreement"
RELATION_GENUINE_DISAGREEMENT = "genuine_disagreement"
RELATION_UNKNOWN = "unknown"

_DIRECTIONAL = frozenset({POLARITY_BULLISH, POLARITY_BEARISH})


def _stance_relation(polarity_a: str, polarity_b: str) -> str:
    """Refine a structural relation with polarity semantics."""
    if polarity_a in _DIRECTIONAL and polarity_b in _DIRECTIONAL:
        if polarity_a == polarity_b:
            return "agreement"
        return "conflict"
    return "indeterminate"


def classify_pair(
    claim_a: FactClaim,
    claim_b: FactClaim,
    *,
    closure: Callable[[str], tuple[str, ...]] | None = None,
) -> str:
    """Classify the epistemic relation between two desk claims.

    Direct share means both claims *use* the same primitive as an input
    (``facts_used`` intersection).  A primitive appearing only in the other
    claim's ``derived_facts`` is a derivation link, not a direct share.
    """
    used_a = set(claim_a.facts_used)
    used_b = set(claim_b.facts_used)

    direct_shared = used_a & used_b
    if not direct_shared:
        refs_a = set(claim_a.referenced_facts)
        refs_b = set(claim_b.referenced_facts)
        linked_without_closure = bool(
            (used_a & set(claim_b.derived_facts))
            or (used_b & set(claim_a.derived_facts))
        )
        if not linked_without_closure and closure is not None and refs_a and refs_b:
            closure_a: set[str] = set()
            for fid in refs_a:
                closure_a.update(closure(fid))
            closure_b: set[str] = set()
            for fid in refs_b:
                closure_b.update(closure(fid))
            linked_without_closure = bool(
                (closure_a & refs_b) or (closure_b & refs_a) or (closure_a & closure_b)
            )
    else:
        linked_without_closure = False

    stance = _stance_relation(claim_a.polarity, claim_b.polarity)

    if direct_shared:
        if stance == "conflict":
            return RELATION_GENUINE_DISAGREEMENT
        if stance == "agreement":
            return RELATION_SAME_FACT_AGREEMENT
        return RELATION_UNKNOWN

    if linked_without_closure:
        # Structurally linked through derivation.  A conflict detected only
        # through a derived chain is not adjudicable yet -- honest unknown
        # instead of a forced verdict.
        return (
            RELATION_DERIVED_AGREEMENT if stance == "agreement" else RELATION_UNKNOWN
        )

    if stance == "conflict":
        # Two genuinely independent views clashing is real disagreement even
        # when they cite disjoint primitives.
        return RELATION_GENUINE_DISAGREEMENT
    if stance == "agreement":
        return RELATION_INDEPENDENT_AGREEMENT
    return RELATION_UNKNOWN


def vote_clusters(
    claims: tuple[FactClaim, ...] | list[FactClaim],
    *,
    closure: Callable[[str], tuple[str, ...]] | None = None,
) -> dict[str, Any]:
    """Cluster claims into distinct primitive clusters (reporting only).

    Returns a deterministic summary::

        {
          "total_claims": N,
          "deduplicated_votes": <number of clusters>,
          "clusters": [
             {"members": [indices...], "primitive_ids": [...],
              "relations": {"i-j": relation, ...}}, ...
          ]
        }

    This is NOT a vote: nothing here scores, weights or decides.
    """
    items = list(claims)
    n = len(items)
    parent = list(range(n))

    def find(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    def union(i: int, j: int) -> None:
        ri, rj = find(i), find(j)
        if ri != rj:
            parent[max(ri, rj)] = min(ri, rj)

    relations: dict[str, str] = {}
    for i in range(n):
        for j in range(i + 1, n):
            relation = classify_pair(items[i], items[j], closure=closure)
            relations[f"{i}-{j}"] = relation
            if relation in (
                RELATION_SAME_FACT_AGREEMENT,
                RELATION_DERIVED_AGREEMENT,
                RELATION_GENUINE_DISAGREEMENT,
            ):
                union(i, j)

    clusters: dict[int, list[int]] = {}
    for i in range(n):
        clusters.setdefault(find(i), []).append(i)
    ordered_members = sorted(
        (sorted(members) for members in clusters.values()), key=lambda m: m[0]
    )

    payload_clusters = []
    for members in ordered_members:
        primitives: set[str] = set()
        for idx in members:
            primitives.update(items[idx].referenced_facts)
        cluster_relations = {
            key: value
            for key, value in sorted(relations.items())
            if int(key.split("-")[0]) in members and int(key.split("-")[1]) in members
        }
        payload_clusters.append(
            {
                "members": members,
                "primitive_ids": sorted(primitives),
                "relations": cluster_relations,
            }
        )

    return {
        "total_claims": n,
        "deduplicated_votes": len(payload_clusters),
        "clusters": payload_clusters,
    }
