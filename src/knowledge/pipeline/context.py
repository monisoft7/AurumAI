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
    asset: str = "ASSET"
    query: str = ""
    reasoning_condition: dict[str, str] | None = None
    reasoning_horizon: int | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
