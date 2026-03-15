"""Random/mutation-based fuzzer for baseline comparison."""

from __future__ import annotations

import random
import sys
import uuid
from datetime import datetime, timezone

from llmfuzz.coverage.collector import CoverageCollector
from llmfuzz.execution.runner import FuzzRunner
from llmfuzz.execution.sandbox import SandboxExecutor
from llmfuzz.models.coverage import CoverageSnapshot
from llmfuzz.models.execution import CrashReport, ExecutionOutcome
from llmfuzz.models.input import TestInput
from llmfuzz.models.session import FuzzSession
from llmfuzz.models.target import FuzzTarget

# Type-aware random generators
_GENERATORS: dict[str, list] = {
    "int": [0, 1, -1, 42, -42, 2**31, -(2**31), 2**63, 0, 100, -100, 999999],
    "float": [0.0, 1.0, -1.0, 0.5, -0.5, 1e10, -1e10, 1e-10, float("inf"), float("-inf"), float("nan")],
    "str": ["", "a", "hello", "hello world", " ", "\n", "\t", "\x00", "x" * 100, "123", "true", "null", "<script>"],
    "bool": [True, False],
    "list": [[], [1], [1, 2, 3], list(range(20)), [None], ["a", "b"], [[1, 2], [3, 4]], [0] * 100],
    "dict": [{}, {"a": 1}, {"key": "value"}, {"nested": {"a": 1}}, {str(i): i for i in range(10)}],
    "None": [None],
}

# Fallback generator for unknown types
_FALLBACK = [None, 0, 1, -1, "", "test", [], {}, True, False, 0.0, 42]


def _random_value(annotation: str | None) -> object:
    """Generate a random value based on type annotation."""
    if annotation is None:
        return random.choice(_FALLBACK)

    # Strip Optional, | None, etc.
    clean = annotation.replace("Optional[", "").replace("]", "").strip()
    clean = clean.split("|")[0].strip()

    pool = _GENERATORS.get(clean, _FALLBACK)
    return random.choice(pool)


async def run_random_fuzzer(
    target: FuzzTarget,
    total_inputs: int = 200,
    batch_size: int = 10,
    timeout_per_input: float = 5.0,
) -> FuzzSession:
    """Run random fuzzing and return a FuzzSession for comparison."""
    collector = CoverageCollector(target)
    collector.analyze_totals()
    sandbox = SandboxExecutor(timeout_s=timeout_per_input)
    runner = FuzzRunner(target, sandbox, collector)

    session = FuzzSession(
        session_id=uuid.uuid4().hex,
        target_id=target.target_id,
    )

    num_batches = (total_inputs + batch_size - 1) // batch_size

    seen_crashes: set[tuple[str, str]] = set()

    for batch_idx in range(num_batches):
        remaining = total_inputs - session.inputs_generated
        current_batch_size = min(batch_size, remaining)
        if current_batch_size <= 0:
            break

        inputs: list[TestInput] = []
        for _ in range(current_batch_size):
            args = []
            for param in target.signature.parameters:
                args.append(_random_value(param.annotation))
            inputs.append(TestInput(
                target_id=target.target_id,
                args=args,
                kwargs={},
                generation_strategy="random",
                rationale="randomly generated",
            ))

        results = await runner.execute_batch(inputs)
        snapshot = collector.get_snapshot(batch_idx)
        session.coverage_snapshots.append(snapshot)
        session.inputs_generated += len(inputs)
        session.iteration = batch_idx + 1

        # Record crashes (deduplicated by exception type + message)
        for inp, result in zip(inputs, results):
            if result.outcome in (ExecutionOutcome.EXCEPTION, ExecutionOutcome.CRASH):
                crash_key = (result.exception_type or "Unknown", result.exception_message or "")
                if crash_key in seen_crashes:
                    continue
                seen_crashes.add(crash_key)
                crash = CrashReport(
                    crash_id=uuid.uuid4().hex[:12],
                    target_id=target.target_id,
                    input=inp,
                    outcome=result.outcome,
                    exception_type=result.exception_type or "Unknown",
                    exception_message=result.exception_message or "",
                    traceback=result.traceback or "",
                    reproducer_code=f"# Random input: {inp.as_call_repr()}",
                    first_seen_at=datetime.now(timezone.utc),
                    iteration=batch_idx,
                )
                session.crashes.append(crash)

    session.completed_at = datetime.now(timezone.utc)
    return session
