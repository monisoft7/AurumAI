"""
Capability 13.1 — DXY Context Layer

Four-way comparison:
  A. CPI-only (baseline)
  B. CPI + US10Y
  C. CPI + DXY
  D. CPI + US10Y + DXY

Core v1.0 is frozen. DXY enrichment runs as a standalone step outside the
pipeline, using the same standalone pattern as YieldContextEnricher.
"""

import json, shutil, sys, time
from pathlib import Path

sys.path.insert(0, str(Path("src").resolve()))

from knowledge.events.cpi import CPIEvent
from knowledge.pipeline.context import PipelineContext
from knowledge.pipeline.pipeline import InferencePipeline
from knowledge.lesson_summary import LessonSummaryAggregator, LessonSummaryConfig
from knowledge.context.comparison import ContextComparisonConfig, ContextComparisonReport
from knowledge.context.dxy import DXYContextConfig, DXYContextEnricher
import pandas as pd

BASE = Path("data/output/dxy_capability")
if BASE.exists():
    shutil.rmtree(BASE)

CPI_PATH = Path("data/economic/CPIAUCSL.csv")
GOLD_PATH = Path("data/history/gold/gold.csv")
YIELD_PATH = Path("data/economic/DGS10.csv")
DXY_PATH = Path("data/context/dxy/dxy.csv")
HORIZONS = (1, 5, 20)

pipeline = InferencePipeline()

# =====================================================================
# HELPER: build knowledge from enriched lessons (standalone)
# =====================================================================
def build_knowledge(lessons_path: Path, output_path: Path,
                    condition_columns: tuple[str, ...],
                    prefix: str) -> dict:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    config = LessonSummaryConfig(
        lessons_path=lessons_path,
        output_path=output_path,
        condition_columns=condition_columns,
        knowledge_prefix=prefix,
        event_type="CPI",
        asset="GOLD",
        horizons=HORIZONS,
    )
    return LessonSummaryAggregator(config).build_and_save()


def build_comparison(baseline_path: Path, contextual_path: Path,
                     output_path: Path,
                     base_cols: tuple[str, ...],
                     context_cols: tuple[str, ...]) -> dict:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    config = ContextComparisonConfig(
        baseline_path=baseline_path,
        contextual_path=contextual_path,
        output_path=output_path,
        base_condition_columns=base_cols,
        context_condition_columns=context_cols,
    )
    return ContextComparisonReport(config).build_and_save()


# =====================================================================
# A. CPI-only baseline
# =====================================================================
print("=" * 65)
print("A. CPI-only BASELINE")
print("=" * 65)
out_a = BASE / "a_cpi_only"
t0 = time.perf_counter()
ctx_a = PipelineContext(
    event=CPIEvent(),
    event_data_path=CPI_PATH,
    gold_path=GOLD_PATH,
    output_dir=out_a / "artifacts",
    knowledge_prefix="cpi_baseline_v1",
    condition_columns=("cpi_pressure",),
    asset="GOLD",
)
r_a = pipeline.run(ctx_a)
elapsed_a = (time.perf_counter() - t0) * 1000
print(f"  Pipeline: {elapsed_a:.0f}ms")
print(f"  Lessons: {len(r_a.lessons['dataframe'])}")
print(f"  Knowledge: {r_a.knowledge_summary['record_count']} records")
print(f"  Decision: {r_a.decision.decision_type} (conf={r_a.decision.confidence:.4f})")
baseline_lessons_path = out_a / "artifacts" / "lessons.csv"
baseline_knowledge_path = out_a / "artifacts" / "knowledge.json"

# Save a clean copy for enrichment
clean_lessons = out_a / "lessons_clean.csv"
shutil.copy2(baseline_lessons_path, clean_lessons)

