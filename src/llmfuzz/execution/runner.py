"""Orchestrates batch execution of test inputs with coverage collection."""

from __future__ import annotations

import tempfile
from pathlib import Path

from llmfuzz.coverage.collector import CoverageCollector
from llmfuzz.execution.sandbox import SandboxExecutor
from llmfuzz.models.execution import ExecutionOutcome, ExecutionResult
from llmfuzz.models.input import TestInput
from llmfuzz.models.target import FuzzTarget


class FuzzRunner:
    def __init__(
        self,
        target: FuzzTarget,
        sandbox: SandboxExecutor,
        collector: CoverageCollector,
    ):
        self.target = target
        self.sandbox = sandbox
        self.collector = collector

    async def execute_batch(self, inputs: list[TestInput]) -> list[ExecutionResult]:
        """Execute all inputs sequentially, collecting coverage for each."""
        results: list[ExecutionResult] = []

        for inp in inputs:
            with tempfile.TemporaryDirectory() as cov_dir:
                result = await self.sandbox.execute(self.target, inp, cov_dir)

                # Collect coverage if execution didn't timeout
                if result.outcome != ExecutionOutcome.TIMEOUT:
                    cov_file = Path(cov_dir) / f".coverage.{inp.input_id}"
                    if cov_file.exists():
                        lines, branches = self.collector.collect_from_data_file(str(cov_file))
                        new_lines, new_branches = self.collector.merge_and_compute_new(
                            lines, branches
                        )
                        result.lines_covered = sorted(lines)
                        result.branches_covered = sorted(branches)
                        result.new_lines_covered = sorted(new_lines)
                        result.new_branches_covered = sorted(new_branches)

                results.append(result)

        return results
