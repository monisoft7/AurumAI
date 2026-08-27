"""Historical Validation pure historical inference path (no orchestrator).

Boundary-corrected FULL vs NO_HISTORY harness.  The validation flow NEVER
enters the default pipeline entry point, W3 pre-market, any live fetcher or
refresher, checkpointing, runtime registration, or production output/state
writers.  Every stage below is an EXISTING production engine invoked with
inputs supplied directly and immutably:

    ValidationCase
      -> ValidationSnapshot                        (as-of safe)
      -> in-memory as-of episode corpus            (event_date < D)
      -> HistoricalSituationRetriever              (snapshot-derived query)
      -> build_historical_adjudication             (existing engine)
      -> EvidenceReasoner (W6)                     (existing engine)
      -> CounterEvidenceAssessor (W7)              (existing engine)
      -> ThesisConstructor (W8) / ThesisUpdater    (existing engines)
      -> ScenarioGenerator / RiskRewardValidator   (existing engines)
      -> ConfidenceEngine / DecisionEngine         (existing engines)

The W5 evidence collection is supplied as the immutable empty collection
under this boundary: its real producer is the W4 signal assessment whose
upstream is exactly the forbidden pre-market/fetcher stack.  Nothing is
fabricated in its place; see UPSTREAM_EVIDENCE_DEPENDENCY.

Writes: none.  This module performs no filesystem writes at all.
"""

from __future__ import annotations

from contextlib import contextmanager
from typing import Any

from .spec import TRACE_ID

UPSTREAM_EVIDENCE_DEPENDENCY = (
    "W5 institutional evidence requires the W4 SignalAssessment, produced "
    "only by the forbidden W3 pre-market/fetcher stack; under the pure "
    "boundary it is supplied as the immutable empty collection and NO "
    "observation or knowledge semantics are fabricated."
)


# ---------------------------------------------------------------------------
# Guards
# ---------------------------------------------------------------------------


def today_guard():
    """Assert that no present-day context function fires during a run."""

    class _Guard:
        def __enter__(self):
            import evidence_reasoning.historical_analogue as ha

            self._ha = ha
            self._original = ha.current_context_trends

            def _forbidden(*args, **kwargs):
                raise AssertionError("current_context_trends was invoked")

            ha.current_context_trends = _forbidden
            return self

        def __exit__(self, *exc):
            self._ha.current_context_trends = self._original
            return False

    return _Guard()


def verify_no_lookahead(snapshot) -> dict[str, bool]:
    """Mandatory pre-run assertions over one ValidationSnapshot."""
    d = snapshot.evaluation_date.isoformat()

    def le(value) -> bool:
        return value is None or value.isoformat() <= d

    checks: dict[str, bool] = {
        "us10y_observation_le_D": le(snapshot.us10y_observation_date),
        "us10y_anchor_le_D": le(snapshot.us10y_anchor_date),
        "dxy_observation_le_D": le(snapshot.dxy_observation_date),
        "dxy_anchor_le_D": le(snapshot.dxy_anchor_date),
        "regime_source_max_le_D": le(snapshot.regime_source_max_date),
        "knowledge_source_max_le_D": le(snapshot.knowledge_source_max_lesson_date),
        "analogue_cutoff_lt_D": (
            snapshot.analogue_cutoff is None
            or snapshot.analogue_cutoff.isoformat() < d
        ),
        "current_episode_excluded": snapshot.lesson_id
        not in set(snapshot.analogue_eligible_lesson_ids),
        "future_outcomes_evaluation_only": len(snapshot.evaluation_only_outcomes) == 3
        and all(
            item.get("evaluation_only") is True
            for item in snapshot.evaluation_only_outcomes
        ),
    }
    snapshot.assert_no_lookahead()
    failed = [name for name, ok in checks.items() if not ok]
    if failed:
        raise AssertionError(
            f"NO-LOOKAHEAD FAILURE {snapshot.lesson_id}: {failed}"
        )
    return checks


