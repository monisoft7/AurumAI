from __future__ import annotations

import hashlib
import math
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from evidence_collection.contracts import Evidence, EvidenceCollection
from evidence_collection.strength import EvidenceStrengthComputer
from knowledge.evidence.query import EvidenceQuery
from knowledge.graph.graph import GraphNode, KnowledgeGraph
from knowledge.integrity.provenance import Provenance
from signal_assessment.contracts import (
    ClassificationLabel,
    ClassifiedObservation,
    CriterionScore,
    SignalAssessment,
)
from signal_assessment.volume import ETF_FLOW_THRESHOLD_PCT

SIGNAL_LABELS = {
    ClassificationLabel.SIGNAL.value,
    ClassificationLabel.WEAK_SIGNAL.value,
    ClassificationLabel.WATCH.value,
}

INSTRUMENT_TO_EVENT_TYPE: dict[str, str] = {
    "XAU/USD": "GENERAL",
    "DXY": "USD_FX",
    "US10Y Real Yield": "REAL_YIELD",
    "US10Y Nominal Yield": "REAL_YIELD",
    "Breakeven Inflation": "INFLATION",
    "CPI Release": "INFLATION",
    "S&P 500 Futures": "GENERAL",
    "Brent Crude": "GENERAL",
    "EUR/USD": "USD_FX",
    "USD/JPY": "USD_FX",
    "Gold Positioning": "ETF_FLOW",
}

INSTRUMENT_TO_REGIME_BIAS: dict[str, str] = {
    "XAU/USD": "bullish",
    "DXY": "bearish",
    "US10Y Real Yield": "bearish",
    "US10Y Nominal Yield": "neutral",
    "Breakeven Inflation": "bullish",
    "S&P 500 Futures": "bullish",
    "Brent Crude": "neutral",
    "EUR/USD": "bearish",
    "USD/JPY": "bullish",
    "Gold Positioning": "bullish",
}

EVENT_TYPE_TO_EVIDENCE_CLASS: dict[str, str] = {
    "CPI": "INFLATION",
    "PPI": "INFLATION",
    "FOMC": "REAL_YIELD",
    "INTEREST_RATE": "REAL_YIELD",
    "DXY": "USD_FX",
    "ETF": "ETF_FLOW",
}

DIRECTIONAL_INSTRUMENT_GOLD_BIAS: dict[str, dict[str, str]] = {
    "XAU/USD": {"up": "bullish", "down": "bearish"},
    "DXY": {"up": "bearish", "down": "bullish"},
    "US10Y Real Yield": {"up": "bearish", "down": "bullish"},
    "Breakeven Inflation": {"up": "bullish", "down": "bearish"},
    "S&P 500 Futures": {"up": "bullish", "down": "bearish"},
    "Brent Crude": {"up": "bullish", "down": "bearish"},
    "EUR/USD": {"up": "bearish", "down": "bullish"},
    "USD/JPY": {"up": "bearish", "down": "bullish"},
}


def _observation_provenance_anchor(observation_id: str) -> str:
    """Deterministic sentinel for evidence with no valid KnowledgeRecord."""
    digest = hashlib.sha256(observation_id.encode("utf-8")).hexdigest()[:16]
    return f"no_kr_{digest}"


