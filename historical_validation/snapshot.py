"""Historical Validation Run 001 -- Step 2 as-of snapshot engine (READ-ONLY).

Builds a deterministic, validation-only snapshot for one evaluation date D
containing ONLY information available at or before D.

Reuse-only adapter semantics (no new scoring/thresholds/sub-systems):

* US10Y  : existing post-Correction-029 ``trend_state_at`` fold over
           ``data/economic/DFII10.csv`` observations <= D
           (30-calendar-day anchor; threshold 10.0 bps on value*100, exactly
           as ``knowledge.context.yields`` does).
* DXY    : same 029 fold over ``data/context/dxy/dxy.csv`` <= D
           (30-calendar-day anchor; threshold 1.0 index point, exactly as
           ``knowledge.context.dxy`` does).
* GOLD   : no gold observations enter the snapshot; future outcomes stored
           on the ValidationCase stay evaluation-only.
* REGIME : existing ``CompositeScoreBuilder`` z-score/12m-change semantics,
           sliced to <= D (via an as-of subclass), then existing
           ``InstitutionalRegimeDetector(random_state=42)`` fit.  Fails
           explicitly when the historical source is unavailable.
* KNOWLEDGE: deterministic AS-OF knowledge view derived IN MEMORY from the
           canonical lesson artifact restricted to event_date <= D using the
           EXISTING ``LessonSummaryAggregator`` producer semantics
           (identical grouping/horizons/statistics fields), then filtered by
           the unchanged eligibility rule: a record is eligible only when
           every one of its ``source_lesson_ids`` resolves to a lesson with
           event_date <= D.  The persisted convenience artifact under
           ``data/economic/output/knowledge.json`` aggregates its own
           extraction window and is therefore NOT authoritative for
           historical dates; it remains readable through
           ``knowledge_eligible_records`` as a provenance/equivalence view.
           No global graph is loaded or mutated; nothing is written.
* ANALOGUE CUTOFF: strictly < D; the evaluated episode itself is always
           excluded.
* T5YIE  : recorded as NOT part of the live historical query (same as the
           production analogue path, which queries CPI + US10Y trend +
           DXY trend + regime only).

Deterministic: no timestamps, UUIDs, network, or writes of any kind.
"""

from __future__ import annotations

from dataclasses import dataclass, field, fields as dataclass_fields
from datetime import date, timedelta
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]

DEFAULT_LESSONS_PATH = _REPO_ROOT / "data" / "lessons" / "cpi_gold_lessons.csv"
DEFAULT_DFII10_PATH = _REPO_ROOT / "data" / "economic" / "DFII10.csv"
DEFAULT_DXY_PATH = _REPO_ROOT / "data" / "context" / "dxy" / "dxy.csv"
DEFAULT_ECONOMIC_DIR = _REPO_ROOT / "data" / "economic"
DEFAULT_KNOWLEDGE_RECORDS_PATH = _REPO_ROOT / "data" / "economic" / "output" / "knowledge.json"

YIELD_LOOKBACK_DAYS = 30
DXY_LOOKBACK_DAYS = 30
YIELD_FLAT_CHANGE_BPS = 10.0
DXY_FLAT_CHANGE = 1.0

T5YIE_NOT_IN_LIVE_QUERY_NOTE = (
    "T5YIE is not part of the live historical query (CPI + US10Y trend + DXY trend + regime)."
)

_TREND_TO_YIELD = {"flat": "yields_flat", "rising": "yields_rising", "falling": "yields_falling"}
_TREND_TO_DXY = {"flat": "dxy_flat", "rising": "dxy_rising", "falling": "dxy_falling"}


class ValidationError(Exception):
    """Raised when a no-lookahead assertion fails or a required historical
    input is unavailable (never silently replaced by today's values)."""


@dataclass(frozen=True)
class SnapshotConfig:
    lessons_path: Path = DEFAULT_LESSONS_PATH
    dfii10_path: Path = DEFAULT_DFII10_PATH
    dxy_path: Path = DEFAULT_DXY_PATH
    economic_dir: Path = DEFAULT_ECONOMIC_DIR
    knowledge_records_path: Path = DEFAULT_KNOWLEDGE_RECORDS_PATH
    yield_lookback_days: int = YIELD_LOOKBACK_DAYS
    dxy_lookback_days: int = DXY_LOOKBACK_DAYS
    yield_flat_change_bps: float = YIELD_FLAT_CHANGE_BPS
    dxy_flat_change: float = DXY_FLAT_CHANGE


