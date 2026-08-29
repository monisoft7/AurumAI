"""Run-003 aggregate -- computes the frozen evaluation-contract metrics from
the pass results and compares with the Run-002 baseline artifact.

Scoring replicates the FROZEN ``src/simulation`` evaluation semantics
(dead zone 0.10, HOLD scored as FLAT, NO_TRADE abstains, 5-bin ECE)
as local pure functions: the validation package must not import
``simulation`` (historical-validation boundary contract).

Outputs: historical_validation/run003/aggregate_summary.json
Run-002 artifacts are read ONLY as immutable comparison inputs.
Writes: none outside historical_validation/run003/.
"""

from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

RUN003_DIR = Path(__file__).resolve().parent / "run003"
RUN002_AGGREGATE = Path(__file__).resolve().parent / "run002" / "aggregate_summary.json"

VARIANTS = ("FULL_TECH", "NO_HISTORY_TECH", "FULL_NO_TECH")
DECISION_TO_DIRECTION = {
    "BUY": "POSITIVE",
    "SELL": "NEGATIVE",
    "HOLD": "NEUTRAL",
}
HORIZONS = ("1d", "5d", "20d")

DEAD_ZONE = 0.10


def _classify_actual_direction(
    actual_return_pct: float, dead_zone: float = DEAD_ZONE
) -> str:
    """Frozen semantics: UP (>dead_zone), DOWN (<-dead_zone), else FLAT."""
    if actual_return_pct > dead_zone:
        return "UP"
    if actual_return_pct < -dead_zone:
        return "DOWN"
    return "FLAT"


def _decision_is_correct(
    decision: str, actual_direction: str
) -> bool | None:
    """Frozen semantics: directional bets vs UP/DOWN, HOLD vs FLAT,
    NO_TRADE/INSUFFICIENT_EVIDENCE abstain (None)."""
    decision_upper = decision.upper()
    if decision_upper in ("INSUFFICIENT_EVIDENCE", "NO_TRADE"):
        return None
    if decision_upper in ("POSITIVE", "STRONG_POSITIVE", "BUY"):
        return actual_direction == "UP"
    if decision_upper in ("NEGATIVE", "STRONG_NEGATIVE", "SELL"):
        return actual_direction == "DOWN"
    if decision_upper in ("NEUTRAL", "HOLD"):
        return actual_direction == "FLAT"
    return None


def _ece(scored: list[dict], n_bins: int = 5) -> float | None:
    """Frozen 5-bin equal-width ECE over the scored events."""
    confidences = [s["confidence"] for s in scored]
    corrects = [s["correct"] is True for s in scored]
    n = len(confidences)
    if n == 0:
        return None
    bin_edges = [i / n_bins for i in range(n_bins + 1)]
    bin_edges[-1] = 1.0 + 1e-9
    ece_value = 0.0
    for b in range(n_bins):
        lo, hi = bin_edges[b], bin_edges[b + 1]
        mask = [lo <= c < hi for c in confidences]
        bin_size = sum(mask)
        if bin_size == 0:
            continue
        bin_correct = sum(c for c, m in zip(corrects, mask) if m)
        bin_accuracy = bin_correct / bin_size
        bin_conf = sum(c for c, m in zip(confidences, mask) if m) / bin_size
        ece_value += (bin_size / n) * abs(bin_accuracy - bin_conf)
    return ece_value


def _load_results(pass_id: int) -> list[dict]:
    path = RUN003_DIR / f"run003_pass{pass_id}_results.jsonl"
    records = []
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records


