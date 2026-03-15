from __future__ import annotations

from datetime import datetime, timezone

from pydantic import BaseModel, Field

from llmfuzz.models.coverage import CoverageSnapshot
from llmfuzz.models.execution import CrashReport


class FuzzSession(BaseModel):
    session_id: str
    target_id: str
    iteration: int = 0
    inputs_generated: int = 0
    coverage_snapshots: list[CoverageSnapshot] = Field(default_factory=list)
    crashes: list[CrashReport] = Field(default_factory=list)
    started_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: datetime | None = None
    plateau_detected: bool = False
