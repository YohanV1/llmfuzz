"""Analyzes coverage gaps and provides source context for the LLM."""

from __future__ import annotations

from llmfuzz.coverage.collector import CoverageCollector
from llmfuzz.models.coverage import BranchInfo, CoverageGap
from llmfuzz.models.target import FuzzTarget


class CoverageAnalyzer:
    def __init__(self, target: FuzzTarget, collector: CoverageCollector):
        self.target = target
        self.collector = collector
        self._source_lines: list[str] | None = None

    @property
    def source_lines(self) -> list[str]:
        if self._source_lines is None:
            self._source_lines = self.target.signature.source_code.splitlines()
        return self._source_lines

    def find_uncovered_lines(self) -> list[CoverageGap]:
        """Find uncovered executable lines and return with source context."""
        snapshot = self.collector.get_snapshot(iteration=0)
        gaps: list[CoverageGap] = []

        for line_num in sorted(snapshot.missing_lines):
            rel_line = line_num - self.target.signature.start_line
            if rel_line < 0 or rel_line >= len(self.source_lines):
                continue

            line_text = self.source_lines[rel_line].strip()
            if not line_text or line_text.startswith("#"):
                continue

            surrounding = self._get_context(rel_line, window=5)
            condition = self._extract_condition(rel_line)

            gaps.append(CoverageGap(
                branch=BranchInfo(
                    source_file=self.target.source_file,
                    from_line=line_num,
                    to_line=line_num,
                    hit=False,
                    source_text=line_text,
                ),
                surrounding_source=surrounding,
                condition_text=condition,
            ))

        return gaps

    def find_coverage_gaps(self) -> list[CoverageGap]:
        """Find uncovered branches and lines, return with source context for the LLM."""
        gaps = self.find_uncovered_lines()

        # Also add branch-specific gaps from coverage data
        for from_line, to_line in sorted(self.collector.cumulative_branches):
            # These are branches that WERE hit - we want the ones NOT hit
            pass

        # Deduplicate and prioritize branch points (if/elif/else, try/except)
        seen_lines: set[int] = set()
        unique_gaps: list[CoverageGap] = []
        for gap in gaps:
            if gap.branch.from_line not in seen_lines:
                seen_lines.add(gap.branch.from_line)
                unique_gaps.append(gap)

        return unique_gaps

    def format_gaps_for_prompt(self, max_gaps: int = 10) -> str:
        """Format coverage gaps as text for the LLM prompt."""
        gaps = self.find_coverage_gaps()[:max_gaps]
        if not gaps:
            return "All branches covered!"

        sections: list[str] = []
        for i, gap in enumerate(gaps, 1):
            section = f"### Gap {i}: Line {gap.branch.from_line}"
            if gap.condition_text:
                section += f" - Condition: `{gap.condition_text}`"
            section += f"\n```python\n{gap.surrounding_source}\n```"
            sections.append(section)

        return "\n\n".join(sections)

    def _get_context(self, rel_line: int, window: int = 5) -> str:
        """Get source context around a line with markers."""
        start = max(0, rel_line - window)
        end = min(len(self.source_lines), rel_line + window + 1)
        lines: list[str] = []
        for i in range(start, end):
            abs_line = self.target.signature.start_line + i
            marker = ">" if i == rel_line else " "
            lines.append(f"{marker} {abs_line:4d}: {self.source_lines[i]}")
        return "\n".join(lines)

    def _extract_condition(self, rel_line: int) -> str | None:
        """Try to extract condition text from an if/elif/while/for line."""
        if rel_line < 0 or rel_line >= len(self.source_lines):
            return None
        line = self.source_lines[rel_line].strip()

        # Walk backwards to find the controlling statement
        for offset in range(min(5, rel_line + 1)):
            check_idx = rel_line - offset
            if check_idx < 0:
                break
            check_line = self.source_lines[check_idx].strip()
            for keyword in ("if ", "elif ", "while ", "for ", "except ", "case "):
                if check_line.startswith(keyword):
                    return check_line.rstrip(":")
        return None
