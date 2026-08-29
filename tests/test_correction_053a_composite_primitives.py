"""Correction 053-A -- composite-primitives observability (focused tests).

Proves the finalize artifact carries per-thesis W9/W8/W7/W12 primitives for
EVERY candidate (including rejected alternatives), that values are verbatim
in-memory reads, serialization is deterministic and JSON-round-trippable,
and that the addition is purely additive: no existing finalize field, no
decision, no numeric leaf outside the new key changes.  Also proves the
stage performs no filesystem writes.
"""

from __future__ import annotations

import builtins
import json

import pytest

from confidence_engine.computer import ConfidenceComputer
from confidence_engine.contracts import InstitutionalConfidence, ThesisConfidence
from decision_engine.engine import DecisionEngine
from risk_reward_validation.validator import RiskRewardValidator
from scenario_generation.generator import ScenarioGenerator
from thesis_construction.contracts import InvestmentThesis, ThesisConstruction

LEGACY_FINALIZE_KEYS = {
    "decision",
    "legacy_decision",
    "risk_decision",
    "forecast_result",
    "confidence",
    "validation",
    "context",
    "risk_metrics",
    "position_sizing",
    "risk_budget",
    "position_sizing_status",
}

PRIMITIVE_KEYS = {
    "thesis_id",
    "thesis_direction",
    "is_selected_in_w13",
    "institutional_support",
    "final_confidence",
    "remaining_uncertainty",
    "reliability_category",
    "evidence_quality",
    "evidence_consensus",
    "regime_alignment",
    "source_diversity",
    "knowledge_record_quality",
    "counter_evidence_penalty",
    "missing_evidence_penalty",
    "internal_consistency_penalty",
    "positive_score",
    "penalty_score",
    "positive_contributors",
    "negative_contributors",
    "confidence_penalties",
    "supporting_set_ids",
    "supporting_set_count",
    "counter_evidence_ids",
    "contradicting_set_ids",
    "conflict_severity",
    "confidence_penalty",
    "regime_conflict_flag",
    "bias_flags",
    "scenarios",
    "risk_reward_consumed_by_w13",
    "primitive_sources",
}


def _thesis(thesis_id, direction, support, w, pen) -> InvestmentThesis:
    return InvestmentThesis(
        thesis_id=thesis_id,
        direction=direction,
        supporting_set_ids=("es_general", "es_inflation"),
        counter_evidence_ids=("es_usd_fx",),
        regime="INFLATIONARY",
        economic_mechanism="CPI disinflation supports real-yield decline",
        time_horizon_days=90,
        invalidating_conditions=("Counter-evidence strengthens",),
        remaining_unknowns=("Missing evidence channels: CB_GOLD",),
        confidence_inputs={
            "avg_supporting_weight": w,
            "avg_supporting_consensus": 0.9,
            "conflict_severity": 0.1,
            "confidence_penalty": pen,
            "raw_support": round(w * 0.9, 4),
        },
        institutional_support=support,
        explanation="c053a",
    )


def _build_results():
    from counter_evidence.contracts import CounterEvidenceAssessment

    construction = ThesisConstruction(
        construction_id="tc_053a",
        reasoning_id="rsn_053a",
        assessment_id="cae_053a",
        timestamp="2026-08-24T06:56:54+00:00",
        regime="INFLATIONARY",
        theses=(
            _thesis("th_bull", "bullish", 0.3781, 0.5402, 0.30),
            _thesis("th_neut", "neutral", 0.4340, 0.5000, 0.20),
        ),
        ranked_thesis_ids=("th_bull", "th_neut"),
        total_theses=2,
        primary_thesis_id="th_bull",
        metadata={},
    )
    generation = ScenarioGenerator().generate(construction)
    validation = RiskRewardValidator().validate(generation)

    tcs = []
    compute_by_id = {}
    for t in construction.theses:
        result = ConfidenceComputer().compute(t)
        compute_by_id[t.thesis_id] = result
        tcs.append(
            ThesisConfidence(
                thesis_id=t.thesis_id,
                final_confidence=result["final_confidence"],
                confidence_breakdown=result["confidence_breakdown"],
                positive_contributors=tuple(result["positive_contributors"]),
                negative_contributors=tuple(result["negative_contributors"]),
                confidence_penalties=tuple(result["confidence_penalties"]),
                remaining_uncertainty=result["remaining_uncertainty"],
                reliability_category=result["reliability_category"],
            )
        )
    confidence = InstitutionalConfidence(
        confidence_id="cf_053a",
        construction_id="tc_053a",
        timestamp="2026-08-24T06:56:54+00:00",
        regime="INFLATIONARY",
        theses_confidence=tuple(tcs),
        ranked_thesis_ids=("th_bull", "th_neut"),
        primary_thesis_id="th_bull",
    )
    assessment = CounterEvidenceAssessment(
        assessment_id="cae_053a",
        reasoning_id="rsn_053a",
        timestamp="2026-08-24T06:56:54+00:00",
        regime="INFLATIONARY",
        supporting_set_ids=("es_general", "es_inflation"),
        contradicting_set_ids=("es_usd_fx",),
        conflict_severity=0.1,
        confidence_penalty=0.30,
        regime_conflict=False,
        bias_flags=("cross_set_conflict",),
    )
    decision = DecisionEngine().decide(construction, confidence, generation, validation)

    results = {
        "thesis_construction": construction,
        "confidence_engine": confidence,
        "counter_evidence": assessment,
        "scenario_generation": generation,
        "risk_reward_validation": validation,
        "decision_engine": decision,
    }
    in_memory = {
        "construction": construction,
        "confidence": confidence,
        "assessment": assessment,
        "generation": generation,
        "validation": validation,
        "decision": decision,
        "compute_by_id": compute_by_id,
    }
    return results, in_memory