def _score_variant(records: list[dict], variant: str, horizon: str) -> dict:
    scored = []
    decisions = Counter()
    confidences = []
    support_by_dir_acc = []
    for rec in records:
        if rec.get("status") != "ok":
            continue
        variant_data = rec[variant]
        decision = variant_data["decision"]
        confidence = variant_data.get("institutional_confidence")
        decisions[decision] += 1
        if confidence is not None:
            confidences.append(float(confidence))
        outcome = rec["gold_outcomes"][horizon]
        actual = _classify_actual_direction(float(outcome["return_pct"]))
        correct = _decision_is_correct(decision, actual)
        if correct is not None:
            scored.append(
                {"decision": decision, "confidence": float(confidence or 0.0),
                 "correct": correct}
            )
    n_scored = len(scored)
    correct = sum(1 for s in scored if s["correct"])
    per_class: dict[str, dict] = {}
    for label in ("BUY", "SELL", "HOLD"):
        cls = [s for s in scored if s["decision"] == label]
        per_class[label] = {
            "n": len(cls),
            "accuracy": round(sum(1 for s in cls if s["correct"]) / len(cls), 6)
            if cls else None,
        }
    return {
        "decisions": dict(decisions),
        "scored_events": n_scored,
        "abstentions": sum(
            1 for rec in records if rec.get("status") == "ok"
        ) - n_scored,
        "accuracy": round(correct / n_scored, 6) if n_scored else None,
        "per_decision_class": per_class,
        "ece": round(_ece(scored), 6) if n_scored else None,
        "mean_confidence": round(sum(confidences) / len(confidences), 6)
        if confidences else None,
    }


def _leaf_delta(a: dict, b: dict) -> int:
    la = a.get("numeric_leaves") or {}
    lb = b.get("numeric_leaves") or {}
    keys = set(la) | set(lb)
    return sum(1 for k in keys if la.get(k) != lb.get(k))


def _memory_effect(records: list[dict]) -> dict:
    decision_changes = 0
    numeric_delta_cases = 0
    confidence_changes = 0
    for rec in records:
        if rec.get("status") != "ok":
            continue
        full = rec["FULL_TECH"]
        nohist = rec["NO_HISTORY_TECH"]
        if full["decision"] != nohist["decision"]:
            decision_changes += 1
        if full.get("institutional_confidence") != nohist.get(
            "institutional_confidence"
        ):
            confidence_changes += 1
        if _leaf_delta(full, nohist) > 0:
            numeric_delta_cases += 1
    return {
        "decision_changes_full_vs_no_history": decision_changes,
        "confidence_changes_full_vs_no_history": confidence_changes,
        "numeric_delta_cases": numeric_delta_cases,
        "memory_bias_scan": _load_memory_bias_scan(),
    }


def _load_memory_bias_scan() -> dict | None:
    scan_path = RUN003_DIR / "memory_bias_scan.json"
    if scan_path.is_file():
        data = json.loads(scan_path.read_text(encoding="utf-8"))
        return {
            "cases": data.get("cases"),
            "directional": data.get("directional"),
            "uninformative": data.get("uninformative"),
            "mean_base_confidence": data.get("mean_base_confidence"),
        }
    return None


def _technical_effect(records: list[dict]) -> dict:
    decision_changes = 0
    numeric_delta_cases = 0
    technical_emitted = 0
    for rec in records:
        if rec.get("status") != "ok":
            continue
        full = rec["FULL_TECH"]
        notech = rec["FULL_NO_TECH"]
        if full["decision"] != notech["decision"]:
            decision_changes += 1
        if _leaf_delta(full, notech) > 0:
            numeric_delta_cases += 1
        emitted = (full.get("technical_summary") or {}).get("trend_direction")
        tech_summary = full.get("evidence_summary", {}).get("technical_desk", {})
        if tech_summary.get("evidence_emitted"):
            technical_emitted += 1
    return {
        "decision_changes_full_vs_no_tech": decision_changes,
        "numeric_delta_cases": numeric_delta_cases,
        "technical_evidence_emitted_cases": technical_emitted,
    }


