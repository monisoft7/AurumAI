"""EXP-003 — Condition Filtering Validation.

Compares inference with reasoning_condition active (Run A) vs
disabled/None (Run B) to measure the material impact of
condition-aware evidence retrieval.

Usage:
    python scripts/run_experiment_003.py
"""

import json
import shutil
from pathlib import Path

import pandas as pd

from knowledge.events.cpi import CPIEvent
from knowledge.pipeline.context import PipelineContext
from knowledge.pipeline.pipeline import InferencePipeline
from knowledge.pipeline.repository import PipelineRepository
from knowledge.pipeline.result import PipelineResult
from knowledge.decision.decision import DECISION_INSUFFICIENT_EVIDENCE


def _gold_rows() -> list[dict]:
    rows = []
    price = 1000.0
    for i in range(60):
        d = pd.Timestamp("2020-01-31") + pd.Timedelta(days=i)
        if d.weekday() >= 5:
            continue
        rows.append({"Date": d.date().isoformat(), "Close": price})
        price += 10.0
    return rows


def _cpi_rows() -> list[dict]:
    return [
        {"Date": "2020-01-01", "Value": 100.0},
        {"Date": "2020-02-01", "Value": 101.0},
        {"Date": "2020-03-01", "Value": 99.0},
        {"Date": "2020-04-01", "Value": 102.0},
    ]