# =====================================================================
# B. CPI + US10Y (via InferencePipeline with yield_data_path)
# =====================================================================
print()
print("=" * 65)
print("B. CPI + US10Y")
print("=" * 65)
out_b = BASE / "b_cpi_us10y"
report_b_path = out_b / "context_comparison.json"
t0 = time.perf_counter()
ctx_b = PipelineContext(
    event=CPIEvent(),
    event_data_path=CPI_PATH,
    gold_path=GOLD_PATH,
    yield_data_path=YIELD_PATH,
    yield_context_lookback_days=30,
    output_dir=out_b / "artifacts",
    knowledge_prefix="cpi_us10y_v1",
    condition_columns=("cpi_pressure", "us10y_trend"),
    context_comparison_baseline_path=baseline_knowledge_path,
    context_comparison_output_path=report_b_path,
    context_comparison_base_columns=("cpi_pressure",),
    context_comparison_context_columns=("us10y_trend",),
    asset="GOLD",
)
r_b = pipeline.run(ctx_b)
elapsed_b = (time.perf_counter() - t0) * 1000
print(f"  Pipeline: {elapsed_b:.0f}ms")
print(f"  Knowledge: {r_b.knowledge_summary['record_count']} records")
us10y_lessons_path = out_b / "artifacts" / "lessons.csv"

# Save a clean copy with US10Y columns for further DXY enrichment
us10y_clean = out_b / "lessons_us10y.csv"
shutil.copy2(us10y_lessons_path, us10y_clean)

# =====================================================================
# C. CPI + DXY (standalone enrichment)
# =====================================================================
print()
print("=" * 65)
print("C. CPI + DXY")
print("=" * 65)
out_c = BASE / "c_cpi_dxy"
out_c.mkdir(parents=True, exist_ok=True)

dxy_enriched = out_c / "lessons_dxy.csv"
t0 = time.perf_counter()
DXYContextEnricher(
    DXYContextConfig(dxy_path=DXY_PATH)
).enrich_csv(clean_lessons, dxy_enriched)
elapsed_c1 = (time.perf_counter() - t0) * 1000

t0 = time.perf_counter()
knowledge_c = build_knowledge(
    dxy_enriched,
    out_c / "knowledge.json",
    condition_columns=("cpi_pressure", "dxy_trend"),
    prefix="cpi_dxy_v1",
)
elapsed_c2 = (time.perf_counter() - t0) * 1000

report_c_path = out_c / "context_comparison.json"
build_comparison(
    baseline_knowledge_path,
    out_c / "knowledge.json",
    report_c_path,
    base_cols=("cpi_pressure",),
    context_cols=("dxy_trend",),
)

print(f"  Enrich: {elapsed_c1:.0f}ms")
print(f"  Knowledge: {elapsed_c2:.0f}ms, {knowledge_c['record_count']} records")

# =====================================================================
# D. CPI + US10Y + DXY (chain: pipeline US10Y then standalone DXY)
# =====================================================================
print()
print("=" * 65)
print("D. CPI + US10Y + DXY")
print("=" * 65)
out_d = BASE / "d_cpi_us10y_dxy"
out_d.mkdir(parents=True, exist_ok=True)

# Enrich US10Y-enriched lessons further with DXY
us10y_dxy_enriched = out_d / "lessons_us10y_dxy.csv"
t0 = time.perf_counter()
DXYContextEnricher(
    DXYContextConfig(dxy_path=DXY_PATH)
).enrich_csv(us10y_clean, us10y_dxy_enriched)
elapsed_d1 = (time.perf_counter() - t0) * 1000

t0 = time.perf_counter()
knowledge_d = build_knowledge(
    us10y_dxy_enriched,
    out_d / "knowledge.json",
    condition_columns=("cpi_pressure", "us10y_trend", "dxy_trend"),
    prefix="cpi_us10y_dxy_v1",
)
elapsed_d2 = (time.perf_counter() - t0) * 1000

# Compare D vs A (CPI+US10Y+DXY vs CPI-only baseline)
report_d_vs_a = out_d / "comparison_vs_baseline.json"
build_comparison(
    baseline_knowledge_path,
    out_d / "knowledge.json",
    report_d_vs_a,
    base_cols=("cpi_pressure",),
    context_cols=("us10y_trend", "dxy_trend"),
)

# Compare D vs B (CPI+US10Y+DXY vs CPI+US10Y)
report_d_vs_b = out_d / "comparison_vs_us10y.json"
build_comparison(
    out_b / "artifacts" / "knowledge.json",
    out_d / "knowledge.json",
    report_d_vs_b,
    base_cols=("cpi_pressure", "us10y_trend"),
    context_cols=("dxy_trend",),
)

