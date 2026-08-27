"""Focused tests for Correction 047-A -- validation-only episode enrichment."""

from __future__ import annotations

import hashlib
import subprocess
import sys
from datetime import date
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from historical_validation.enriched_corpus import (
    asof_enriched_episode_corpus,
    asof_enriched_frame,
    enriched_query_surface,
)
from historical_validation.cases import build_validation_cases
from historical_validation.snapshot import SnapshotConfig, build_snapshot

LESSONS = ROOT / "data" / "lessons" / "cpi_gold_lessons.csv"


def _trend_conditions(cutoff: date):
    _, eligible, trends = asof_enriched_episode_corpus(cutoff, LESSONS)
    return eligible, trends


# ---------------------------------------------------------------------------
# 1/2. US10Y and DXY enrichment is as-of safe
# ---------------------------------------------------------------------------


def test_us10y_enrichment_asof_safe() -> None:
    # A shared episode's derived trend must not depend on the corpus cutoff:
    # it is computed strictly from observations <= that episode's own date.
    _, t_june = _trend_conditions(date(2015, 6, 1))
    _, t_later = _trend_conditions(date(2016, 6, 1))
    shared = set(t_june) & set(t_later)
    assert {"CPI_GOLD_2015-02-01", "CPI_GOLD_2015-03-01"} <= shared
    for lesson_id in shared:
        assert t_june[lesson_id]["us10y_trend"] == t_later[lesson_id]["us10y_trend"], lesson_id

    # Direct Correction-029 recomputation for one episode/date pair.
    import pandas as pd

    from knowledge.context.trend_state import trend_state_at

    dfii10 = pd.read_csv(ROOT / "data/economic/DFII10.csv")
    dfii10["Date"] = pd.to_datetime(dfii10["Date"])
    dfii10 = dfii10.dropna().sort_values("Date")
    ep_date = pd.Timestamp("2015-03-01")
    sliced = dfii10[dfii10["Date"] <= ep_date]
    state = trend_state_at(
        sliced["Date"],
        sliced["Value"].astype(float) * 100.0,
        ep_date,
        30,
        10.0,
    )
    expected = {"flat": "yields_flat", "rising": "yields_rising", "falling": "yields_falling"}[state]
    assert t_june["CPI_GOLD_2015-03-01"]["us10y_trend"] == expected


def test_dxy_enrichment_asof_safe() -> None:
    _, t_june = _trend_conditions(date(2015, 6, 1))
    _, t_later = _trend_conditions(date(2016, 6, 1))
    for lesson_id in set(t_june) & set(t_later):
        assert t_june[lesson_id]["dxy_trend"] == t_later[lesson_id]["dxy_trend"], lesson_id
    values = {v["dxy_trend"] for v in list(t_june.values()) + list(t_later.values())}
    assert values <= {"dxy_rising", "dxy_falling", "dxy_flat"}


# ---------------------------------------------------------------------------
# 3. Current lesson excluded
# ---------------------------------------------------------------------------


def test_current_lesson_excluded() -> None:
    cutoff = date(2015, 6, 1)
    indexer, eligible, _ = asof_enriched_episode_corpus(cutoff, LESSONS)
    ids = {s.state_id for s in indexer._ensure_sorted()}
    assert "CPI_GOLD_2015-06-01" not in ids
    assert "CPI_GOLD_2015-06-01" not in eligible
    assert all(s.date < cutoff.isoformat() for s in indexer._ensure_sorted())


# ---------------------------------------------------------------------------
# 4. Deterministic repeated enrichment
# ---------------------------------------------------------------------------


def test_deterministic_repeated_enrichment() -> None:
    e1, ids1, t1 = asof_enriched_episode_corpus(date(2020, 9, 1), LESSONS)
    e2, ids2, t2 = asof_enriched_episode_corpus(date(2020, 9, 1), LESSONS)
    assert ids1 == ids2
    s1 = [(s.state_id, s.date, dict(s.metadata)) for s in e1._ensure_sorted()]
    s2 = [(s.state_id, s.date, dict(s.metadata)) for s in e2._ensure_sorted()]
    assert s1 == s2
    assert t1 == t2


# ---------------------------------------------------------------------------
# 5. Canonical artifact unchanged
# ---------------------------------------------------------------------------


def test_canonical_artifact_unchanged() -> None:
    before = hashlib.sha256(LESSONS.read_bytes()).hexdigest()
    asof_enriched_episode_corpus(date(2020, 9, 1), LESSONS)
    after = hashlib.sha256(LESSONS.read_bytes()).hexdigest()
    assert before == after


