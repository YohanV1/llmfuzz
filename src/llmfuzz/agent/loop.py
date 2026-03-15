"""Core agent loop - orchestrates the analyze/generate/execute/reflect cycle."""

from __future__ import annotations

import json
import uuid
from collections.abc import Callable
from datetime import datetime, timezone
from typing import Any

import anthropic

from llmfuzz.agent.memory import AgentMemory
from llmfuzz.agent.prompts import (
    INPUT_GENERATION_TOOL,
    SYSTEM_PROMPT,
    build_coverage_guided_prompt,
    build_initial_prompt,
    build_signature_text,
)
from llmfuzz.agent.strategy import FuzzStrategy, select_strategy
from llmfuzz.coverage.analyzer import CoverageAnalyzer
from llmfuzz.coverage.collector import CoverageCollector
from llmfuzz.execution.runner import FuzzRunner
from llmfuzz.execution.sandbox import SandboxExecutor
from llmfuzz.models.execution import CrashReport, ExecutionOutcome
from llmfuzz.models.input import TestInput
from llmfuzz.models.session import FuzzSession
from llmfuzz.models.target import FuzzTarget


async def run_agent_loop(
    target: FuzzTarget,
    client: anthropic.AsyncAnthropic,
    max_iterations: int = 20,
    batch_size: int = 10,
    timeout_per_input: float = 5.0,
    model: str = "claude-sonnet-4-20250514",
    on_iteration: Callable[[FuzzSession, int], Any] | None = None,
) -> FuzzSession:
    """Run the full fuzzing agent loop on a target function.

    This is the core of the system: analyze code → generate inputs →
    execute → observe coverage → generate smarter inputs.
    """
    memory = AgentMemory(target.target_id)
    collector = CoverageCollector(target)
    collector.analyze_totals()
    analyzer = CoverageAnalyzer(target, collector)
    sandbox = SandboxExecutor(timeout_s=timeout_per_input)
    runner = FuzzRunner(target, sandbox, collector)

    session = FuzzSession(
        session_id=uuid.uuid4().hex,
        target_id=target.target_id,
    )

    sig_text = build_signature_text(target)

    for iteration in range(max_iterations):
        strategy = select_strategy(memory, iteration)

        # Build the prompt
        if iteration == 0:
            prompt = build_initial_prompt(
                module_path=target.module_path,
                function_name=target.function_name,
                source_code=target.signature.source_code,
                start_line=target.signature.start_line,
                end_line=target.signature.end_line,
                source_file=target.source_file,
                signature_text=sig_text,
                docstring=target.signature.docstring,
                batch_size=batch_size,
            )
        else:
            snapshot = collector.get_snapshot(iteration)
            gaps_text = analyzer.format_gaps_for_prompt(max_gaps=10, iteration=iteration)
            memory_summary = memory.summarize_for_prompt()

            prompt = build_coverage_guided_prompt(
                module_path=target.module_path,
                function_name=target.function_name,
                source_code=target.signature.source_code,
                start_line=target.signature.start_line,
                end_line=target.signature.end_line,
                source_file=target.source_file,
                signature_text=sig_text,
                iteration=iteration,
                branch_pct=snapshot.branch_coverage_pct,
                line_pct=snapshot.line_coverage_pct,
                branches_covered=snapshot.branches_covered,
                branches_total=snapshot.branches_total,
                lines_covered=snapshot.lines_covered,
                lines_total=snapshot.lines_total,
                coverage_gaps=gaps_text,
                memory_summary=memory_summary,
                strategy=strategy.value,
                batch_size=batch_size,
            )

        # Call the LLM
        inputs = await _call_llm(client, model, prompt, target.target_id, strategy.value)

        if not inputs:
            # LLM returned no inputs - try once more with explicit instruction
            inputs = await _call_llm(
                client, model,
                prompt + "\n\nYou MUST generate at least 1 test input. Try harder.",
                target.target_id, strategy.value,
            )

        if not inputs:
            continue

        # Execute all inputs
        results = await runner.execute_batch(inputs)

        # Update coverage and memory
        coverage = collector.get_snapshot(iteration)
        memory.record_iteration(iteration, inputs, results, coverage, strategy.value)

        session.iteration = iteration + 1
        session.inputs_generated += len(inputs)
        session.coverage_snapshots.append(coverage)

        # Record crashes (deduplicated by exception type + message)
        seen_crashes = {
            (c.exception_type, c.exception_message) for c in session.crashes
        }
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
                    reproducer_code=_build_reproducer(target, inp),
                    first_seen_at=datetime.now(timezone.utc),
                    iteration=iteration,
                )
                session.crashes.append(crash)

        # Check for plateau
        if memory.get_coverage_plateau_detected(window=3) and iteration >= 5:
            session.plateau_detected = True
            break

        if on_iteration:
            await on_iteration(session, iteration)

    session.completed_at = datetime.now(timezone.utc)
    return session


async def _call_llm(
    client: anthropic.AsyncAnthropic,
    model: str,
    prompt: str,
    target_id: str,
    strategy: str,
) -> list[TestInput]:
    """Call Claude to generate test inputs."""
    try:
        response = await client.messages.create(
            model=model,
            max_tokens=4096,
            system=SYSTEM_PROMPT,
            tools=[INPUT_GENERATION_TOOL],
            tool_choice={"type": "tool", "name": "generate_test_inputs"},
            messages=[{"role": "user", "content": prompt}],
        )
    except anthropic.APIError:
        return []

    # Extract tool use from response
    for block in response.content:
        if block.type == "tool_use" and block.name == "generate_test_inputs":
            return _parse_tool_inputs(block.input, target_id, strategy)

    return []


def _parse_tool_inputs(
    tool_input: dict,
    target_id: str,
    strategy: str,
) -> list[TestInput]:
    """Parse the LLM's tool response into TestInput objects."""
    inputs: list[TestInput] = []
    raw_inputs = tool_input.get("inputs", [])

    for raw in raw_inputs:
        if not isinstance(raw, dict):
            continue

        args = raw.get("args", [])
        kwargs = raw.get("kwargs", {})

        if not isinstance(args, list):
            args = [args]
        if not isinstance(kwargs, dict):
            kwargs = {}

        # Validate that args and kwargs are JSON-serializable
        try:
            json.dumps(args)
            json.dumps(kwargs)
        except (TypeError, ValueError):
            continue

        inputs.append(TestInput(
            target_id=target_id,
            args=args,
            kwargs=kwargs,
            generation_strategy=strategy,
            rationale=raw.get("rationale"),
        ))

    return inputs


def _build_reproducer(target: FuzzTarget, inp: TestInput) -> str:
    """Build a standalone Python script to reproduce a crash."""
    args_repr = ", ".join(repr(a) for a in inp.args)
    kwargs_repr = ", ".join(f"{k}={v!r}" for k, v in inp.kwargs.items())
    all_args = ", ".join(filter(None, [args_repr, kwargs_repr]))

    return f"""\
#!/usr/bin/env python3
\"\"\"Reproducer for crash in {target.qualified_name}\"\"\"
from {target.module_path} import {target.function_name}

# This input caused an exception:
result = {target.function_name}({all_args})
"""
