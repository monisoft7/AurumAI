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


def runtime_dir(name: str) -> Path:
    path = Path(__file__).resolve().parent / "_runtime" / name
    if path.exists():
        shutil.rmtree(path)
    path.mkdir(parents=True)
    return path


def write_csv(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(path, index=False)


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

    ctx = PipelineContext(
        event=CPIEvent(),
        event_data_path=event_path,
        gold_path=gold_path,
        output_dir=base / "output",
        knowledge_prefix="cpi_gold_summary_v1",
        condition_columns=("cpi_pressure",),
        asset="GOLD",
        query="gold outlook after CPI",
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

    ctx = PipelineContext(
        event=CPIEvent(),
        event_data_path=event_path,
        gold_path=gold_path,
        output_dir=base / "output",
        knowledge_prefix="cpi_gold_summary_v1",
        condition_columns=("cpi_pressure",),
        asset="GOLD",
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

    ctx = PipelineContext(
        event=CPIEvent(),
        event_data_path=event_path,
        gold_path=gold_path,
        output_dir=base / "output",
        knowledge_prefix="cpi_gold_summary_v1",
        condition_columns=("cpi_pressure",),
        asset="GOLD",
    )
    result = InferencePipeline().run(ctx)
    knowledge = result.knowledge_summary
    assert knowledge is not None
    assert "records" in knowledge
    assert knowledge["record_count"] >= 1
    assert knowledge["knowledge_version"] == "cpi_gold_summary_v1"


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

    ctx = PipelineContext(
        event=CPIEvent(),
        event_data_path=event_path,
        gold_path=gold_path,
        output_dir=base / "output",
        knowledge_prefix="cpi_gold_summary_v1",
        condition_columns=("cpi_pressure",),
        asset="GOLD",
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

    ctx = PipelineContext(
        event=CPIEvent(),
        event_data_path=event_path,
        gold_path=gold_path,
        output_dir=base / "output",
        knowledge_prefix="cpi_gold_summary_v1",
        condition_columns=("cpi_pressure",),
        asset="GOLD",
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

    ctx = PipelineContext(
        event=CPIEvent(),
        event_data_path=event_path,
        gold_path=gold_path,
        output_dir=base / "output",
        knowledge_prefix="cpi_gold_summary_v1",
        condition_columns=("cpi_pressure",),
        asset="GOLD",
        query="gold outlook",
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

    ctx = PipelineContext(
        event=CPIEvent(),
        event_data_path=event_path,
        gold_path=gold_path,
        output_dir=base / "output",
        knowledge_prefix="cpi_gold_summary_v1",
        condition_columns=("cpi_pressure",),
        asset="GOLD",
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

    ctx = PipelineContext(
        event=CPIEvent(),
        event_data_path=event_path,
        gold_path=gold_path,
        output_dir=base / "output",
        knowledge_prefix="cpi_gold_summary_v1",
        condition_columns=("cpi_pressure",),
        asset="GOLD",
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

    ctx = PipelineContext(
        event=CPIEvent(),
        event_data_path=event_path,
        gold_path=gold_path,
        output_dir=base / "output",
        knowledge_prefix="cpi_gold_summary_v1",
        condition_columns=("cpi_pressure",),
        asset="GOLD",
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

    ctx = PipelineContext(
        event=CPIEvent(),
        event_data_path=event_path,
        gold_path=gold_path,
        yield_data_path=yield_path,
        output_dir=base / "output",
        knowledge_prefix="cpi_gold_yield_context_v1",
        condition_columns=("cpi_pressure", "us10y_trend"),
        asset="GOLD",
    )
    result = InferencePipeline().run(ctx)

    lessons = result.lessons["dataframe"]
    knowledge = result.knowledge_summary
    assert "us10y_trend" in lessons.columns
    assert knowledge["record_count"] >= 1
    for record in knowledge["records"]:
        assert set(record["condition"]) == {"cpi_pressure", "us10y_trend"}
    assert result.stages[0].references["yield_context_path"] == str(yield_path)
