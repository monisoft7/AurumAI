from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from knowledge._compat import FrozenDict, freeze_dict

# ———————————————————————————————————————
# Validation Severity
# ———————————————————————————————————————

SEVERITY_ERROR = "error"
SEVERITY_WARNING = "warning"
SEVERITY_INFO = "info"

VALID_SEVERITIES = frozenset({SEVERITY_ERROR, SEVERITY_WARNING, SEVERITY_INFO})

# ———————————————————————————————————————
# Models
# ———————————————————————————————————————


@dataclass(frozen=True)
class ValidationIssue:
    """A single issue found during signal validation.

    Fields:
        target_field: Which field on the FactorSignal has the issue.
        message: Human-readable description.
        severity: How serious — error (blocks publish), warning, or info.
        code: Machine-readable error code for programmatic handling.
    """
    target_field: str = ""
    message: str = ""
    severity: str = SEVERITY_ERROR
    code: str = ""
    metadata: dict[str, Any] = field(default_factory=lambda: FrozenDict())

    def __post_init__(self) -> None:
        object.__setattr__(self, "metadata", freeze_dict(self.metadata))


@dataclass(frozen=True)
class ValidationResult:
    """Result of validating a single FactorSignal before publishing.

    Why a dedicated type:
    — Separates validation concerns from publishing concerns
    — Allows callers to inspect failures before deciding to publish
    — Provides structured issues rather than a boolean + string

    Fields:
        is_valid: True if the signal passes all department-level rules.
        signal_id: The factor_id of the validated signal.
        issues: Zero or more issues found during validation.
    """
    is_valid: bool = True
    signal_id: str = ""
    issues: tuple[ValidationIssue, ...] = ()


@dataclass(frozen=True)
class PublishingContext:
    """Context for a single publishing operation.

    This is the envelope every department provides when publishing.
    It describes the who, when, and how of the publishing act itself
    (not the signal content, which lives in FactorSignal).

    Why separate from FactorSignal:
    — The context is about the *act of publishing*, not the signal
    — A single context can apply to many signals (publish_many)
    — Keeps FactorSignal focused on the factor observation + influence

    Fields:
        publisher_id: Unique identifier for the publisher instance
            (e.g., "cfi.cb_gold_reserve_fetcher").
        observation_timestamp: When the underlying data was observed
            (ISO 8601). Distinct from "when this publish call happens".
        analyst: Identifier of the human or automated process that
            produced the signal.
        methodology_version: Version string identifying which
            methodology produced this signal. Enables consumers to
            detect methodology changes over time.
        additional_context: Any extra context the department wishes
            to attach to the publishing operation.
    """
    publisher_id: str = ""
    observation_timestamp: str = ""
    analyst: str = ""
    methodology_version: str | None = None
    additional_context: dict[str, Any] = field(
        default_factory=lambda: FrozenDict(),
    )

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "additional_context",
            freeze_dict(self.additional_context),
        )


@dataclass(frozen=True)
class PublishingMetadata:
    """Immutable record of a completed publishing operation.

    This is the receipt. Every publish() or publish_many() call
    produces one. It documents what happened, when, and how fast.

    Why this exists:
    — Enables auditing of all published signals
    — Provides batch_id for cross-referencing
    — Carries performance telemetry (duration_ms)

    Fields:
        published_at: ISO 8601 timestamp of the publish() call.
        signal_count: Number of FactorSignals in this batch.
        batch_id: Unique identifier for this publishing batch.
            Used for cross-referencing, audit, and debugging.
        duration_ms: Wall-clock duration of the publish call.
    """
    published_at: str = ""
    signal_count: int = 0
    batch_id: str = ""
    duration_ms: float = 0.0
    metadata: dict[str, Any] = field(default_factory=lambda: FrozenDict())

    def __post_init__(self) -> None:
        object.__setattr__(self, "metadata", freeze_dict(self.metadata))


@dataclass(frozen=True)
class PublishResult:
    """Result of a publish() or publish_many() call.

    Every department's publish method returns this. It is the canonical
    response type for the entire publishing layer.

    Why a single type for both single and batch:
    — publish(single) and publish_many(list) both return the same shape
    — For single: signal_count == 1, signal_ids has one element
    — For batch: signal_count == N, signal_ids has N elements
    — Unified response simplifies downstream consumption

    Fields:
        success: True if all signals were published without error.
        signal_ids: Tuple of all published signal factor_ids.
        metadata: The PublishingMetadata receipt for this operation.
        errors: Tuple of error messages for any signals that failed.
            Empty tuple on complete success.
    """
    success: bool = True
    signal_ids: tuple[str, ...] = ()
    metadata: PublishingMetadata | None = None
    errors: tuple[str, ...] = ()
