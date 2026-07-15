from __future__ import annotations

from knowledge.reasoning.chain import ReasoningChain
from knowledge.reasoning.step import STEP_AGGREGATION, STEP_CONCLUSION
from knowledge.decision.context import DecisionContext
from knowledge.decision.decision import (
    Decision,
    DECISION_STRONG_POSITIVE,
    DECISION_POSITIVE,
    DECISION_NEUTRAL,
    DECISION_NEGATIVE,
    DECISION_STRONG_NEGATIVE,
)


class DecisionEngine:
    def decide(
        self,
        chain: ReasoningChain,
        context: DecisionContext | None = None,
    ) -> Decision:
        ctx = context or DecisionContext(
            event_type=chain.context.event_type,
            query="",
        )
        avg_return = self._extract_avg_return(chain)
        confidence = chain.overall_confidence
        decision_type = self._classify(avg_return, confidence)
        explanation = self._build_explanation(
            decision_type, avg_return, confidence, chain
        )
        decision_id = f"dec_{chain.chain_id}"

        return Decision(
            decision_id=decision_id,
            decision_type=decision_type,
            confidence=confidence,
            reasoning_chain_id=chain.chain_id,
            evidence_count=chain.evidence_count,
            explanation=explanation,
            context=ctx,
            metadata={
                "avg_return_pct": avg_return,
                "chain_confidence": confidence,
            },
        )

    def _extract_avg_return(self, chain: ReasoningChain) -> float:
        for step in reversed(chain.steps):
            if step.step_type in (STEP_AGGREGATION, STEP_CONCLUSION):
                val = step.details.get("avg_return_pct")
                if val is not None:
                    return val
                val = step.details.get("average_return_pct")
                if val is not None:
                    return val
        return 0.0

    def _classify(self, avg_return: float, confidence: float) -> str:
        if avg_return > 1.0 and confidence >= 0.7:
            return DECISION_STRONG_POSITIVE
        if avg_return > 0 and confidence >= 0.5:
            return DECISION_POSITIVE
        if avg_return < -1.0 and confidence >= 0.7:
            return DECISION_STRONG_NEGATIVE
        if avg_return < 0 and confidence >= 0.5:
            return DECISION_NEGATIVE
        return DECISION_NEUTRAL

    def _build_explanation(
        self,
        decision_type: str,
        avg_return: float,
        confidence: float,
        chain: ReasoningChain,
    ) -> str:
        return (
            f"Decision {decision_type} based on reasoning chain '{chain.chain_id}': "
            f"aggregated evidence of {chain.evidence_count} items "
            f"shows average return of {avg_return:+.6f}% "
            f"with overall confidence of {confidence:.3f}."
        )
