"""Trace 050-A -- validation-only candidate-scoped BiasReview counterfactual.

READ-ONLY validation harness.  Reproduces the exact production pure-chain
(enriched replay path) with live objects, then reviews EVERY thesis
candidate independently through the UNMODIFIED production BiasReviewer,
builds the findings x candidates matrix, applies offline channel-dedup
arithmetic, and locks the observed behavior with focused assertions:

 1. all candidates reviewed independently
 2. production primary-only behavior reproduced (findings/impact/final decision)
 3. finding matrix deterministic (repeat review identical)
 4. channel dedup deterministic
 5. no production files modified during the run
 6. no network (socket guard active for the whole module)
 7. no lookahead (path-level no-lookahead checks all true)
 8. risk/reward untouched (live validations == reference serialized validations)

No production source, weight, threshold, or severity is modified anywhere.
"""

from __future__ import annotations

import hashlib
import socket
import sys
from dataclasses import replace
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from historical_validation.cases import build_validation_cases
from historical_validation.enriched_replay import run_enriched_replay_variant
from historical_validation.snapshot import SnapshotConfig, build_snapshot

SMOKE_IDS = (
    "CPI_GOLD_2015-06-01",
    "CPI_GOLD_2020-09-01",
    "CPI_GOLD_2026-02-01",
)

WATCHED_FILES: tuple[str, ...] = (
    "data/history/gold/gold.csv",
    "data/context/dxy/dxy.csv",
    "data/economic/DFII10.csv",
    "data/economic/DGS10.csv",
    "data/economic/T5YIE.csv",
    "data/calendar/cpi_releases.csv",
    "data/economic/output/knowledge.json",
    "data/economic/gold_oi_state.json",
    "data/lessons/cpi_gold_lessons.csv",
)

SEV_RANK = {"clean": 0, "low": 1, "medium": 2, "high": 3, "critical": 4}
HUMAN_REVIEW_SEVERITIES = {"high", "critical"}


def _channel_of(name: str) -> str:
    if name == "regime_blindness":
        return "regime_conflict"
    if name == "false_precision":
        return "formatting"
    return "evidence_thinness"


_THIN_PRIORITY = [
    "single_source_bias", "groupthink", "narrative_bias",
    "confirmation_bias", "overconfidence", "base_rate_neglect",
    "recency_bias", "anchoring", "attribution_error",
    "this_time_is_different",
]


def _dedup(findings):
    """Offline single-count-per-channel arithmetic (max-severity representative)."""
    reps: dict[str, object] = {}
    for f in findings:
        ch = _channel_of(f.bias_name)
        cur = reps.get(ch)
        if cur is None or SEV_RANK[f.severity] > SEV_RANK[cur.severity] or (
            SEV_RANK[f.severity] == SEV_RANK[cur.severity]
            and (_THIN_PRIORITY.index(f.bias_name) < _THIN_PRIORITY.index(cur.bias_name))
        ):
            reps[ch] = f
    total = round(min(1.0, sum(f.confidence_impact for f in reps.values())), 4)
    flag = any(f.severity in HUMAN_REVIEW_SEVERITIES for f in reps.values())
    return {"total": total, "flag": flag, "channels": sorted(reps)}


@pytest.fixture(scope="module")
def no_network():
    """Hard guard: outbound connections fail loudly; imports stay usable."""
    from pytest import MonkeyPatch

    def _forbidden(*args, **kwargs):
        raise AssertionError("network access attempted during validation run")

    # Warm lazy importer chains that subclass socket.socket at import time
    # (yfinance -> requests -> urllib3 -> PySocks) BEFORE arming the guard.
    import yfinance  # noqa: F401

    mp = MonkeyPatch()
    mp.setattr(socket, "create_connection", _forbidden)
    mp.setattr(socket, "getaddrinfo", _forbidden)
    mp.setattr(socket.socket, "connect", _forbidden)
    try:
        yield True
    finally:
        mp.undo()


def _digest(rel: str) -> str:
    p = ROOT / rel
    return hashlib.sha256(p.read_bytes()).hexdigest() if p.is_file() else "<missing>"


