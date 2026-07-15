from dataclasses import dataclass, field
from typing import Any

from knowledge.decision.decision import Decision
from knowledge.reasoning.chain import ReasoningChain
from knowledge.evidence.collection import EvidenceCollection
from knowledge.graph.graph import KnowledgeGraph
from knowledge.pipeline.context import PipelineContext


@dataclass
class PipelineStage:
    name: str
    output: Any
    duration_ms: float
    references: dict[str, str] = field(default_factory=dict)


class PipelineResult:
    def __init__(self, context: PipelineContext):
        self.context = context
        self.stages: list[PipelineStage] = []

    def add_stage(
        self,
        name: str,
        output: Any,
        duration_ms: float,
        references: dict[str, str] | None = None,
    ) -> None:
        self.stages.append(
            PipelineStage(name, output, duration_ms, references or {})
        )

    @property
    def lessons(self) -> Any:
        return self._stage_output("build_lessons")

    @property
    def knowledge_summary(self) -> Any:
        return self._stage_output("build_knowledge")

    @property
    def knowledge_graph(self) -> KnowledgeGraph | None:
        out = self._stage_output("build_graph")
        return out if isinstance(out, KnowledgeGraph) else None

    @property
    def evidence(self) -> EvidenceCollection | None:
        out = self._stage_output("query_evidence")
        return out if isinstance(out, EvidenceCollection) else None

    @property
    def reasoning_chain(self) -> ReasoningChain | None:
        out = self._stage_output("reason")
        return out if isinstance(out, ReasoningChain) else None

    @property
    def decision(self) -> Decision | None:
        out = self._stage_output("decide")
        return out if isinstance(out, Decision) else None

    def _stage_output(self, name: str) -> Any:
        for s in reversed(self.stages):
            if s.name == name:
                return s.output
        return None

    @property
    def stages_completed(self) -> list[str]:
        return [s.name for s in self.stages]
