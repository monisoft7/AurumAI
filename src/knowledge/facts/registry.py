"""Sprint 061 -- In-memory canonical fact registry.

Pure Python, no database, no graph engine.  The registry is an *index over
identity*: it groups content-addressed assertions by primitive id, tracks
which desk assessments referenced which primitives, and exposes deterministic
queries plus optional emission of edges into the existing ``LineageRegistry``.

It never mutates registered facts, never participates in decisions, and has
no persistence requirement in this sprint (facts are embedded verbatim into
the stage artifacts that produce them).
"""

from __future__ import annotations

from typing import Any, Callable

from knowledge.facts.contracts import (
    CanonicalFact,
    DeskProvenance,
    assert_no_lookahead,
)


class CanonicalFactRegistry:
    """Deterministic in-memory index of canonical facts and desk references."""

    def __init__(self) -> None:
        self._by_fact_id: dict[str, list[CanonicalFact]] = {}
        self._by_record: dict[tuple[str, str], CanonicalFact] = {}
        self._desk_declarations: list[DeskProvenance] = []

    # ------------------------------------------------------------------
    # Registration (idempotent)
    # ------------------------------------------------------------------

    def register(
        self,
        fact: CanonicalFact,
        *,
        lineage_registry: Any | None = None,
    ) -> CanonicalFact:
        """Register one assertion; identical assertions return the original.

        Idempotency key is ``(fact_id, record_hash)``.  A different assertion
        of the same primitive (different producer/value/source) is stored as
        a separate observation -- disagreement stays visible.
        """
        errors = fact.validate()
        if errors:
            raise ValueError(f"invalid CanonicalFact: {errors}")
        key = (fact.fact_id, fact.record_hash())
        existing = self._by_record.get(key)
        if existing is not None:
            return existing
        stored = CanonicalFact.from_dict(fact.to_dict())
        self._by_record[key] = stored
        self._by_fact_id.setdefault(stored.fact_id, []).append(stored)
        self._by_fact_id[stored.fact_id].sort(
            key=lambda f: (f.record_hash(), f.producer, f.source_artifact_id)
        )
        if lineage_registry is not None:
            lineage_registry.add(
                source_id=stored.source_artifact_id or stored.producer,
                source_type="fact_producer",
                target_id=stored.fact_id,
                target_type="canonical_fact",
                relation_type="references",
                metadata={"producer": stored.producer},
            )
            for upstream in stored.derived_from:
                lineage_registry.add(
                    source_id=upstream,
                    source_type="canonical_fact",
                    target_id=stored.fact_id,
                    target_type="canonical_fact",
                    relation_type="derives_from",
                )
        return stored

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def get(self, fact_id: str) -> tuple[CanonicalFact, ...]:
        """All recorded observations of one primitive, deterministically ordered."""
        return tuple(self._by_fact_id.get(fact_id, ()))

    def fact_ids(self) -> tuple[str, ...]:
        return tuple(sorted(self._by_fact_id.keys()))

    def all_facts(self) -> tuple[CanonicalFact, ...]:
        facts: list[CanonicalFact] = []
        for fid in self.fact_ids():
            facts.extend(self.get(fid))
        return tuple(facts)

    def find(
        self,
        *,
        asset: str | None = None,
        topic: str | None = None,
        as_of: str | None = None,
        producer: str | None = None,
    ) -> tuple[CanonicalFact, ...]:
        def matches(fact: CanonicalFact) -> bool:
            if asset and fact.asset != asset:
                return False
            if topic and fact.topic != topic:
                return False
            if as_of and fact.as_of != as_of:
                return False
            if producer and fact.producer != producer:
                return False
            return True

        return tuple(f for f in self.all_facts() if matches(f))

    def producers(self, fact_id: str) -> tuple[str, ...]:
        seen: dict[str, None] = {}
        for fact in self.get(fact_id):
            seen.setdefault(fact.producer, None)
        return tuple(seen)

    # ------------------------------------------------------------------
    # Desk declarations
    # ------------------------------------------------------------------

    def declare_desk(self, declaration: DeskProvenance) -> DeskProvenance:
        errors = declaration.validate()
        if errors:
            raise ValueError(f"invalid DeskProvenance: {errors}")
        for existing in self._desk_declarations:
            if (
                existing.desk_id == declaration.desk_id
                and existing.assessment_id == declaration.assessment_id
                and existing.to_dict() == declaration.to_dict()
            ):
                return existing
        self._desk_declarations.append(declaration)
        return declaration

    def desk_provenances(
        self,
        *,
        desk_id: str | None = None,
        assessment_id: str | None = None,
    ) -> tuple[DeskProvenance, ...]:
        results = [
            d
            for d in self._desk_declarations
            if (desk_id is None or d.desk_id == desk_id)
            and (assessment_id is None or d.assessment_id == assessment_id)
        ]
        return tuple(results)

    # ------------------------------------------------------------------
    # Derivation traversal
    # ------------------------------------------------------------------

    def derivation_upstream(self, fact_id: str) -> tuple[str, ...]:
        """Direct parents of one primitive across all its observations."""
        parents: dict[str, None] = {}
        for fact in self.get(fact_id):
            for upstream in fact.derived_from:
                parents.setdefault(upstream, None)
        return tuple(sorted(parents))

    def derivation_closure(self, fact_id: str) -> tuple[str, ...]:
        """Transitive ancestors, deterministically ordered (BFS, sorted)."""
        closure: dict[str, None] = {}
        frontier = [fact_id]
        while frontier:
            current = frontier.pop(0)
            for parent in self.derivation_upstream(current):
                if parent not in closure and parent != fact_id:
                    closure[parent] = None
                    frontier.append(parent)
        return tuple(sorted(closure))

    # ------------------------------------------------------------------
    # Historical safety
    # ------------------------------------------------------------------

    def assert_no_lookahead_all(self, evaluation_date: str | Any) -> None:
        """Reject any registered fact beyond the cutoff, transitively.

        Facts are visited in sorted fact-id order so the first violation is
        deterministic.  Existing historical-validation semantics are untouched;
        this only makes fact identity compatible with them.
        """
        for fid in self.fact_ids():
            for fact in self.get(fid):
                assert_no_lookahead(
                    fact, evaluation_date, resolve=self.get
                )

    # ------------------------------------------------------------------
    # Interop with existing LineageRegistry
    # ------------------------------------------------------------------

    def wire_lineage(self, lineage_registry: Any) -> int:
        """Emit REFERENCES/DERIVES_FROM edges into an existing LineageRegistry."""
        emitted = 0
        for fid in self.fact_ids():
            for fact in self.get(fid):
                lineage_registry.add(
                    source_id=fact.source_artifact_id or fact.producer,
                    source_type="fact_producer",
                    target_id=fid,
                    target_type="canonical_fact",
                    relation_type="references",
                    metadata={"producer": fact.producer},
                )
                emitted += 1
                for upstream in fact.derived_from:
                    lineage_registry.add(
                        source_id=upstream,
                        source_type="canonical_fact",
                        target_id=fid,
                        target_type="canonical_fact",
                        relation_type="derives_from",
                    )
                    emitted += 1
        return emitted

    # ------------------------------------------------------------------
    # Reporting
    # ------------------------------------------------------------------

    def summary(self) -> dict[str, Any]:
        producers: dict[str, int] = {}
        for fact in self.all_facts():
            producers[fact.producer] = producers.get(fact.producer, 0) + 1
        return {
            "primitive_count": len(self.fact_ids()),
            "observation_count": len(self.all_facts()),
            "observations_by_producer": {
                k: producers[k] for k in sorted(producers)
            },
            "desk_declaration_count": len(self._desk_declarations),
        }
