from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import StrEnum

from pydantic import BaseModel, Field

from llmfuzz.models.coverage import CoverageSnapshot
from llmfuzz.models.execution import CrashReport
from llmfuzz.models.target import FuzzTarget


class TaskStatus(StrEnum):
    PENDING = "pending"
    ASSIGNED = "assigned"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class FuzzTask(BaseModel):
    task_id: str = Field(default_factory=lambda: uuid.uuid4().hex)
    target: FuzzTarget
    max_iterations: int = 20
    timeout_per_input_s: float = 5.0
    strategy_hint: str | None = None
    assigned_worker: str | None = None
    status: TaskStatus = TaskStatus.PENDING
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class TaskResult(BaseModel):
    task_id: str
    worker_id: str
    target_id: str
    final_coverage: CoverageSnapshot
    crashes: list[CrashReport]
    iterations_completed: int
    total_inputs_generated: int
    total_duration_s: float
    coverage_progression: list[float]
