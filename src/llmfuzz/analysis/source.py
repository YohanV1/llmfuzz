"""AST-based source code analysis to build FuzzTarget objects."""

from __future__ import annotations

import ast
import importlib.util
import inspect
import textwrap
from pathlib import Path

from llmfuzz.models.target import (
    FunctionSignature,
    FuzzTarget,
    ParameterInfo,
    TargetType,
)


def discover_targets(file_path: str, function_filter: str | None = None) -> list[FuzzTarget]:
    """Discover all fuzzable functions/methods in a Python file."""
    path = Path(file_path).resolve()
    source = path.read_text()
    tree = ast.parse(source, filename=str(path))
    module_path = _file_to_module_path(path)
    targets: list[FuzzTarget] = []

    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            if node.name.startswith("_"):
                continue
            if function_filter and node.name != function_filter:
                continue

            qualified = _get_qualified_name(tree, node)
            target_type = TargetType.METHOD if "." in qualified else TargetType.FUNCTION
            func_source = ast.get_source_segment(source, node)
            if func_source is None:
                continue

            sig = FunctionSignature(
                name=node.name,
                qualified_name=f"{module_path}.{qualified}" if module_path else qualified,
                parameters=_extract_parameters(node),
                return_annotation=_unparse_annotation(node.returns),
                docstring=ast.get_docstring(node),
                source_code=func_source,
                source_file=str(path),
                start_line=node.lineno,
                end_line=node.end_lineno or node.lineno,
            )

            context = _get_class_source(tree, source, node) if target_type == TargetType.METHOD else None

            targets.append(FuzzTarget(
                target_type=target_type,
                module_path=module_path or path.stem,
                function_name=node.name,
                qualified_name=sig.qualified_name,
                source_file=str(path),
                signature=sig,
                context_source=context,
            ))

    return targets


def build_target(file_path: str, function_name: str) -> FuzzTarget:
    """Build a FuzzTarget for a specific function in a file."""
    targets = discover_targets(file_path, function_filter=function_name)
    if not targets:
        raise ValueError(
            f"Function '{function_name}' not found in {file_path}. "
            f"Only public (non-underscore) functions are fuzzable."
        )
    return targets[0]


def _extract_parameters(node: ast.FunctionDef | ast.AsyncFunctionDef) -> list[ParameterInfo]:
    params: list[ParameterInfo] = []
    args = node.args

    # Calculate defaults alignment (defaults align to the end of positional args)
    num_positional = len(args.args)
    num_defaults = len(args.defaults)
    default_offset = num_positional - num_defaults

    for i, arg in enumerate(args.args):
        if arg.arg == "self" or arg.arg == "cls":
            continue
        default_idx = i - default_offset
        default = None
        if default_idx >= 0 and default_idx < len(args.defaults):
            default = ast.unparse(args.defaults[default_idx])

        params.append(ParameterInfo(
            name=arg.arg,
            annotation=_unparse_annotation(arg.annotation),
            default=default,
            kind="POSITIONAL_OR_KEYWORD",
        ))

    for arg, default in zip(args.kwonlyargs, args.kw_defaults):
        params.append(ParameterInfo(
            name=arg.arg,
            annotation=_unparse_annotation(arg.annotation),
            default=ast.unparse(default) if default else None,
            kind="KEYWORD_ONLY",
        ))

    if args.vararg:
        params.append(ParameterInfo(
            name=f"*{args.vararg.arg}",
            annotation=_unparse_annotation(args.vararg.annotation),
            kind="VAR_POSITIONAL",
        ))

    if args.kwarg:
        params.append(ParameterInfo(
            name=f"**{args.kwarg.arg}",
            annotation=_unparse_annotation(args.kwarg.annotation),
            kind="VAR_KEYWORD",
        ))

    return params


def _unparse_annotation(node: ast.expr | None) -> str | None:
    if node is None:
        return None
    return ast.unparse(node)


def _get_qualified_name(tree: ast.Module, target_node: ast.FunctionDef) -> str:
    """Get qualified name like 'ClassName.method_name' for methods."""
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            for item in node.body:
                if item is target_node:
                    return f"{node.name}.{target_node.name}"
    return target_node.name


def _get_class_source(tree: ast.Module, source: str, method_node: ast.FunctionDef) -> str | None:
    """Get the source code of the class containing a method."""
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            for item in node.body:
                if item is method_node:
                    return ast.get_source_segment(source, node)
    return None


def _file_to_module_path(file_path: Path) -> str:
    """Best-effort conversion of file path to importable module path."""
    # Walk up to find a parent without __init__.py (the package root)
    parts: list[str] = [file_path.stem]
    parent = file_path.parent
    while (parent / "__init__.py").exists():
        parts.append(parent.name)
        parent = parent.parent
    parts.reverse()
    return ".".join(parts)
