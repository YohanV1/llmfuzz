"""Test source code analysis and target discovery."""

from llmfuzz.analysis.source import build_target, discover_targets
from llmfuzz.models.target import TargetType


def test_discover_targets(simple_math_path):
    targets = discover_targets(simple_math_path)
    names = {t.function_name for t in targets}
    assert "safe_divide" in names
    assert "classify_number" in names
    assert "fibonacci" in names


def test_discover_filters_private(simple_math_path):
    targets = discover_targets(simple_math_path)
    for t in targets:
        assert not t.function_name.startswith("_")


def test_build_specific_target(simple_math_path):
    target = build_target(simple_math_path, "safe_divide")
    assert target.function_name == "safe_divide"
    assert target.target_type == TargetType.FUNCTION
    assert len(target.signature.parameters) == 2
    assert target.signature.parameters[0].name == "a"
    assert target.signature.parameters[0].annotation == "float"


def test_discover_with_filter(simple_math_path):
    targets = discover_targets(simple_math_path, function_filter="fibonacci")
    assert len(targets) == 1
    assert targets[0].function_name == "fibonacci"


def test_target_has_source(simple_math_path):
    target = build_target(simple_math_path, "safe_divide")
    assert "def safe_divide" in target.signature.source_code
    assert target.signature.start_line > 0
    assert target.signature.end_line >= target.signature.start_line


def test_string_parser_targets(string_parser_path):
    targets = discover_targets(string_parser_path)
    names = {t.function_name for t in targets}
    assert "parse_key_value" in names
    assert "tokenize" in names
