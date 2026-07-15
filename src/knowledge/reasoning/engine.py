from __future__ import annotations

from typing import Any

from knowledge.evidence.collection import EvidenceCollection
from knowledge.evidence.evidence import Evidence
from knowledge.reasoning.context import ReasoningContext
from knowledge.reasoning.step import (
    ReasoningStep,
    STEP_EVIDENCE_REVIEW,
    STEP_COMPARISON,
    STEP_AGGREGATION,
    STEP_CONCLUSION,
)
from knowledge.reasoning.chain import ReasoningChain


class ReasoningEngine:
    def reason(self, evidence: EvidenceCollection, context: ReasoningContext) -> ReasoningChain:
        steps: list[ReasoningStep] = []

        for i, ev in enumerate(evidence):
            step = self._build_evidence_review(ev, i)
            steps.append(step)

        self._add_comparison_steps(evidence, steps)

        if steps:
            step = self._build_aggregation(evidence, steps, len(steps))
            steps.append(step)

            step = self._build_conclusion(evidence, context, steps, len(steps))
            steps.append(step)

        chain_id = self._build_chain_id(context)
        overall_confidence = self._compute_overall_confidence(evidence)
        final_conclusion = steps[-1].conclusion if steps else "No evidence to reason from."

        return ReasoningChain(
            chain_id=chain_id,
            context=context,
            steps=tuple(steps),
            final_conclusion=final_conclusion,
            overall_confidence=overall_confidence,
            evidence_count=len(evidence),
        )

    def _build_evidence_review(self, ev: Evidence, index: int) -> ReasoningStep:
        step_id = f"step_{index}"
        condition_str = self._format_condition(ev.condition)
        detail = round(ev.average_return_pct, 3)
        conclusion = (
            f"{ev.event_type} with condition {condition_str} "
            f"shows {detail:+.3f}% average return over {ev.horizon_days} days "
            f"(confidence: {ev.confidence:.3f}, samples: {ev.sample_count})."
        )
        return ReasoningStep(
            step_id=step_id,
            step_type=STEP_EVIDENCE_REVIEW,
            conclusion=conclusion,
            confidence=ev.confidence,
            supporting_evidence_ids=(ev.evidence_id,),
            details={
                "event_type": ev.event_type,
                "condition": ev.condition,
                "horizon_days": ev.horizon_days,
                "average_return_pct": ev.average_return_pct,
                "sample_count": ev.sample_count,
                "bias": ev.bias,
            },
        )

    def _add_comparison_steps(self, evidence: EvidenceCollection, steps: list[ReasoningStep]) -> None:
        by_event: dict[str, list[Evidence]] = {}
        for ev in evidence:
            by_event.setdefault(ev.event_type, []).append(ev)

        for event_type, evs in by_event.items():
            if len(evs) < 2:
                continue

            step = self._build_comparison(evs, event_type, len(steps))
            steps.append(step)

    def _build_comparison(self, evs: list[Evidence], event_type: str, index: int) -> ReasoningStep:
        step_id = f"step_{index}"
        by_condition: dict[str, list[Evidence]] = {}
        for ev in evs:
            cond_str = self._format_condition(ev.condition)
            by_condition.setdefault(cond_str, []).append(ev)

        lines: list[str] = []
        for cond_str, group in by_condition.items():
            avg_ret = sum(e.average_return_pct for e in group) / len(group)
            avg_conf = sum(e.confidence for e in group) / len(group)
            lines.append(f"  {cond_str}: {avg_ret:+.3f}% avg return (confidence: {avg_conf:.3f})")

        condition_labels = list(by_condition.keys())
        if len(condition_labels) >= 2:
            returns = []
            for cond_str, group in by_condition.items():
                returns.append(sum(e.average_return_pct for e in group) / len(group))
            directions = ["positive" if r > 0 else "negative" if r < 0 else "flat" for r in returns]
            if all(d == directions[0] for d in directions):
                direction_summary = f"all conditions point in the same direction ({directions[0]})"
            else:
                pos = [c for c, r in zip(condition_labels, returns) if r > 0]
                neg = [c for c, r in zip(condition_labels, returns) if r < 0]
                parts = []
                if pos:
                    parts.append(f"{' and '.join(pos)} show positive returns")
                if neg:
                    parts.append(f"{' and '.join(neg)} show negative returns")
                direction_summary = "; ".join(parts)

        conclusion = (
            f"Comparing conditions within {event_type}:\n" + "\n".join(lines)
        )
        if len(condition_labels) >= 2:
            conclusion += f"\n{direction_summary}."

        return ReasoningStep(
            step_id=step_id,
            step_type=STEP_COMPARISON,
            conclusion=conclusion,
            confidence=self._average_confidence(evs),
            supporting_evidence_ids=tuple(e.evidence_id for e in evs),
            details={
                "event_type": event_type,
                "condition_groups": {
                    cond: [e.evidence_id for e in group]
                    for cond, group in by_condition.items()
                },
                "evidence_count": len(evs),
            },
        )

    def _build_aggregation(self, evidence: EvidenceCollection, steps: list[ReasoningStep], index: int) -> ReasoningStep:
        step_id = f"step_{index}"
        agg = evidence.aggregate()
        avg_ret = agg["avg_return_pct"]
        avg_conf = agg["avg_confidence"]
        direction = "positive" if avg_ret > 0 else "negative" if avg_ret < 0 else "flat"
        all_ids = tuple(e.evidence_id for e in evidence)

        conclusion = (
            f"Across {agg['count']} evidence items, the average return is {avg_ret:+.6f}% "
            f"({direction}) with mean confidence of {avg_conf:.6f} "
            f"and average sample count of {agg['avg_sample_count']}."
        )
        return ReasoningStep(
            step_id=step_id,
            step_type=STEP_AGGREGATION,
            conclusion=conclusion,
            confidence=avg_conf,
            supporting_evidence_ids=all_ids,
            details=dict(agg),
        )

    def _build_conclusion(self, evidence: EvidenceCollection, context: ReasoningContext, steps: list[ReasoningStep], index: int) -> ReasoningStep:
        step_id = f"step_{index}"
        avg_ret = evidence.aggregate()["avg_return_pct"]
        avg_conf = evidence.aggregate()["avg_confidence"]

        if avg_ret > 0.5:
            direction = "positive directional bias"
        elif avg_ret < -0.5:
            direction = "negative directional bias"
        elif avg_ret > 0:
            direction = "modestly positive"
        elif avg_ret < 0:
            direction = "modestly negative"
        else:
            direction = "neutral"

        context_desc = f"{context.event_type}"
        if context.condition:
            context_desc += f" condition {self._format_condition(context.condition)}"
        if context.horizon_days is not None:
            context_desc += f" over {context.horizon_days} days"

        step_ids = tuple(s.step_id for s in steps)
        all_evidence_ids = tuple(e.evidence_id for e in evidence)

        conclusion = (
            f"For {context_desc}, the evidence indicates {direction} "
            f"(aggregate confidence: {avg_conf:.3f}, "
            f"based on {len(evidence)} evidence items)."
        )
        return ReasoningStep(
            step_id=step_id,
            step_type=STEP_CONCLUSION,
            conclusion=conclusion,
            confidence=avg_conf,
            supporting_evidence_ids=all_evidence_ids,
            details={
                "context_event_type": context.event_type,
                "context_condition": context.condition,
                "context_horizon_days": context.horizon_days,
                "average_return_pct": avg_ret,
                "direction": direction,
            },
        )

    def _compute_overall_confidence(self, evidence: EvidenceCollection) -> float:
        if not evidence:
            return 0.0
        return round(
            sum(e.confidence for e in evidence) / len(evidence), 6
        )

    def _format_condition(self, condition: dict[str, str]) -> str:
        if not condition:
            return "any"
        return "; ".join(f"{k}={v}" for k, v in condition.items())

    def _average_confidence(self, evs: list[Evidence]) -> float:
        if not evs:
            return 0.0
        return round(sum(e.confidence for e in evs) / len(evs), 6)

    def _build_chain_id(self, context: ReasoningContext) -> str:
        parts = ["reason", context.event_type]
        if context.condition:
            for v in context.condition.values():
                parts.append(v.replace(" ", "_"))
        if context.horizon_days is not None:
            parts.append(str(context.horizon_days))
        return "_".join(parts)
