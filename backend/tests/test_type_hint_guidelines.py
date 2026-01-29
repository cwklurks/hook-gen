"""Test that type hint guidelines are documented in LINTING_SETUP.md."""

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
LINTING_SETUP = PROJECT_ROOT / "LINTING_SETUP.md"


class TestTypeHintGuidelinesExist:
    """Verify the LINTING_SETUP.md contains type hint guidelines."""

    def test_linting_setup_exists(self):
        assert LINTING_SETUP.exists(), "LINTING_SETUP.md not found at project root"

    def test_contains_type_hint_section(self):
        content = LINTING_SETUP.read_text()
        assert "## Python Type Hint Guidelines" in content

    def test_documents_target_version(self):
        content = LINTING_SETUP.read_text()
        assert "3.10" in content, "Should document Python 3.10+ target version"

    def test_documents_pep585_syntax(self):
        """PEP 585 built-in generics (list[] instead of List[])."""
        content = LINTING_SETUP.read_text()
        assert "PEP 585" in content
        assert "list[" in content
        assert "dict[" in content
        assert "tuple[" in content

    def test_documents_pep604_union_syntax(self):
        """PEP 604 union syntax (X | None instead of Optional[X])."""
        content = LINTING_SETUP.read_text()
        assert "PEP 604" in content
        assert "| None" in content

    def test_documents_numpy_typing(self):
        """NumPy array type hints are documented."""
        content = LINTING_SETUP.read_text()
        assert "NDArray" in content
        assert "numpy.typing" in content or "numpy" in content

    def test_documents_mypy_configuration(self):
        """Mypy configuration settings are documented."""
        content = LINTING_SETUP.read_text()
        assert "check_untyped_defs" in content
        assert "warn_return_any" in content
        assert "disallow_untyped_defs" in content

    def test_documents_when_to_annotate(self):
        """Guidelines about when type hints are required."""
        content = LINTING_SETUP.read_text()
        assert "public function" in content.lower() or "All public functions" in content

    def test_guidelines_match_pyproject_toml(self):
        """Verify guidelines are consistent with pyproject.toml mypy config."""
        pyproject = PROJECT_ROOT / "pyproject.toml"
        assert pyproject.exists(), "pyproject.toml not found"

        pyproject_content = pyproject.read_text()
        guidelines_content = LINTING_SETUP.read_text()

        # Both should reference Python 3.10
        assert 'python_version = "3.10"' in pyproject_content
        assert "3.10" in guidelines_content

        # Both should reference key mypy settings
        assert "check_untyped_defs" in pyproject_content
        assert "check_untyped_defs" in guidelines_content
