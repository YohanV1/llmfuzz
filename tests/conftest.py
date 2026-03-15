"""Shared test fixtures."""

from pathlib import Path

import pytest

FIXTURES_DIR = Path(__file__).parent / "fixtures" / "sample_targets"


@pytest.fixture
def simple_math_path() -> str:
    return str(FIXTURES_DIR / "simple_math.py")


@pytest.fixture
def string_parser_path() -> str:
    return str(FIXTURES_DIR / "string_parser.py")


@pytest.fixture
def buggy_module_path() -> str:
    return str(FIXTURES_DIR / "buggy_module.py")
