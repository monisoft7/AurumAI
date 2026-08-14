"""Correction 025: derived per-episode lesson index (rebuildable, additive).

Builds one ``TemporalState`` per lesson row (``SOURCE_TYPE_LESSON``) from the
existing lesson artifact, preserving the bounded episode fields required for
the first gold analogue capability and deriving the institutional six-state
regime label from the existing deterministic ``ECONOMIC_REGIME_LABELS``
mapping.

The lesson artifact remains the single source of truth; this index is a
deterministic, rebuildable projection of it.  Missing optional fields are
omitted -- never fabricated.  No new identities are created: ``state_id`` is
always the lesson's own ``lesson_id``.
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any

import pandas as pd

from knowledge.evidence.collection import EvidenceCollection
from knowledge.evidence.evidence import Evidence
from knowledge.evidence.query import RetrievalStrategy
from knowledge.regime.institutional_regime_detector import ECONOMIC_REGIME_LABELS
from knowledge.temporal.adapter import (
    EPISODE_CONDITION_KEYS,
    TemporalEvidenceAdapter,
)
from knowledge.temporal.indexer import TemporalIndexer
from knowledge.temporal.repository import TemporalRepository
from knowledge.temporal.state import SOURCE_TYPE_LESSON, TemporalState

GOLD_EPISODE_FIELDS: tuple[str, ...] = (
    "anchor_gold_date",
    "gold_close_at_event",
    "gold_return_1d_pct",
    "gold_return_5d_pct",
    "gold_return_20d_pct",
    "gold_direction_1d",
    "gold_direction_5d",
    "gold_direction_20d",
)

EPISODE_SCALAR_FIELDS: tuple[str, ...] = ("primary_horizon_days",)

PROVENANCE_FIELDS: tuple[str, ...] = (
    "release_timestamp",
    "source_artifact_path",
    "source_artifact_sha256",
)


def build_lesson_episode_index(
    lessons: pd.DataFrame | str | Path,
) -> TemporalIndexer:
    """Build one TemporalState per lesson row from the existing lesson artifact.

    Rows without a ``lesson_id`` or ``event_date`` are skipped; no values are
    fabricated for absent optional fields.
    """
    df = lessons if isinstance(lessons, pd.DataFrame) else pd.read_csv(lessons)
    indexer = TemporalIndexer()
    for _, row in df.iterrows():
        state = row_to_lesson_state(row)
        if state is not None:
            indexer.index(state)
    return indexer


def row_to_lesson_state(row: pd.Series) -> TemporalState | None:
    """Convert one lesson row into a SOURCE_TYPE_LESSON episode TemporalState."""
    lesson_id = _scalar(row, "lesson_id")
    event_date = _scalar(row, "event_date")
    if not lesson_id or not event_date:
        return None

    metadata: dict[str, Any] = {}
    for key in EPISODE_CONDITION_KEYS:
        value = _scalar(row, key)
        if value:
            metadata[key] = str(value)

    for key in GOLD_EPISODE_FIELDS + EPISODE_SCALAR_FIELDS:
        value = _scalar(row, key)
        if value is not None:
            metadata[key] = value

    macro_regime = _scalar(row, "macro_regime")
    if macro_regime:
        metadata["macro_regime"] = str(macro_regime)
        derived = ECONOMIC_REGIME_LABELS.get(str(macro_regime))
        if derived:
            metadata["regime"] = derived

    for key in PROVENANCE_FIELDS:
        value = _scalar(row, key)
        if value is not None:
            metadata[key] = str(value)

    return TemporalState(
        state_id=lesson_id,
        date=event_date,
        source_type=SOURCE_TYPE_LESSON,
        source_id=lesson_id,
        metadata=metadata,
    )


def save_lesson_episode_index(indexer: TemporalIndexer, path: str | Path) -> None:
    """Persist the episode index with the existing TemporalRepository."""
    TemporalRepository().save_index(indexer, Path(path))


def load_lesson_episode_index(path: str | Path) -> TemporalIndexer:
    """Load a persisted episode index with the existing TemporalRepository."""
    return TemporalRepository().load_index(Path(path))


def rebuild_lesson_episode_index(
    lessons: str | Path,
    episodes_json: str | Path,
) -> TemporalIndexer:
    """Rebuild and persist the derived episode index (Correction 025-B).

    The lesson artifact remains the single source of truth; the index
    persists under ``data/state/lesson_episodes.json`` and is disposable and
    rebuildable at any time.
    """
    indexer = build_lesson_episode_index(lessons)
    save_lesson_episode_index(indexer, episodes_json)
    return indexer


class LessonEpisodeQuery:
    """EvidenceQuery-compatible view over the lesson episode index.

    Implements exactly the two methods ``HistoricalSituationRetriever``
    consumes (``matching`` and ``by_event_type``) with the same
    subset-over-conditions semantics as ``EvidenceQuery``.  It is a
    read-only view over the episode index; ``EvidenceQuery`` itself is not
    modified.
    """

    def __init__(self, indexer: TemporalIndexer) -> None:
        adapter = TemporalEvidenceAdapter()
        self._items: list[Evidence] = [
            adapter.state_to_evidence(state)
            for state in indexer._ensure_sorted()
            if state.source_type == SOURCE_TYPE_LESSON
        ]

    def by_event_type(self, event_type: str) -> EvidenceCollection:
        return EvidenceCollection(
            [e for e in self._items if e.event_type == event_type]
        )

    def matching(
        self,
        event_type: str | None = None,
        condition: dict[str, str] | None = None,
        horizon_days: int | None = None,
        strategy: RetrievalStrategy = RetrievalStrategy.SINGLE_EVENT,
    ) -> EvidenceCollection:
        items = self._items
        if (
            strategy is RetrievalStrategy.SINGLE_EVENT
            and event_type is not None
        ):
            items = [e for e in items if e.event_type == event_type]
        if horizon_days is not None:
            items = [e for e in items if e.horizon_days == horizon_days]
        if condition is not None:
            items = [
                e for e in items
                if all(
                    e.condition.get(key) == value
                    for key, value in condition.items()
                )
            ]
        return EvidenceCollection(items)


def _scalar(row: pd.Series, key: str) -> Any:
    if key not in row.index:
        return None
    value = row[key]
    if value is None:
        return None
    if isinstance(value, float) and math.isnan(value):
        return None
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    return value
