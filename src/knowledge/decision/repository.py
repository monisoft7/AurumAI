import json
from pathlib import Path

from knowledge.decision.context import DecisionContext
from knowledge.decision.decision import Decision


class DecisionRepository:
    def save(self, decision: Decision, path: Path) -> None:
        payload = {
            "decision_id": decision.decision_id,
            "decision_type": decision.decision_type,
            "confidence": decision.confidence,
            "reasoning_chain_id": decision.reasoning_chain_id,
            "evidence_count": decision.evidence_count,
            "explanation": decision.explanation,
            "context": {
                "event_type": decision.context.event_type,
                "query": decision.context.query,
                "metadata": decision.context.metadata,
            },
            "metadata": decision.metadata,
        }
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, indent=2))

    def load(self, path: Path) -> Decision:
        payload = json.loads(path.read_text())
        ctx_data = payload.get("context", {})
        context = DecisionContext(
            event_type=ctx_data.get("event_type", ""),
            query=ctx_data.get("query", ""),
            metadata=ctx_data.get("metadata", {}),
        )
        return Decision(
            decision_id=payload["decision_id"],
            decision_type=payload["decision_type"],
            confidence=payload.get("confidence", 0.0),
            reasoning_chain_id=payload.get("reasoning_chain_id", ""),
            evidence_count=payload.get("evidence_count", 0),
            explanation=payload.get("explanation", ""),
            context=context,
            metadata=payload.get("metadata", {}),
        )