@dataclass(frozen=True)
class ValidationSnapshot:
    """Immutable read-only as-of snapshot for one evaluation date D."""

    lesson_id: str
    evaluation_date: date
    cpi_pressure: str

    us10y_value: float
    us10y_observation_date: date
    us10y_anchor_value: float | None
    us10y_anchor_date: date | None
    us10y_change: float | None  # basis points, rounded 6dp (existing enricher basis)
    us10y_trend: str

    dxy_value: float
    dxy_observation_date: date
    dxy_anchor_value: float | None
    dxy_anchor_date: date | None
    dxy_change: float | None  # index points, rounded 6dp (existing enricher basis)
    dxy_trend: str

    institutional_regime: str
    regime_source_max_date: date

    knowledge_cutoff: date
    eligible_knowledge_ids: tuple[str, ...] = ()
    knowledge_source_max_lesson_date: date | None = None

    analogue_cutoff: date | None = None
    analogue_eligible_lesson_ids: tuple[str, ...] = ()
    excluded_lesson_ids: tuple[str, ...] = ()

    t5yie_required: bool = False
    t5yie_note: str = T5YIE_NOT_IN_LIVE_QUERY_NOTE

    evaluation_only_outcomes: tuple[dict[str, object], ...] = ()

    def assert_no_lookahead(self) -> None:
        """Raise ``ValidationError`` if any as-of invariant is violated."""
        d = self.evaluation_date
        if self.us10y_observation_date > d:
            raise ValidationError("US10Y observation is after evaluation_date")
        if self.us10y_anchor_date is not None and self.us10y_anchor_date > d:
            raise ValidationError("US10Y anchor is after evaluation_date")
        if self.dxy_observation_date > d:
            raise ValidationError("DXY observation is after evaluation_date")
        if self.dxy_anchor_date is not None and self.dxy_anchor_date > d:
            raise ValidationError("DXY anchor is after evaluation_date")
        if self.regime_source_max_date > d:
            raise ValidationError("regime source max date is after evaluation_date")
        if self.knowledge_cutoff > d:
            raise ValidationError("knowledge cutoff is after evaluation_date")
        if self.knowledge_source_max_lesson_date is not None and self.knowledge_source_max_lesson_date > d:
            raise ValidationError("knowledge source lesson date is after evaluation_date")
        if self.analogue_cutoff is not None and self.analogue_cutoff >= d:
            raise ValidationError("analogue cutoff must be strictly < evaluation_date")
        if self.lesson_id in self.analogue_eligible_lesson_ids:
            raise ValidationError("current lesson must never be analogue-eligible")
        for item in self.evaluation_only_outcomes:
            if not item.get("evaluation_only"):
                raise ValidationError("future outcome must be marked evaluation_only")
        self._assert_outcomes_isolated()

    def _assert_outcomes_isolated(self) -> None:
        outcome_values: list[object] = []
        for item in self.evaluation_only_outcomes:
            outcome_values.append(item.get("return_pct"))
            outcome_values.append(item.get("direction"))
        for f in dataclass_fields(self):
            if f.name == "evaluation_only_outcomes":
                continue
            value = getattr(self, f.name)
            # A bool field can never legitimately carry a gold outcome, and
            # Python's ``False == 0.0`` would otherwise false-positive on
            # episodes whose realized 1d return is exactly zero.
            if isinstance(value, bool):
                continue
            if value in outcome_values:
                raise ValidationError(
                    f"future gold outcome leaked into snapshot field '{f.name}'"
                )


# ---------------------------------------------------------------------------
# US10Y / DXY as-of series helpers (existing 029 semantics, sliced to <= D)
# ---------------------------------------------------------------------------


