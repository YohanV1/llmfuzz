from __future__ import annotations

from enum import StrEnum
from hashlib import sha256

from pydantic import BaseModel, computed_field


class TargetType(StrEnum):
    FUNCTION = "function"
    METHOD = "method"


class ParameterInfo(BaseModel):
    name: str
    annotation: str | None = None
    default: str | None = None
    kind: str = "POSITIONAL_OR_KEYWORD"


class FunctionSignature(BaseModel):
    name: str
    qualified_name: str
    parameters: list[ParameterInfo]
    return_annotation: str | None = None
    docstring: str | None = None
    source_code: str
    source_file: str
    start_line: int
    end_line: int


class FuzzTarget(BaseModel):
    target_type: TargetType
    module_path: str
    function_name: str
    qualified_name: str
    source_file: str
    signature: FunctionSignature
    context_source: str | None = None

    @computed_field
    @property
    def target_id(self) -> str:
        raw = f"{self.qualified_name}:{self.source_file}"
        return sha256(raw.encode()).hexdigest()[:16]
