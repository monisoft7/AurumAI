"""Correction 047-A -- validation-only episode condition enrichment (READ-ONLY).

Builds an IN-MEMORY historical episode corpus whose conditions carry the
FULL Correction-029 configuration:

    cpi_pressure + us10y_trend + dxy_trend

derived for EACH episode strictly from observations <= that episode's own
event_date using the EXISTING production enrichers (YieldContextEnricher /
DXYContextEnricher -- identical formulas/lookbacks as the runtime lesson
boundary), plus a thin query-surface wrapper that surfaces each episode's
stored event_date as ``metadata["last_event_date"]`` so the UNCHANGED
retriever's temporal criterion can engage.

Nothing here modifies production artifacts, weights, thresholds or
retriever semantics; nothing is persisted.
"""

from __future__ import annotations

from typing import Any

from .cases import load_lessons


def asof_enriched_frame(evaluation_date, lessons_path=None, *, yield_path=None,
                        dxy_path=None, lookback_days: int = 30):
    """Lesson rows (< evaluation_date) enriched with as-of trend columns."""
    import pandas as pd

    from knowledge.context.dxy import DXYContextConfig, DXYContextEnricher
    from knowledge.context.yields import YieldContextConfig, YieldContextEnricher

    from .snapshot import SnapshotConfig

    cfg = SnapshotConfig()
    cutoff = evaluation_date.isoformat()
    rows = [
        r for r in load_lessons(lessons_path or cfg.lessons_path)
        if r["event_date"] < cutoff
    ]
    df = pd.DataFrame(rows)

    y_cfg = YieldContextConfig(
        yield_path=yield_path or cfg.dfii10_path, lookback_days=lookback_days
    )
    framed_y = YieldContextEnricher(y_cfg).enrich(df[["event_date"]].copy())
    df["us10y_trend"] = framed_y["us10y_trend"].to_numpy()

    d_cfg = DXYContextConfig(
        dxy_path=dxy_path or cfg.dxy_path, lookback_days=lookback_days
    )
    framed_d = DXYContextEnricher(d_cfg).enrich(df[["event_date"]].copy())
    df["dxy_trend"] = framed_d["dxy_trend"].to_numpy()
    return df


def asof_enriched_episode_corpus(evaluation_date, lessons_path=None, *,
                                 yield_path=None, dxy_path=None,
                                 lookback_days: int = 30):
    """In-memory TemporalIndexer over the enriched frame."""
    from knowledge.temporal.lesson_index import build_lesson_episode_index

    from .snapshot import SnapshotConfig

    cfg = SnapshotConfig()
    df = asof_enriched_frame(
        evaluation_date,
        lessons_path,
        yield_path=yield_path or cfg.dfii10_path,
        dxy_path=dxy_path or cfg.dxy_path,
        lookback_days=lookback_days,
    )
    indexer = build_lesson_episode_index(df)
    eligible = tuple(sorted(df["lesson_id"].tolist()))
    trends = {
        row["lesson_id"]: {
            "cpi_pressure": row.get("cpi_pressure"),
            "us10y_trend": row.get("us10y_trend"),
            "dxy_trend": row.get("dxy_trend"),
        }
        for _, row in df.iterrows()
    }
    return indexer, eligible, trends


def enriched_query_surface(indexer):
    """LessonEpisodeQuery wrapper surfacing state.date as last_event_date."""

    import dataclasses

    from knowledge.evidence.collection import EvidenceCollection
    from knowledge.evidence.query import RetrievalStrategy
    from knowledge.temporal.lesson_index import LessonEpisodeQuery

    class _Surface:
        def __init__(self, inner: LessonEpisodeQuery) -> None:
            self._inner = inner
            self._dates = {s.state_id: s.date for s in indexer._ensure_sorted()}

        def _stamp(self, coll) -> EvidenceCollection:
            stamped = []
            for e in coll:
                d = self._dates.get(e.evidence_id)
                if d is None or "last_event_date" in e.metadata:
                    stamped.append(e)
                    continue
                meta = dict(e.metadata)
                meta["last_event_date"] = d
                stamped.append(dataclasses.replace(e, metadata=meta))
            return EvidenceCollection(stamped)

        def by_event_type(self, event_type: str) -> EvidenceCollection:
            return self._stamp(self._inner.by_event_type(event_type))

        def matching(self, event_type=None, condition=None, horizon_days=None,
                     strategy: RetrievalStrategy = RetrievalStrategy.SINGLE_EVENT):
            return self._stamp(
                self._inner.matching(
                    event_type=event_type,
                    condition=condition,
                    horizon_days=horizon_days,
                    strategy=strategy,
                )
            )

    return _Surface(LessonEpisodeQuery(indexer))