def verify_payload_lookahead(case, analogue_payload: dict | None) -> dict[str, bool]:
    """No current and no future lesson may appear among retrieved analogues."""
    d = case.evaluation_date.isoformat()
    matches = (analogue_payload or {}).get("matches") or []
    from .cases import load_lessons

    dates_by_id = {row["lesson_id"]: row["event_date"] for row in load_lessons(None)}
    match_ids = [m.get("lesson_id") for m in matches]
    checks = {
        "no_current_lesson_retrieved": case.lesson_id not in set(match_ids),
        "no_future_lesson_retrieved": all(
            dates_by_id.get(mid, d) < d for mid in match_ids
        ),
    }
    if not all(checks.values()):
        raise AssertionError(f"PAYLOAD LOOKAHEAD FAILURE {case.lesson_id}: {checks}")
    return checks


# ---------------------------------------------------------------------------
# Analogue payload (reuses the Step-3 retrieval flow verbatim)
# ---------------------------------------------------------------------------


def build_analogue_payload(snapshot) -> tuple[dict[str, Any], dict[str, Any]]:
    """Retrieve analogues for ONE snapshot via the existing Step-3 flow."""
    from evidence_reasoning.historical_analogue import _match_entry_honest
    from knowledge.evidence.collection import EvidenceCollection
    from knowledge.reasoning.retrieval import HistoricalSituationRetriever
    from knowledge.reasoning.retrieval import SituationQuery
    from knowledge.temporal.lesson_index import LessonEpisodeQuery

    from .analogue import asof_episode_corpus, snapshot_query
    from .snapshot import SnapshotConfig

    indexer, eligible_ids = asof_episode_corpus(
        snapshot.evaluation_date, SnapshotConfig().lessons_path
    )

    base_query = snapshot_query(snapshot)
    surface = LessonEpisodeQuery(indexer)
    retriever = HistoricalSituationRetriever()

    effective_query = base_query
    matches = retriever.retrieve(base_query, surface)
    context_relaxed: Any = False
    if not matches and base_query.institutional_context:
        effective_query = SituationQuery(
            event_type=base_query.event_type,
            condition=dict(base_query.condition),
            institutional_context={},
        )
        matches = retriever.retrieve(effective_query, surface)
        context_relaxed = ["regime"]

    state_by_id = {s.state_id: s for s in indexer._ensure_sorted()}
    honesty_regime = (
        None if context_relaxed else snapshot.institutional_regime or None
    )
    selected = matches[:3]
    entries = [
        _match_entry_honest(m, state_by_id, honesty_regime) for m in selected
    ]
    aggregate = (
        EvidenceCollection([m.evidence for m in selected]).aggregate()
        if selected
        else {}
    )
    query_block = {
        "event_type": effective_query.event_type,
        "condition": dict(effective_query.condition),
        "institutional_context": dict(effective_query.institutional_context),
    }
    payload = {
        "primary_query": query_block,
        "effective_query": query_block,
        "context_relaxed": context_relaxed,
        "match_count": len(entries),
        "matches": entries,
        "aggregate": aggregate,
        "top_k": 3,
        "aggregate_scope": "top_k",
        "query": query_block,
    }
    info = {
        "match_ids": [e["lesson_id"] for e in entries],
        "retrieval_methods": {
            e["lesson_id"]: e["similarity"]["retrieval_method"] for e in entries
        },
        "context_relaxed": context_relaxed,
        "eligible_episode_count": len(eligible_ids),
    }
    return payload, info


# ---------------------------------------------------------------------------
# Contract plumbing: splice the W10-versioned primary into the candidate set
# (pure dataclass reshuffling -- mirrors the existing stage boundary logic;
# no scoring formula involved)
# ---------------------------------------------------------------------------


