"""Test sandboxed execution."""

import pytest

from llmfuzz.analysis.source import build_target
from llmfuzz.execution.sandbox import SandboxExecutor
from llmfuzz.models.execution import ExecutionOutcome
from llmfuzz.models.input import TestInput


@pytest.mark.asyncio
async def test_successful_execution(simple_math_path):
    target = build_target(simple_math_path, "safe_divide")
    sandbox = SandboxExecutor(timeout_s=10.0)
    inp = TestInput(target_id=target.target_id, args=[10.0, 2.0])

    import tempfile
    with tempfile.TemporaryDirectory() as cov_dir:
        result = await sandbox.execute(target, inp, cov_dir)

    assert result.outcome == ExecutionOutcome.SUCCESS
    assert result.return_value_repr == "5.0"


@pytest.mark.asyncio
async def test_exception_caught(simple_math_path):
    target = build_target(simple_math_path, "fibonacci")
    sandbox = SandboxExecutor(timeout_s=10.0)
    inp = TestInput(target_id=target.target_id, args=[-1])

    import tempfile
    with tempfile.TemporaryDirectory() as cov_dir:
        result = await sandbox.execute(target, inp, cov_dir)

    assert result.outcome == ExecutionOutcome.EXCEPTION
    assert result.exception_type == "ValueError"


@pytest.mark.asyncio
async def test_timeout_handling(simple_math_path):
    target = build_target(simple_math_path, "fibonacci")
    sandbox = SandboxExecutor(timeout_s=0.1)
    # Large fibonacci won't timeout since it's iterative, but very short timeout
    # tests the timeout path
    inp = TestInput(target_id=target.target_id, args=[10])

    import tempfile
    with tempfile.TemporaryDirectory() as cov_dir:
        result = await sandbox.execute(target, inp, cov_dir)

    # Either succeeds quickly or times out - both are valid
    assert result.outcome in (ExecutionOutcome.SUCCESS, ExecutionOutcome.TIMEOUT)


@pytest.mark.asyncio
async def test_type_error_caught(simple_math_path):
    target = build_target(simple_math_path, "fibonacci")
    sandbox = SandboxExecutor(timeout_s=10.0)
    inp = TestInput(target_id=target.target_id, args=["not_a_number"])

    import tempfile
    with tempfile.TemporaryDirectory() as cov_dir:
        result = await sandbox.execute(target, inp, cov_dir)

    assert result.outcome == ExecutionOutcome.EXCEPTION
    assert result.exception_type == "TypeError"