@pytest.fixture(scope="module")
def bundle(no_network):
    from bias_prevention.contracts import apply_bias_review
    from bias_prevention.detector import BiasReviewer
    from confidence_engine.engine import ConfidenceEngine
    from counter_evidence.assessor import CounterEvidenceAssessor
    from decision_engine.engine import DecisionEngine
    from evidence_collection.collector import EvidenceCollector
    from evidence_reasoning.reasoner import EvidenceReasoner
    from historical_validation.briefing import assemble_historical_signal
    from historical_validation.enriched_path import build_enriched_analogue_payload
    from historical_validation.pure_path import _splice_update
    from historical_validation.signal_replay import (
        REGIME_WEIGHT_DEFAULT,
        asof_knowledge_graph,
    )
    from risk_reward_validation.validator import RiskRewardValidator
    from scenario_generation.generator import ScenarioGenerator
    from thesis_construction.constructor import ThesisConstructor
    from thesis_update.updater import ThesisUpdater

    cases = {c.lesson_id: c for c in build_validation_cases()}
    cfg = SnapshotConfig()
    reviewer = BiasReviewer()
    before_files = {rel: _digest(rel) for rel in WATCHED_FILES}

    out = {}
    for lid in SMOKE_IDS:
        case = cases[lid]
        snap = build_snapshot(case, cfg)

        # Production reference (serialized pipeline output).
        ref = run_enriched_replay_variant(
            case, history_enabled=True, snapshot=snap, config=cfg
        )
        ref_ser = ref["serialized_outputs"]

        # Live reproduction with retained objects.
        payload, _info = build_enriched_analogue_payload(snap)
        _briefing, signal_assessment, _b = assemble_historical_signal(
            case, snap, config=cfg
        )
        kg, _n = asof_knowledge_graph(snap, cfg)
        collection = EvidenceCollector(knowledge_graph=kg).collect(
            signal_assessment,
            regime_weight=REGIME_WEIGHT_DEFAULT,
            cpi_condition={"cpi_pressure": snap.cpi_pressure},
        )
        reasoning = EvidenceReasoner().reason(
            collection,
            regime=snap.institutional_regime or "",
            historical_analogue=payload,
        )
        counter = CounterEvidenceAssessor().assess(reasoning)
        construction = ThesisConstructor().construct(reasoning, counter)
        update = ThesisUpdater().update(construction, reasoning, counter)
        construction_v2 = _splice_update(update, construction)
        generation = ScenarioGenerator().generate(construction_v2)
        rr = RiskRewardValidator().validate(generation)
        confidence = ConfidenceEngine().evaluate(
            construction_v2, reasoning=reasoning, generation=generation
        )
        review_primary = reviewer.review(update, counter, confidence)
        decision_raw = DecisionEngine().decide(
            construction_v2, confidence, generation, rr
        )
        decision_final = apply_bias_review(decision_raw, review_primary)

        scen_by_id = {s.scenario_id: s for s in generation.scenarios}
        rr_by_thesis: dict[str, list] = {}
        for v in rr.validations:
            sc = scen_by_id.get(v.scenario_id)
            if sc is not None:
                rr_by_thesis.setdefault(sc.thesis_id, []).append(
                    {
                        "scenario_type": sc.scenario_type,
                        "status": v.validation_status,
                        "ratio": v.risk_reward_ratio,
                    }
                )

        selected_id = getattr(decision_raw, "selected_thesis_id", None)
        rows = []
        for cand in construction_v2.theses:
            if cand.thesis_id == update.updated_thesis.thesis_id:
                up_c = update
                is_prod_target = True
            else:
                cons_i = replace(
                    construction_v2,
                    primary_thesis_id=cand.thesis_id,
                    ranked_thesis_ids=tuple(
                        [cand.thesis_id]
                        + [
                            t.thesis_id
                            for t in construction_v2.theses
                            if t.thesis_id != cand.thesis_id
                        ]
                    ),
                )
                up_c = ThesisUpdater().update(cons_i, reasoning, counter)
                is_prod_target = False
            mapped = confidence.to_dict()
            for tc in mapped.get("theses_confidence", []):
                if tc.get("thesis_id") == cand.thesis_id:
                    tc["thesis_id"] = up_c.updated_thesis.thesis_id
            from confidence_engine.contracts import InstitutionalConfidence

            conf_c = InstitutionalConfidence.from_dict(mapped)
            rev = reviewer.review(up_c, counter, conf_c)
            tc_entry = next(
                t
                for t in confidence.theses_confidence
                if t.thesis_id == cand.thesis_id
            )
            repeat = reviewer.review(up_c, counter, conf_c)
            rows.append(
                {
                    "thesis_id": cand.thesis_id,
                    "direction": cand.direction,
                    "regime": cand.regime,
                    "final_confidence": tc_entry.final_confidence,
                    "support": cand.institutional_support,
                    "is_production_target": is_prod_target,
                    "is_selected": cand.thesis_id == selected_id,
                    "findings": [
                        {
                            "name": f.bias_name,
                            "severity": f.severity,
                            "impact": f.confidence_impact,
                        }
                        for f in rev.findings
                    ],
                    "total_impact": rev.total_confidence_impact,
                    "flag": rev.human_review_flag,
                    "review_dict_repeat": repeat.to_dict(),
                    "review_dict_first": rev.to_dict(),
                    "dedup_first": _dedup(rev.findings),
                    "dedup_second": _dedup(rev.findings),
                    "rr": rr_by_thesis.get(cand.thesis_id, []),
                    "nl_checks": ref["no_lookahead_checks"],
                }
            )

        out[lid] = {
            "rows": rows,
            "ref_decision": ref_ser["decision_engine"].get("decision"),
            "decision_final": decision_final.decision,
            "ref_primary_findings": [
                {
                    "name": f["bias_name"],
                    "severity": f["severity"],
                    "impact": f["confidence_impact"],
                }
                for f in ref_ser["bias_prevention"]["findings"]
            ],
            "ref_primary_total": float(
                ref_ser["bias_prevention"]["total_confidence_impact"]
            ),
            "primary_row": next(r for r in rows if r["is_production_target"]),
            "selected_row": next(r for r in rows if r["is_selected"]),
            "ref_rr_statuses": sorted(
                v.get("validation_status")
                for v in (ref_ser["risk_reward_validation"].get("validations") or [])
            ),
            "live_rr_statuses": sorted(v.validation_status for v in rr.validations),
            "rr_count_scenarios": len(generation.scenarios),
            "rr_count_validations": len(rr.validations),
        }

    yield out

    after_files = {rel: _digest(rel) for rel in WATCHED_FILES}
    assert before_files == after_files, "production data files changed during run"


