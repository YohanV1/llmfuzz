from __future__ import annotations

from datetime import datetime, timezone
from enum import StrEnum

from pydantic import BaseModel, Field

from llmfuzz.models.input import TestInput


class ExecutionOutcome(StrEnum):
    SUCCESS = "success"
    EXCEPTION = "exception"
    TIMEOUT = "timeout"
    CRASH = "crash"


class ExecutionResult(BaseModel):
    input_id: str
    target_id: str
    outcome: ExecutionOutcome
    return_value_repr: str | None = None
    exception_type: str | None = None
    exception_message: str | None = None
    traceback: str | None = None
    duration_ms: float = 0.0
    lines_covered: list[int] = Field(default_factory=list)
    branches_covered: list[tuple[int, int]] = Field(default_factory=list)
    new_lines_covered: list[int] = Field(default_factory=list)
    new_branches_covered: list[tuple[int, int]] = Field(default_factory=list)
    executed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class CrashReport(BaseModel):
    crash_id: str
    target_id: str
    input: TestInput
    outcome: ExecutionOutcome
    exception_type: str
    exception_message: str
    traceback: str
    reproducer_code: str
    first_seen_at: datetime
    iteration: int