# ---------------------------------------------------------------------------
# 6-8. Retrieval value test on the enriched surface
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def experiments():
    cases = {c.lesson_id: c for c in build_validation_cases(path=LESSONS)}
    out = {}
    for lesson_id in (
        "CPI_GOLD_2015-06-01",
        "CPI_GOLD_2020-09-01",
        "CPI_GOLD_2026-02-01",
    ):
        case = cases[lesson_id]
        snap = build_snapshot(case, SnapshotConfig())
        d = case.evaluation_date.isoformat()
        indexer, eligible, trends = asof_enriched_episode_corpus(case.evaluation_date, LESSONS)
        surface = enriched_query_surface(indexer)

        from knowledge.reasoning.retrieval import HistoricalSituationRetriever, SituationQuery

        query = SituationQuery(
            event_type="CPI",
            condition={
                "cpi_pressure": snap.cpi_pressure,
                "us10y_trend": snap.us10y_trend,
                "dxy_trend": snap.dxy_trend,
            },
            institutional_context={"regime": snap.institutional_regime},
            date=d,
        )
        retriever = HistoricalSituationRetriever()
        matches = retriever.retrieve(query, surface)
        condition_exact = sum(
            1 for m in matches if m.evidence.condition == query.condition
        )
        out[lesson_id] = {
            "snapshot": snap,
            "query": query,
            "matches": matches,
            "condition_exact": condition_exact,
            "top_ids": [m.evidence.evidence_id for m in matches[:3]],
        }
    return out


def test_exact_matches_become_possible_where_conditions_align(experiments) -> None:
    for lesson_id, exp in experiments.items():
        assert exp["condition_exact"] >= 1, lesson_id


def test_broadened_classification_remains_honest(experiments) -> None:
    """Per-match honesty is defined by the existing production entry
    projection (_match_entry_honest): exact = full condition + same regime;
    contextual = full condition, regime differs; broadened = relaxed
    condition."""
    from evidence_reasoning.historical_analogue import _match_entry_honest

    for exp in experiments.values():
        q = exp["query"]
        state_by_id = {}
        indexer, _, _ = asof_enriched_episode_corpus(
            date.fromisoformat(q.date), LESSONS
        )
        state_by_id = {s.state_id: s for s in indexer._ensure_sorted()}
        regime = q.institutional_context.get("regime")
        for m in exp["matches"]:
            entry = _match_entry_honest(m, state_by_id, regime)
            label = entry["similarity"]["retrieval_method"]
            full_condition = m.evidence.condition == q.condition
            episode_regime = m.evidence.metadata.get("institutional_context", {}).get("regime")
            if label == "exact":
                assert full_condition and episode_regime == regime
            else:
                # Production semantics: contextual/broadened both mean this
                # match is NOT a verified full-condition + same-regime match.
                assert label in {"contextual", "broadened"}
                assert (not full_condition) or (episode_regime != regime)


def test_cohorts_configuration_sensitive_and_not_artifact_order(experiments) -> None:
    cohorts = {tuple(exp["top_ids"]) for exp in experiments.values()}
    assert len(cohorts) >= 3, "cohorts still collapsed"
    # Ranking must respect similarity, not raw chronological artifact order.
    exp = experiments["CPI_GOLD_2015-06-01"]
    sims = [round(m.overall_similarity, 6) for m in exp["matches"][:3]]
    assert sims == sorted(sims, reverse=True)


def test_temporal_field_engages(experiments) -> None:
    exp = experiments["CPI_GOLD_2020-09-01"]
    m0 = exp["matches"][0]
    assert m0.temporal_similarity > 0.5, "temporal criterion still neutral"
    assert "last_event_date" in m0.evidence.metadata


def test_existing_retriever_behavior_unchanged() -> None:
    from knowledge.reasoning.retrieval import RetrievalConfig

    cfg = RetrievalConfig()
    assert (cfg.top_k, cfg.min_similarity, cfg.broaden_on_empty) == (5, 0.3, True)
    assert abs(
        cfg.event_type_weight + cfg.condition_weight + cfg.horizon_weight
        + cfg.maturity_weight + cfg.temporal_weight + cfg.institutional_context_weight
        - 1.0
    ) < 1e-9


# ---------------------------------------------------------------------------
# 9. No production files changed
# ---------------------------------------------------------------------------


def test_no_production_files_changed() -> None:
    tracked = subprocess.run(
        ["git", "diff", "--name-only", "HEAD", "--", "src", "run.py"],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    assert tracked == "", f"production sources modified: {tracked}"

    watched = [
        "data/history/gold/gold.csv",
        "data/context/dxy/dxy.csv",
        "data/economic/DFII10.csv",
        "data/economic/T5YIE.csv",
        "data/calendar/cpi_releases.csv",
        "data/lessons/cpi_gold_lessons.csv",
        "data/state/lesson_episodes.json",
        "runtime/run_registry.jsonl",
    ]

    def digest(rel: str):
        p = ROOT / rel
        return hashlib.sha256(p.read_bytes()).hexdigest() if p.is_file() else "<missing>"

    before = {rel: digest(rel) for rel in watched}
    _trend_conditions(date(2020, 9, 1))
    asof_enriched_episode_corpus(date(2020, 9, 1), LESSONS)
    after = {rel: digest(rel) for rel in watched}
    assert before == after
