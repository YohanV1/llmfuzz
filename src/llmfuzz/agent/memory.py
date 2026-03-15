"""Agent memory — tracks what has been tried, what worked, what didn't."""

from __future__ import annotations

from dataclasses import dataclass, field

from llmfuzz.models.coverage import CoverageSnapshot
from llmfuzz.models.execution import ExecutionOutcome, ExecutionResult
from llmfuzz.models.input import TestInput


@dataclass
class IterationRecord:
    iteration: int
    inputs: list[TestInput]
    results: list[ExecutionResult]
    coverage: CoverageSnapshot
    new_lines: int
    new_branches: int
    strategy: str


class AgentMemory:
    def __init__(self, target_id: str):
        self.target_id = target_id
        self.iterations: list[IterationRecord] = []
        self.all_inputs: list[TestInput] = []
        self.successful_patterns: list[str] = []
        self.failed_patterns: list[str] = []

    def record_iteration(
        self,
        iteration: int,
        inputs: list[TestInput],
        results: list[ExecutionResult],
        coverage: CoverageSnapshot,
        strategy: str,
    ) -> None:
        new_lines = sum(len(r.new_lines_covered) for r in results)
        new_branches = sum(len(r.new_branches_covered) for r in results)

        record = IterationRecord(
            iteration=iteration,
            inputs=inputs,
            results=results,
            coverage=coverage,
            new_lines=new_lines,
            new_branches=new_branches,
            strategy=strategy,
        )
        self.iterations.append(record)
        self.all_inputs.extend(inputs)

        # Track which inputs found new coverage
        for inp, res in zip(inputs, results):
            if res.new_lines_covered or res.new_branches_covered:
                self.successful_patterns.append(
                    f"{inp.generation_strategy}: {inp.as_call_repr()} "
                    f"-> {len(res.new_lines_covered)} new lines, "
                    f"{len(res.new_branches_covered)} new branches"
                )
            elif res.outcome == ExecutionOutcome.SUCCESS and not res.new_lines_covered:
                self.failed_patterns.append(
                    f"{inp.as_call_repr()} -> no new coverage"
                )

    def get_coverage_plateau_detected(self, window: int = 3) -> bool:
        """True if coverage hasn't improved in the last `window` iterations."""
        if len(self.iterations) < window:
            return False
        recent = self.iterations[-window:]
        return all(r.new_lines == 0 and r.new_branches == 0 for r in recent)

    def summarize_for_prompt(self, max_items: int = 15) -> str:
        """Produce a concise summary for the LLM prompt."""
        if not self.iterations:
            return "No previous attempts."

        sections: list[str] = []

        # Recent iterations summary
        for record in self.iterations[-5:]:
            crash_count = sum(
                1 for r in record.results
                if r.outcome in (ExecutionOutcome.EXCEPTION, ExecutionOutcome.CRASH)
            )
            sections.append(
                f"- Iteration {record.iteration} ({record.strategy}): "
                f"{len(record.inputs)} inputs, "
                f"+{record.new_lines} lines, +{record.new_branches} branches, "
                f"{crash_count} exceptions"
            )

        # Successful patterns
        if self.successful_patterns:
            sections.append("\n**Inputs that found new coverage:**")
            for p in self.successful_patterns[-max_items:]:
                sections.append(f"  - {p}")

        # Failed patterns (abbreviated)
        if self.failed_patterns:
            sections.append(
                f"\n**{len(self.failed_patterns)} inputs produced no new coverage** "
                f"(avoid similar patterns)"
            )

        return "\n".join(sections)
