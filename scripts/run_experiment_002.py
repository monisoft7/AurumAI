#!/usr/bin/env python3
"""EXP-002: Evidence Isolation Experiment.

Hypothesis
----------
When InferencePipeline runs with default parameters (reasoning_condition=None,
reasoning_horizon=None), EvidenceQuery.matching() returns ALL knowledge nodes.
EvidenceCollection.aggregate() then takes an unweighted mean across
heterogeneous conditions, collapsing directional signal into a single blended
number. Running the pipeline independently per unique condition reveals
condition-specific signals that cancel in the merged path.

Methodology
-----------
1. Baseline: Run InferencePipeline normally with CPI data.
   - condition_columns = ("cpi_pressure",)
   - reasoning_condition = None, reasoning_horizon = None (default)
   - Produces one merged Decision from all evidence.

2. Isolated: For each unique condition in the knowledge graph:
   - Query evidence for that condition only
   - Reason on filtered evidence
   - Decide on per-condition reasoning chain
   - Record the per-condition decision

3. Compare: Are per-condition decisions different from the merged decision?
   Quantify signal loss from aggregation.

Constraints
-----------
- No frozen core modifications.
- All components reused — none modified.
- Deterministic, measurable, comparable outputs.
"""

from __future__ import annotations

import json
import shutil
import sys
import time
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from knowledge.decision.context import DecisionContext
from knowledge.decision.engine import DecisionEngine
from knowledge.events.cpi import CPIEvent
from knowledge.evidence.query import EvidenceQuery
from knowledge.integrity.lineage import LineageRegistry
from knowledge.pipeline.context import PipelineContext
from knowledge.pipeline.pipeline import InferencePipeline
from knowledge.reasoning.context import ReasoningContext
from knowledge.reasoning.engine import ReasoningEngine

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

BASE_DIR = Path(__file__).resolve().parent.parent
CPI_PATH = BASE_DIR / "data/economic/CPIAUCSL.csv"
GOLD_PATH = BASE_DIR / "data/history/gold/gold.csv"
RELEASE_CALENDAR_PATH = "data/calendar/cpi_releases.csv"
OUT_ROOT = BASE_DIR / "data/experiments/EXP-002-Evidence-Isolation"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _pct(val: float | None) -> str:
    if val is None:
        return "N/A"
    return f"{val:+.4f}%"


def _val(val: Any) -> str:
    if val is None:
        return "N/A"
    return str(val)


def extract_unique_conditions(knowledge_records: list[dict]) -> list[dict[str, str]]:
    """Extract unique non-empty condition dicts from knowledge records, preserving order."""
    seen: set[tuple[tuple[str, str], ...]] = set()
    conditions: list[dict[str, str]] = []
    for r in knowledge_records:
        cond = r.get("condition", {})
        if not isinstance(cond, dict) or not cond:
            continue
        key = tuple(sorted(cond.items()))
        if key not in seen:
            seen.add(key)
            conditions.append(dict(cond))
    return conditions


def condition_label(cond: dict[str, str]) -> str:
    return "; ".join(f"{k}={v}" for k, v in cond.items())


# ---------------------------------------------------------------------------
# Experiment Runner
# ---------------------------------------------------------------------------

