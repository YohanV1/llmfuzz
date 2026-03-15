"""Sandboxed subprocess execution with timeout and crash detection."""

from __future__ import annotations

import asyncio
import json
import os
import sys
import tempfile
import time
from pathlib import Path

from llmfuzz.execution.harness_template import render_harness
from llmfuzz.models.execution import ExecutionOutcome, ExecutionResult
from llmfuzz.models.input import TestInput
from llmfuzz.models.target import FuzzTarget

RESULT_MARKER = "__LLMFUZZ_RESULT__"


class SandboxExecutor:
    def __init__(self, timeout_s: float = 5.0):
        self.timeout_s = timeout_s

    async def execute(
        self,
        target: FuzzTarget,
        test_input: TestInput,
        coverage_dir: str,
    ) -> ExecutionResult:
        """Run a single test input in a sandboxed subprocess."""
        coverage_file = os.path.join(coverage_dir, f".coverage.{test_input.input_id}")
        source_dir = str(Path(target.source_file).parent)
        project_root = self._find_project_root(target.source_file)

        # Figure out the simple function name for the harness
        # qualified_name might be "module.ClassName.method" — we need "ClassName.method"
        qualified = target.qualified_name
        module_prefix = target.module_path + "."
        if qualified.startswith(module_prefix):
            func_name = qualified[len(module_prefix):]
        else:
            func_name = target.function_name

        harness_code = render_harness(
            project_root=project_root,
            source_file=target.source_file,
            source_dir=source_dir,
            module_path=target.module_path,
            function_name=func_name,
            args_json=json.dumps(test_input.args),
            kwargs_json=json.dumps(test_input.kwargs),
            coverage_data_file=coverage_file,
        )

        start = time.perf_counter()
        try:
            proc = await asyncio.create_subprocess_exec(
                sys.executable, "-c", harness_code,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
            )
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(), timeout=self.timeout_s
            )
            duration_ms = (time.perf_counter() - start) * 1000
        except (asyncio.TimeoutError, TimeoutError):
            try:
                proc.kill()
            except ProcessLookupError:
                pass
            await proc.wait()
            duration_ms = (time.perf_counter() - start) * 1000
            return ExecutionResult(
                input_id=test_input.input_id,
                target_id=target.target_id,
                outcome=ExecutionOutcome.TIMEOUT,
                duration_ms=duration_ms,
            )

        stdout_str = stdout.decode("utf-8", errors="replace")

        # Parse result from stdout
        if RESULT_MARKER in stdout_str:
            result_json_str = stdout_str.split(RESULT_MARKER, 1)[1].strip()
            try:
                result_data = json.loads(result_json_str)
            except json.JSONDecodeError:
                return ExecutionResult(
                    input_id=test_input.input_id,
                    target_id=target.target_id,
                    outcome=ExecutionOutcome.CRASH,
                    exception_message="Failed to parse harness output",
                    duration_ms=duration_ms,
                )

            outcome = ExecutionOutcome(result_data["outcome"])
            return ExecutionResult(
                input_id=test_input.input_id,
                target_id=target.target_id,
                outcome=outcome,
                return_value_repr=result_data.get("return_value"),
                exception_type=result_data.get("exception_type"),
                exception_message=result_data.get("exception_message"),
                traceback=result_data.get("traceback"),
                duration_ms=result_data.get("duration_ms", duration_ms),
            )

        # No result marker — process crashed
        return ExecutionResult(
            input_id=test_input.input_id,
            target_id=target.target_id,
            outcome=ExecutionOutcome.CRASH,
            exception_message=stderr.decode("utf-8", errors="replace")[:2000],
            duration_ms=duration_ms,
        )

    def _find_project_root(self, source_file: str) -> str:
        """Walk up from source file to find the project root (dir without __init__.py)."""
        path = Path(source_file).resolve().parent
        while (path / "__init__.py").exists() and path.parent != path:
            path = path.parent
        return str(path)