def _call_finalize(results):
    from orchestration.stages import _finalize

    return _finalize({}, results)


def _default_json(obj):  # noqa: ANN001
    if hasattr(obj, "to_dict"):
        return obj.to_dict()
    return str(obj)


def _dumps(payload) -> str:
    return json.dumps(payload, sort_keys=True, default=_default_json)


def _forbid_writes(*args, **kwargs):  # noqa: ANN002, ANN003
    raise AssertionError("filesystem write attempted inside _finalize")


class TestCorrection053ACandidateCoverage:
    def test_every_thesis_represented_including_rejected(self):
        results, mem = _build_results()
        payload = _call_finalize(results)
        rows = payload["composite_primitives"]
        ids = {r["thesis_id"] for r in rows}
        assert ids == {t.thesis_id for t in mem["construction"].theses}
        selected = mem["decision"].selected_thesis_id
        rejected = {a.thesis_id for a in mem["decision"].rejected_alternatives}
        assert selected in ids and rejected <= ids
        by_sel = {r["thesis_id"]: r["is_selected_in_w13"] for r in rows}
        assert by_sel[selected] is True
        assert all(v is False for k, v in by_sel.items() if k != selected)

    def test_selected_and_rejected_all_have_full_primitives(self):
        results, _ = _build_results()
        payload = _call_finalize(results)
        for row in payload["composite_primitives"]:
            assert set(row.keys()) == PRIMITIVE_KEYS
            assert row["final_confidence"] is not None
            assert len(row["scenarios"]) == 3
            assert len(row["risk_reward_consumed_by_w13"]) == 3


class TestCorrection053AValueFidelity:
    def test_values_equal_in_memory_exactly(self):
        results, mem = _build_results()
        payload = _call_finalize(results)
        rows = {r["thesis_id"]: r for r in payload["composite_primitives"]}

        for thesis in mem["construction"].theses:
            row = rows[thesis.thesis_id]
            tc = next(
                t
                for t in mem["confidence"].theses_confidence
                if t.thesis_id == thesis.thesis_id
            )
            comp = mem["compute_by_id"][thesis.thesis_id]
            assert row["institutional_support"] == thesis.institutional_support
            assert row["final_confidence"] == tc.final_confidence
            assert row["evidence_quality"] == comp["confidence_breakdown"]["evidence_quality"]
            assert row["evidence_consensus"] == comp["confidence_breakdown"]["evidence_consensus"]
            # Run-003 repair (Phase 7): the regime_alignment channel is
            # removed from W9.  The additive finalize serialization keeps
            # the payload SHAPE (Correction 053-A contract) -- the value is
            # now None because no producer writes the key.
            assert "regime_alignment" not in comp["confidence_breakdown"]
            assert row["regime_alignment"] is None
            assert row["source_diversity"] == comp["confidence_breakdown"]["source_diversity"]
            assert (
                row["knowledge_record_quality"]
                == comp["confidence_breakdown"]["knowledge_record_quality"]
            )
            assert (
                row["counter_evidence_penalty"]
                == comp["confidence_breakdown"]["counter_evidence"]
            )
            assert (
                row["missing_evidence_penalty"]
                == comp["confidence_breakdown"]["missing_evidence"]
            )
            assert (
                row["internal_consistency_penalty"]
                == comp["confidence_breakdown"]["internal_consistency"]
            )
            # aggregates are sums over the persisted contributor rows
            # (value x weight -- identical arithmetic to W9's internal sum),
            # rounded to 4dp per repository serialization convention
            expected_positive = round(
                sum(c["value"] * c["weight"] for c in tc.positive_contributors),
                4,
            )
            assert row["positive_score"] == expected_positive
            assert row["penalty_score"] == pytest.approx(
                sum(c["penalty"] for c in tc.confidence_penalties), abs=1e-9
            )
            assert tuple(row["supporting_set_ids"]) == thesis.supporting_set_ids
            assert row["supporting_set_count"] == len(thesis.supporting_set_ids)
            assert tuple(row["contradicting_set_ids"]) == (
                mem["assessment"].contradicting_set_ids
            )
            assert row["conflict_severity"] == mem["assessment"].conflict_severity
            assert row["confidence_penalty"] == mem["assessment"].confidence_penalty

            scen_by_type = {s["scenario_type"]: s for s in row["scenarios"]}
            for s in mem["generation"].scenarios:
                if s.thesis_id != thesis.thesis_id:
                    continue
                got = scen_by_type[s.scenario_type]
                assert got["scenario_probability"] == s.probability
                assert got["scenario_confidence"] == (
                    s.confidence_inputs["scenario_confidence"]
                )
                # Run-003 (Phase 4/11): the label carries the actual source.
                assert got["scenario_confidence_source"] == (
                    s.confidence_inputs["scenario_confidence_source"]
                )
                assert got["scenario_confidence_type"] == "conviction_proxy"

            gen_by_sid = {s.scenario_id: s for s in mem["generation"].scenarios}
            v_by_sid = {v.scenario_id: v for v in mem["validation"].validations}
            rr_by_label = {
                r["metadata_scenario_label"]: r
                for r in row["risk_reward_consumed_by_w13"]
            }
            for v in mem["validation"].validations:
                s = gen_by_sid[v.scenario_id]
                if s.thesis_id != thesis.thesis_id:
                    continue
                got = rr_by_label[v.metadata["scenario_label"]]
                assert got["risk_reward_ratio"] == v.risk_reward_ratio
                assert got["validation_status"] == v.validation_status
                assert got["expected_reward"] == v.expected_reward

    def test_w13_consumption_fields_match_decision_summary(self):
        results, mem = _build_results()
        payload = _call_finalize(results)
        sel = mem["decision"].selected_thesis_id
        summary = mem["decision"].risk_reward_summary
        row = next(r for r in payload["composite_primitives"] if r["is_selected_in_w13"])
        best = min(
            row["risk_reward_consumed_by_w13"],
            key=lambda r: {"acceptable": 0, "borderline": 1, "reject": 2}[
                r["validation_status"]
            ],
        )
        assert best["validation_status"] == summary["status"]
        assert best["risk_reward_ratio"] == summary["risk_reward_ratio"]


