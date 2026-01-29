"""Tests to validate the pre-commit hook configuration."""

import subprocess
import sys
from pathlib import Path

import pytest
import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[2]
PRE_COMMIT_CONFIG = PROJECT_ROOT / ".pre-commit-config.yaml"


@pytest.fixture()
def pre_commit_config():
    """Load and parse the pre-commit configuration YAML."""
    assert PRE_COMMIT_CONFIG.exists(), f"Config not found at {PRE_COMMIT_CONFIG}"
    content = PRE_COMMIT_CONFIG.read_text()
    parsed = yaml.safe_load(content)
    assert isinstance(parsed, dict), "Config must be a valid YAML mapping"
    return parsed


def _get_hook_ids(config):
    """Extract all hook IDs from the pre-commit config."""
    ids = []
    for repo in config.get("repos", []):
        for hook in repo.get("hooks", []):
            ids.append(hook["id"])
    return ids


def _get_repos(config):
    """Extract all repo URLs from the pre-commit config."""
    return [repo.get("repo", "") for repo in config.get("repos", [])]


class TestPreCommitConfigExists:
    """Test that the pre-commit config file exists and is valid."""

    def test_config_file_exists(self):
        assert PRE_COMMIT_CONFIG.exists(), ".pre-commit-config.yaml must exist at the project root"

    def test_config_is_valid_yaml(self):
        content = PRE_COMMIT_CONFIG.read_text()
        parsed = yaml.safe_load(content)
        assert isinstance(parsed, dict), "Config must be a valid YAML mapping"

    def test_config_has_repos(self, pre_commit_config):
        assert "repos" in pre_commit_config, "Config must define 'repos'"
        assert len(pre_commit_config["repos"]) > 0, "Config must have at least one repo"


class TestRuffHooks:
    """Test that ruff linting and formatting hooks are configured."""

    def test_has_ruff_repo(self, pre_commit_config):
        repos = _get_repos(pre_commit_config)
        assert any("ruff" in r for r in repos), "Config must include the ruff pre-commit repo"

    def test_has_ruff_check_hook(self, pre_commit_config):
        hook_ids = _get_hook_ids(pre_commit_config)
        assert "ruff" in hook_ids, "Config must include the 'ruff' (check) hook"

    def test_has_ruff_format_hook(self, pre_commit_config):
        hook_ids = _get_hook_ids(pre_commit_config)
        assert "ruff-format" in hook_ids, "Config must include the 'ruff-format' hook"

    def test_ruff_hook_scoped_to_python_dirs(self, pre_commit_config):
        """Ruff hooks should only run on the Python source directories."""
        for repo in pre_commit_config["repos"]:
            if "ruff" not in repo.get("repo", ""):
                continue
            for hook in repo.get("hooks", []):
                if hook["id"] in ("ruff", "ruff-format"):
                    files_pattern = hook.get("files", "")
                    assert files_pattern, (
                        f"Hook '{hook['id']}' must have a 'files' pattern "
                        "to scope it to the Python directories"
                    )
                    for directory in ("backend", "hook-aid", "hookgen_core"):
                        assert directory in files_pattern, (
                            f"Hook '{hook['id']}' files pattern must include '{directory}'"
                        )


class TestGeneralHooks:
    """Test that general code hygiene hooks are configured."""

    def test_has_pre_commit_hooks_repo(self, pre_commit_config):
        repos = _get_repos(pre_commit_config)
        assert any("pre-commit-hooks" in r for r in repos), (
            "Config must include the pre-commit/pre-commit-hooks repo"
        )

    def test_has_trailing_whitespace_hook(self, pre_commit_config):
        hook_ids = _get_hook_ids(pre_commit_config)
        assert "trailing-whitespace" in hook_ids, "Config must include trailing-whitespace hook"

    def test_has_end_of_file_fixer_hook(self, pre_commit_config):
        hook_ids = _get_hook_ids(pre_commit_config)
        assert "end-of-file-fixer" in hook_ids, "Config must include end-of-file-fixer hook"

    def test_has_check_yaml_hook(self, pre_commit_config):
        hook_ids = _get_hook_ids(pre_commit_config)
        assert "check-yaml" in hook_ids, "Config must include check-yaml hook"

    def test_has_check_large_files_hook(self, pre_commit_config):
        hook_ids = _get_hook_ids(pre_commit_config)
        assert "check-added-large-files" in hook_ids, (
            "Config must include check-added-large-files hook"
        )

    def test_has_check_merge_conflict_hook(self, pre_commit_config):
        hook_ids = _get_hook_ids(pre_commit_config)
        assert "check-merge-conflict" in hook_ids, "Config must include check-merge-conflict hook"


class TestRepoVersionsPinned:
    """Test that all repos have pinned versions."""

    def test_all_repos_have_rev(self, pre_commit_config):
        for repo in pre_commit_config.get("repos", []):
            repo_url = repo.get("repo", "")
            if repo_url in ("local", "meta"):
                continue
            assert "rev" in repo, f"Repo '{repo_url}' must have a pinned 'rev'"
            assert repo["rev"], f"Repo '{repo_url}' rev must not be empty"


class TestGitHooksInstalled:
    """Test that pre-commit git hooks are installed."""

    _pre_commit_check = subprocess.run(
        [sys.executable, "-m", "pre_commit", "--version"], capture_output=True
    )

    @pytest.mark.skipif(_pre_commit_check.returncode != 0, reason="pre-commit not installed")
    def test_pre_commit_hook_file_exists(self):
        """The .git/hooks/pre-commit file should exist after installation."""
        hook_file = PROJECT_ROOT / ".git" / "hooks" / "pre-commit"
        assert hook_file.exists(), (
            "Git pre-commit hook is not installed. Run 'pre-commit install' to set up the hooks."
        )