def _read_series(path: Path, as_of: date) -> tuple[list[date], list[float]]:
    """Latest-on-or-before ordered series of observations <= as_of."""
    import pandas as pd

    if not path.is_file():
        raise ValidationError(f"required historical input missing: {path}")
    df = pd.read_csv(path)
    missing = {"Date", "Value"}.difference(df.columns)
    if missing:
        raise ValidationError(f"{path} is missing required columns: {sorted(missing)}")
    df = df.copy()
    df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
    df["Value"] = pd.to_numeric(df["Value"], errors="coerce")
    df = df.dropna(subset=["Date", "Value"])
    df = df.sort_values("Date").drop_duplicates("Date", keep="last")
    cutoff = pd.Timestamp(as_of)
    df = df[df["Date"] <= cutoff]
    if df.empty:
        raise ValidationError(f"no observation <= evaluation_date {as_of} in {path}")
    return [d.date() for d in df["Date"].tolist()], [float(v) for v in df["Value"].tolist()]


def _trend_state_at(dates: list[date], values: list[float], as_of: date, lookback_days: int, threshold: float) -> str:
    """Existing post-Correction-029 ``trend_state_at`` folded over <= as_of."""
    from knowledge.context.trend_state import trend_state_at

    import pandas as pd

    return trend_state_at(
        pd.Series([pd.Timestamp(d) for d in dates]),
        pd.Series(values),
        pd.Timestamp(as_of),
        lookback_days,
        threshold,
    )


def _yield_block(as_of: date, config: SnapshotConfig) -> dict[str, object]:
    dates, values = _read_series(config.dfii10_path, as_of)
    scaled = [v * 100.0 for v in values]
    trend_state = _trend_state_at(
        dates, scaled, as_of, config.yield_lookback_days, config.yield_flat_change_bps
    )
    obs_date = dates[-1]
    obs_value = values[-1]
    anchor_cutoff = as_of - timedelta(days=config.yield_lookback_days)
    anchor_date: date | None = None
    anchor_value: float | None = None
    for d, v in zip(dates, values):
        if d <= anchor_cutoff:
            anchor_date, anchor_value = d, v
        else:
            break
    return {
        "us10y_value": round(obs_value, 6),
        "us10y_observation_date": obs_date,
        "us10y_anchor_value": None if anchor_value is None else round(anchor_value, 6),
        "us10y_anchor_date": anchor_date,
        "us10y_change": (
            None
            if anchor_value is None
            else round((obs_value - anchor_value) * 100.0, 6)
        ),
        "us10y_trend": _TREND_TO_YIELD.get(trend_state, "yields_flat"),
    }


def _dxy_block(as_of: date, config: SnapshotConfig) -> dict[str, object]:
    dates, values = _read_series(config.dxy_path, as_of)
    trend_state = _trend_state_at(
        dates, values, as_of, config.dxy_lookback_days, config.dxy_flat_change
    )
    obs_date = dates[-1]
    obs_value = values[-1]
    anchor_cutoff = as_of - timedelta(days=config.dxy_lookback_days)
    anchor_date: date | None = None
    anchor_value: float | None = None
    for d, v in zip(dates, values):
        if d <= anchor_cutoff:
            anchor_date, anchor_value = d, v
        else:
            break
    return {
        "dxy_value": round(obs_value, 6),
        "dxy_observation_date": obs_date,
        "dxy_anchor_value": None if anchor_value is None else round(anchor_value, 6),
        "dxy_anchor_date": anchor_date,
        "dxy_change": None if anchor_value is None else round(obs_value - anchor_value, 6),
        "dxy_trend": _TREND_TO_DXY.get(trend_state, "dxy_flat"),
    }


# ---------------------------------------------------------------------------
# Regime (existing CompositeScoreBuilder semantics sliced to <= D)
# ---------------------------------------------------------------------------


