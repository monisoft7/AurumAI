from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, TYPE_CHECKING

from knowledge.economics.classifier import EconomicClassifier
from knowledge.economics.state import EconomicState
from knowledge.economics.adapter import EconomicEvidenceAdapter
from knowledge.cbi.contracts import (
    PolicyBiasScore,
    ForwardGuidanceRecord,
    RatePathProjection,
)
from knowledge.cbi.adapter import CbiEvidenceAdapter
from knowledge.cai.contracts import (
    CrossAssetCorrelation,
    SpreadAnalysis,
    VolatilityRegime,
)
from knowledge.cai.adapter import CaiEvidenceAdapter
from knowledge.cfi.contracts import (
    CentralBankReserveFlowReport,
    ETFFlowMonitor,
    GoldPositioningDashboard,
)
from knowledge.cfi.adapter import CfiEvidenceAdapter
from knowledge.regime.macro_regime_detector import MacroRegimeDetector
from knowledge.regime.composite_score import CompositeScoreBuilder
from knowledge.temporal.indexer import TemporalIndexer
from knowledge.temporal.adapter import TemporalEvidenceAdapter
from knowledge.causal.graph import CausalGraph
from knowledge.causal.analyzer import CausalAnalyzer
from knowledge.evidence.query import EvidenceQuery
from knowledge.evidence.evidence import Evidence
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

    cbi_bias_scores: list[PolicyBiasScore] | None = None
    cbi_guidance_records: list[ForwardGuidanceRecord] | None = None
    cbi_rate_paths: list[RatePathProjection] | None = None
    cbi_adapter: CbiEvidenceAdapter | None = None

    cai_correlations: list[CrossAssetCorrelation] | None = None
    cai_spreads: list[SpreadAnalysis] | None = None
    cai_volatilities: list[VolatilityRegime] | None = None
    cai_adapter: CaiEvidenceAdapter | None = None

    cfi_etf_flows: list[ETFFlowMonitor] | None = None
    cfi_cb_reserve_reports: list[CentralBankReserveFlowReport] | None = None
    cfi_positioning_dashboards: list[GoldPositioningDashboard] | None = None
    cfi_adapter: CfiEvidenceAdapter | None = None

    composite_score_builder: CompositeScoreBuilder | None = None
    regime_detector: MacroRegimeDetector | None = None
    regime_evidence: list[Evidence] | None = None

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
    institutional_context: dict[str, str] = field(default_factory=dict)
