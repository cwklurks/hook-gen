"""Test that mypy type checking passes with zero errors."""

import subprocess
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]


_mypy_check = subprocess.run(
    [sys.executable, "-m", "mypy", "--version"], capture_output=True
)


@pytest.mark.skipif(_mypy_check.returncode != 0, reason="mypy not installed")
def test_mypy_returns_zero_errors():
    """Run mypy on backend/, hook-aid/, and packages/hookgen_core/ and assert 0 errors."""
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "mypy",
            "backend/",
            "hook-aid/",
            "packages/hookgen_core/",
        ],
        capture_output=True,
        text=True,
        cwd=PROJECT_ROOT,
    )
    assert result.returncode == 0, f"mypy found errors:\n{result.stdout}\n{result.stderr}"