class _AsOfCompositeScoreBuilder:  # adapts CompositeScoreBuilder with a <= D slice
    def __init__(self, data_dir: str | Path, as_of: date) -> None:
        from knowledge.regime.composite_score import (
            CompositeScoreBuilder,
            load_synthetic_exclusions,
        )

        self._builder = CompositeScoreBuilder(data_dir=data_dir)
        self._as_of = as_of
        # Final Hardening (D-03): the live composite excludes files listed
        # in synthetic_data_index.json; the as-of replay applies the SAME
        # exclusion so validation semantics match the live path.
        self._synthetic = load_synthetic_exclusions(data_dir)

    def build(self):
        import pandas as pd

        builder = self._builder
        z_scores = []
        common = None
        for name, filename in builder._INDICATORS.items():
            if filename in self._synthetic:
                continue
            path = Path(builder._data_dir) / filename
            if not path.exists():
                continue
            df = pd.read_csv(path, parse_dates=["Date"])
            df = df[pd.to_datetime(df["Date"]) <= pd.Timestamp(self._as_of)]
            df = df.dropna(subset=["Date", "Value"]).sort_values("Date")
            df["Value"] = pd.to_numeric(df["Value"], errors="coerce")
            if df["Value"].isna().all():
                continue
            series = builder._transform_series(name, df.set_index("Date")["Value"])
            if series is None or series.empty:
                continue
            z = builder._z_score(series).rename(name)
            common = z.index if common is None else common.union(z.index)
            z_scores.append(z)
        if not z_scores or common is None:
            return pd.DataFrame(columns=["Date", "composite_score"])
        aligned = [z.reindex(common) for z in z_scores]
        composite = pd.concat(aligned, axis=1).mean(axis=1, skipna=True).dropna()
        return pd.DataFrame(
            {"Date": composite.index, "composite_score": composite.values.round(6)}
        ).reset_index(drop=True)


def _regime_block(as_of: date, config: SnapshotConfig) -> dict[str, object]:
    from knowledge.regime.institutional_regime_detector import InstitutionalRegimeDetector

    composite = _AsOfCompositeScoreBuilder(config.economic_dir, as_of).build()
    if len(composite) == 0:
        raise ValidationError(
            f"no composite_score data on or before {as_of} -- cannot fit historical regime"
        )
    detector = InstitutionalRegimeDetector(random_state=42).fit(composite)
    regime_rows = detector.get_regime_data()
    last = regime_rows.iloc[-1]
    return {
        "institutional_regime": str(last["regime"]),
        "regime_source_max_date": composite["Date"].max().date()
        if hasattr(composite["Date"].max(), "date")
        else date.fromisoformat(str(composite["Date"].max())),
    }


# ---------------------------------------------------------------------------
# Knowledge eligibility view (read-only, fail-closed)
# ---------------------------------------------------------------------------


def _lesson_dates_by_id(lessons_path: Path) -> dict[str, date]:
    from .cases import load_lessons

    return {
        row["lesson_id"]: date.fromisoformat(row["event_date"])
        for row in load_lessons(lessons_path)
    }


def knowledge_eligible_records(
    as_of: date,
    *,
    knowledge_records_path: Path = DEFAULT_KNOWLEDGE_RECORDS_PATH,
    lessons_path: Path = DEFAULT_LESSONS_PATH,
) -> tuple[list[str], date | None]:
    """Read-only eligibility view.

    A knowledge record is eligible iff every ``source_lesson_ids`` entry
    resolves to a lesson with event_date <= as_of.  Unresolvable or empty
    source lesson ids make the record ineligible (fail-closed, no invention).
    """
    import json

    from knowledge.integrity.knowledge_record import KnowledgeRecord

    if not Path(knowledge_records_path).is_file():
        raise ValidationError(
            f"knowledge records artifact missing: {knowledge_records_path}"
        )
    payload = json.loads(Path(knowledge_records_path).read_text(encoding="utf-8"))
    records = payload.get("records", [])
    if not isinstance(records, list) or not records:
        raise ValidationError(
            f"knowledge records artifact has no records: {knowledge_records_path}"
        )

    lesson_dates = _lesson_dates_by_id(lessons_path)
    eligible: list[str] = []
    source_maxes: list[date] = []
    for item in records:
        record = KnowledgeRecord.from_dict(item)
        ids = record.source_lesson_ids
        if not ids:
            continue
        dates = []
        ok = True
        for lesson_id in ids:
            lesson_date = lesson_dates.get(lesson_id)
            if lesson_date is None:
                ok = False
                break
            dates.append(lesson_date)
        if not ok:
            continue
        if any(d > as_of for d in dates):
            continue
        eligible.append(record.knowledge_id)
        source_maxes.append(max(dates))

    return sorted(eligible), (max(source_maxes) if source_maxes else None)