def _splice_update(update, original_construction):
    from thesis_construction.contracts import ThesisConstruction

    thesis = update.updated_thesis
    spliced: list = []
    replaced = False
    for t in original_construction.theses:
        if t.thesis_id == update.previous_thesis_id:
            spliced.append(thesis)
            replaced = True
        else:
            spliced.append(t)
    if not replaced:
        spliced.append(thesis)
    ranked_ids = [
        t.thesis_id
        for t in sorted(spliced, key=lambda t: t.institutional_support, reverse=True)
    ]
    return ThesisConstruction(
        construction_id=update.update_id,
        reasoning_id=original_construction.reasoning_id,
        assessment_id=original_construction.assessment_id,
        timestamp=update.timestamp,
        regime=original_construction.regime,
        theses=tuple(spliced),
        ranked_thesis_ids=tuple(ranked_ids),
        total_theses=len(spliced),
        primary_thesis_id=thesis.thesis_id,
        metadata=dict(original_construction.metadata),
    )


# ---------------------------------------------------------------------------
# Variant execution (pure)
# ---------------------------------------------------------------------------


def _run_inference_chain(collection, regime, payload) -> dict[str, Any]:
    """Existing W6-W13 production engines over directly-supplied inputs."""
    from counter_evidence.assessor import CounterEvidenceAssessor
    from confidence_engine.engine import ConfidenceEngine
    from decision_engine.engine import DecisionEngine
    from evidence_reasoning.reasoner import EvidenceReasoner
    from risk_reward_validation.validator import RiskRewardValidator
    from scenario_generation.generator import ScenarioGenerator
    from thesis_construction.constructor import ThesisConstructor
    from thesis_update.updater import ThesisUpdater

    reasoning = EvidenceReasoner().reason(
        collection,
        regime=regime or "",
        historical_analogue=payload,
    )
    counter = CounterEvidenceAssessor().assess(reasoning)
    construction = ThesisConstructor().construct(reasoning, counter)
    update = ThesisUpdater().update(construction, reasoning, counter)
    construction_v2 = _splice_update(update, construction)
    generation = ScenarioGenerator().generate(construction_v2)
    rr_validation = RiskRewardValidator().validate(generation)
    confidence = ConfidenceEngine().evaluate(
        construction_v2, reasoning=reasoning, generation=generation
    )

    from bias_prevention.contracts import apply_bias_review
    from bias_prevention.detector import BiasReviewer

    bias_review = BiasReviewer().review(update, counter, confidence)
    decision = apply_bias_review(
        DecisionEngine().decide(construction_v2, confidence, generation, rr_validation),
        bias_review,
    )
    return {
        "evidence_reasoning": reasoning,
        "counter_evidence": counter,
        "thesis_construction": construction,
        "thesis_update": update,
        "scenario_generation": generation,
        "risk_reward_validation": rr_validation,
        "confidence_engine": confidence,
        "bias_prevention": bias_review,
        "decision_engine": decision,
    }


def run_pure_variant(
    case,
    *,
    history_enabled: bool,
    run_label: str = "a",
    config=None,
    snapshot=None,
    workspace_root: Any = None,
) -> dict[str, Any]:
    """Run the full pure validation chain once for ONE variant.  Read-only.

    ``workspace_root`` is accepted for caller compatibility and ignored:
    the pure path performs NO filesystem writes at all.
    """
    from evidence_collection.contracts import EvidenceCollection

    from .snapshot import SnapshotConfig, build_snapshot

    snap = snapshot if snapshot is not None else build_snapshot(case, config or SnapshotConfig())
    snap.assert_no_lookahead()
    nl_checks = verify_no_lookahead(snap)

    with today_guard():
        payload = None
        payload_info: dict[str, Any] = {
            "match_ids": [],
            "retrieval_methods": {},
            "context_relaxed": False,
            "eligible_episode_count": None,
        }
        if history_enabled:
            payload, payload_info = build_analogue_payload(snap)

        # Immutable empty W5 input under the pure boundary (see module docstring).
        collection = EvidenceCollection(
            collection_id="ec_hv_pure",
            assessment_id="hv_pure_boundary",
            timestamp="validation-only",
            regime=snap.institutional_regime or "",
            items=(),
        )

        outputs = _run_inference_chain(
            collection, snap.institutional_regime, payload
        )

    payload_checks = verify_payload_lookahead(case, payload)

    result = _extract_comparison(outputs, history_enabled, snap, payload_info)
    result["no_lookahead_checks"] = nl_checks
    result["payload_lookahead_checks"] = payload_checks
    result["eligible_episode_count"] = payload_info["eligible_episode_count"]
    result["upstream_evidence_dependency"] = UPSTREAM_EVIDENCE_DEPENDENCY
    return result


