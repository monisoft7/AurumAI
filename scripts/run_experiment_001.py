#!/usr/bin/env python3
"""Institutional Experiment 001: CPI baseline vs CPI + US10Y candidate."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from simulation.experiment import (
    ExperimentConfig,
    ExperimentReportBuilder,
    ExperimentRunner,
    RunConfig,
)
from simulation.experiment_registry import ExperimentRegistry

DATA_DIR = Path("data")
GOLD_PATH = DATA_DIR / "history" / "gold" / "gold.csv"
US10Y_PATH = DATA_DIR / "economic" / "DGS10.csv"
CHECKPOINT_DIR = None
CUTOFF_DATE = "2024-01-01"
GIT_COMMIT = "4dc7d030f57038e59bbe28b72e66f4959a3cc53c"

baseline_cfg = RunConfig(
    name="CPI",
    horizon=12,
    max_workers=4,
    yield_data_path=None,
)

candidate_cfg = RunConfig(
    name="CPI+US10Y",
    horizon=12,
    max_workers=4,
    yield_data_path=str(US10Y_PATH),
)

experiment_cfg = ExperimentConfig(
    experiment_name="EXP-001-CPI-vs-CPI-US10Y",
    cutoff_date=CUTOFF_DATE,
    baseline=baseline_cfg,
    candidate=candidate_cfg,
    description="Institutional Experiment 001: Compare CPI-only baseline against CPI+US10Y context enrichment for gold directional decisions.",
)

runner = ExperimentRunner(
    config=experiment_cfg,
    data_dir=DATA_DIR,
    gold_path=GOLD_PATH,
    checkpoint_dir=CHECKPOINT_DIR,
)

print("=" * 72)
print("  Institutional Experiment 001")
print("  Baseline:  CPI")
print("  Candidate: CPI + US10Y")
print("  Cutoff:    ", CUTOFF_DATE)
print("=" * 72)
print()

result = runner.run()

registry = ExperimentRegistry()
record = registry.register(
    result=result,
    git_commit=GIT_COMMIT,
    tags=("cpi", "us10y", "context-enrichment", "experiment-001"),
)

report = ExperimentReportBuilder.build(result)
print(report.human_text)

print()
print("  --- Registry ---")
print(f"  Experiment ID: {record.experiment_id}")
print(f"  Registry path: {registry._path}")
print()

bs = result.baseline_result.summary
cs = result.candidate_result.summary
comp = result.comparison

print("  --- Scientific Summary ---")
print(f"  Baseline directional accuracy:   {bs.directional_accuracy:.4f}" if bs and bs.directional_accuracy is not None else "  Baseline directional accuracy:   N/A")
print(f"  Candidate directional accuracy:  {cs.directional_accuracy:.4f}" if cs and cs.directional_accuracy is not None else "  Candidate directional accuracy:  N/A")
if comp:
    print(f"  Directional accuracy Δ:         {comp.directional_accuracy_delta:+.4f}" if comp.directional_accuracy_delta is not None else "  Directional accuracy Δ:         N/A")
    print(f"  Macro precision Δ:              {comp.macro_precision_delta:+.4f}" if comp.macro_precision_delta is not None else "  Macro precision Δ:              N/A")
    print(f"  Macro recall Δ:                 {comp.macro_recall_delta:+.4f}" if comp.macro_recall_delta is not None else "  Macro recall Δ:                 N/A")
    print(f"  Coverage Δ:                     {comp.coverage_delta:+.4f}" if comp.coverage_delta is not None else "  Coverage Δ:                     N/A")
    print(f"  Abstention rate Δ:              {comp.abstention_rate_delta:+.4f}" if comp.abstention_rate_delta is not None else "  Abstention rate Δ:              N/A")
    print(f"  Strong error rate Δ:            {comp.strong_error_rate_delta:+.4f}" if comp.strong_error_rate_delta is not None else "  Strong error rate Δ:            N/A")
    print(f"  ECE Δ:                          {comp.ece_delta:+.4f}" if comp.ece_delta is not None else "  ECE Δ:                          N/A")
    print(f"  Decisions changed:              {comp.total_decisions_changed}")
    print(f"  Decisions improved:             {comp.total_decisions_improved}")
    print(f"  Decisions degraded:             {comp.total_decisions_degraded}")
print()
