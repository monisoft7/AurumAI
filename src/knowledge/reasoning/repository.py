import json
from pathlib import Path

from knowledge.reasoning.context import ReasoningContext
from knowledge.reasoning.step import ReasoningStep
from knowledge.reasoning.chain import ReasoningChain
from knowledge.integrity.provenance import serialize_provenance, deserialize_provenance


class ReasoningRepository:
    def save(self, chain: ReasoningChain, path: Path) -> None:
        payload = {
            "chain_id": chain.chain_id,
            "context": {
                "event_type": chain.context.event_type,
                "condition": chain.context.condition,
                "horizon_days": chain.context.horizon_days,
                "metadata": chain.context.metadata,
            },
            "steps": [
                {
                    "step_id": s.step_id,
                    "step_type": s.step_type,
                    "conclusion": s.conclusion,
                    "confidence": s.confidence,
                    "supporting_evidence_ids": list(s.supporting_evidence_ids),
                    "details": s.details,
                }
                for s in chain.steps
            ],
            "final_conclusion": chain.final_conclusion,
            "overall_confidence": chain.overall_confidence,
            "evidence_count": chain.evidence_count,
            "provenance": serialize_provenance(chain.provenance),
            "metadata": chain.metadata,
        }
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, indent=2))

    def load(self, path: Path) -> ReasoningChain:
        payload = json.loads(path.read_text())
        context_data = payload.get("context", {})
        context = ReasoningContext(
            event_type=context_data.get("event_type", ""),
            condition=context_data.get("condition"),
            horizon_days=context_data.get("horizon_days"),
            metadata=context_data.get("metadata", {}),
        )
        steps = []
        for s_data in payload.get("steps", []):
            steps.append(ReasoningStep(
                step_id=s_data["step_id"],
                step_type=s_data["step_type"],
                conclusion=s_data["conclusion"],
                confidence=s_data.get("confidence", 0.0),
                supporting_evidence_ids=tuple(s_data.get("supporting_evidence_ids", [])),
                details=s_data.get("details", {}),
            ))
        return ReasoningChain(
            chain_id=payload["chain_id"],
            context=context,
            steps=tuple(steps),
            final_conclusion=payload.get("final_conclusion", ""),
            overall_confidence=payload.get("overall_confidence", 0.0),
            evidence_count=payload.get("evidence_count", 0),
            provenance=deserialize_provenance(payload.get("provenance")),
            metadata=payload.get("metadata", {}),
        )
