"""Wraps coverage.py to parse .coverage data files and track incremental coverage."""

from __future__ import annotations

import coverage as coverage_lib

from llmfuzz.models.coverage import CoverageSnapshot
from llmfuzz.models.target import FuzzTarget


class CoverageCollector:
    def __init__(self, target: FuzzTarget):
        self.target = target
        self.cumulative_lines: set[int] = set()
        self.cumulative_branches: set[tuple[int, int]] = set()
        self._total_lines: int | None = None
        self._total_branches: int | None = None
        self._all_lines: set[int] | None = None
        self._all_branches: set[tuple[int, int]] | None = None

    def collect_from_data_file(
        self, data_file: str
    ) -> tuple[set[int], set[tuple[int, int]]]:
        """Parse a .coverage data file, return (lines, branches) for the target."""
        cov = coverage_lib.Coverage(data_file=data_file)
        cov.load()
        data = cov.get_data()

        source_file = self.target.source_file
        start = self.target.signature.start_line
        end = self.target.signature.end_line

        raw_lines = data.lines(source_file) or []
        lines = {l for l in raw_lines if start <= l <= end}

        raw_arcs = data.arcs(source_file) or []
        branches = {(a, b) for a, b in raw_arcs if start <= a <= end}

        # Also discover all possible arcs to track missing branches
        if self._all_branches is not None and not self._all_branches:
            self._discover_all_arcs(data_file)

        return lines, branches

    def _discover_all_arcs(self, data_file: str) -> None:
        """Use coverage.py branch analysis to discover all possible arcs."""
        try:
            cov = coverage_lib.Coverage(
                data_file=data_file,
                branch=True,
            )
            cov.load()
            analysis = cov._analyze(self.target.source_file)
            start = self.target.signature.start_line
            end = self.target.signature.end_line

            # coverage.py FileAnalysis has .missing_branch_arcs() for uncovered
            # and the arc data for all possible arcs
            if hasattr(analysis, 'arcs'):
                all_arcs = {
                    (a, b) for a, b in (analysis.arcs() or [])
                    if start <= a <= end
                }
                if all_arcs:
                    self._all_branches = all_arcs
                    self._total_branches = len(all_arcs)
        except Exception:
            pass  # Fall back to AST-based estimate

    def merge_and_compute_new(
        self, lines: set[int], branches: set[tuple[int, int]]
    ) -> tuple[set[int], set[tuple[int, int]]]:
        """Merge into cumulative coverage and return newly covered items."""
        new_lines = lines - self.cumulative_lines
        new_branches = branches - self.cumulative_branches
        self.cumulative_lines |= lines
        self.cumulative_branches |= branches
        return new_lines, new_branches

    def analyze_totals(self) -> None:
        """Determine total possible lines and branches for the target function.

        Uses coverage.py's analysis to figure out which lines are executable
        and which branches exist within the target function's line range.
        """
        cov = coverage_lib.Coverage(
            branch=True,
            source=[str(self.target.source_file)],
        )
        # We need to at least load the file to analyze it
        cov.load()

        try:
            analysis = cov.analysis2(self.target.source_file)
        except coverage_lib.CoverageException:
            # Fallback: estimate from source
            self._estimate_totals_from_source()
            return

        # analysis2 returns: (filename, executable, excluded, missing, formatted)
        _, executable, _, _, _ = analysis
        start = self.target.signature.start_line
        end = self.target.signature.end_line

        func_executable = {l for l in executable if start <= l <= end}
        self._all_lines = func_executable
        self._total_lines = len(func_executable)

        # For branches, we estimate based on control flow nodes in source
        self._estimate_branch_totals()

    def _estimate_totals_from_source(self) -> None:
        """Estimate executable lines and branches from source code."""
        source = self.target.signature.source_code
        lines = source.splitlines()
        executable = 0
        for line in lines:
            stripped = line.strip()
            if stripped and not stripped.startswith("#") and not stripped.startswith('"""'):
                executable += 1
        self._total_lines = executable
        self._all_lines = set(
            range(self.target.signature.start_line, self.target.signature.end_line + 1)
        )
        self._estimate_branch_totals()

    def _estimate_branch_totals(self) -> None:
        """Estimate total branches from control flow keywords in source."""
        import ast

        source = self.target.signature.source_code
        try:
            tree = ast.parse(source)
        except SyntaxError:
            self._total_branches = 0
            self._all_branches = set()
            return

        branch_count = 0
        for node in ast.walk(tree):
            if isinstance(node, ast.If):
                branch_count += 2  # true + false
            elif isinstance(node, ast.For | ast.While):
                branch_count += 2  # enter loop + skip loop
            elif isinstance(node, ast.Try):
                branch_count += 1 + len(node.handlers)
            elif isinstance(node, ast.Match):
                branch_count += len(node.cases)

        self._total_branches = branch_count
        self._all_branches = set()  # We'll track the actual branches via coverage data

    def get_snapshot(self, iteration: int) -> CoverageSnapshot:
        """Build a CoverageSnapshot of current state."""
        if self._total_lines is None:
            self.analyze_totals()

        total_lines = self._total_lines or 1
        total_branches = self._total_branches or 0

        # If we've discovered more branches via coverage data than estimated, update
        if len(self.cumulative_branches) > total_branches:
            total_branches = len(self.cumulative_branches) + 2  # assume a few more uncovered

        missing_lines = (self._all_lines or set()) - self.cumulative_lines
        missing_branches = (self._all_branches or set()) - self.cumulative_branches

        return CoverageSnapshot(
            target_id=self.target.target_id,
            iteration=iteration,
            lines_total=total_lines,
            lines_covered=len(self.cumulative_lines),
            branches_total=max(total_branches, len(self.cumulative_branches)),
            branches_covered=len(self.cumulative_branches),
            covered_lines=set(self.cumulative_lines),
            covered_branches=set(self.cumulative_branches),
            missing_lines=missing_lines,
            missing_branches=missing_branches,
        )
