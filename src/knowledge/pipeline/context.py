from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from knowledge.events.base import MacroEvent


@dataclass
class PipelineContext:
    event: MacroEvent
    event_data_path: Path
    gold_path: Path
    output_dir: Path
    knowledge_prefix: str = "knowledge_summary_v1"
    condition_columns: tuple[str, ...] = ("condition",)
    horizons: tuple[int, ...] = (1, 5, 20)
    min_samples_for_confidence: int = 12
    yield_data_path: Path | None = None
    yield_context_lookback_days: int = 30
    context_comparison_baseline_path: Path | None = None
    context_comparison_output_path: Path | None = None
    context_comparison_base_columns: tuple[str, ...] | None = None
    context_comparison_context_columns: tuple[str, ...] | None = None
    asset: str = "ASSET"
    query: str = ""
    reasoning_condition: dict[str, str] | None = None
    reasoning_horizon: int | None = None
    min_evidence_count: int = 1
    release_calendar_path: str | None = None
    lesson_builder: Any | None = None
    prebuilt_lessons_path: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