# Backward-compatible entrypoint name used by tests and the pilot runner.
run_variant = run_pure_variant


# ---------------------------------------------------------------------------
# Serialization / numeric-leaf extraction (shared contract with compare.py)
# ---------------------------------------------------------------------------

HISTORICAL_METADATA_KEYS: tuple[str, ...] = (
    "historical_analogue",
    "historical_adjudication",
    "contextual_historical_adjudication",
    "historical_assessment",
)


def _serialize(obj: Any) -> Any:
    if obj is None or isinstance(obj, (str, int, float, bool)):
        return obj
    if isinstance(obj, dict):
        return {str(key): _serialize(value) for key, value in obj.items()}
    if isinstance(obj, (list, tuple, set)):
        return [_serialize(value) for value in obj]
    from datetime import date as _date, datetime as _datetime

    if isinstance(obj, (_date, _datetime)):
        return obj.isoformat()
    if hasattr(obj, "to_dict"):
        return _serialize(obj.to_dict())
    import dataclasses

    if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
        return _serialize(dataclasses.asdict(obj))
    if hasattr(obj, "__dict__"):
        return _serialize(vars(obj))
    return str(obj)


def numeric_leaves(node: Any, prefix: str = "") -> dict[str, float]:
    """Collect every int/float leaf keyed by its path.

    Paths under any historical-metadata key are EXCLUDED -- those carry the
    intended FULL-only payload; everything else must be invariant.
    """
    leaves: dict[str, float] = {}
    if isinstance(node, dict):
        for key, value in node.items():
            path = f"{prefix}.{key}" if prefix else str(key)
            if key in HISTORICAL_METADATA_KEYS:
                continue
            leaves.update(numeric_leaves(value, path))
    elif isinstance(node, (list, tuple)):
        for idx, value in enumerate(node):
            leaves.update(numeric_leaves(value, f"{prefix}[{idx}]"))
    elif isinstance(node, bool) or node is None:
        return leaves
    elif isinstance(node, (int, float)):
        leaves[prefix] = float(node)
    return leaves


def _first_number(node: Any, *paths: str) -> float | None:
    for path in paths:
        cur: Any = node
        found = True
        for part in path.split("."):
            if isinstance(cur, dict) and part in cur:
                cur = cur[part]
            else:
                found = False
                break
        if found and isinstance(cur, (int, float)) and not isinstance(cur, bool):
            return float(cur)
    return None


# ---------------------------------------------------------------------------
# Comparison extraction (same result contract as the legacy harness)
# ---------------------------------------------------------------------------


