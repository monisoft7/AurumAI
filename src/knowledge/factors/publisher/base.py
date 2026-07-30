from __future__ import annotations

from abc import ABC, abstractmethod

from knowledge.factors.contracts import FactorSignal
from knowledge.factors.publisher.models import (
    PublishResult,
    PublishingContext,
    ValidationResult,
)


class InstitutionalFactorPublisher(ABC):
    """Canonical publishing interface for all institutional departments.

    Every department that produces gold-relevant intelligence —
    CBI, CAI, CFI, Geopolitical, Macro, Energy, etc. —
    MUST implement this interface.

    After this interface is established, every department has exactly
    one responsibility: produce FactorSignals and publish them through
    this interface.

    Departments never communicate directly with each other.
    Reasoning consumes only FactorSignals published through this layer.

    The five abstract methods form the complete contract:

    — department_name()       : Who am I?
    — supported_factor_categories() : What kinds of factors do I produce?
    — validate(signal)        : Is this signal valid before publishing?
    — publish(signal, ctx)    : Publish one signal.
    — publish_many(signals, ctx) : Publish many signals atomically.
    """

    # ———————————————————————————————————
    # Identity
    # ———————————————————————————————————

    @abstractmethod
    def department_name(self) -> str:
        """Return the canonical department identifier.

        Must be a stable, unique string that other parts of the system
        can use to identify the source of published signals.

        Examples: "cfi", "cbi", "geopolitical", "macro", "energy"
        """
        ...

    @abstractmethod
    def supported_factor_categories(self) -> frozenset[str]:
        """Return the set of factor categories this department publishes.

        Must be a subset of VALID_CATEGORIES from factors.contracts.
        Enables automated routing and validation.

        Example: CBI returns {CATEGORY_MONETARY_POLICY, CATEGORY_CENTRAL_BANK}
        """
        ...

    # ———————————————————————————————————
    # Validation
    # ———————————————————————————————————

    @abstractmethod
    def validate(self, signal: FactorSignal) -> ValidationResult:
        """Validate a FactorSignal before publishing.

        Checks department-specific rules:
        — Is the factor_id in this department's scope?
        — Is the category one this department handles?
        — Are required fields populated?
        — Are numeric fields within expected ranges?
        — Is the provenance complete?

        This is the department's opportunity to reject malformed signals
        before they enter the institutional record.

        Must not raise exceptions. Returns a ValidationResult that
        is_valid=True only when all checks pass.
        """
        ...

    # ———————————————————————————————————
    # Publishing
    # ———————————————————————————————————

    @abstractmethod
    def publish(
        self,
        signal: FactorSignal,
        context: PublishingContext,
    ) -> PublishResult:
        """Publish a single FactorSignal into the institutional record.

        Every call to publish() is an atomic operation:
        — The signal is validated before publishing
        — On success, the signal enters the institutional record
        — A PublishResult with the signal's ID and metadata is returned

        The PublishingContext provides the who/when/how of this act.
        """
        ...

    @abstractmethod
    def publish_many(
        self,
        signals: list[FactorSignal],
        context: PublishingContext,
    ) -> PublishResult:
        """Publish multiple FactorSignals in a single batch.

        Every call is logically atomic:
        — All signals are validated before any are published
        — If any signal fails validation, the entire batch is rejected
        — The PublishResult contains all signal IDs on success,
          or error details on failure

        Why batch:
        — A department often fetches multiple data points at once
          (e.g., a full COT report with gold, silver, copper)
        — Atomic batching preserves consistency
        — Single receipt simplifies audit

        Implementations should validate all signals first, then
        publish only if all pass.
        """
        ...
