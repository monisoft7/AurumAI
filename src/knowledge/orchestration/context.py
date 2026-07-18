from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, TYPE_CHECKING

from knowledge.economics.classifier import EconomicClassifier
from knowledge.economics.state import EconomicState
from knowledge.economics.adapter import EconomicEvidenceAdapter
from knowledge.temporal.indexer import TemporalIndexer
from knowledge.temporal.adapter import TemporalEvidenceAdapter
from knowledge.causal.graph import CausalGraph
from knowledge.causal.analyzer import CausalAnalyzer
from knowledge.evidence.query import EvidenceQuery
from knowledge.reasoning.engine import ReasoningEngine
from knowledge.decision.engine import DecisionEngine
from knowledge.integrity.lineage import LineageRegistry

if TYPE_CHECKING:
    from knowledge.reasoning.retrieval import HistoricalSituationRetriever


@dataclass
class OrchestrationContext:
    event_type: str = "CPI"
    condition: dict[str, str] | None = None
    date: str = ""
    horizon_days: int | None = None
    query: str = ""
    event_types: tuple[str, ...] | None = None

    economic_classifier: EconomicClassifier | None = None
    economic_states: list[EconomicState] | None = None
    economic_adapter: EconomicEvidenceAdapter | None = None

    temporal_indexer: TemporalIndexer | None = None
    temporal_adapter: TemporalEvidenceAdapter | None = None

    causal_graph: CausalGraph | None = None
    causal_analyzer: CausalAnalyzer | None = None

    evidence_query: EvidenceQuery | None = None
    retriever: HistoricalSituationRetriever | None = None
    reasoning_engine: ReasoningEngine | None = None
    decision_engine: DecisionEngine | None = None

    lineage_registry: LineageRegistry | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
