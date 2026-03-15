"""Template for the Python script executed in a subprocess to run a fuzz input."""

HARNESS_TEMPLATE = '''\
import sys
import json
import time
import traceback

sys.path.insert(0, {project_root!r})

import coverage

cov = coverage.Coverage(
    branch=True,
    data_file={coverage_data_file!r},
    source=[{source_dir!r}],
    include=[{source_file!r}],
)
cov.start()

start = time.perf_counter()
try:
    {import_statement}

    args = json.loads({args_json!r})
    kwargs = json.loads({kwargs_json!r})

    result = {callable_expr}(*args, **kwargs)

    duration_ms = (time.perf_counter() - start) * 1000
    output = {{
        "outcome": "success",
        "return_value": repr(result)[:1000],
        "duration_ms": duration_ms,
    }}
except Exception as e:
    duration_ms = (time.perf_counter() - start) * 1000
    output = {{
        "outcome": "exception",
        "exception_type": type(e).__name__,
        "exception_message": str(e)[:1000],
        "traceback": traceback.format_exc()[:3000],
        "duration_ms": duration_ms,
    }}
finally:
    cov.stop()
    cov.save()

print("__LLMFUZZ_RESULT__" + json.dumps(output))
'''


def render_harness(
    project_root: str,
    source_file: str,
    source_dir: str,
    module_path: str,
    function_name: str,
    args_json: str,
    kwargs_json: str,
    coverage_data_file: str,
) -> str:
    """Render the harness template with concrete values."""
    # Build import statement and callable expression
    # For methods like "MyClass.my_method", we need to import and instantiate
    parts = function_name.split(".")
    if len(parts) == 1:
        import_statement = f"from {module_path} import {function_name}"
        callable_expr = function_name
    else:
        # Class method: import class, instantiate, call method
        class_name = parts[0]
        method_name = parts[1]
        import_statement = f"from {module_path} import {class_name}"
        callable_expr = f"{class_name}().{method_name}"

    return HARNESS_TEMPLATE.format(
        project_root=project_root,
        coverage_data_file=coverage_data_file,
        source_dir=source_dir,
        source_file=source_file,
        import_statement=import_statement,
        callable_expr=callable_expr,
        args_json=args_json,
        kwargs_json=kwargs_json,
    )
