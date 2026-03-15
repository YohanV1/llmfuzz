from __future__ import annotations

from pydantic import BaseModel, computed_field


class BranchInfo(BaseModel):
    source_file: str
    from_line: int
    to_line: int
    hit: bool
    source_text: str | None = None


class CoverageSnapshot(BaseModel):
    target_id: str
    iteration: int
    lines_total: int
    lines_covered: int
    branches_total: int
    branches_covered: int
    covered_lines: set[int] = set()
    covered_branches: set[tuple[int, int]] = set()
    missing_lines: set[int] = set()
    missing_branches: set[tuple[int, int]] = set()

    @computed_field
    @property
    def line_coverage_pct(self) -> float:
        if self.lines_total == 0:
            return 0.0
        return round(self.lines_covered / self.lines_total * 100, 2)

    @computed_field
    @property
    def branch_coverage_pct(self) -> float:
        if self.branches_total == 0:
            return 0.0
        return round(self.branches_covered / self.branches_total * 100, 2)


class CoverageGap(BaseModel):
    branch: BranchInfo
    surrounding_source: str
    condition_text: str | None = None
    why_hard: str | None = None