def _extract_comparison(
    outputs: dict[str, Any],
    history_enabled: bool,
    snapshot,
    payload_info: dict[str, Any],
) -> dict[str, Any]:
    reasoning_d = _serialize(outputs.get("evidence_reasoning")) or {}
    reasoning_meta = reasoning_d.get("metadata") or {}
    historical_metadata_present = {
        key: (key in reasoning_meta) for key in HISTORICAL_METADATA_KEYS[:3]
    }

    construction_d = _serialize(outputs.get("thesis_construction")) or {}
    theses = construction_d.get("theses") or []
    evaluated = [
        {
            "thesis_id": t.get("thesis_id"),
            "direction": t.get("direction"),
            "institutional_support": _first_number(t, "institutional_support"),
        }
        for t in theses
        if isinstance(t, dict)
    ]

    update_d = _serialize(outputs.get("thesis_update")) or {}
    updated_thesis = update_d.get("updated_thesis") or {}
    selected_direction = updated_thesis.get("direction")
    primary_thesis_id = updated_thesis.get("thesis_id") or construction_d.get(
        "primary_thesis_id"
    )

    confidence_d = _serialize(outputs.get("confidence_engine")) or {}
    conf_by_thesis = {
        tc.get("thesis_id"): tc
        for tc in (confidence_d.get("theses_confidence") or [])
        if isinstance(tc, dict)
    }
    primary_confidence = conf_by_thesis.get(primary_thesis_id) or {}

    rr_d = _serialize(outputs.get("risk_reward_validation")) or {}
    decision_d = _serialize(outputs.get("decision_engine")) or {}

    assessments = None
    update_obj = outputs.get("thesis_update")
    if update_obj is not None:
        spliced = _splice_update(update_obj, outputs.get("thesis_construction"))
        assessments = [
            {
                "thesis_id": t.thesis_id,
                "thesis_direction": t.direction,
                "historical_assessment": t.metadata.get("historical_assessment"),
            }
            for t in spliced.theses
        ]

    analogue_payload_present = reasoning_meta.get("historical_analogue") is not None

    return {
        "variant": "FULL" if history_enabled else "NO_HISTORY",
        "history_enabled": history_enabled,
        "lesson_id": snapshot.lesson_id,
        "evaluation_date": snapshot.evaluation_date,
        "snapshot_summary": {
            "cpi_pressure": snapshot.cpi_pressure,
            "us10y_trend": snapshot.us10y_trend,
            "dxy_trend": snapshot.dxy_trend,
            "institutional_regime": snapshot.institutional_regime,
            "analogue_cutoff": snapshot.analogue_cutoff,
        },
        "historical_metadata_present": historical_metadata_present,
        "analogue_match_ids": tuple(payload_info["match_ids"]),
        "retrieval_methods": dict(payload_info["retrieval_methods"]),
        "context_relaxed": payload_info["context_relaxed"],
        "historical_retrieval_payload_present": analogue_payload_present,
        "historical_adjudication_present": reasoning_meta.get(
            "historical_adjudication"
        )
        is not None,
        "evaluated_theses": evaluated,
        "evaluated_thesis_directions": sorted(
            {e["direction"] for e in evaluated if e["direction"]}
        ),
        "institutional_support_by_direction": {
            e["direction"]: e["institutional_support"]
            for e in evaluated
            if e["direction"] is not None and e["institutional_support"] is not None
        },
        "primary_thesis_id": primary_thesis_id,
        "selected_thesis_direction": selected_direction,
        "institutional_confidence": _first_number(
            decision_d, "institutional_confidence"
        ),
        "confidence_payload_summary": {
            "final_confidence": _first_number(primary_confidence, "final_confidence"),
            "remaining_uncertainty": _first_number(
                primary_confidence, "remaining_uncertainty"
            ),
            "reliability_category": primary_confidence.get("reliability_category"),
        },
        "risk_reward_summary": rr_d.get("summary"),
        "risk_reward_ratios": sorted(
            v
            for v in (
                _first_number(item, "risk_reward_ratio")
                for item in (rr_d.get("validations") or [])
                if isinstance(item, dict)
            )
            if v is not None
        ),
        "decision": decision_d.get("decision"),
        "decision_risk_reward_summary": decision_d.get("risk_reward_summary") or {},
        "candidate_historical_assessments": assessments,
        "serialized_outputs": {
            key: _serialize(value) for key, value in outputs.items()
        },
    }
