from __future__ import annotations

import hashlib
import math
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from evidence_collection.contracts import Evidence, EvidenceCollection
from evidence_collection.strength import EvidenceStrengthComputer
from knowledge.evidence.query import EvidenceQuery
from knowledge.graph.graph import KnowledgeGraph, GraphNode
from knowledge.integrity.provenance import Provenance
from signal_assessment.volume import ETF_FLOW_THRESHOLD_PCT
from signal_assessment.contracts import (
    ClassificationLabel,
    ClassifiedObservation,
    CriterionScore,
    SignalAssessment,
)

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


def _observation_provenance_anchor(observation_id: str) -> str:
    """Deterministic sentinel for evidence with no valid KnowledgeRecord.

    Explicitly namespaced as a non-knowledge-record anchor (Contract 4 rule 5),
    derived from the observation identity so dedup semantics stay stable.
    """
    digest = hashlib.sha256(observation_id.encode("utf-8")).hexdigest()[:16]
    return f"no_kr_{digest}"


class EvidenceCollector:
    """Consumes SignalAssessment and transforms meaningful signals into Evidence.

    Filters: Noise and Ignore are discarded.
    Signal → always generates Evidence.
    Weak Signal and Watch → generate Evidence with explicit justification.
    """

    def __init__(
        self,
        knowledge_graph: KnowledgeGraph | None = None,
        strength_computer: EvidenceStrengthComputer | None = None,
    ) -> None:
        self._kg = knowledge_graph
        self._strength = strength_computer or EvidenceStrengthComputer()

    def collect(
        self,
        assessment: SignalAssessment,
        regime_weight: float = 0.8,
        cpi_condition: dict[str, str] | None = None,
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

        collection_id = f"ec_{uuid4().hex[:12]}"
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
            temporal_recency=(min(max(1.0 / (1.0 + abs(obs.change_sigma)), 0.1), 1.0) if obs.change_sigma is not None and math.isfinite(obs.change_sigma) else float('nan')),
            metadata={
                "classification": obs.classification,
                "criteria_count": len(obs.evidence),
                "instrument": obs.instrument,
                "change_pct": obs.change_pct,
                "change_sigma": obs.change_sigma,
                "provenance_type": provenance_type,
                "knowledge_record_id": knowledge_record_id,
            },
        )

    def _query_knowledge_records(
        self,
        obs: ClassifiedObservation,
        event_type: str,
        cpi_condition: dict[str, str] | None = None,
    ) -> tuple[list[str], list[str]]:
        """Resolve KnowledgeRecord IDs linked to an observation.

        When a valid current CPI condition is supplied and the lookup falls
        back onto the CPI event class, the Legacy EvidenceQuery (exact
        condition matching) is used instead of any condition-blind
        ``nodes[:3]`` / insertion-order selection.  When no condition is
        supplied the historical fallback behaviour is preserved unchanged.
        """
        if self._kg is None:
            return [], []
        nodes = self._kg.filter_nodes(event_type=event_type)
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
                nodes = self._kg.filter_nodes(event_type=mapped_type)
                if nodes:
                    break
        if not nodes:
            nodes = self._kg.filter_nodes(event_type="GENERAL")
        kr_ids = [n.node_id for n in nodes[:3]] if nodes else []
        return kr_ids, kr_ids

    @staticmethod
    def _filter_nodes_by_condition(
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
            if node is not None:
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
            # ETF proxy direction semantics: same +/-1.0% boundary as the
            # accumulating/distributing momentum label in pre_market.positioning.
            if abs(obs.change_pct) > ETF_FLOW_THRESHOLD_PCT:
                return "bullish" if obs.change_pct > 0 else "bearish"
            return "neutral"
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
