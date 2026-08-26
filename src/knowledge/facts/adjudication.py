"""Sprint 061 -- Future Institutional Adjudication contract (design only).

This module is a **boundary declaration**, not an implementation.  Sprint 061
builds canonical fact identity so that adjudication *can* later answer:

1. What does each desk say?                       -> ``DeskClaim`` inputs
2. Which facts does each claim rely on?           -> ``FactClaim.facts_used``
3. Which facts are shared between desks?          -> ``shared_primitive_ids``
4. Which evidence is genuinely independent?       -> ``IndependentEvidenceSet``
5. Where is the real disagreement?                -> ``DisagreementReport``
6. Where is one truth re-described twice?         -> ``SameFactReport``
7. What is the agreement after de-duplication?    -> ``AgreementSummary``
8. What cannot be resolved at all?                -> ``UnresolvedQuestion``

Explicitly forbidden by the architecture: naive majority vote.  Any future
implementation must resolve claims through primitive identity, derivation
lineage and calibration -- never through counting heads.

Nothing in this module is wired into W8/W9/W12/W13 or any decision path.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable

from knowledge.facts.contracts import CanonicalFact, DeskProvenance, FactClaim


@dataclass(frozen=True)
class SharedPrimitiveReport:
    """One primitive referenced by more than one desk claim."""

    fact_id: str
    referencing_assessments: tuple[str, ...] = ()
    observations: tuple[CanonicalFact, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "referencing_assessments", tuple(self.referencing_assessments)
        )
        object.__setattr__(self, "observations", tuple(self.observations))


@dataclass(frozen=True)
class AgreementSummary:
    """Post-de-duplication agreement snapshot (reporting shape only)."""

    total_claims: int = 0
    deduplicated_votes: int = 0
    same_fact_pairs: int = 0
    derived_pairs: int = 0
    independent_pairs: int = 0
    disagreement_pairs: int = 0
    indeterminate_pairs: int = 0


@dataclass(frozen=True)
class DisagreementReport:
    """A genuine conflict between desk stances."""

    assessment_a: str = ""
    assessment_b: str = ""
    shared_fact_ids: tuple[str, ...] = ()
    explanation: str = ""


@dataclass(frozen=True)
class UnresolvedQuestion:
    """Something adjudication could not decide (honest boundary)."""

    question: str = ""
    related_fact_ids: tuple[str, ...] = ()
    reason: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "related_fact_ids", tuple(self.related_fact_ids))


@runtime_checkable
class InstitutionalAdjudicationContract(Protocol):
    """Protocol every future adjudicator must satisfy.

    Implementations receive the registry snapshot plus desk declarations and
    MUST derive all answers from canonical fact identity and lineage -- no
    naive majority vote.
    """

    def desk_claims(self) -> tuple[FactClaim, ...]: ...

    def facts_used_by(self, assessment_id: str) -> tuple[str, ...]: ...

    def shared_facts(
        self, assessment_a: str, assessment_b: str
    ) -> tuple[SharedPrimitiveReport, ...]: ...

    def independent_evidence_set(self) -> AgreementSummary: ...

    def genuine_disagreements(self) -> tuple[DisagreementReport, ...]: ...

    def agreement_after_deduplication(self) -> AgreementSummary: ...

    def unresolved_questions(self) -> tuple[UnresolvedQuestion, ...]: ...


def adjudication_input_shape(
    declarations: tuple[DeskProvenance, ...],
    claims: tuple[FactClaim, ...],
) -> dict[str, Any]:
    """Documented input shape for the future implementation (pure function)."""
    return {
        "desk_declarations": [d.to_dict() for d in declarations],
        "claims": [
            {
                "desk_id": c.desk_id,
                "assessment_id": c.assessment_id,
                "label": c.label,
                "polarity": c.polarity,
                "facts_used": list(c.facts_used),
                "derived_facts": list(c.derived_facts),
            }
            for c in claims
        ],
        "majority_vote_permitted": False,
    }