def _determinism(pass1: list[dict], pass2: list[dict]) -> dict:
    by_id_1 = {r["lesson_id"]: r for r in pass1 if r.get("status") == "ok"}
    by_id_2 = {r["lesson_id"]: r for r in pass2 if r.get("status") == "ok"}
    assert set(by_id_1) == set(by_id_2), "pass coverage mismatch"
    findings = []
    for lid in sorted(by_id_1):
        r1, r2 = by_id_1[lid], by_id_2[lid]
        for variant in VARIANTS:
            if r1[variant]["decision"] != r2[variant]["decision"]:
                findings.append(f"{lid}/{variant}: decision")
            la = r1[variant].get("numeric_leaves") or {}
            lb = r2[variant].get("numeric_leaves") or {}
            if la != lb:
                findings.append(f"{lid}/{variant}: numeric leaves")
    return {
        "cases_compared": len(by_id_1),
        "variants_per_case": len(VARIANTS),
        "findings": findings[:50],
        "finding_count": len(findings),
        "status": "PASS" if not findings else "FAIL",
    }


def _run002_baseline() -> dict:
    if not RUN002_AGGREGATE.is_file():
        return {"available": False}
    data = json.loads(RUN002_AGGREGATE.read_text(encoding="utf-8"))
    return {
        "available": True,
        "decisions": data.get("decision_distribution"),
        "accuracy_1d": data.get("scored_accuracy", {}).get("1d")
        if isinstance(data.get("scored_accuracy"), dict) else None,
        "ece_1d": data.get("ece", {}).get("1d")
        if isinstance(data.get("ece"), dict) else None,
        "raw": {k: data[k] for k in list(data)[:0]},
    }


def main() -> None:
    pass1 = _load_results(1)
    pass2 = _load_results(2)
    ok1 = [r for r in pass1 if r.get("status") == "ok"]
    failed1 = [r for r in pass1 if r.get("status") != "ok"]
    lookahead_failures = []
    for r in pass1:
        for variant in VARIANTS:
            v = r.get(variant) or {}
            for group in (
                "no_lookahead_checks", "payload_lookahead_checks",
                "briefing_asof_checks", "market_context_checks",
                "technical_checks",
            ):
                checks = v.get(group) or {}
                for name, ok in checks.items():
                    if not ok:
                        lookahead_failures.append(
                            f"{r['lesson_id']}/{variant}/{group}/{name}"
                        )

    summary = {
        "cases": {
            "total": len(pass1),
            "ok": len(ok1),
            "failed": len(failed1),
        },
        "no_lookahead": {
            "violations": lookahead_failures,
            "status": "PASS" if not lookahead_failures else "FAIL",
        },
        "determinism": _determinism(pass1, pass2),
        "variants": {
            variant: {
                horizon: _score_variant(ok1, variant, horizon)
                for horizon in HORIZONS
            }
            for variant in VARIANTS
        },
        "memory_effect": _memory_effect(ok1),
        "technical_effect": _technical_effect(ok1),
        "run002_baseline": _run002_baseline(),
        "regime_breakdown": {},
    }
    # Regime-conditional 1d accuracy per variant.
    for variant in VARIANTS:
        by_regime: dict[str, list] = {}
        for rec in ok1:
            regime = rec["snapshot_summary"]["institutional_regime"]
            by_regime.setdefault(regime, []).append(rec)
        out = {}
        for regime, recs in sorted(by_regime.items()):
            scored = _score_variant(recs, variant, "1d")
            out[regime] = {
                "n": len(recs),
                "accuracy_1d": scored["accuracy"],
                "decisions": scored["decisions"],
            }
        summary["regime_breakdown"][variant] = out

    out_path = RUN003_DIR / "aggregate_summary.json"
    out_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps({
        "cases": summary["cases"],
        "no_lookahead": summary["no_lookahead"]["status"],
        "determinism": summary["determinism"]["status"],
        "FULL_TECH_1d": summary["variants"]["FULL_TECH"]["1d"],
        "memory_effect": summary["memory_effect"],
        "technical_effect": summary["technical_effect"],
    }, indent=2))


if __name__ == "__main__":
    main()