class EvidenceCollector:
    """Consumes SignalAssessment and transforms meaningful signals into Evidence."""

    def __init__(
        self,
        knowledge_graph: KnowledgeGraph | None = None,
        strength_computer: EvidenceStrengthComputer | None = None,
    ) -> None:
        self._kg = knowledge_graph
        self._strength = strength_computer or EvidenceStrengthComputer()
        self._kb_ingested = False

    def _fallback_institutional_kb_nodes(self, event_type: str) -> list[GraphNode]:
        """Load Institutional_Gold_Knowledge_Base.md only in production runtime
        when the primary pipeline graph has no matching KnowledgeRecord."""
        if "pytest" in sys.modules or os.environ.get("PYTEST_CURRENT_TEST"):
            return []
        if self._kg is None:
            return []
        if not self._kb_ingested:
            self._kb_ingested = True
            try:
                kb_path = (
                    Path(__file__).resolve().parent.parent.parent
                    / "Institutional_Gold_Knowledge_Base.md"
                )
                if kb_path.is_file():
                    from knowledge.ingestion.ingestion_pipeline import KrIngestionPipeline

                    kb_graph, _ = KrIngestionPipeline(str(kb_path)).run()
                    for nid in list(kb_graph._graph.nodes):
                        node = kb_graph.get_node(nid)
                        if node is not None and self._kg.get_node(nid) is None:
                            self._kg.add_node(node)
            except Exception:
                return []
        nodes = [
            n for n in self._kg.filter_nodes(event_type=event_type)
            if self._is_valid_kr_node(n)
        ]
        if not nodes:
            nodes = [
                n for n in self._kg.filter_nodes(event_type="GENERAL")
                if self._is_valid_kr_node(n)
            ]
        return nodes

    def collect(
        self,
        assessment: SignalAssessment,
        regime_weight: float = 0.8,
        cpi_condition: dict[str, str] | None = None,
        technical_assessment: Any = None,
    ) -> EvidenceCollection:
        evidence_items: list[Evidence] = []
        filtered_noise = 0
        filtered_ignore = 0
        signals = 0
        weak_signals = 0
        watch = 0

        if not (isinstance(cpi_condition, dict) and cpi_condition):
            cpi_condition = None

        for obs in assessment.observations:
            if obs.classification == ClassificationLabel.NOISE.value:
                filtered_noise += 1
                continue
            if obs.classification == ClassificationLabel.IGNORE.value:
                filtered_ignore += 1
                continue

            if obs.classification == ClassificationLabel.SIGNAL.value:
                signals += 1
            elif obs.classification == ClassificationLabel.WEAK_SIGNAL.value:
                weak_signals += 1
            elif obs.classification == ClassificationLabel.WATCH.value:
                watch += 1

            evidence = self._build_evidence(
                obs, assessment, regime_weight, cpi_condition
            )
            evidence_items.append(evidence)

        technical_item = None
        if technical_assessment is not None:
            from evidence_collection.desk_evidence import build_technical_evidence

            technical_item = build_technical_evidence(technical_assessment)

        collection_id = f"ec_{uuid4().hex[:12]}"
        collection_metadata: dict[str, Any] = {}
        news_registry = assessment.metadata.get("news_provenance")
        if isinstance(news_registry, dict) and news_registry:
            collection_metadata["news_intelligence"] = {
                "article_count": len(news_registry),
                "observation_ids": sorted(news_registry.keys()),
                "event_types": sorted(
                    {
                        str(entry.get("event_type"))
                        for entry in news_registry.values()
                        if isinstance(entry, dict) and entry.get("event_type")
                    }
                ),
            }
        if technical_assessment is not None:
            def _ta_field(name: str, default: Any = None) -> Any:
                if isinstance(technical_assessment, dict):
                    return technical_assessment.get(name, default)
                return getattr(technical_assessment, name, default)

            collection_metadata["technical_desk"] = {
                "evidence_emitted": technical_item is not None,
                "assessment_id": _ta_field("assessment_id"),
                "as_of": _ta_field("as_of"),
            }
        if technical_item is not None:
            evidence_items.append(technical_item)
        return EvidenceCollection(
            collection_id=collection_id,
            assessment_id=assessment.assessment_id,
            timestamp=datetime.now(timezone.utc).isoformat(),
            regime=assessment.regime,
            items=tuple(evidence_items),
            total_classified=len(assessment.observations),
            signals_count=signals,
            weak_signals_count=weak_signals,
            watch_count=watch,
            filtered_noise_count=filtered_noise,
            filtered_ignore_count=filtered_ignore,
            metadata=collection_metadata,
        )

    def _build_evidence(
        self,
        obs: ClassifiedObservation,
        assessment: SignalAssessment,
        regime_weight: float,
        cpi_condition: dict[str, str] | None = None,
    ) -> Evidence:
        event_type = INSTRUMENT_TO_EVENT_TYPE.get(obs.instrument, "GENERAL")
        bias = self._resolve_bias(obs, assessment.regime)
        base_confidence = obs.confidence
        cw = round(base_confidence * regime_weight, 4)

        kr_ids, kr_nodes = self._query_knowledge_records(
            obs, event_type, cpi_condition
        )
        if kr_ids:
            source_kr_id = kr_ids[0]
            source_kr_node_id = kr_nodes[0] if kr_nodes else kr_ids[0]
            knowledge_record_id = source_kr_id
            provenance_type = "knowledge_record"
        else:
            source_kr_id = _observation_provenance_anchor(obs.observation_id)
            source_kr_node_id = source_kr_id
            knowledge_record_id = None
            provenance_type = "observation"

        supporting = self._get_supporting_observation_ids(obs)
        contradicting = self._get_contradicting_observation_ids(obs)

        reason_parts = [obs.reason]
        if obs.classification == ClassificationLabel.WEAK_SIGNAL.value:
            reason_parts.append("justification: weak signal — needs confirmation")
        elif obs.classification == ClassificationLabel.WATCH.value:
            reason_parts.append("justification: watch — not actionable, requires additional data")
        explanation = " | ".join(reason_parts)

        provenance = Provenance(
            created_at=datetime.now(timezone.utc).isoformat(),
            created_by="W6 EvidenceCollector",
            entity_version="1.0.0",
            metadata={"knowledge_record_link": knowledge_record_id},
        )

        metadata: dict[str, Any] = {
            "classification": obs.classification,
            "criteria_count": len(obs.evidence),
            "instrument": obs.instrument,
            "change_pct": obs.change_pct,
            "change_sigma": obs.change_sigma,
            "provenance_type": provenance_type,
            "knowledge_record_id": knowledge_record_id,
        }
        from evidence_collection.desk_evidence import (
            _assessment_date,
            canonical_fact_identity,
        )

        metadata["canonical_fact_id"] = canonical_fact_identity(
            obs.instrument, event_type, _assessment_date(assessment.timestamp)
        )
        news_prov = self._news_provenance_payload(obs, assessment)
        if news_prov is not None:
            metadata["news"] = news_prov
        knowledge_semantics = self._knowledge_semantics_payload(
            source_kr_node_id
        )
        if knowledge_semantics is not None:
            metadata["knowledge_semantics"] = knowledge_semantics

        return Evidence(
            evidence_id=f"ev_{source_kr_id}_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}",
            source_kr_id=source_kr_id,
            source_kr_node_id=source_kr_node_id,
            event_type=event_type,
            condition={"instrument": obs.instrument},
            bias=bias,
            base_confidence=base_confidence,
            regime_weight=regime_weight,
            composite_weight=cw,
            explanation=explanation,
            regime=assessment.regime,
            source_label=obs.source,
            supporting_observation_ids=tuple(supporting),
            contradicting_observation_ids=tuple(contradicting),
            mechanism=self._resolve_mechanism(obs.instrument),
            provenance=provenance,
            temporal_recency=(
                min(max(1.0 / (1.0 + abs(obs.change_sigma)), 0.1), 1.0)
                if obs.change_sigma is not None and math.isfinite(obs.change_sigma)
                else float("nan")
            ),
            metadata=metadata,
        )

    KNOWLEDGE_SEMANTICS_FIELDS: tuple[str, ...] = (
        "horizon_days",
        "sample_count",
        "average_return_pct",
        "confidence",
        "positive_return_rate_pct",
    )

    @staticmethod
    def _news_provenance_payload(
        obs: ClassifiedObservation,
        assessment: SignalAssessment,
    ) -> dict[str, Any] | None:
        if obs.source != "news":
            return None
        registry = assessment.metadata.get("news_provenance")
        if not isinstance(registry, dict):
            return None
        entry = registry.get(obs.observation_id)
        if not isinstance(entry, dict) or not entry:
            return None
        return dict(entry)

    KNOWLEDGE_SEMANTICS_OPTIONAL_FIELDS: tuple[str, ...] = (
        "bias",
        "last_event_date",
        "institutional_context",
    )

    @staticmethod
    def _is_valid_kr_node(node: GraphNode | None) -> bool:
        """Contract 4 rule 5: only genuine knowledge_record nodes whose
        knowledge_id matches their node_id may be claimed as KnowledgeRecords."""
        if node is None or node.node_type != "knowledge_record":
            return False
        props = node.properties or {}
        kr_id = props.get("knowledge_id")
        if not isinstance(kr_id, str) or not kr_id.strip():
            return False
        return kr_id.strip() == node.node_id

    def _knowledge_semantics_payload(
        self, source_kr_node_id: str
    ) -> dict[str, Any] | None:
        if self._kg is None or not source_kr_node_id:
            return None
        node = self._kg.get_node(source_kr_node_id)
        if not self._is_valid_kr_node(node):
            return None
        props = node.properties or {}
        semantics: dict[str, Any] = {}
        condition = props.get("condition")
        if isinstance(condition, dict) and condition:
            semantics["condition"] = dict(condition)
        for field in self.KNOWLEDGE_SEMANTICS_FIELDS:
            if field in props and props[field] is not None:
                semantics[field] = props[field]
        for field in self.KNOWLEDGE_SEMANTICS_OPTIONAL_FIELDS:
            if field in props and props[field] not in (None, "", {}):
                semantics[field] = props[field]
        return semantics or None

    def _query_knowledge_records(
        self,
        obs: ClassifiedObservation,
        event_type: str,
        cpi_condition: dict[str, str] | None = None,
    ) -> tuple[list[str], list[str]]:
        """Resolve KnowledgeRecord IDs linked to an observation."""
        if self._kg is None:
            return [], []
        nodes = [
            n for n in self._kg.filter_nodes(event_type=event_type)
            if self._is_valid_kr_node(n)
        ]
        if not nodes:
            mapped_types = [
                t for t, cls in EVENT_TYPE_TO_EVIDENCE_CLASS.items()
                if cls == event_type
            ]
            for mapped_type in mapped_types:
                if mapped_type == "CPI" and cpi_condition:
                    nodes = self._filter_nodes_by_condition(
                        "CPI", cpi_condition, self._kg
                    )
                    if nodes:
                        break
                    continue
                nodes = [
                    n for n in self._kg.filter_nodes(event_type=mapped_type)
                    if self._is_valid_kr_node(n)
                ]
                if nodes:
                    break
        if not nodes:
            nodes = [
                n for n in self._kg.filter_nodes(event_type="GENERAL")
                if self._is_valid_kr_node(n)
            ]
        if not nodes:
            nodes = self._fallback_institutional_kb_nodes(event_type)
        kr_ids = [n.node_id for n in nodes[:3]] if nodes else []
        return kr_ids, kr_ids

    @classmethod
    def _filter_nodes_by_condition(
        cls,
        event_type: str,
        condition: dict[str, str],
        graph: KnowledgeGraph,
    ) -> list[GraphNode]:
        matched = EvidenceQuery(graph).matching(
            event_type=event_type,
            condition=condition,
        )
        nodes: list[GraphNode] = []
        for item in matched:
            node = graph.get_node(item.source_node_id)
            if cls._is_valid_kr_node(node):
                nodes.append(node)
        return nodes

    @staticmethod
    def _resolve_bias(obs: ClassifiedObservation, regime: str) -> str:
        base = INSTRUMENT_TO_REGIME_BIAS.get(obs.instrument, "neutral")
        if (
            obs.instrument == "Gold Positioning"
            and obs.change_pct is not None
            and math.isfinite(obs.change_pct)
        ):
            if abs(obs.change_pct) > ETF_FLOW_THRESHOLD_PCT:
                return "bullish" if obs.change_pct > 0 else "bearish"
            return "neutral"
        directional = DIRECTIONAL_INSTRUMENT_GOLD_BIAS.get(obs.instrument)
        if directional is not None:
            change = obs.change_pct
            if change is not None and math.isfinite(change) and change != 0.0:
                return directional["up"] if change > 0 else directional["down"]
        return base

    @staticmethod
    def _get_supporting_observation_ids(obs: ClassifiedObservation) -> list[str]:
        passed = [s for s in obs.evidence if s.passed]
        return [s.criterion for s in passed]

    @staticmethod
    def _get_contradicting_observation_ids(obs: ClassifiedObservation) -> list[str]:
        failed = [s for s in obs.evidence if not s.passed and s.score > 0.0]
        if not failed and obs.classification in (
            ClassificationLabel.WEAK_SIGNAL.value,
            ClassificationLabel.WATCH.value,
        ):
            return ["insufficient_criteria"]
        return [s.criterion for s in failed]

    @staticmethod
    def _resolve_mechanism(instrument: str) -> str:
        mechanisms = {
            "XAU/USD": "Direct gold price observation",
            "DXY": "USD inverse correlation with gold",
            "US10Y Real Yield": "Real yield opportunity cost channel",
            "US10Y Nominal Yield": "Nominal yield opportunity cost",
            "Breakeven Inflation": "Inflation premium channel",
            "S&P 500 Futures": "Risk appetite / wealth effect",
            "Brent Crude": "Commodity inflation / supply shock",
            "EUR/USD": "USD valuation channel",
            "USD/JPY": "Safe-haven flow channel",
            "Gold Positioning": "Positioning / flow pressure",
        }
        return mechanisms.get(instrument, "Cross-asset transmission channel")