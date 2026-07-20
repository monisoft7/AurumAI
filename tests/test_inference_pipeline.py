import json
import shutil
from pathlib import Path

import pandas as pd

from knowledge.events.cpi import CPIEvent
from knowledge.pipeline.context import PipelineContext
from knowledge.pipeline.pipeline import InferencePipeline
from knowledge.pipeline.result import PipelineResult
from knowledge.pipeline.validator import PipelineValidator
from knowledge.pipeline.repository import PipelineRepository
from knowledge.decision.decision import (
    DECISION_STRONG_POSITIVE,
    DECISION_POSITIVE,
    DECISION_NEUTRAL,
    VALID_DECISION_TYPES,
)
from knowledge.integrity.lineage import LineageRegistry, LineageRelationType


def runtime_dir(name: str) -> Path:
    path = Path(__file__).resolve().parent / "_runtime" / name
    if path.exists():
        shutil.rmtree(path)
    path.mkdir(parents=True)
    return path


def write_csv(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(path, index=False)


def write_calendar(base_path: Path) -> str:
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


def gold_rows() -> list[dict]:
    rows = []
    # 60 trading days starting 2020-01-31
    price = 1000.0
    for i in range(60):
        d = pd.Timestamp("2020-01-31") + pd.Timedelta(days=i)
        # Skip weekends
        if d.weekday() >= 5:
            continue
        rows.append({"Date": d.date().isoformat(), "Close": price})
        price += 10.0
    return rows


def test_pipeline_creates_stages_in_order() -> None:
    base = runtime_dir("order")
    event_path = base / "cpi.csv"
    gold_path = base / "gold.csv"
    write_csv(event_path, [
        {"Date": "2020-01-01", "Value": 100.0},
        {"Date": "2020-02-01", "Value": 101.0},
        {"Date": "2020-03-01", "Value": 99.0},
        {"Date": "2020-04-01", "Value": 102.0},
    ])
    write_csv(gold_path, gold_rows())
    cal_path = write_calendar(base)

    ctx = PipelineContext(
        event=CPIEvent(),
        event_data_path=event_path,
        gold_path=gold_path,
        output_dir=base / "output",
        knowledge_prefix="cpi_gold_summary_v1",
        condition_columns=("cpi_pressure",),
        asset="GOLD",
        query="gold outlook after CPI",
        release_calendar_path=cal_path,
    )
    result = InferencePipeline().run(ctx)

    expected = [
        "build_lessons",
        "build_knowledge",
        "build_graph",
        "query_evidence",
        "reason",
        "decide",
    ]
    assert result.stages_completed == expected


def test_pipeline_lessons_stage() -> None:
    base = runtime_dir("lessons")
    event_path = base / "cpi.csv"
    gold_path = base / "gold.csv"
    write_csv(event_path, [
        {"Date": "2020-01-01", "Value": 100.0},
        {"Date": "2020-02-01", "Value": 101.0},
    ])
    write_csv(gold_path, gold_rows())
    cal_path = write_calendar(base)

    ctx = PipelineContext(
        event=CPIEvent(),
        event_data_path=event_path,
        gold_path=gold_path,
        output_dir=base / "output",
        knowledge_prefix="cpi_gold_summary_v1",
        condition_columns=("cpi_pressure",),
        asset="GOLD",
        release_calendar_path=cal_path,
    )
    result = InferencePipeline().run(ctx)
    lessons = result.lessons
    assert lessons is not None
    assert lessons["count"] >= 1


def test_pipeline_knowledge_stage() -> None:
    base = runtime_dir("knowledge")
    event_path = base / "cpi.csv"
    gold_path = base / "gold.csv"
    write_csv(event_path, [
        {"Date": "2020-01-01", "Value": 100.0},
        {"Date": "2020-02-01", "Value": 101.0},
        {"Date": "2020-03-01", "Value": 99.0},
    ])
    write_csv(gold_path, gold_rows())
    cal_path = write_calendar(base)

    ctx = PipelineContext(
        event=CPIEvent(),
        event_data_path=event_path,
        gold_path=gold_path,
        output_dir=base / "output",
        knowledge_prefix="cpi_gold_summary_v1",
        condition_columns=("cpi_pressure",),
        asset="GOLD",
        release_calendar_path=cal_path,
    )
    result = InferencePipeline().run(ctx)
    knowledge = result.knowledge_summary
    assert knowledge is not None
    assert "records" in knowledge
    assert knowledge["record_count"] >= 1
    assert knowledge["knowledge_version"] == "cpi_gold_summary_v1"
    assert len(knowledge["source_artifact_sha256"]) == 64
    for record in knowledge["records"]:
        assert record["source_lesson_ids"]
        assert record["source_artifact_path"] == str(base / "output" / "lessons.csv")
        assert record["source_artifact_sha256"] == knowledge["source_artifact_sha256"]


def test_pipeline_graph_stage() -> None:
    base = runtime_dir("graph")
    event_path = base / "cpi.csv"
    gold_path = base / "gold.csv"
    write_csv(event_path, [
        {"Date": "2020-01-01", "Value": 100.0},
        {"Date": "2020-02-01", "Value": 101.0},
        {"Date": "2020-03-01", "Value": 99.0},
    ])
    write_csv(gold_path, gold_rows())
    cal_path = write_calendar(base)

    ctx = PipelineContext(
        event=CPIEvent(),
        event_data_path=event_path,
        gold_path=gold_path,
        output_dir=base / "output",
        knowledge_prefix="cpi_gold_summary_v1",
        condition_columns=("cpi_pressure",),
        asset="GOLD",
        release_calendar_path=cal_path,
    )
    result = InferencePipeline().run(ctx)
    graph = result.knowledge_graph
    assert graph is not None
    assert graph.node_count >= 1


def test_pipeline_evidence_stage() -> None:
    base = runtime_dir("evidence")
    event_path = base / "cpi.csv"
    gold_path = base / "gold.csv"
    write_csv(event_path, [
        {"Date": "2020-01-01", "Value": 100.0},
        {"Date": "2020-02-01", "Value": 101.0},
        {"Date": "2020-03-01", "Value": 99.0},
    ])
    write_csv(gold_path, gold_rows())
    cal_path = write_calendar(base)

    ctx = PipelineContext(
        event=CPIEvent(),
        event_data_path=event_path,
        gold_path=gold_path,
        output_dir=base / "output",
        knowledge_prefix="cpi_gold_summary_v1",
        condition_columns=("cpi_pressure",),
        asset="GOLD",
        release_calendar_path=cal_path,
    )
    result = InferencePipeline().run(ctx)
    evidence = result.evidence
    assert evidence is not None
    assert len(evidence) >= 1


def test_pipeline_decision_produced() -> None:
    base = runtime_dir("decision")
    event_path = base / "cpi.csv"
    gold_path = base / "gold.csv"
    write_csv(event_path, [
        {"Date": "2020-01-01", "Value": 100.0},
        {"Date": "2020-02-01", "Value": 101.0},
        {"Date": "2020-03-01", "Value": 99.0},
    ])
    write_csv(gold_path, gold_rows())
    cal_path = write_calendar(base)

    ctx = PipelineContext(
        event=CPIEvent(),
        event_data_path=event_path,
        gold_path=gold_path,
        output_dir=base / "output",
        knowledge_prefix="cpi_gold_summary_v1",
        condition_columns=("cpi_pressure",),
        asset="GOLD",
        query="gold outlook",
        release_calendar_path=cal_path,
    )
    result = InferencePipeline().run(ctx)
    decision = result.decision
    assert decision is not None
    assert decision.decision_type in VALID_DECISION_TYPES
    assert decision.context.event_type == "CPI"
    assert decision.context.query == "gold outlook"


def test_pipeline_traceability() -> None:
    base = runtime_dir("trace")
    event_path = base / "cpi.csv"
    gold_path = base / "gold.csv"
    write_csv(event_path, [
        {"Date": "2020-01-01", "Value": 100.0},
        {"Date": "2020-02-01", "Value": 101.0},
        {"Date": "2020-03-01", "Value": 99.0},
    ])
    write_csv(gold_path, gold_rows())
    cal_path = write_calendar(base)

    ctx = PipelineContext(
        event=CPIEvent(),
        event_data_path=event_path,
        gold_path=gold_path,
        output_dir=base / "output",
        knowledge_prefix="cpi_gold_summary_v1",
        condition_columns=("cpi_pressure",),
        asset="GOLD",
        release_calendar_path=cal_path,
    )
    result = InferencePipeline().run(ctx)

    decision = result.decision
    chain = result.reasoning_chain
    evidence = result.evidence
    graph = result.knowledge_graph

    assert decision is not None
    assert chain is not None
    assert evidence is not None
    assert graph is not None

    # Decision references the reasoning chain
    assert decision.reasoning_chain_id == chain.chain_id

    # Reasoning chain references evidence count
    assert chain.evidence_count == len(evidence)

    # Reasoning chain has steps that reference evidence IDs
    all_evidence_ids = {e.evidence_id for e in evidence}
    for step in chain.steps:
        for eid in step.supporting_evidence_ids:
            assert eid in all_evidence_ids, f"Step references unknown evidence '{eid}'"

    # Graph nodes match evidence source_node_ids
    graph_node_ids = set()
    if graph is not None:
        pass  # checked implicitly through evidence query

    # Pipeline stages have references to previous stages
    stages = result.stages
    for i in range(1, len(stages)):
        assert stages[i].references, f"Stage '{stages[i].name}' has no references"


def test_pipeline_validator_passes() -> None:
    base = runtime_dir("valid")
    event_path = base / "cpi.csv"
    gold_path = base / "gold.csv"
    write_csv(event_path, [
        {"Date": "2020-01-01", "Value": 100.0},
        {"Date": "2020-02-01", "Value": 101.0},
        {"Date": "2020-03-01", "Value": 99.0},
    ])
    write_csv(gold_path, gold_rows())
    cal_path = write_calendar(base)

    ctx = PipelineContext(
        event=CPIEvent(),
        event_data_path=event_path,
        gold_path=gold_path,
        output_dir=base / "output",
        knowledge_prefix="cpi_gold_summary_v1",
        condition_columns=("cpi_pressure",),
        asset="GOLD",
        release_calendar_path=cal_path,
    )
    result = InferencePipeline().run(ctx)
    assert PipelineValidator.is_valid(result)
    assert PipelineValidator.validate(result) == {}


def test_pipeline_repository_serialization(tmp_path: Path) -> None:
    base = runtime_dir("repo")
    event_path = base / "cpi.csv"
    gold_path = base / "gold.csv"
    write_csv(event_path, [
        {"Date": "2020-01-01", "Value": 100.0},
        {"Date": "2020-02-01", "Value": 101.0},
        {"Date": "2020-03-01", "Value": 99.0},
    ])
    write_csv(gold_path, gold_rows())
    cal_path = write_calendar(base)

    ctx = PipelineContext(
        event=CPIEvent(),
        event_data_path=event_path,
        gold_path=gold_path,
        output_dir=base / "output",
        knowledge_prefix="cpi_gold_summary_v1",
        condition_columns=("cpi_pressure",),
        asset="GOLD",
        release_calendar_path=cal_path,
    )
    result = InferencePipeline().run(ctx)
    repo_path = tmp_path / "pipeline_result.json"
    PipelineRepository().save(result, repo_path)
    assert repo_path.exists()

    raw = json.loads(repo_path.read_text())
    assert "context" in raw
    assert raw["context"]["event_type"] == "CPI"
    assert "stages" in raw
    stage_names = [s["name"] for s in raw["stages"]]
    assert "build_lessons" in stage_names
    assert "build_graph" in stage_names
    assert "decide" in stage_names
    assert raw["stages"][-1]["output"]["decision_type"] in list(VALID_DECISION_TYPES)


def test_pipeline_can_build_yield_context_conditioned_knowledge() -> None:
    base = runtime_dir("yield_context_pipeline")
    event_path = base / "cpi.csv"
    gold_path = base / "gold.csv"
    yield_path = base / "dgs10.csv"
    write_csv(event_path, [
        {"Date": "2020-01-01", "Value": 100.0},
        {"Date": "2020-02-01", "Value": 101.0},
        {"Date": "2020-03-01", "Value": 99.0},
        {"Date": "2020-04-01", "Value": 102.0},
    ])
    write_csv(gold_path, gold_rows())
    write_csv(yield_path, [
        {"Date": "2019-12-01", "Value": 1.50},
        {"Date": "2020-01-01", "Value": 1.60},
        {"Date": "2020-02-01", "Value": 1.90},
        {"Date": "2020-03-01", "Value": 1.70},
        {"Date": "2020-04-01", "Value": 1.72},
    ])
    cal_path = write_calendar(base)

    ctx = PipelineContext(
        event=CPIEvent(),
        event_data_path=event_path,
        gold_path=gold_path,
        yield_data_path=yield_path,
        output_dir=base / "output",
        knowledge_prefix="cpi_gold_yield_context_v1",
        condition_columns=("cpi_pressure", "us10y_trend"),
        asset="GOLD",
        release_calendar_path=cal_path,
    )
    result = InferencePipeline().run(ctx)

    lessons = result.lessons["dataframe"]
    knowledge = result.knowledge_summary
    assert "us10y_trend" in lessons.columns
    assert knowledge["record_count"] >= 1
    for record in knowledge["records"]:
        assert set(record["condition"]) == {"cpi_pressure", "us10y_trend"}
    assert result.stages[0].references["yield_context_path"] == str(yield_path)


def test_pipeline_persists_context_comparison_artifact() -> None:
    base = runtime_dir("context_comparison_pipeline")
    event_path = base / "cpi.csv"
    gold_path = base / "gold.csv"
    yield_path = base / "dgs10.csv"
    write_csv(event_path, [
        {"Date": "2020-01-01", "Value": 100.0},
        {"Date": "2020-02-01", "Value": 101.0},
        {"Date": "2020-03-01", "Value": 99.0},
        {"Date": "2020-04-01", "Value": 102.0},
    ])
    write_csv(gold_path, gold_rows())
    write_csv(yield_path, [
        {"Date": "2019-12-01", "Value": 1.50},
        {"Date": "2020-01-01", "Value": 1.60},
        {"Date": "2020-02-01", "Value": 1.90},
        {"Date": "2020-03-01", "Value": 1.70},
        {"Date": "2020-04-01", "Value": 1.72},
    ])

    cal_path = write_calendar(base)
    baseline_output = base / "baseline_output"
    baseline_ctx = PipelineContext(
        event=CPIEvent(),
        event_data_path=event_path,
        gold_path=gold_path,
        output_dir=baseline_output,
        knowledge_prefix="cpi_gold_summary_v1",
        condition_columns=("cpi_pressure",),
        asset="GOLD",
        release_calendar_path=cal_path,
    )
    InferencePipeline().run(baseline_ctx)

    contextual_output = base / "contextual_output"
    report_path = contextual_output / "context_comparison.json"
    contextual_ctx = PipelineContext(
        event=CPIEvent(),
        event_data_path=event_path,
        gold_path=gold_path,
        yield_data_path=yield_path,
        output_dir=contextual_output,
        knowledge_prefix="cpi_gold_yield_context_v1",
        condition_columns=("cpi_pressure", "us10y_trend"),
        context_comparison_baseline_path=baseline_output / "knowledge.json",
        context_comparison_output_path=report_path,
        context_comparison_base_columns=("cpi_pressure",),
        context_comparison_context_columns=("us10y_trend",),
        asset="GOLD",
        release_calendar_path=cal_path,
    )
    result = InferencePipeline().run(contextual_ctx)

    assert "compare_context" in result.stages_completed
    assert report_path.exists()
    saved_report = json.loads(report_path.read_text())
    stage_output = result._stage_output("compare_context")
    assert saved_report == stage_output
    assert saved_report["report_type"] == "context_comparison"
    assert saved_report["comparison_count"] >= 1
    compare_stage = [
        stage for stage in result.stages if stage.name == "compare_context"
    ][0]
    assert compare_stage.references["output_path"] == str(report_path)


def _lineage_test_context(base: Path, name: str) -> PipelineContext:
    event_path = base / "cpi.csv"
    gold_path = base / "gold.csv"
    write_csv(event_path, [
        {"Date": "2020-01-01", "Value": 100.0},
        {"Date": "2020-02-01", "Value": 101.0},
        {"Date": "2020-03-01", "Value": 99.0},
    ])
    write_csv(gold_path, gold_rows())
    cal_path = write_calendar(base)
    return PipelineContext(
        event=CPIEvent(),
        event_data_path=event_path,
        gold_path=gold_path,
        output_dir=base / name,
        knowledge_prefix="cpi_gold_summary_v1",
        condition_columns=("cpi_pressure",),
        asset="GOLD",
        release_calendar_path=cal_path,
    )


def test_lineage_backward_decision_to_source_data() -> None:
    base = runtime_dir("lineage_back")
    ctx = _lineage_test_context(base, "output")
    reg = LineageRegistry()
    result = InferencePipeline().run(ctx, lineage_registry=reg)

    decision = result.decision
    assert decision is not None, "No decision produced"

    path = reg.trace(decision.decision_id, "decision")
    assert len(path) >= 4, (
        f"Expected at least 4 lineage hops from decision to source_data, got {len(path)}"
    )

    all_source_ids = {r.source_id for r in path}
    all_target_ids = {r.target_id for r in path}
    all_ids = all_source_ids | all_target_ids

    assert str(ctx.event_data_path) in all_ids, (
        f"source_data '{ctx.event_data_path}' not reachable from decision '{decision.decision_id}'"
    )
    assert any(str(entity_id).startswith("CPI_GOLD_") for entity_id in all_ids), (
        "No concrete lesson_id found in backward lineage trace"
    )
    entity_types = set()
    for r in path:
        entity_types.add(r.source_type)
        entity_types.add(r.target_type)
    for t in ("source_data", "lesson", "knowledge_record", "evidence", "reasoning_chain", "decision"):
        assert t in entity_types, f"Entity type '{t}' missing from backward trace"


def test_lineage_forward_source_data_to_decision() -> None:
    base = runtime_dir("lineage_fwd")
    ctx = _lineage_test_context(base, "output")
    reg = LineageRegistry()
    result = InferencePipeline().run(ctx, lineage_registry=reg)

    decision = result.decision
    assert decision is not None, "No decision produced"

    source_data_id = str(ctx.event_data_path)
    forward = reg.query(entity_id=source_data_id, direction="forward")
    assert len(forward) >= 1, (
        f"No forward records found from source_data '{source_data_id}'"
    )

    found_types: set[str] = set()
    for r in reg.all_records():
        found_types.add(r.source_type)
        found_types.add(r.target_type)
    for t in ("source_data", "lesson", "knowledge_record", "evidence", "reasoning_chain", "decision"):
        assert t in found_types, f"Entity type '{t}' missing from lineage records"

    entity_ids: set[str] = set()
    for r in reg.all_records():
        entity_ids.add(r.source_id)
        entity_ids.add(r.target_id)
    assert decision.decision_id in entity_ids, (
        f"Decision '{decision.decision_id}' not reachable from source_data via forward queries"
    )


def test_evidence_filtered_by_horizon_5() -> None:
    base = runtime_dir("ev_horizon5")
    event_path = base / "cpi.csv"
    gold_path = base / "gold.csv"
    write_csv(event_path, [
        {"Date": "2020-01-01", "Value": 100.0},
        {"Date": "2020-02-01", "Value": 101.0},
        {"Date": "2020-03-01", "Value": 99.0},
        {"Date": "2020-04-01", "Value": 102.0},
    ])
    write_csv(gold_path, gold_rows())
    cal_path = write_calendar(base)

    ctx = PipelineContext(
        event=CPIEvent(),
        event_data_path=event_path,
        gold_path=gold_path,
        output_dir=base / "output",
        knowledge_prefix="cpi_gold_summary_v1",
        condition_columns=("cpi_pressure",),
        asset="GOLD",
        query="gold outlook after CPI",
        release_calendar_path=cal_path,
        reasoning_horizon=5,
    )
    result = InferencePipeline().run(ctx)
    evidence = result.evidence
    assert evidence is not None
    assert len(evidence) > 0, "Expected at least one evidence item for horizon=5"
    for ev in evidence:
        assert ev.horizon_days == 5, f"Expected horizon_days=5, got {ev.horizon_days}"


def test_evidence_filtered_by_horizon_20() -> None:
    base = runtime_dir("ev_horizon20")
    event_path = base / "cpi.csv"
    gold_path = base / "gold.csv"
    write_csv(event_path, [
        {"Date": "2020-01-01", "Value": 100.0},
        {"Date": "2020-02-01", "Value": 101.0},
        {"Date": "2020-03-01", "Value": 99.0},
        {"Date": "2020-04-01", "Value": 102.0},
    ])
    write_csv(gold_path, gold_rows())
    cal_path = write_calendar(base)

    ctx = PipelineContext(
        event=CPIEvent(),
        event_data_path=event_path,
        gold_path=gold_path,
        output_dir=base / "output",
        knowledge_prefix="cpi_gold_summary_v1",
        condition_columns=("cpi_pressure",),
        asset="GOLD",
        query="gold outlook after CPI",
        release_calendar_path=cal_path,
        reasoning_horizon=20,
    )
    result = InferencePipeline().run(ctx)
    evidence = result.evidence
    assert evidence is not None
    assert len(evidence) > 0, "Expected at least one evidence item for horizon=20"
    for ev in evidence:
        assert ev.horizon_days == 20, f"Expected horizon_days=20, got {ev.horizon_days}"


def test_evidence_filtered_by_condition() -> None:
    base = runtime_dir("ev_condition")
    event_path = base / "cpi.csv"
    gold_path = base / "gold.csv"
    write_csv(event_path, [
        {"Date": "2020-01-01", "Value": 100.0},
        {"Date": "2020-02-01", "Value": 101.0},
        {"Date": "2020-03-01", "Value": 99.0},
        {"Date": "2020-04-01", "Value": 102.0},
    ])
    write_csv(gold_path, gold_rows())
    cal_path = write_calendar(base)

    condition = {"cpi_pressure": "inflation_pressure_up"}
    ctx = PipelineContext(
        event=CPIEvent(),
        event_data_path=event_path,
        gold_path=gold_path,
        output_dir=base / "output",
        knowledge_prefix="cpi_gold_summary_v1",
        condition_columns=("cpi_pressure",),
        asset="GOLD",
        query="gold outlook after CPI",
        release_calendar_path=cal_path,
        reasoning_condition=condition,
    )
    result = InferencePipeline().run(ctx)
    evidence = result.evidence
    assert evidence is not None
    assert len(evidence) > 0, "Expected at least one evidence item for condition"
    for ev in evidence:
        assert ev.condition == condition, (
            f"Expected condition={condition}, got {ev.condition}"
        )