print(f"  Enrich: {elapsed_d1:.0f}ms")
print(f"  Knowledge: {elapsed_d2:.0f}ms, {knowledge_d['record_count']} records")

# =====================================================================
# SUMMARY TABLE
# =====================================================================
print()
print("=" * 65)
print("FOUR-WAY COMPARISON SUMMARY")
print("=" * 65)

def load_json(p):
    return json.loads(p.read_text())

def summarize_variant(label, rec_count, decision_type, decision_conf, knowledge_path):
    comp = knowledge_path.parent / "context_comparison.json"
    assess = ""
    if comp.exists():
        r = load_json(comp)
        assess = r["overall_assessment"]
    return f"{label:20s} | records={rec_count:2d} | decision={decision_type:8s} (conf={decision_conf:.4f}) | {assess}"

print(f"{'Variant':20s} | {'Records':8s} | {'Decision':30s} | {'Assessment'}")
print("-" * 90)
print(summarize_variant("CPI-only", r_a.knowledge_summary["record_count"],
      r_a.decision.decision_type, r_a.decision.confidence, baseline_knowledge_path))
print(summarize_variant("CPI+US10Y", r_b.knowledge_summary["record_count"],
      r_b.decision.decision_type, r_b.decision.confidence, out_b / "artifacts" / "knowledge.json"))
print(summarize_variant("CPI+DXY", knowledge_c["record_count"],
      r_a.decision.decision_type, r_a.decision.confidence, out_c / "knowledge.json"))
print(summarize_variant("CPI+US10Y+DXY", knowledge_d["record_count"],
      r_a.decision.decision_type, r_a.decision.confidence, out_d / "knowledge.json"))

# =====================================================================
# CONTEXT CONTRIBUTION
# =====================================================================
print()
print("=" * 65)
print("CONTEXT CONTRIBUTION ANALYSIS")
print("=" * 65)

for label, report_path in [
    ("US10Y vs CPI-only", report_b_path),
    ("DXY vs CPI-only", report_c_path),
    ("US10Y+DXY vs CPI-only", report_d_vs_a),
    ("DXY added to US10Y", report_d_vs_b),
]:
    r = load_json(report_path)
    print(f"\n{label}:")
    print(f"  Overall: {r['overall_assessment']}")
    print(f"  Decisions: {r['decision_counts']}")
    print(f"  Records compared: {r['comparison_count']}")

# =====================================================================
# DECISION CONSISTENCY
# =====================================================================
print()
print("=" * 65)
print("DECISION CONSISTENCY ACROSS VARIANTS")
print("=" * 65)

# For standalone variants (C, D), we use the same baseline decision
# since the standalone flow doesn't re-run the decision engine
print(f"  CPI-only (A):     {r_a.decision.decision_type} (conf={r_a.decision.confidence:.4f})")
print(f"  CPI+US10Y (B):    {r_b.decision.decision_type} (conf={r_b.decision.confidence:.4f})")
print(f"  CPI+DXY (C):      {r_a.decision.decision_type} (conf={r_a.decision.confidence:.4f}) — decision from baseline (standalone)")
print(f"  CPI+US10Y+DXY (D): {r_a.decision.decision_type} (conf={r_a.decision.confidence:.4f}) — decision from baseline (standalone)")

# =====================================================================
# EXPLAINABILITY SAMPLES
# =====================================================================
print()
print("=" * 65)
print("EXPLAINABILITY SAMPLES")
print("=" * 65)

for label, kp in [
    ("CPI-only", baseline_knowledge_path),
    ("CPI+US10Y", out_b / "artifacts" / "knowledge.json"),
    ("CPI+DXY", out_c / "knowledge.json"),
    ("CPI+US10Y+DXY", out_d / "knowledge.json"),
]:
    records = load_json(kp)["records"]
    if records:
        sample = records[0]
        print(f"\n{label} — {sample['knowledge_id']}:")
        print(f"  Condition: {sample['condition']}")
        print(f"  n={sample['sample_count']}, conf={sample['confidence']:.4f}, bias={sample['bias']}")
        print(f"  avg_ret={sample['average_return_pct']:.4f}%")

print()
print(f"All artifacts saved to: {BASE}")