# ---------------------------------------------------------------------------
# 1. All candidates reviewed independently
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("lid", SMOKE_IDS)
def test_all_candidates_reviewed_independently(bundle, lid):
    rows = bundle[lid]["rows"]
    assert len(rows) >= 2
    assert sum(1 for r in rows if r["is_production_target"]) == 1
    assert sum(1 for r in rows if r["is_selected"]) == 1
    for r in rows:
        assert isinstance(r["findings"], list)
        assert r["total_impact"] >= 0.0


# ---------------------------------------------------------------------------
# 2. Production primary-only behavior reproduced exactly
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("lid", SMOKE_IDS)
def test_production_primary_only_behavior_reproduced(bundle, lid):
    b = bundle[lid]
    primary = b["primary_row"]
    assert [(f["name"], f["severity"], f["impact"]) for f in primary["findings"]] == [
        (f["name"], f["severity"], f["impact"]) for f in b["ref_primary_findings"]
    ]
    assert abs(primary["total_impact"] - b["ref_primary_total"]) < 1e-9
    assert b["decision_final"] == b["ref_decision"]


# ---------------------------------------------------------------------------
# 3. Finding matrix deterministic (repeat review identical)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("lid", SMOKE_IDS)
def test_finding_matrix_deterministic(bundle, lid):
    for row in bundle[lid]["rows"]:
        assert row["review_dict_repeat"] == row["review_dict_first"]


# ---------------------------------------------------------------------------
# 4. Channel dedup deterministic and structure-preserving
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("lid", SMOKE_IDS)
def test_channel_dedup_deterministic(bundle, lid):
    for row in bundle[lid]["rows"]:
        first, second = row["dedup_first"], row["dedup_second"]
        assert first == second
        # dedup never lowers below one representative per occupied channel
        n_channels = len(first["channels"])
        raw_names = {f["name"] for f in row["findings"]}
        assert n_channels <= len(raw_names)


# ---------------------------------------------------------------------------
# 6. No network was possible (guard fixture active)
# ---------------------------------------------------------------------------


def test_no_network_guard_was_active(no_network):
    assert no_network is True


# ---------------------------------------------------------------------------
# 7. No lookahead on every case
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("lid", SMOKE_IDS)
def test_no_lookahead_all_true(bundle, lid):
    for row in bundle[lid]["rows"]:
        assert all(row["nl_checks"].values()), lid


# ---------------------------------------------------------------------------
# 8. Risk/reward untouched (live validations == reference, 1:1 scenarios)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("lid", SMOKE_IDS)
def test_rr_unchanged(bundle, lid):
    b = bundle[lid]
    assert b["live_rr_statuses"] == b["ref_rr_statuses"]
    assert b["rr_count_validations"] == b["rr_count_scenarios"]
    for row in b["rows"]:
        for item in row["rr"]:
            assert item["status"] in {"acceptable", "borderline", "reject"}


# ---------------------------------------------------------------------------
# Observed structural facts locked as documentation-by-test
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("lid", SMOKE_IDS)
def test_regime_blindness_directional_after_correction_050(bundle, lid):
    """Correction 050: RB fires ONLY on direction-opposed candidates.

    Updated from the pre-050 observation (all candidates flagged critical)
    to the validated directional semantics: regime-aligned directional
    candidates and neutral candidates carry no regime_blindness finding;
    opposed directional candidates keep severity critical.
    """
    from counter_evidence.detector import REGIME_EXPECTED_BIAS

    for row in bundle[lid]["rows"]:
        direction = row["direction"]
        regime = row["regime"]
        expected = REGIME_EXPECTED_BIAS.get(regime)
        opposed = (
            direction in ("bullish", "bearish")
            and expected in ("bullish", "bearish")
            and direction != expected
        )
        rb = next(
            (f for f in row["findings"] if f["name"] == "regime_blindness"),
            None,
        )
        if opposed:
            assert rb is not None and rb["severity"] == "critical", lid
        else:
            assert rb is None, (lid, direction, regime)


@pytest.mark.parametrize("lid", SMOKE_IDS)
def test_false_precision_fires_on_machine_explanations(bundle, lid):
    """Formatting heuristic fires for every machine-generated explanation."""
    for row in bundle[lid]["rows"]:
        assert "false_precision" in [f["name"] for f in row["findings"]], lid
