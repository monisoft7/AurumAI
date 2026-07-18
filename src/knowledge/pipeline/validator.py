from __future__ import annotations

from knowledge.pipeline.result import PipelineResult
from knowledge.decision.decision import VALID_DECISION_TYPES


class PipelineValidator:
    @staticmethod
    def validate(result: PipelineResult) -> dict[str, list[str]]:
        errors: dict[str, list[str]] = {}

        stages = result.stages_completed
        expected_order = [
            "build_lessons",
            "build_knowledge",
        ]
        if "compare_context" in stages:
            expected_order.append("compare_context")
        expected_order.extend([
            "build_graph",
            "query_evidence",
            "reason",
            "decide",
        ])

        for i, expected in enumerate(expected_order):
            if expected not in stages:
                errors.setdefault("missing_stages", []).append(
                    f"Stage '{expected}' not found in pipeline result."
                )
            elif stages.index(expected) != i:
                actual_pos = stages.index(expected)
                errors.setdefault("stage_order", []).append(
                    f"Stage '{expected}' at position {actual_pos}, expected {i}."
                )

        unexpected = [stage for stage in stages if stage not in expected_order]
        if unexpected:
            errors["unexpected_stages"] = [
                f"Unexpected stage '{stage}'." for stage in unexpected
            ]

        for stage in stages:
            s = next(s for s in result.stages if s.name == stage)
            if s.output is None:
                errors.setdefault("empty_stage_output", []).append(
                    f"Stage '{stage}' has None output."
                )

        decision = result.decision
        if decision is not None:
            if decision.decision_type not in VALID_DECISION_TYPES:
                errors.setdefault("invalid_decision_type", []).append(
                    f"Decision type '{decision.decision_type}' is not valid."
                )
            chain = result.reasoning_chain
            if chain is not None:
                if decision.reasoning_chain_id != chain.chain_id:
                    errors.setdefault("chain_mismatch", []).append(
                        f"Decision references chain '{decision.reasoning_chain_id}' "
                        f"but pipeline chain is '{chain.chain_id}'."
                    )
                evidence = result.evidence
                if evidence is not None and chain.evidence_count != len(evidence):
                    errors.setdefault("evidence_count_mismatch", []).append(
                        f"Chain reports {chain.evidence_count} evidence items "
                        f"but collection has {len(evidence)}."
                    )

        return errors

    @staticmethod
    def is_valid(result: PipelineResult) -> bool:
        return not any(PipelineValidator.validate(result).values())
