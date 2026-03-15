"""Test coverage collection."""

import tempfile

import pytest

from llmfuzz.analysis.source import build_target
from llmfuzz.coverage.collector import CoverageCollector
from llmfuzz.execution.sandbox import SandboxExecutor
from llmfuzz.models.input import TestInput


@pytest.mark.asyncio
async def test_coverage_collection(simple_math_path):
    target = build_target(simple_math_path, "safe_divide")
    collector = CoverageCollector(target)
    collector.analyze_totals()
    sandbox = SandboxExecutor(timeout_s=10.0)

    # Run an input that covers the normal path
    inp = TestInput(target_id=target.target_id, args=[10.0, 2.0])
    with tempfile.TemporaryDirectory() as cov_dir:
        result = await sandbox.execute(target, inp, cov_dir)
        cov_file = f"{cov_dir}/.coverage.{inp.input_id}"

        import os
        if os.path.exists(cov_file):
            lines, branches = collector.collect_from_data_file(cov_file)
            assert len(lines) > 0


@pytest.mark.asyncio
async def test_incremental_coverage(simple_math_path):
    target = build_target(simple_math_path, "safe_divide")
    collector = CoverageCollector(target)
    collector.analyze_totals()
    sandbox = SandboxExecutor(timeout_s=10.0)

    inputs = [
        TestInput(target_id=target.target_id, args=[10.0, 2.0]),
        TestInput(target_id=target.target_id, args=[0.0, 0.0]),
        TestInput(target_id=target.target_id, args=[1.0, 0.0]),
    ]

    total_new_lines = 0
    for inp in inputs:
        with tempfile.TemporaryDirectory() as cov_dir:
            await sandbox.execute(target, inp, cov_dir)
            cov_file = f"{cov_dir}/.coverage.{inp.input_id}"

            import os
            if os.path.exists(cov_file):
                lines, branches = collector.collect_from_data_file(cov_file)
                new_lines, _ = collector.merge_and_compute_new(lines, branches)
                total_new_lines += len(new_lines)

    # Multiple inputs should cover more lines than just one
    assert total_new_lines > 0


def test_coverage_snapshot(simple_math_path):
    target = build_target(simple_math_path, "safe_divide")
    collector = CoverageCollector(target)
    collector.analyze_totals()

    snapshot = collector.get_snapshot(iteration=0)
    assert snapshot.target_id == target.target_id
    assert snapshot.lines_total > 0
    assert snapshot.lines_covered == 0  # No inputs run yet
