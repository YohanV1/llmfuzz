"""All LLM prompt templates for the fuzzing agent."""

SYSTEM_PROMPT = """\
You are an expert software tester and security researcher specializing in fuzz testing.
Your goal is to achieve maximum branch coverage of a target Python function by generating
diverse, targeted test inputs.

You reason carefully about:
- Code paths and branch conditions
- Edge cases and boundary values
- Type coercion and unusual inputs
- Error-handling branches and exception paths
- Inputs that are difficult to generate randomly

You MUST respond by calling the generate_test_inputs tool with your analysis and inputs.
Each input must include a rationale explaining which code path you're targeting.
"""

INPUT_GENERATION_TOOL = {
    "name": "generate_test_inputs",
    "description": "Generate test inputs for the target function to maximize branch coverage",
    "input_schema": {
        "type": "object",
        "properties": {
            "analysis": {
                "type": "string",
                "description": "Brief analysis of the code's branch structure and your strategy",
            },
            "inputs": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "args": {
                            "type": "array",
                            "description": "Positional arguments for the function call",
                        },
                        "kwargs": {
                            "type": "object",
                            "description": "Keyword arguments for the function call",
                        },
                        "rationale": {
                            "type": "string",
                            "description": "Which branch or code path this input targets and why",
                        },
                    },
                    "required": ["args", "kwargs", "rationale"],
                },
            },
        },
        "required": ["analysis", "inputs"],
    },
}


def build_initial_prompt(
    module_path: str,
    function_name: str,
    source_code: str,
    start_line: int,
    end_line: int,
    source_file: str,
    signature_text: str,
    docstring: str | None,
    batch_size: int,
) -> str:
    """Build the prompt for the first iteration (no coverage data yet)."""
    doc_section = f"\n## Docstring\n{docstring}" if docstring else ""

    return f"""\
## Target Function
Module: {module_path}
Function: {function_name}
File: {source_file}

## Source Code (lines {start_line}-{end_line})
```python
{_add_line_numbers(source_code, start_line)}
```

## Signature
{signature_text}
{doc_section}

## Task
Analyze this function and generate {batch_size} diverse test inputs that aim to cover
as many branches as possible. Consider:
- Normal cases for each parameter type
- Edge cases: empty collections, zero, negative numbers, None, very large values
- Boundary conditions in comparisons (off-by-one, exact boundary, just past boundary)
- Inputs that trigger each branch of if/elif/else chains
- Inputs that trigger exception handlers and error paths
- Type coercion edge cases (passing a float where int expected, etc.)

Generate inputs that are JSON-serializable (no custom objects, lambdas, etc.).
"""


def build_coverage_guided_prompt(
    module_path: str,
    function_name: str,
    source_code: str,
    start_line: int,
    end_line: int,
    source_file: str,
    signature_text: str,
    iteration: int,
    branch_pct: float,
    line_pct: float,
    branches_covered: int,
    branches_total: int,
    lines_covered: int,
    lines_total: int,
    coverage_gaps: str,
    memory_summary: str,
    strategy: str,
    batch_size: int,
) -> str:
    """Build the prompt for coverage-guided iterations."""
    strategy_instructions = _get_strategy_instructions(strategy)

    return f"""\
## Target Function
Module: {module_path}
Function: {function_name}
File: {source_file}

## Source Code (lines {start_line}-{end_line})
```python
{_add_line_numbers(source_code, start_line)}
```

## Coverage So Far (Iteration {iteration})
- Branch coverage: {branch_pct}% ({branches_covered}/{branches_total} branches)
- Line coverage: {line_pct}% ({lines_covered}/{lines_total} lines)

## Uncovered Code Paths
{coverage_gaps}

## Previous Attempts
{memory_summary}

## Strategy: {strategy}
{strategy_instructions}

## Task
Generate {batch_size} new inputs specifically targeting the uncovered code paths listed above.
For each input, explain which uncovered branch you're trying to hit and why you believe
this input will reach it. Do NOT repeat inputs that have already been tried.

Inputs must be JSON-serializable (no custom objects, lambdas, etc.).
"""


def _get_strategy_instructions(strategy: str) -> str:
    instructions = {
        "broad": "Generate diverse inputs covering as many different code paths as possible.",
        "branch_target": (
            "Focus precisely on the uncovered branches. Study the conditions guarding them "
            "and craft inputs that satisfy those exact conditions."
        ),
        "boundary": (
            "Focus on boundary values around comparisons in the source code. "
            "Try values exactly at, just below, and just above comparison thresholds."
        ),
        "error_path": (
            "Focus on triggering exception handlers, error branches, and edge cases "
            "that cause the function to fail gracefully. Try invalid types, None values, "
            "empty collections, and values that violate implicit assumptions."
        ),
        "type_coercion": (
            "Try unusual types: pass a float where int is expected, a list where a string "
            "is expected, None for required parameters, nested structures, very large values."
        ),
        "mutation": (
            "Take the most successful previous inputs (those that covered new branches) "
            "and mutate them slightly - change one argument at a time, negate values, "
            "swap types, add/remove elements from collections."
        ),
    }
    return instructions.get(strategy, instructions["branch_target"])


def build_signature_text(target) -> str:
    """Build a human-readable signature string from a FuzzTarget."""
    params = []
    for p in target.signature.parameters:
        part = p.name
        if p.annotation:
            part += f": {p.annotation}"
        if p.default is not None:
            part += f" = {p.default}"
        params.append(part)

    ret = ""
    if target.signature.return_annotation:
        ret = f" -> {target.signature.return_annotation}"

    return f"def {target.function_name}({', '.join(params)}){ret}"


def _add_line_numbers(source: str, start_line: int) -> str:
    lines = source.splitlines()
    return "\n".join(
        f"{start_line + i:4d}: {line}" for i, line in enumerate(lines)
    )
