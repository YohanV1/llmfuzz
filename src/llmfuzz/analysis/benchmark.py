"""Benchmark runner - compares LLM-guided vs random fuzzing."""

from __future__ import annotations

from dataclasses import dataclass

import anthropic

from llmfuzz.agent.loop import run_agent_loop
from llmfuzz.coverage.visualizer import plot_comparison
from llmfuzz.models.session import FuzzSession
from llmfuzz.models.target import FuzzTarget
from llmfuzz.random_fuzzer.baseline import run_random_fuzzer


@dataclass
class BenchmarkResult:
    target: FuzzTarget
    llm_session: FuzzSession
    random_session: FuzzSession

    @property
    def llm_final_branch_pct(self) -> float:
        if self.llm_session.coverage_snapshots:
            return self.llm_session.coverage_snapshots[-1].branch_coverage_pct
        return 0.0

    @property
    def random_final_branch_pct(self) -> float:
        if self.random_session.coverage_snapshots:
            return self.random_session.coverage_snapshots[-1].branch_coverage_pct
        return 0.0

    @property
    def llm_wins(self) -> bool:
        return self.llm_final_branch_pct > self.random_final_branch_pct


async def run_benchmark(
    target: FuzzTarget,
    client: anthropic.AsyncAnthropic,
    llm_iterations: int = 20,
    batch_size: int = 10,
    timeout_per_input: float = 5.0,
    model: str = "claude-sonnet-4-20250514",
    output_dir: str = "./benchmark_results",
) -> BenchmarkResult:
    """Run LLM-guided vs random fuzzing comparison."""
    total_llm_inputs = llm_iterations * batch_size

    # Run LLM-guided fuzzing
    llm_session = await run_agent_loop(
        target=target,
        client=client,
        max_iterations=llm_iterations,
        batch_size=batch_size,
        timeout_per_input=timeout_per_input,
        model=model,
    )

    # Run random fuzzing with same input budget
    random_session = await run_random_fuzzer(
        target=target,
        total_inputs=total_llm_inputs,
        batch_size=batch_size,
        timeout_per_input=timeout_per_input,
    )

    result = BenchmarkResult(
        target=target,
        llm_session=llm_session,
        random_session=random_session,
    )

    # Generate comparison chart
    llm_progression = [
        s.branch_coverage_pct for s in llm_session.coverage_snapshots
    ]
    random_progression = [
        s.branch_coverage_pct for s in random_session.coverage_snapshots
    ]

    plot_comparison(
        llm_progression=llm_progression,
        random_progression=random_progression,
        target_name=target.qualified_name,
        output_path=f"{output_dir}/{target.target_id}_comparison.png",
        llm_inputs=llm_session.inputs_generated,
        random_inputs=random_session.inputs_generated,
    )

    return result
