from __future__ import annotations

from collections import Counter
from typing import Any
from uuid import uuid4

from counter_evidence.contracts import CounterEvidenceAssessment
from evidence_reasoning.contracts import EvidenceReasoning, EvidenceSet
from knowledge.integrity.provenance import Provenance
from thesis_construction.contracts import InvestmentThesis

# Map event_types to economic mechanism descriptions
EVENT_TYPE_TO_MECHANISM: dict[str, str] = {
    "REAL_YIELD": "Real yield opportunity cost channel driving gold relative value",
    "USD_FX": "US dollar valuation channel through gold's dollar denomination",
    "INFLATION": "Inflation premium channel as gold serves as inflation hedge",
    "CB_GOLD": "Central bank reserve diversification supporting structural gold demand",
    "GEOPOLITICAL": "Safe-haven demand driven by geopolitical uncertainty",
    "ETF_FLOW": "Gold ETF flow momentum reflecting investor sentiment",
    "GENERAL": "Multi-factor cross-asset transmission affecting gold price",
}

_HISTORICAL_HORIZON_KEYS: tuple[str, ...] = ("1d", "5d", "20d")


class ThesisBuilder:
    """Builds individual InvestmentThesis objects from W6 evidence and W7 counter-evidence."""

    DEFAULT_TIME_HORIZON_DAYS = 90

    def build_thesis(
        self,
        direction: str,
        reasoning: EvidenceReasoning,
        assessment: CounterEvidenceAssessment,
        supporting_set_ids: list[str],
        counter_set_ids: list[str],
    ) -> InvestmentThesis:
        supporting_sets = [s for s in reasoning.evidence_sets if s.set_id in supporting_set_ids]

        mechanism = self._derive_mechanism(supporting_sets, direction)
        invalidating = self._build_invalidating_conditions(assessment, direction, counter_set_ids)
        unknowns = list(assessment.missing_evidence)
        confidence_inputs = self._build_confidence_inputs(supporting_sets, assessment)
        support = self._compute_institutional_support(supporting_sets, assessment)
        explanation = self._build_explanation(
            direction, len(supporting_set_ids), len(counter_set_ids),
            support, assessment,
        )
        knowledge_chunk = self._compose_knowledge_rationale(supporting_sets)
        if knowledge_chunk:
            explanation += f" | {knowledge_chunk}"
        factor_chunk = self._compose_factor_rationale(reasoning)
        if factor_chunk:
            explanation += f" | {factor_chunk}"
        analogue_chunk = self._compose_historical_analogue(reasoning)
        if analogue_chunk:
            explanation += f" | {analogue_chunk}"
        adjudication_chunk = self._compose_historical_adjudication(reasoning, direction)
        if adjudication_chunk:
            explanation += f" | {adjudication_chunk}"
        contextual_chunk = self._compose_contextual_historical_adjudication(reasoning)
        if contextual_chunk:
            explanation += f" | {contextual_chunk}"
        prov = Provenance(
            created_at=assessment.timestamp,
            created_by="W8 ThesisBuilder",
            entity_version="1.0.0",
        )
        provenance = list(assessment.provenance_chain) + [prov]

        thesis_id = f"th_{uuid4().hex[:12]}"

        historical_assessment = self._build_historical_assessment(reasoning, direction)
        metadata: dict[str, Any] = {}
        if historical_assessment is not None:
            metadata["historical_assessment"] = historical_assessment

        return InvestmentThesis(
            thesis_id=thesis_id,
            direction=direction,
            supporting_set_ids=tuple(supporting_set_ids),
            counter_evidence_ids=tuple(counter_set_ids),
            regime=reasoning.regime,
            economic_mechanism=mechanism,
            time_horizon_days=self.DEFAULT_TIME_HORIZON_DAYS,
            invalidating_conditions=tuple(invalidating),
            remaining_unknowns=tuple(unknowns),
            confidence_inputs=confidence_inputs,
            institutional_support=support,
            explanation=explanation,
            provenance_chain=tuple(provenance),
            metadata=metadata,
        )

    @staticmethod
    def _derive_mechanism(supporting_sets: list[EvidenceSet], direction: str) -> str:
        if not supporting_sets:
            return "No active evidence channels identified"
        event_types = [s.event_type for s in supporting_sets if s.event_type]
        mechanism_parts = []
        for et in event_types:
            desc = EVENT_TYPE_TO_MECHANISM.get(et, f"{et} channel")
            mechanism_parts.append(desc)
        return "; ".join(sorted(set(mechanism_parts)))

    @staticmethod
    def _build_invalidating_conditions(
        assessment: CounterEvidenceAssessment,
        direction: str,
        counter_set_ids: list[str],
    ) -> list[str]:
        conditions: list[str] = []
        if counter_set_ids:
            conditions.append(f"Counter-evidence from sets {', '.join(counter_set_ids)} strengthens")
        if assessment.regime_conflict:
            conditions.append("Current regime conflicts with thesis direction")
        if "regime_conflict" in assessment.bias_flags:
            conditions.append("Regime-dependent evidence weakening thesis")
        if "missing_evidence" in assessment.bias_flags and assessment.missing_evidence:
            missing = ", ".join(assessment.missing_evidence)
            conditions.append(f"Missing evidence channels: {missing}")
        return conditions if conditions else ["No specific invalidating conditions identified"]

    @staticmethod
    def _build_confidence_inputs(
        supporting_sets: list[EvidenceSet],
        assessment: CounterEvidenceAssessment,
    ) -> dict[str, float]:
        avg_set_weight = 0.0
        avg_set_consensus = 0.0
        if supporting_sets:
            avg_set_weight = round(
                sum(s.net_institutional_weight for s in supporting_sets) / len(supporting_sets), 4
            )
            avg_set_consensus = round(
                sum(s.consensus_score for s in supporting_sets) / len(supporting_sets), 4
            )
        return {
            "avg_supporting_weight": avg_set_weight,
            "avg_supporting_consensus": avg_set_consensus,
            "conflict_severity": assessment.conflict_severity,
            "confidence_penalty": assessment.confidence_penalty,
            "raw_support": avg_set_weight * avg_set_consensus,
        }

    @staticmethod
    def _compute_institutional_support(
        supporting_sets: list[EvidenceSet],
        assessment: CounterEvidenceAssessment,
    ) -> float:
        if not supporting_sets:
            return 0.0
        raw = sum(
            s.net_institutional_weight * s.consensus_score
            for s in supporting_sets
        ) / len(supporting_sets)
        penalty = assessment.confidence_penalty
        support = raw * (1.0 - penalty)
        return max(0.0, min(round(support, 4), 1.0))

    @staticmethod
    def _build_explanation(
        direction: str,
        num_supporting: int,
        num_counter: int,
        support: float,
        assessment: CounterEvidenceAssessment,
    ) -> str:
        return (
            f"Thesis direction={direction} | "
            f"supporting_sets={num_supporting} | "
            f"counter_evidence_sets={num_counter} | "
            f"institutional_support={support} | "
            f"conflict_severity={assessment.conflict_severity} | "
            f"confidence_penalty={assessment.confidence_penalty} | "
            f"regime_conflict={assessment.regime_conflict} | "
            f"bias_flags={list(assessment.bias_flags)}"
        )

    @staticmethod
    def _compose_knowledge_rationale(supporting_sets: list[EvidenceSet]) -> str:
        """Compose the explanation-only KR rationale chunk (Correction 008-B).

        Mirrors the deterministic per-evidence rationale carried in
        ``set.metadata["knowledge_rationale"]`` into a single ``knowledge:``
        suffix.  Returns "" when no supporting set carries a rationale, so
        explanations for non-KR pipelines are byte-identical to before.
        """
        lines: list[str] = []
        for s in supporting_sets:
            for entry in s.metadata.get("knowledge_rationale") or []:
                condition = entry.get("condition") or {}
                cond_str = "; ".join(f"{k}={v}" for k, v in condition.items()) or "any"
                parts = [
                    f"{entry.get('family', '')} {cond_str}: "
                    f"avg {entry.get('average_return_pct', 0.0):+.3f}% "
                    f"over {entry.get('horizon_days', 0)}d | "
                    f"conf {entry.get('confidence', 0.0):.3f} | "
                    f"{entry.get('sample_count', 0)} samples",
                ]
                if "positive_return_rate_pct" in entry:
                    parts.append(
                        f"{entry['positive_return_rate_pct']:.1f}% positive-rate"
                    )
                lines.append(" | ".join(parts))
        if not lines:
            return ""
        return "knowledge: " + "; ".join(lines)

    @staticmethod
    def _compose_factor_rationale(reasoning: EvidenceReasoning) -> str:
        """Compose the explanation-only cross-factor rationale chunk.

        Trace 016-B: mirrors the deterministic gold_rule_001 rationale carried
        in ``reasoning.metadata["factor_rationale"]`` into a single
        ``factor:`` suffix.  Returns "" when no factor rationale is present
        (e.g. inputs unavailable), so explanations are byte-identical to
        before.  Stale inputs are annotated explicitly and never presented as
        current observations.
        """
        rationale = reasoning.metadata.get("factor_rationale")
        if not isinstance(rationale, dict) or not rationale:
            return ""
        parts = [
            f"{rationale.get('rule_id', 'gold_rule_001')} "
            f"bias={rationale.get('composite_bias', '')} "
            f"strength={rationale.get('composite_strength', 0.0):+.4f} "
            f"confidence={rationale.get('composite_confidence', 0.0):.4f} "
            f"dispersion={rationale.get('signal_dispersion', 0.0):.4f}",
        ]
        for f in rationale.get("factors") or []:
            parts.append(
                f"{f.get('factor_id', '')}: obs={f.get('observation_date', '')} "
                f"bias={f.get('influence_bias', '')} "
                f"strength={f.get('influence_strength', 0.0):+.4f} "
                f"conf={f.get('confidence', 0.0):.4f} "
                f"quality={f.get('data_quality', '')} ({f.get('status', '')})"
            )
        summary = "; ".join(parts)
        if rationale.get("freshness_note"):
            summary += f" | {rationale['freshness_note']}"
        adjudicated = [
            f"{key}={rationale[key]}"
            for key in (
                "regime",
                "dominant_factor",
                "weaker_factor",
                "precedence_reason",
                "adjudicated_interpretation",
            )
            if rationale.get(key)
        ]
        if adjudicated:
            summary += " | " + " | ".join(adjudicated)
        return "factor: " + summary

    @staticmethod
    def _compose_historical_analogue(reasoning: EvidenceReasoning) -> str:
        """Compose the explanation-only historical analogue chunk.

        Correction 025-B: mirrors the deterministic payload carried in
        ``reasoning.metadata["historical_analogue"]`` into a single
        ``historical_analogue:`` suffix.  Uses only the retrieved fields and
        the existing ``EvidenceCollection.aggregate()`` values already present
        in the payload -- no new statistic is invented.  Returns "" when no
        payload is present (e.g. index unavailable), so explanations are
        byte-identical to before.
        """
        payload = reasoning.metadata.get("historical_analogue")
        if not isinstance(payload, dict) or not payload:
            return ""
        count = int(payload.get("match_count", 0))
        if count <= 0:
            return ""
        noun = "episode" if count == 1 else "episodes"
        parts = [
            f"historical_analogue: {count} comparable CPI {noun} "
            "matched the current configuration"
        ]
        aggregate = payload.get("aggregate")
        if isinstance(aggregate, dict) and aggregate.get("count"):
            parts.append(
                f"aggregate gold outcome avg "
                f"{float(aggregate.get('avg_return_pct', 0.0)):+.3f}% (1d)"
            )
        top_ids = [
            m.get("lesson_id") for m in payload.get("matches") or []
            if m.get("lesson_id")
        ]
        if top_ids:
            parts.append(f"top={','.join(top_ids)}")
        return " | ".join(parts)

    @staticmethod
    def _direction_verdict(direction: str, status: str) -> str:
        """Map an existing adjudication status onto a candidate direction.

        Correction 033: reuse only the already-established semantics --
        positive history supports bullish and contradicts bearish; negative
        history supports bearish and contradicts bullish; mixed history is
        never converted into a directional label; neutralized / flat history
        is non-directional.  Average-return magnitude plays no role.
        """
        if status == "positive":
            if direction == "bullish":
                return "supports"
            if direction == "bearish":
                return "contradicts"
            return "no directional confirmation"
        if status == "negative":
            if direction == "bearish":
                return "supports"
            if direction == "bullish":
                return "contradicts"
            return "no directional confirmation"
        if status == "mixed":
            if direction == "neutral":
                return "supports neutral/uncertain interpretation"
            return "no directional confirmation"
        return "non-directional"

    @staticmethod
    def _direction_support_summary(
        direction: str,
        statuses: dict[str, str],
        verdicts: dict[str, str],
    ) -> str:
        """Deterministic direction support summary built from actual statuses."""
        present = list(verdicts)
        if direction == "neutral":
            if any(statuses.get(hk) == "mixed" for hk in present):
                return (
                    "historical outcomes remain mixed/context-dependent; "
                    "mixed history supports a neutral/uncertain interpretation"
                )
            if all(verdicts[hk] == "non-directional" for hk in present):
                return (
                    "history is non-directional (neutralized or flat); "
                    "consistent with a neutral interpretation"
                )
            return (
                "history is directional and provides no confirmation "
                "for a neutral thesis"
            )
        contradicts = [hk for hk in present if verdicts[hk] == "contradicts"]
        supports = [hk for hk in present if verdicts[hk] == "supports"]
        if contradicts:
            return (
                f"history contradicts {direction} direction at "
                f"{', '.join(contradicts)} and does not provide uniform "
                f"{direction} confirmation"
            )
        if supports and len(supports) == len(present):
            return (
                f"history provides uniform {direction} confirmation across "
                f"{', '.join(present)}"
            )
        if supports:
            return (
                f"history does not provide uniform {direction} confirmation "
                f"(supports at {', '.join(supports)}; no directional "
                "confirmation elsewhere)"
            )
        return f"history provides no directional confirmation for {direction}"

    @staticmethod
    def _build_historical_assessment(
        reasoning: EvidenceReasoning,
        direction: str,
    ) -> dict[str, Any] | None:
        """Build the structured candidate-direction-aware historical assessment.

        Correction 033: projects the explanation-only
        ``reasoning.metadata["historical_adjudication"]`` payload onto the
        thesis direction.  Only existing payload values are used -- statuses,
        lesson_ids, query context, and provenance are copied verbatim; no new
        IDs, scores, or statistics are invented.  Horizon statuses stay
        separate (1d / 5d / 20d are never collapsed into one directional
        claim).  Returns ``None`` when no adjudication is present, so the
        thesis metadata stays byte-identical to before.
        """
        payload = reasoning.metadata.get("historical_adjudication")
        if not isinstance(payload, dict) or not payload:
            return None
        results = payload.get("horizon_results")
        if not isinstance(results, dict) or not results:
            return None

        statuses: dict[str, str] = {}
        for key in _HISTORICAL_HORIZON_KEYS:
            result = results.get(key)
            if not isinstance(result, dict):
                continue
            status = result.get("status")
            if isinstance(status, str) and status:
                statuses[key] = status
        if not statuses:
            return None

        horizon_results: dict[str, Any] = {}
        for key, status in statuses.items():
            result = results.get(key) or {}
            horizon_results[key] = {
                "status": status,
                "direction_summary": result.get("direction_summary"),
                "count": result.get("count"),
                "verdict": ThesisBuilder._direction_verdict(direction, status),
            }
        verdicts = {
            key: entry["verdict"] for key, entry in horizon_results.items()
        }
        summary = ThesisBuilder._direction_support_summary(
            direction, statuses, verdicts
        )

        provenance: dict[str, Any] = {
            "query": dict(payload.get("query") or {}),
        }
        sources: list[dict[str, Any]] = []
        seen: set[Any] = set()
        for key in _HISTORICAL_HORIZON_KEYS:
            result = results.get(key)
            if not isinstance(result, dict):
                continue
            for entry in result.get("inputs") or []:
                if not isinstance(entry, dict):
                    continue
                lesson_id = entry.get("lesson_id")
                if lesson_id is None or lesson_id in seen:
                    continue
                seen.add(lesson_id)
                sources.append(
                    {
                        "lesson_id": lesson_id,
                        "event_date": entry.get("event_date"),
                        "horizon": entry.get("horizon"),
                        "source_artifact_path": entry.get(
                            "source_artifact_path"
                        ),
                        "source_artifact_sha256": entry.get(
                            "source_artifact_sha256"
                        ),
                    }
                )
        provenance["sources"] = sources

        analogue = reasoning.metadata.get("historical_analogue")
        if isinstance(analogue, dict):
            similarity: dict[str, dict[str, Any]] = {}
            for match in analogue.get("matches") or []:
                if not isinstance(match, dict):
                    continue
                lesson_id = match.get("lesson_id")
                sim = match.get("similarity")
                if lesson_id is None or not isinstance(sim, dict):
                    continue
                entry = {
                    key: sim.get(key)
                    for key in ("overall_similarity", "retrieval_method")
                    if sim.get(key) is not None
                }
                if entry:
                    similarity[str(lesson_id)] = entry
            if similarity:
                provenance["similarity"] = similarity

        return {
            "thesis_direction": direction,
            "horizon_results": horizon_results,
            "direction_support_summary": summary,
            "evidence_ids": list(payload.get("evidence_ids") or []),
            "provenance": provenance,
        }

    @staticmethod
    def _compose_historical_adjudication(
        reasoning: EvidenceReasoning,
        direction: str,
    ) -> str:
        """Compose the candidate-direction-aware historical adjudication chunk.

        Correction 033: replaces the generic historical chunk with a
        candidate-specific one.  Each horizon status is preserved separately
        and evaluated against the thesis direction using the established
        status vocabulary; deterministic text is built from the actual
        statuses (never hardcoded).  Returns "" when no adjudication is
        present, so explanations are byte-identical to before.
        """
        payload = reasoning.metadata.get("historical_adjudication")
        if not isinstance(payload, dict) or not payload:
            return ""
        results = payload.get("horizon_results")
        if not isinstance(results, dict) or not results:
            return ""
        status_parts: list[str] = []
        statuses: dict[str, str] = {}
        for key in _HISTORICAL_HORIZON_KEYS:
            result = results.get(key)
            if not isinstance(result, dict):
                continue
            status = str(result.get("status", "n/a"))
            statuses[key] = status
            agg = result.get("aggregation")
            avg = 0.0
            if isinstance(agg, dict) and isinstance(
                agg.get("avg_return_pct"), (int, float)
            ):
                avg = float(agg["avg_return_pct"])
            status_parts.append(
                f"{key}={status} ({avg:+.3f}%)"
            )
        if not status_parts:
            return ""
        parts = ["historical_adjudication: " + "; ".join(status_parts)]
        if statuses:
            verdicts = {
                key: ThesisBuilder._direction_verdict(direction, status)
                for key, status in statuses.items()
            }
            summary = ThesisBuilder._direction_support_summary(
                direction, statuses, verdicts
            )
            parts.append(f"direction_support: {summary}")
        interpretation = payload.get("overall_interpretation")
        if isinstance(interpretation, str) and interpretation:
            parts.append(interpretation)
        return " | ".join(parts)

    @staticmethod
    def _compose_contextual_historical_adjudication(
        reasoning: EvidenceReasoning,
    ) -> str:
        """Compose the explanation-only contextual historical chunk.

        Correction 030: mirrors the deterministic payload carried in
        ``reasoning.metadata["contextual_historical_adjudication"]`` into a
        single ``contextual_historical_adjudication:`` suffix after the
        ``historical_adjudication:`` chunk.  Uses only the fields already
        present in the payload -- no new statistic is invented.  Returns ""
        when no payload is present, so explanations are byte-identical to
        before.
        """
        payload = reasoning.metadata.get("contextual_historical_adjudication")
        if not isinstance(payload, dict) or not payload:
            return ""
        tendency = (payload.get("historical_tendency") or {}).get(
            "tendency", "unknown"
        )
        current = payload.get("current_context") or {}
        regime_context = payload.get("regime_context") or {}
        effect = payload.get("context_effect", "")
        parts = [
            "contextual_historical_adjudication: "
            f"effect={effect} tendency={tendency} "
            f"composite_bias={current.get('composite_bias', 'n/a')}",
        ]
        if regime_context.get("regime"):
            parts.append(f"regime={regime_context['regime']}")
        interpretation = payload.get("overall_interpretation")
        if isinstance(interpretation, str) and interpretation:
            parts.append(interpretation)
        invalidation = payload.get("invalidation_conditions")
        if isinstance(invalidation, list) and invalidation:
            parts.append("invalidation: " + "; ".join(invalidation))
        return " | ".join(parts)