# ---------------------------------------------------------------------------
# As-of knowledge derivation (existing producer semantics, <= D, in memory)
# ---------------------------------------------------------------------------

# Mirrors the economic pipeline knowledge configuration for CPI / XAU/USD
# (knowledge.pipeline -> LessonSummaryConfig): identical condition columns,
# horizons, aggregation fields and identifiers.
ASOF_KNOWLEDGE_CONDITION_COLUMNS: tuple[str, ...] = ("cpi_pressure",)
ASOF_KNOWLEDGE_HORIZONS: tuple[int, ...] = (1, 5, 20)
ASOF_KNOWLEDGE_EVENT_TYPE = "CPI"
ASOF_KNOWLEDGE_ASSET = "XAU/USD"
ASOF_KNOWLEDGE_PREFIX = "knowledge_summary_v1"


def asof_knowledge_records(
    as_of: date,
    *,
    lessons_path: Path = DEFAULT_LESSONS_PATH,
) -> list[dict[str, object]]:
    """Derive the knowledge records a real-time system could have held at D.

    Reuses the EXISTING ``LessonSummaryAggregator`` record projection
    (``_summarize_group``) over the canonical lesson rows restricted to
    ``event_date <= as_of``.  Deterministic: same artifact + date yield the
    identical record set (grouping/horizons/statistics/identifiers are the
    producer's own code paths).  Empty when no lessons exist at or before D.
    """
    import pandas as pd

    from knowledge.lesson_summary import LessonSummaryAggregator, LessonSummaryConfig

    from .cases import load_lessons

    cutoff = as_of.isoformat()
    rows = [
        row for row in load_lessons(lessons_path) if row["event_date"] <= cutoff
    ]
    if not rows:
        return []
    df = pd.DataFrame(rows)
    for horizon in ASOF_KNOWLEDGE_HORIZONS:
        col = f"gold_return_{horizon}d_pct"
        df[col] = pd.to_numeric(df[col], errors="raise")
    config = LessonSummaryConfig(
        lessons_path=Path(lessons_path),
        condition_columns=ASOF_KNOWLEDGE_CONDITION_COLUMNS,
        knowledge_prefix=ASOF_KNOWLEDGE_PREFIX,
        event_type=ASOF_KNOWLEDGE_EVENT_TYPE,
        asset=ASOF_KNOWLEDGE_ASSET,
        horizons=ASOF_KNOWLEDGE_HORIZONS,
        institutional_context=(),
    )
    aggregator = LessonSummaryAggregator(config)

    records: list[dict[str, object]] = []
    for condition_values, group in df.groupby(
        list(ASOF_KNOWLEDGE_CONDITION_COLUMNS), sort=True
    ):
        if not isinstance(condition_values, tuple):
            condition_values = (condition_values,)
        condition_dict = dict(
            zip(ASOF_KNOWLEDGE_CONDITION_COLUMNS, condition_values)
        )
        for horizon in ASOF_KNOWLEDGE_HORIZONS:
            records.append(aggregator._summarize_group(condition_dict, group, horizon))
    return records


def eligible_asof_knowledge_records(snapshot, cfg) -> list[dict[str, object]]:
    """Derived-as-of knowledge records for one snapshot's eligible ids.

    Single source of truth shared with ``_knowledge_block``: the record set
    is re-derived deterministically for the snapshot's evaluation date and
    filtered to ``snapshot.eligible_knowledge_ids``.
    """
    records = asof_knowledge_records(
        snapshot.evaluation_date,
        lessons_path=cfg.lessons_path,
    )
    eligible = set(snapshot.eligible_knowledge_ids)
    return [r for r in records if r.get("knowledge_id") in eligible]


