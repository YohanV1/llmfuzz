"""Test Pydantic model validation."""

from llmfuzz.models.coverage import CoverageSnapshot
from llmfuzz.models.execution import ExecutionOutcome, ExecutionResult
from llmfuzz.models.input import TestInput
from llmfuzz.models.target import FuzzTarget, FunctionSignature, ParameterInfo, TargetType


def test_test_input_defaults():
    inp = TestInput(target_id="abc123")
    assert inp.input_id
    assert inp.args == []
    assert inp.kwargs == {}
    assert inp.generation_strategy == "initial"


def test_test_input_call_repr():
    inp = TestInput(target_id="abc", args=[1, "hello"], kwargs={"x": True})
    assert inp.as_call_repr() == "(1, 'hello', x=True)"


def test_execution_result_outcomes():
    for outcome in ExecutionOutcome:
        result = ExecutionResult(
            input_id="test", target_id="target", outcome=outcome
        )
        assert result.outcome == outcome


def test_coverage_snapshot_percentages():
    snap = CoverageSnapshot(
        target_id="t",
        iteration=0,
        lines_total=100,
        lines_covered=75,
        branches_total=20,
        branches_covered=15,
    )
    assert snap.line_coverage_pct == 75.0
    assert snap.branch_coverage_pct == 75.0


def test_coverage_snapshot_zero_total():
    snap = CoverageSnapshot(
        target_id="t",
        iteration=0,
        lines_total=0,
        lines_covered=0,
        branches_total=0,
        branches_covered=0,
    )
    assert snap.line_coverage_pct == 0.0
    assert snap.branch_coverage_pct == 0.0


def test_fuzz_target_id_deterministic():
    sig = FunctionSignature(
        name="foo",
        qualified_name="mod.foo",
        parameters=[],
        source_code="def foo(): pass",
        source_file="/tmp/test.py",
        start_line=1,
        end_line=1,
    )
    t1 = FuzzTarget(
        target_type=TargetType.FUNCTION,
        module_path="mod",
        function_name="foo",
        qualified_name="mod.foo",
        source_file="/tmp/test.py",
        signature=sig,
    )
    t2 = FuzzTarget(
        target_type=TargetType.FUNCTION,
        module_path="mod",
        function_name="foo",
        qualified_name="mod.foo",
        source_file="/tmp/test.py",
        signature=sig,
    )
    assert t1.target_id == t2.target_id
