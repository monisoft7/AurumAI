"""Historical Validation Run 001 -- Step 1 skeleton (READ-ONLY).

Isolation boundary: this package is a standalone analysis/validation module.
It is NOT wired into src/orchestration, src/evidence_reasoning,
src/confidence_engine, src/decision_engine, or production pipeline stages.
It imports nothing from the production source tree.

Step 1 scope only:
    * deterministic 25-episode cohort selection (Trace 044-B)
    * structured read-only validation-case representation
    * validation-only metadata placeholders
    * safety assertions

Explicitly NOT computed in Step 1: regime, HistoricalSituationRetriever
queries, production orchestrator calls, FULL vs NO_HISTORY variants.
"""

from .cases import (
    ActualOutcome,
    CohortIntegrityError,
    ValidationCase,
    build_validation_cases,
    cohort_positions,
    load_lessons,
    select_cohort,
    verify_cohort_integrity,
)
from .snapshot import (
    T5YIE_NOT_IN_LIVE_QUERY_NOTE,
    SnapshotConfig,
    ValidationError,
    ValidationSnapshot,
    asof_knowledge_records,
    build_snapshot,
    eligible_asof_knowledge_records,
    knowledge_eligible_records,
)
from .spec import (
    BASELINE_ID,
    COHORT_SIZE,
    FROZEN_COHORT_IDS,
    POSITION_DENOMINATOR as COHORT_DENOMINATOR,
    TOTAL_EPISODES as COHORT_TOTAL_EPISODES,
    TRACE_ID,
)

__all__ = [
    "TRACE_ID",
    "BASELINE_ID",
    "COHORT_TOTAL_EPISODES",
    "COHORT_SIZE",
    "COHORT_DENOMINATOR",
    "FROZEN_COHORT_IDS",
    "ActualOutcome",
    "ValidationCase",
    "CohortIntegrityError",
    "cohort_positions",
    "load_lessons",
    "select_cohort",
    "verify_cohort_integrity",
    "build_validation_cases",
    "SnapshotConfig",
    "ValidationSnapshot",
    "ValidationError",
    "build_snapshot",
    "knowledge_eligible_records",
    "asof_knowledge_records",
    "eligible_asof_knowledge_records",
    "T5YIE_NOT_IN_LIVE_QUERY_NOTE",
]