class EvidenceIsolationExperiment:
    """Execute EXP-002: compare merged vs per-condition decisions.

    Zero modifications to frozen core.  All components reused.
    """

    def __init__(self, output_dir: Path = OUT_ROOT):
        self._output_dir = output_dir
        self._artifacts_dir = output_dir / "artifacts"
        self._results: dict[str, Any] = {}

    def run(self) -> dict[str, Any]:
        t_start = time.perf_counter()

        # -- Baseline: merged pipeline ------------------------------------------
        baseline_result = self._run_baseline()

        # -- Isolated: per-condition pipeline ------------------------------------
        knowledge_records = baseline_result["knowledge_records"]
        graph = baseline_result["graph"]
        unique_conditions = extract_unique_conditions(knowledge_records)
        evidence_count_total = baseline_result["merged_evidence_count"]

        isolated_results = self._run_isolated(
            graph=graph,
            event_type="CPI",
            conditions=unique_conditions,
            min_evidence_count=1,
        )

        # -- Comparison ----------------------------------------------------------
        comparison = self._compute_comparison(
            baseline_result["merged_decision"],
            isolated_results,
            evidence_count_total,
        )

        elapsed = time.perf_counter() - t_start

        self._results = {
            "experiment": "EXP-002-Evidence-Isolation",
            "hypothesis": (
                "EvidenceCollection.aggregate() blends heterogeneous conditions, "
                "losing directional signal. Per-condition execution reveals "
                "condition-specific signals that cancel in the merged pipeline."
            ),
            "methodology": {
                "baseline": "InferencePipeline with reasoning_condition=None (merged/blended)",
                "isolated": "Per-condition evidence query, reason, decide (no aggregate cross-condition blend)",
            },
            "event_type": "CPI",
            "condition_columns": ["cpi_pressure"],
            "total_elapsed_seconds": round(elapsed, 3),
            "baseline": baseline_result["summary"],
            "isolated": {
                condition_label(cond): result
                for cond, result in zip(unique_conditions, isolated_results)
            },
            "comparison": comparison,
            "knowledge_records": len(knowledge_records),
            "conditions_found": len(unique_conditions),
        }

        self._save_artifacts()
        return self._results

    def _run_baseline(self) -> dict[str, Any]:
        """Run the standard InferencePipeline with merged evidence."""
        if self._artifacts_dir.exists():
            shutil.rmtree(self._artifacts_dir)
        self._artifacts_dir.mkdir(parents=True, exist_ok=True)

        ctx = PipelineContext(
            event=CPIEvent(),
            event_data_path=CPI_PATH,
            gold_path=GOLD_PATH,
            output_dir=self._artifacts_dir,
            knowledge_prefix="exp002_cpi_gold_v1",
            condition_columns=("cpi_pressure",),
            release_calendar_path=RELEASE_CALENDAR_PATH,
            asset="GOLD",
            query="Does CPI predict gold returns?",
        )

        pipeline = InferencePipeline()
        result = pipeline.run(ctx, lineage_registry=LineageRegistry())

        decision = result.decision
        knowledge = result.knowledge_summary or {}
        records = knowledge.get("records", [])
        graph = result.knowledge_graph
        evidence = result.evidence
        reasoning = result.reasoning_chain

        # Summary
        merged_decision = {
            "decision_id": decision.decision_id if decision else None,
            "decision_type": decision.decision_type if decision else "NO_DECISION",
            "confidence": decision.confidence if decision else 0.0,
            "evidence_count": decision.evidence_count if decision else 0,
            "explanation": decision.explanation if decision else "",
            "avg_return_pct": (
                decision.metadata.get("avg_return_pct", 0.0)
                if decision and decision.metadata
                else 0.0
            ),
        }

        return {
            "merged_decision": merged_decision,
            "merged_evidence_count": len(evidence) if evidence else 0,
            "knowledge_records": records,
            "knowledge_summary": knowledge,
            "graph": graph,
            "evidence": evidence,
            "reasoning_chain": reasoning,
            "decision": decision,
            "summary": {
                "decision_type": merged_decision["decision_type"],
                "confidence": merged_decision["confidence"],
                "evidence_count": merged_decision["evidence_count"],
                "avg_return_pct": merged_decision["avg_return_pct"],
                "knowledge_record_count": len(records),
            },
        }

    def _run_isolated(
        self,
        graph: Any,
        event_type: str,
        conditions: list[dict[str, str]],
        min_evidence_count: int = 1,
    ) -> list[dict[str, Any]]:
        """Run evidence→reason→decide independently for each condition."""
        query = EvidenceQuery(graph)
        reasoner = ReasoningEngine()
        decider = DecisionEngine()
        dctx = DecisionContext(event_type=event_type, query="")

        results = []
        for cond in conditions:
            evidence = query.matching(event_type=event_type, condition=cond)
            ev_count = len(evidence)

            if ev_count == 0:
                results.append({
                    "condition": dict(cond),
                    "decision": None,
                    "decision_type": "NO_EVIDENCE",
                    "confidence": 0.0,
                    "evidence_count": 0,
                    "avg_return_pct": 0.0,
                    "explanation": "No evidence matched this condition.",
                })
                continue

            rctx = ReasoningContext(event_type=event_type, condition=cond)
            chain = reasoner.reason(evidence, rctx)
            decision = decider.decide(chain, context=dctx, min_evidence_count=min_evidence_count)

            results.append({
                "condition": dict(cond),
                "decision_type": decision.decision_type,
                "confidence": decision.confidence,
                "evidence_count": decision.evidence_count,
                "avg_return_pct": (
                    decision.metadata.get("avg_return_pct", 0.0)
                    if decision.metadata else 0.0
                ),
                "explanation": decision.explanation,
            })

        return results

    def _compute_comparison(
        self,
        merged_decision: dict[str, Any],
        isolated_results: list[dict[str, Any]],
        evidence_count_total: int,
    ) -> dict[str, Any]:
        """Compare merged decision against per-condition decisions."""
        merged_type = merged_decision.get("decision_type", "N/A")

        per_condition = []
        for r in isolated_results:
            iso_type = r.get("decision_type", "N/A")
            matches = (iso_type == merged_type)
            per_condition.append({
                "condition": condition_label(r["condition"]),
                "decision_type": iso_type,
                "confidence": r.get("confidence", 0.0),
                "evidence_count": r.get("evidence_count", 0),
                "avg_return_pct": r.get("avg_return_pct", 0.0),
                "matches_baseline": matches,
            })

        conditions_matching = sum(1 for pc in per_condition if pc["matches_baseline"])
        total_conditions = len(per_condition)

        return {
            "merged_decision_type": merged_type,
            "merged_evidence_count": evidence_count_total,
            "per_condition": per_condition,
            "conditions_matching_baseline": conditions_matching,
            "total_conditions": total_conditions,
            "conditions_differing": total_conditions - conditions_matching,
        }

    def _save_artifacts(self) -> None:
        """Save experiment results and reports."""
        results_path = self._output_dir / "results.json"
        self._output_dir.mkdir(parents=True, exist_ok=True)
        results_path.write_text(
            json.dumps(self._results, indent=2, default=str),
            encoding="utf-8",
        )
        report_path = self._output_dir / "report.txt"
        report_path.write_text(self._build_report(), encoding="utf-8")

    def _build_report(self) -> str:
        """Build human-readable experiment report."""
        r = self._results
        lines: list[str] = []
        _w = lines.append

        _w("=" * 72)
        _w(f"  Experiment: {r['experiment']}")
        _w(f"  Hypothesis: {r['hypothesis']}")
        _w("=" * 72)

        # -- Baseline ---------------------------------------------------------
        b = r["baseline"]
        _w("")
        _w("  --- Baseline: Merged Pipeline ---")
        _w(f"  Decision type:       {b['decision_type']}")
        _w(f"  Confidence:          {b['confidence']:.4f}")
        _w(f"  Evidence count:      {b['evidence_count']}")
        _w(f"  Avg return (merged): {_pct(b['avg_return_pct'])}")
        _w(f"  Knowledge records:   {b['knowledge_record_count']}")

        # -- Isolated ---------------------------------------------------------
        _w("")
        _w("  --- Isolated: Per-Condition Pipeline ---")
        _w(f"  Conditions found:    {r['conditions_found']}")
        _w("")

        iso = r["isolated"]
        for cond_label, cond_result in iso.items():
            _w(f"  Condition: {cond_label}")
            _w(f"    Decision type:  {_val(cond_result.get('decision_type'))}")
            _w(f"    Confidence:     {cond_result.get('confidence', 0.0):.4f}")
            _w(f"    Evidence count: {cond_result.get('evidence_count', 0)}")
            _w(f"    Avg return:     {_pct(cond_result.get('avg_return_pct', 0.0))}")
            _w("")

        # -- Comparison --------------------------------------------------------
        c = r["comparison"]
        _w("  --- Comparison (Isolated vs Baseline) ---")
        _w(f"  Baseline decision type:           {c['merged_decision_type']}")
        _w(f"  Baseline evidence count:          {c['merged_evidence_count']}")
        _w("")
        _w(f"  {'Condition':<45} {'Decision':<18} {'Matches':<8} {'Return':<10}")
        _w(f"  {'-'*45} {'-'*18} {'-'*8} {'-'*10}")
        for pc in c["per_condition"]:
            _w(f"  {pc['condition']:<45} {pc['decision_type']:<18} {str(pc['matches_baseline']):<8} {_pct(pc['avg_return_pct']):<10}")
        _w("")
        _w(f"  Conditions matching baseline:  {c['conditions_matching_baseline']} / {c['total_conditions']}")
        _w(f"  Conditions differing:          {c['conditions_differing']} / {c['total_conditions']}")

        # -- Signal Loss Analysis ---------------------------------------------
        _w("")
        _w("  --- Signal Loss Analysis ---")
        if c["conditions_differing"] > 0:
            _w("  SIGNAL LOSS DETECTED: Aggregate() blends heterogeneous conditions,")
            _w("  producing a merged decision that does not match any per-condition")
            _w("  decision.  Directional signals cancel in the mean.")
        else:
            _w("  No signal loss detected — merged decision matches all per-condition")
            _w("  decisions.  Conditions are homogeneous or aggregate preserves signal.")

        _w("")
        _w("=" * 72)
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    exp = EvidenceIsolationExperiment()
    results = exp.run()
    print(exp._build_report())
    print(f"\nResults saved to: {OUT_ROOT / 'report.txt'}")
    print(f"JSON saved to:    {OUT_ROOT / 'results.json'}")