def _knowledge_block(as_of: date, config: SnapshotConfig) -> dict[str, object]:
    """As-of eligible knowledge ids over the derived record set.

    The eligibility rule is unchanged and stays fail-closed: a derived
    record enters the eligible set only when every ``source_lesson_ids``
    entry resolves to a lesson with event_date <= D (derived sources do by
    construction; the check remains explicit).
    """
    from knowledge.integrity.knowledge_record import KnowledgeRecord

    records = asof_knowledge_records(
        as_of,
        lessons_path=config.lessons_path,
    )

    lesson_dates = _lesson_dates_by_id(config.lessons_path)
    eligible: list[str] = []
    source_maxes: list[date] = []
    for item in records:
        record = KnowledgeRecord.from_dict(item)
        ids = record.source_lesson_ids
        if not ids:
            continue
        dates = []
        ok = True
        for lesson_id in ids:
            lesson_date = lesson_dates.get(lesson_id)
            if lesson_date is None:
                ok = False
                break
            dates.append(lesson_date)
        if not ok:
            continue
        if any(d > as_of for d in dates):
            continue
        eligible.append(record.knowledge_id)
        source_maxes.append(max(dates))

    return {
        "knowledge_cutoff": as_of,
        "eligible_knowledge_ids": tuple(sorted(eligible)),
        "knowledge_source_max_lesson_date": max(source_maxes) if source_maxes else None,
    }


# ---------------------------------------------------------------------------
# Analogue cutoff (strictly < D, current episode excluded)
# ---------------------------------------------------------------------------


def _analogue_block(case, lessons_path: Path) -> dict[str, object]:
    from .cases import load_lessons

    rows = load_lessons(lessons_path)
    prior = [row for row in rows if date.fromisoformat(row["event_date"]) < case.evaluation_date]
    eligible_ids = tuple(sorted(row["lesson_id"] for row in prior))
    cutoff = max(date.fromisoformat(row["event_date"]) for row in prior) if prior else None
    return {
        "analogue_cutoff": cutoff,
        "analogue_eligible_lesson_ids": eligible_ids,
        "excluded_lesson_ids": (case.lesson_id,),
    }


# ---------------------------------------------------------------------------
# Snapshot assembly
# ---------------------------------------------------------------------------


def build_snapshot(
    case,
    config: SnapshotConfig | None = None,
) -> ValidationSnapshot:
    """Build the deterministic as-of snapshot for one ValidationCase."""
    cfg = config or SnapshotConfig()
    d = case.evaluation_date

    yield_block = _yield_block(d, cfg)
    dxy_block = _dxy_block(d, cfg)
    regime_block = _regime_block(d, cfg)
    knowledge_block = _knowledge_block(d, cfg)
    analogue_block = _analogue_block(case, cfg.lessons_path)

    evaluation_only = tuple(
        {
            "horizon": outcome.horizon,
            "return_pct": outcome.return_pct,
            "direction": outcome.direction,
            "evaluation_only": True,
        }
        for outcome in case.outcomes
    )

    snapshot = ValidationSnapshot(
        lesson_id=case.lesson_id,
        evaluation_date=d,
        cpi_pressure=case.cpi_pressure,
        us10y_value=yield_block["us10y_value"],
        us10y_observation_date=yield_block["us10y_observation_date"],
        us10y_anchor_value=yield_block["us10y_anchor_value"],
        us10y_anchor_date=yield_block["us10y_anchor_date"],
        us10y_change=yield_block["us10y_change"],
        us10y_trend=yield_block["us10y_trend"],
        dxy_value=dxy_block["dxy_value"],
        dxy_observation_date=dxy_block["dxy_observation_date"],
        dxy_anchor_value=dxy_block["dxy_anchor_value"],
        dxy_anchor_date=dxy_block["dxy_anchor_date"],
        dxy_change=dxy_block["dxy_change"],
        dxy_trend=dxy_block["dxy_trend"],
        institutional_regime=regime_block["institutional_regime"],
        regime_source_max_date=regime_block["regime_source_max_date"],
        knowledge_cutoff=knowledge_block["knowledge_cutoff"],
        eligible_knowledge_ids=knowledge_block["eligible_knowledge_ids"],
        knowledge_source_max_lesson_date=knowledge_block["knowledge_source_max_lesson_date"],
        analogue_cutoff=analogue_block["analogue_cutoff"],
        analogue_eligible_lesson_ids=analogue_block["analogue_eligible_lesson_ids"],
        excluded_lesson_ids=analogue_block["excluded_lesson_ids"],
        evaluation_only_outcomes=evaluation_only,
    )
    snapshot.assert_no_lookahead()
    return snapshot