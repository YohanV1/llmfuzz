from __future__ import annotations

import uuid
from datetime import datetime, timezone

from pydantic import BaseModel, Field


class TestInput(BaseModel):
    input_id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    target_id: str
    args: list = Field(default_factory=list)
    kwargs: dict = Field(default_factory=dict)
    generation_strategy: str = "initial"
    rationale: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    def as_call_repr(self) -> str:
        parts = [repr(a) for a in self.args]
        parts += [f"{k}={v!r}" for k, v in self.kwargs.items()]
        return f"({', '.join(parts)})"


class InputBatch(BaseModel):
    inputs: list[TestInput]
    iteration: int
    strategy: str
