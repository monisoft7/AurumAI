import json
from pathlib import Path

from knowledge.context.comparison import (
    ContextComparisonConfig,
    ContextComparisonReport,
)


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2))


def baseline_summary() -> dict:
    return {
        "knowledge_version": "cpi_gold_summary_v1",
        "event_type": "CPI",
        "asset": "GOLD",
        "records": [
            {
                "knowledge_id": "CPI_GOLD_inflation_pressure_up_20D",
                "event_type": "CPI",
                "asset": "GOLD",
                "condition": {"cpi_pressure": "inflation_pressure_up"},
                "horizon_days": 20,
                "sample_count": 20,
                "confidence": 0.45,
                "bias": "mixed_or_context_dependent",
                "average_return_pct": 0.8,
            },
            {
                "knowledge_id": "CPI_GOLD_inflation_pressure_down_20D",
                "event_type": "CPI",
                "asset": "GOLD",
                "condition": {"cpi_pressure": "inflation_pressure_down"},
                "horizon_days": 20,
                "sample_count": 10,
                "confidence": 0.55,
                "bias": "gold_negative_bias",
                "average_return_pct": -0.5,
            },
        ],
    }


def contextual_summary() -> dict:
    return {
        "knowledge_version": "cpi_gold_yield_context_v1",
        "event_type": "CPI",
        "asset": "GOLD",
        "records": [
            {
                "knowledge_id": "CPI_GOLD_up_yields_rising_20D",
                "event_type": "CPI",
                "asset": "GOLD",
                "condition": {
                    "cpi_pressure": "inflation_pressure_up",
                    "us10y_trend": "yields_rising",
                },
                "horizon_days": 20,
                "sample_count": 8,
                "confidence": 0.62,
                "bias": "gold_positive_bias",
                "average_return_pct": 1.4,
            },
            {
                "knowledge_id": "CPI_GOLD_down_yields_flat_20D",
                "event_type": "CPI",
                "asset": "GOLD",
                "condition": {
                    "cpi_pressure": "inflation_pressure_down",
                    "us10y_trend": "yields_flat",
                },
                "horizon_days": 20,
                "sample_count": 2,
                "confidence": 0.8,
                "bias": "gold_positive_bias",
                "average_return_pct": 2.0,
            },
        ],
    }


def test_context_comparison_report_identifies_value_and_fragmentation(
    tmp_path: Path,
) -> None:
    baseline_path = tmp_path / "baseline.json"
    contextual_path = tmp_path / "contextual.json"
    write_json(baseline_path, baseline_summary())
    write_json(contextual_path, contextual_summary())

    report = ContextComparisonReport(
        ContextComparisonConfig(
            baseline_path=baseline_path,
            contextual_path=contextual_path,
            min_context_samples=3,
        )
    ).build()

    assert report["report_type"] == "context_comparison"
    assert report["comparison_count"] == 2
    assert report["decision_counts"]["context_improves_explanation"] == 1
    assert report["decision_counts"]["context_fragments_evidence"] == 1

    improving = report["comparisons"][0]
    assert improving["confidence_delta"] == 0.17
    assert improving["sample_ratio"] == 0.4
    assert improving["decision"] == "context_improves_explanation"
    assert improving["context_condition"] == {"us10y_trend": "yields_rising"}


def test_context_comparison_report_saves_deterministic_json(tmp_path: Path) -> None:
    baseline_path = tmp_path / "baseline.json"
    contextual_path = tmp_path / "contextual.json"
    output_path = tmp_path / "report.json"
    write_json(baseline_path, baseline_summary())
    write_json(contextual_path, contextual_summary())

    report = ContextComparisonReport(
        ContextComparisonConfig(
            baseline_path=baseline_path,
            contextual_path=contextual_path,
            output_path=output_path,
        )
    ).build_and_save()

    assert output_path.exists()
    saved = json.loads(output_path.read_text())
    assert saved == report
    assert saved["baseline_knowledge_version"] == "cpi_gold_summary_v1"
    assert saved["contextual_knowledge_version"] == "cpi_gold_yield_context_v1"


def test_context_comparison_report_fails_fast_without_records(tmp_path: Path) -> None:
    baseline_path = tmp_path / "baseline.json"
    contextual_path = tmp_path / "contextual.json"
    write_json(baseline_path, {"knowledge_version": "bad"})
    write_json(contextual_path, contextual_summary())

    try:
        ContextComparisonReport(
            ContextComparisonConfig(
                baseline_path=baseline_path,
                contextual_path=contextual_path,
            )
        ).build()
    except ValueError as exc:
        assert "records" in str(exc)
    else:
        raise AssertionError("Expected ValueError for missing records")