def _write_csv(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(path, index=False)


def _write_calendar(base_path: Path) -> str:
    cal_dir = base_path / "calendar"
    cal_dir.mkdir(parents=True, exist_ok=True)
    cal_path = cal_dir / "cpi_releases.csv"
    pd.DataFrame([
        {"reference_period": "2020-01-01", "release_date": "2020-01-14", "release_time": "08:30", "timezone": "US/Eastern"},
        {"reference_period": "2020-02-01", "release_date": "2020-02-01", "release_time": "08:30", "timezone": "US/Eastern"},
        {"reference_period": "2020-03-01", "release_date": "2020-03-02", "release_time": "08:30", "timezone": "US/Eastern"},
        {"reference_period": "2020-04-01", "release_date": "2020-04-01", "release_time": "08:30", "timezone": "US/Eastern"},
    ]).to_csv(cal_path, index=False)
    return str(cal_path)


def _build_condition(event: CPIEvent, data_path: Path) -> dict[str, str]:
    extracted = event.load_and_extract(data_path)
    return event.build_reasoning_condition(extracted.iloc[-1])


def _run_pipeline(
    condition: dict[str, str] | None,
    event_path: Path,
    gold_path: Path,
    cal_path: str,
    output_dir: Path,
    tag: str,
) -> PipelineResult:
    ctx = PipelineContext(
        event=CPIEvent(),
        event_data_path=event_path,
        gold_path=gold_path,
        output_dir=output_dir,
        knowledge_prefix="cpi_gold_summary_v1",
        condition_columns=("cpi_pressure",),
        asset="XAU/USD",
        query="gold outlook after CPI",
        release_calendar_path=cal_path,
        reasoning_condition=condition,
    )
    result = InferencePipeline().run(ctx)
    return result


def _extract_evidence_summary(result: PipelineResult) -> dict:
    evidence = result.evidence
    if evidence is None or len(evidence) == 0:
        return {"count": 0, "ids": [], "avg_return_pct": None, "avg_confidence": None}
    agg = evidence.aggregate()
    return {
        "count": agg["count"],
        "ids": sorted(e.evidence_id for e in evidence),
        "avg_return_pct": agg["avg_return_pct"],
        "avg_confidence": agg["avg_confidence"],
    }


def _extract_decision_summary(result: PipelineResult) -> dict:
    decision = result.decision
    if decision is None:
        return {
            "decision_type": None,
            "confidence": None,
            "is_insufficient_evidence": None,
        }
    return {
        "decision_type": decision.decision_type,
        "confidence": decision.confidence,
        "is_insufficient_evidence": decision.decision_type == DECISION_INSUFFICIENT_EVIDENCE,
    }


def _extract_reasoning_summary(result: PipelineResult) -> dict:
    chain = result.reasoning_chain
    if chain is None:
        return {"conclusion": None, "step_count": 0, "overall_confidence": None}
    return {
        "conclusion": chain.final_conclusion,
        "step_count": len(chain.steps),
        "overall_confidence": chain.overall_confidence,
    }


def _extract_graph_summary(result: PipelineResult) -> dict:
    graph = result.knowledge_graph
    if graph is None:
        return {"node_count": 0}
    node_conditions = set()
    for node_id in graph._graph.nodes:
        node = graph.get_node(node_id)
        if node is not None:
            cond = node.properties.get("condition")
            if isinstance(cond, dict):
                node_conditions.add(tuple(sorted(cond.items())))
    return {
        "node_count": graph.node_count,
        "unique_condition_values": sorted(
            list({v for c in node_conditions for v in c})
        ),
    }


def main() -> None:
    base_dir = Path("data/experiments/EXP-003-Condition-Filtering-Validation")
    if base_dir.exists():
        shutil.rmtree(base_dir)
    base_dir.mkdir(parents=True)

    # -- data setup -----------------------------------------------------------
    event_path = base_dir / "cpi.csv"
    gold_path = base_dir / "gold.csv"
    _write_csv(event_path, _cpi_rows())
    _write_csv(gold_path, _gold_rows())
    cal_path = _write_calendar(base_dir)

    # -- compute the canonical condition (same logic as PIP-2) ---------------
    event = CPIEvent()
    condition = _build_condition(event, event_path)
    print(f"Canonical reasoning condition (from last row): {condition}")
    print()

    # -- Run A: reasoning_condition active -----------------------------------
    out_a = base_dir / "output_a"
    result_a = _run_pipeline(condition, event_path, gold_path, cal_path, out_a, "A")
    summary_a_ev = _extract_evidence_summary(result_a)
    summary_a_dec = _extract_decision_summary(result_a)
    summary_a_reas = _extract_reasoning_summary(result_a)
    summary_a_graph = _extract_graph_summary(result_a)

    # -- Run B: reasoning_condition forced to None ----------------------------
    out_b = base_dir / "output_b"
    result_b = _run_pipeline(None, event_path, gold_path, cal_path, out_b, "B")
    summary_b_ev = _extract_evidence_summary(result_b)
    summary_b_dec = _extract_decision_summary(result_b)
    summary_b_reas = _extract_reasoning_summary(result_b)
    summary_b_graph = _extract_graph_summary(result_b)

    # -- side-by-side report --------------------------------------------------
    lines = []
    lines.append("=" * 78)
    lines.append("EXP-003  CONDITION FILTERING VALIDATION")
    lines.append("=" * 78)
    lines.append("")
    lines.append(f"CPI data:            {_cpi_rows()}")
    lines.append(f"Reasoning condition: {condition}")
    lines.append("")

    # Graph context
    lines.append("--- Knowledge Graph (same for both runs) ---")
    lines.append(f"  Nodes:               {summary_a_graph['node_count']}")
    lines.append(f"  Unique conditions:   {summary_a_graph['unique_condition_values']}")
    lines.append("")

    # Evidence comparison
    lines.append("--- Evidence ---")
    lines.append(f"{'Metric':<35} {'Run A (condition active)':<25} {'Run B (condition=None)':<25}")
    lines.append("-" * 85)
    lines.append(f"{'Evidence count':<35} {summary_a_ev['count']:<25} {summary_b_ev['count']:<25}")
    lines.append(f"{'Evidence IDs':<35} {str(summary_a_ev['ids']):<25} {str(summary_b_ev['ids']):<25}")
    lines.append(f"{'Avg return %':<35} {summary_a_ev['avg_return_pct']:<25} {summary_b_ev['avg_return_pct']:<25}")
    lines.append(f"{'Avg confidence':<35} {summary_a_ev['avg_confidence']:<25} {summary_b_ev['avg_confidence']:<25}")
    lines.append("")

    # Reasoning comparison
    lines.append("--- Reasoning ---")
    lines.append(f"{'Metric':<35} {'Run A (condition active)':<25} {'Run B (condition=None)':<25}")
    lines.append("-" * 85)
    lines.append(f"{'Step count':<35} {summary_a_reas['step_count']:<25} {summary_b_reas['step_count']:<25}")
    lines.append(f"{'Overall confidence':<35} {summary_a_reas['overall_confidence']:<25} {summary_b_reas['overall_confidence']:<25}")
    lines.append("")
    lines.append("Conclusion A:")
    lines.append(f"  {summary_a_reas['conclusion']}")
    lines.append("")
    lines.append("Conclusion B:")
    lines.append(f"  {summary_b_reas['conclusion']}")
    lines.append("")

    # Decision comparison
    lines.append("--- Decision ---")
    lines.append(f"{'Metric':<35} {'Run A (condition active)':<25} {'Run B (condition=None)':<25}")
    lines.append("-" * 85)
    lines.append(f"{'Decision type':<35} {summary_a_dec['decision_type']:<25} {summary_b_dec['decision_type']:<25}")
    lines.append(f"{'Confidence':<35} {summary_a_dec['confidence']:<25} {summary_b_dec['confidence']:<25}")
    lines.append(f"{'Insufficient evidence':<35} {summary_a_dec['is_insufficient_evidence']:<25} {summary_b_dec['is_insufficient_evidence']:<25}")
    lines.append("")

    # Verdict
    ev_diff = summary_a_ev["count"] != summary_b_ev["count"]
    dec_diff = summary_a_dec["decision_type"] != summary_b_dec["decision_type"]
    ret_diff = summary_a_ev["avg_return_pct"] != summary_b_ev["avg_return_pct"]

    lines.append("--- Verdict ---")
    if ev_diff:
        lines.append("  EVIDENCE SET CHANGED: condition filtering removed "
                      f"{summary_b_ev['count'] - summary_a_ev['count']} item(s)")
    else:
        lines.append("  EVIDENCE SET UNCHANGED")
    if ret_diff:
        lines.append("  AVERAGE RETURN CHANGED: filtering shifted aggregate return")
    else:
        lines.append("  AVERAGE RETURN UNCHANGED")
    if dec_diff:
        lines.append("  DECISION CHANGED: condition filtering altered the final decision")
    else:
        lines.append("  DECISION UNCHANGED")
    lines.append("")

    report_text = "\n".join(lines)
    print(report_text)

    # save report
    report_path = base_dir / "report.txt"
    report_path.write_text(report_text)

    # save structured results
    results = {
        "reasoning_condition": condition,
        "run_a": {
            "evidence": summary_a_ev,
            "decision": summary_a_dec,
            "reasoning": summary_a_reas,
            "graph": summary_a_graph,
        },
        "run_b": {
            "evidence": summary_b_ev,
            "decision": summary_b_dec,
            "reasoning": summary_b_reas,
            "graph": summary_b_graph,
        },
    }
    results_path = base_dir / "results.json"
    results_path.write_text(json.dumps(results, indent=2, default=str))
    print(f"Report saved to: {report_path}")
    print(f"Results saved to: {results_path}")


if __name__ == "__main__":
    main()
