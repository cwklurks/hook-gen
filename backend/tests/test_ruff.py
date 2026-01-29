"""Test that ruff linting passes with zero errors."""

import subprocess
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]

_ruff_check = subprocess.run(
    [sys.executable, "-m", "ruff", "--version"], capture_output=True
)


@pytest.mark.skipif(_ruff_check.returncode != 0, reason="ruff not installed")
def test_ruff_returns_zero_errors():
    """Run ruff check on backend/, hook-aid/, and packages/hookgen_core/ and assert 0 errors."""
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "ruff",
            "check",
            "backend/",
            "hook-aid/",
            "packages/hookgen_core/",
        ],
        capture_output=True,
        text=True,
        cwd=PROJECT_ROOT,
    )
    assert result.returncode == 0, (
        f"ruff found errors:\n{result.stdout}\n{result.stderr}"
    )
