"""Distributed fuzzing worker - pulls tasks from Redis, runs agent loop."""

from __future__ import annotations

import os
import socket
import uuid

import anthropic
import redis.asyncio as redis

from llmfuzz.agent.loop import run_agent_loop
from llmfuzz.distributed.streams import (
    RESULT_STREAM,
    TASK_STREAM,
    WORKER_GROUP,
    RedisStreamConsumer,
    RedisStreamProducer,
)
from llmfuzz.models.task import FuzzTask, TaskResult


class FuzzWorker:
    def __init__(
        self,
        worker_id: str | None = None,
        redis_url: str = "redis://localhost:6379",
        api_key: str | None = None,
        model: str = "claude-sonnet-4-20250514",
    ):
        self.worker_id = worker_id or f"worker-{socket.gethostname()}-{uuid.uuid4().hex[:6]}"
        self.redis_client = redis.from_url(redis_url)
        self.anthropic_client = anthropic.AsyncAnthropic(
            api_key=api_key or os.environ.get("ANTHROPIC_API_KEY", ""),
        )
        self.model = model
        self.task_consumer = RedisStreamConsumer(
            self.redis_client, TASK_STREAM, WORKER_GROUP, self.worker_id
        )
        self.result_producer = RedisStreamProducer(self.redis_client, RESULT_STREAM)
        self._running = True

    async def run(self) -> None:
        """Main worker loop - pull tasks, fuzz, report results."""
        await self.task_consumer.ensure_group()
        print(f"[{self.worker_id}] Worker started, waiting for tasks...")

        while self._running:
            messages = await self.task_consumer.read(count=1, block_ms=5000)
            if not messages:
                continue

            msg_id, payload = messages[0]
            task = FuzzTask.model_validate_json(payload)
            print(f"[{self.worker_id}] Received task {task.task_id[:12]} for {task.target.qualified_name}")

            try:
                session = await run_agent_loop(
                    target=task.target,
                    client=self.anthropic_client,
                    max_iterations=task.max_iterations,
                    timeout_per_input=task.timeout_per_input_s,
                    model=self.model,
                )

                final_coverage = session.coverage_snapshots[-1] if session.coverage_snapshots else None
                duration = 0.0
                if session.completed_at and session.started_at:
                    duration = (session.completed_at - session.started_at).total_seconds()

                result = TaskResult(
                    task_id=task.task_id,
                    worker_id=self.worker_id,
                    target_id=task.target.target_id,
                    final_coverage=final_coverage,
                    crashes=session.crashes,
                    iterations_completed=session.iteration,
                    total_inputs_generated=session.inputs_generated,
                    total_duration_s=duration,
                    coverage_progression=[
                        s.branch_coverage_pct for s in session.coverage_snapshots
                    ],
                )
                await self.result_producer.publish(result)
                print(
                    f"[{self.worker_id}] Task {task.task_id[:12]} done: "
                    f"{result.final_coverage.branch_coverage_pct:.1f}% branch coverage, "
                    f"{len(session.crashes)} crashes"
                )

            except Exception as e:
                print(f"[{self.worker_id}] Task {task.task_id[:12]} failed: {e}")

            await self.task_consumer.ack(msg_id)

    def stop(self) -> None:
        self._running = False