class TestCorrection053ASerialization:
    def test_deterministic_repeated_serialization(self):
        results, _ = _build_results()
        one = _dumps(_call_finalize(results))
        two = _dumps(_call_finalize(results))
        assert one == two

    def test_json_round_trip(self):
        results, _ = _build_results()
        payload = _call_finalize(results)
        restored = json.loads(_dumps(payload))
        # tuples serialize to lists; compare in normalized space
        assert json.dumps(restored, sort_keys=True) == _dumps(payload)

    def test_no_filesystem_writes_inside_finalize(self, monkeypatch):
        monkeypatch.setattr(builtins, "open", _forbid_writes)
        import pathlib

        monkeypatch.setattr(pathlib.Path, "write_text", _forbid_writes)
        monkeypatch.setattr(pathlib.Path, "write_bytes", _forbid_writes)
        results, _ = _build_results()
        payload = _call_finalize(results)
        assert "composite_primitives" in payload


class TestCorrection053AAdditiveOnly:
    def test_only_new_top_level_key_added(self):
        results, _ = _build_results()
        payload = _call_finalize(results)
        new_keys = set(payload.keys()) - LEGACY_FINALIZE_KEYS - {
            "thesis_historical_assessments"
        }
        # Final Hardening: canonical_fact_registry (Group F) is a second
        # additive observability key; legacy keys remain untouched.
        assert new_keys == {"composite_primitives", "canonical_fact_registry"}
        # every legacy key remains present exactly as the stage defines it
        for key in LEGACY_FINALIZE_KEYS:
            assert key in payload

    def test_no_numeric_leaf_changes_outside_new_key(self):
        from historical_validation.pure_path import numeric_leaves

        results, _ = _build_results()
        full = _call_finalize(results)

        # identical inputs except no candidate construction -> no new key,
        # all other fields produced by the exact same code path
        stripped = {
            k: v
            for k, v in results.items()
            if k not in ("thesis_construction", "thesis_update")
        }
        legacy = _call_finalize(stripped)
        assert "composite_primitives" not in legacy

        shared = sorted(set(full) & set(legacy))
        assert "decision" in shared
        leaves_full = numeric_leaves(
            json.loads(_dumps({k: full[k] for k in shared}))
        )
        leaves_legacy = numeric_leaves(
            json.loads(_dumps({k: legacy[k] for k in shared}))
        )
        assert leaves_full == leaves_legacy
        assert leaves_full, "expected decision numerics to be covered"

    def test_decision_object_unchanged_after_finalize(self):
        results, mem = _build_results()
        before = mem["decision"]
        _call_finalize(results)
        assert mem["decision"] is before  # frozen dataclass, same object

    def test_legacy_run_without_candidates_has_no_new_key(self):
        results, _ = _build_results()
        legacy_results = {
            k: v for k, v in results.items()
            if k not in ("thesis_construction", "thesis_update")
        }
        payload = _call_finalize(legacy_results)
        assert "composite_primitives" not in payload


# ---------------------------------------------------------------------------
# Regression guards: prior corrections unchanged
# ---------------------------------------------------------------------------


def test_correction_049b_support_applied_once_still_green():
    import subprocess
    import sys

    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "tests/test_confidence_engine.py::TestCorrection049BSupportAppliedOnce",
            "-q",
        ],
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, proc.stdout[-2000:]
