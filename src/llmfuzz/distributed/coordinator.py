"""Distributed fuzzing coordinator — assigns targets, aggregates results."""

from __future__ import annotations

import uuid

import redis.asyncio as redis
from rich.console import Console

from llmfuzz.distributed.streams import (
    COORDINATOR_GROUP,
    RESULT_STREAM,
    TASK_STREAM,
    RedisStreamConsumer,
    RedisStreamProducer,
)
from llmfuzz.models.coverage import CoverageSnapshot
from llmfuzz.models.target import FuzzTarget
from llmfuzz.models.task import FuzzTask, TaskResult

console = Console()


class FuzzCoordinator:
    def __init__(
        self,
        redis_url: str = "redis://localhost:6379",
        max_iterations: int = 20,
    ):
        self.redis_client = redis.from_url(redis_url)
        self.max_iterations = max_iterations
        self.task_producer = RedisStreamProducer(self.redis_client, TASK_STREAM)
        self.result_consumer = RedisStreamConsumer(
            self.redis_client, RESULT_STREAM, COORDINATOR_GROUP, "coord-0"
        )
        self.active_tasks: dict[str, FuzzTask] = {}
        self.completed_results: dict[str, TaskResult] = {}
        self.global_coverage: dict[str, CoverageSnapshot] = {}

    async def submit_targets(self, targets: list[FuzzTarget]) -> None:
        """Create and publish fuzzing tasks for a list of targets."""
        for target in targets:
            task = FuzzTask(
                task_id=uuid.uuid4().hex,
                target=target,
                max_iterations=self.max_iterations,
            )
            await self.task_producer.publish(task)
            self.active_tasks[task.task_id] = task
            console.print(
                f"[bold]Submitted:[/bold] {target.qualified_name} "
                f"(task {task.task_id[:12]})"
            )

    async def monitor_results(self) -> list[TaskResult]:
        """Wait for all active tasks to complete. Returns all results."""
        await self.result_consumer.ensure_group()
        results: list[TaskResult] = []

        while self.active_tasks:
            messages = await self.result_consumer.read(count=5, block_ms=2000)
            for msg_id, payload in messages:
                result = TaskResult.model_validate_json(payload)
                await self._handle_result(result)
                results.append(result)
                await self.result_consumer.ack(msg_id)

        return results

    async def _handle_result(self, result: TaskResult) -> None:
        """Process a completed task result."""
        self.completed_results[result.task_id] = result
        self.global_coverage[result.target_id] = result.final_coverage

        console.print(
            f"[green]Completed:[/green] task {result.task_id[:12]} by {result.worker_id} — "
            f"{result.final_coverage.branch_coverage_pct:.1f}% branch coverage, "
            f"{len(result.crashes)} crashes, "
            f"{result.total_duration_s:.1f}s"
        )

        # Reassignment: if coverage is low, retry with a different strategy
        if result.task_id in self.active_tasks:
            original_task = self.active_tasks.pop(result.task_id)

            if (
                result.final_coverage.branch_coverage_pct < 70.0
                and original_task.strategy_hint != "error_path"
            ):
                console.print(
                    f"[yellow]Reassigning:[/yellow] {original_task.target.qualified_name} "
                    f"with error_path strategy (was {result.final_coverage.branch_coverage_pct:.1f}%)"
                )
                retry_task = FuzzTask(
                    task_id=uuid.uuid4().hex,
                    target=original_task.target,
                    max_iterations=10,
                    strategy_hint="error_path",
                )
                await self.task_producer.publish(retry_task)
                self.active_tasks[retry_task.task_id] = retry_task

    def print_summary(self) -> None:
        """Print a summary of all completed results."""
        console.print("\n[bold]Coordinator Summary[/bold]")
        for target_id, coverage in self.global_coverage.items():
            results_for_target = [
                r for r in self.completed_results.values() if r.target_id == target_id
            ]
            total_crashes = sum(len(r.crashes) for r in results_for_target)
            total_inputs = sum(r.total_inputs_generated for r in results_for_target)
            console.print(
                f"  {target_id[:12]}: {coverage.branch_coverage_pct:.1f}% branches, "
                f"{total_crashes} crashes, {total_inputs} inputs"
            )
