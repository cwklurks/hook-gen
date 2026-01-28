"""Tests to validate the GitHub Actions CI workflow configuration."""

from pathlib import Path

import pytest
import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[2]
CI_WORKFLOW = PROJECT_ROOT / ".github" / "workflows" / "ci.yml"


@pytest.fixture()
def ci_config():
    """Load and parse the CI workflow YAML.

    Note: PyYAML parses the YAML key ``on`` as Python boolean ``True``,
    so we normalise the parsed dict so callers can use ``config["on"]``.
    """
    assert CI_WORKFLOW.exists(), f"CI workflow not found at {CI_WORKFLOW}"
    content = CI_WORKFLOW.read_text()
    parsed = yaml.safe_load(content)
    # Normalise: PyYAML reads the bare key `on` as boolean True
    if True in parsed and "on" not in parsed:
        parsed["on"] = parsed.pop(True)
    return parsed


class TestCIWorkflowExists:
    """Test that CI workflow file exists and is valid YAML."""

    def test_ci_workflow_file_exists(self):
        assert CI_WORKFLOW.exists(), "CI workflow file .github/workflows/ci.yml must exist"

    def test_ci_workflow_is_valid_yaml(self):
        content = CI_WORKFLOW.read_text()
        parsed = yaml.safe_load(content)
        assert isinstance(parsed, dict), "CI workflow must be a valid YAML mapping"


class TestCITriggers:
    """Test that CI triggers on every push."""

    def test_triggers_on_push(self, ci_config):
        assert "push" in ci_config["on"], "CI must trigger on push events"

    def test_push_not_branch_restricted(self, ci_config):
        push_config = ci_config["on"]["push"]
        # push_config should be None (no filters) or a dict without 'branches'
        if push_config is not None:
            assert "branches" not in push_config, (
                "Push trigger must not be restricted to specific branches "
                "so CI runs on every push"
            )

    def test_triggers_on_pull_request(self, ci_config):
        assert "pull_request" in ci_config["on"], "CI must trigger on pull_request events"


class TestCIJobs:
    """Test that CI defines the expected jobs."""

    def test_has_lint_job(self, ci_config):
        assert "lint" in ci_config["jobs"], "CI must have a 'lint' job"

    def test_has_test_job(self, ci_config):
        assert "test" in ci_config["jobs"], "CI must have a 'test' job"

    def test_lint_job_runs_on_ubuntu(self, ci_config):
        assert ci_config["jobs"]["lint"]["runs-on"] == "ubuntu-latest"

    def test_test_job_runs_on_ubuntu(self, ci_config):
        assert ci_config["jobs"]["test"]["runs-on"] == "ubuntu-latest"


class TestLintJob:
    """Test that the lint job has the expected steps."""

    def _step_names(self, ci_config):
        return [s.get("name", "") for s in ci_config["jobs"]["lint"]["steps"]]

    def test_lint_job_checks_out_code(self, ci_config):
        steps = ci_config["jobs"]["lint"]["steps"]
        checkout_steps = [s for s in steps if s.get("uses", "").startswith("actions/checkout")]
        assert len(checkout_steps) >= 1, "Lint job must check out code"

    def test_lint_job_sets_up_python(self, ci_config):
        steps = ci_config["jobs"]["lint"]["steps"]
        python_steps = [s for s in steps if s.get("uses", "").startswith("actions/setup-python")]
        assert len(python_steps) >= 1, "Lint job must set up Python"

    def test_lint_job_runs_ruff(self, ci_config):
        names = self._step_names(ci_config)
        assert any("ruff" in n.lower() for n in names), "Lint job must run ruff"

    def test_lint_job_runs_mypy(self, ci_config):
        names = self._step_names(ci_config)
        assert any("mypy" in n.lower() for n in names), "Lint job must run mypy"

    def test_lint_job_sets_up_node(self, ci_config):
        steps = ci_config["jobs"]["lint"]["steps"]
        node_steps = [s for s in steps if s.get("uses", "").startswith("actions/setup-node")]
        assert len(node_steps) >= 1, "Lint job must set up Node.js"

    def test_lint_job_runs_frontend_lint(self, ci_config):
        names = self._step_names(ci_config)
        assert any("frontend" in n.lower() and "lint" in n.lower() for n in names), (
            "Lint job must run frontend linting"
        )


class TestTestJob:
    """Test that the test job has the expected steps."""

    def _step_names(self, ci_config):
        return [s.get("name", "") for s in ci_config["jobs"]["test"]["steps"]]

    def test_test_job_checks_out_code(self, ci_config):
        steps = ci_config["jobs"]["test"]["steps"]
        checkout_steps = [s for s in steps if s.get("uses", "").startswith("actions/checkout")]
        assert len(checkout_steps) >= 1, "Test job must check out code"

    def test_test_job_sets_up_python(self, ci_config):
        steps = ci_config["jobs"]["test"]["steps"]
        python_steps = [s for s in steps if s.get("uses", "").startswith("actions/setup-python")]
        assert len(python_steps) >= 1, "Test job must set up Python"

    def test_test_job_runs_pytest(self, ci_config):
        steps = ci_config["jobs"]["test"]["steps"]
        has_pytest = any("pytest" in str(s.get("run", "")) for s in steps)
        assert has_pytest, "Test job must run pytest"

    def test_test_job_sets_pythonpath(self, ci_config):
        steps = ci_config["jobs"]["test"]["steps"]
        # Check that PYTHONPATH includes the backend directory
        has_pythonpath = any("PYTHONPATH" in str(s.get("env", {})) for s in steps)
        assert has_pythonpath, "Test job must set PYTHONPATH to include the backend"
