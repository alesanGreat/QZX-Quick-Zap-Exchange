"""Regression tests for the real multi-language formatter workflow."""

from __future__ import annotations

from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = (
    REPOSITORY_ROOT
    / ".github"
    / "workflows"
    / "test-real-format-code-ubuntu-24.04-amd64.yml"
)
PHP_CS_FIXER_SHA256 = (
    "3a06439b16ca8a7713d47da25efbf7808b7c08e6f0bdedf2b0d69cf0ce887414"
)


def test_real_formatter_workflow_avoids_apt_and_verifies_runner_tools():
    """Use the documented runner inventory without a mutable apt mirror."""

    workflow = WORKFLOW.read_text(encoding="utf-8")

    assert "    runs-on: ubuntu-24.04\n" in workflow
    assert "    timeout-minutes: 15\n" in workflow
    assert "apt-get" not in workflow
    assert "sudo " not in workflow
    assert (
        "runner_tools=(clang-format curl gofmt node npm php rustfmt)\n" in workflow
    )
    assert 'command -v "${tool}"' in workflow
    assert "missing_tools" in workflow


def test_real_formatter_workflow_pins_downloads_and_uses_external_tool_paths():
    """Verify downloaded formatters before exposing them to the integration test."""

    workflow = WORKFLOW.read_text(encoding="utf-8")

    assert "black==26.5.1" in workflow
    assert "pytest==9.1.1" in workflow
    assert "prettier@3.6.2" in workflow
    assert workflow.count("python -m pip install") == 2
    assert "            --no-deps \\\n            -e .\n" in workflow
    assert "--ignore-scripts --no-audit --no-fund" in workflow
    assert "PHP-CS-Fixer/releases/download/v3.95.1/php-cs-fixer.phar" in workflow
    assert workflow.count(PHP_CS_FIXER_SHA256) == 1
    assert "sha256sum --check --strict" in workflow
    assert "--proto '=https' --proto-redir '=https' --tlsv1.2" in workflow
    assert "--retry 5 --retry-all-errors --connect-timeout 20 --max-time 120" in workflow
    assert 'npm_prefix="${RUNNER_TEMP}/qzx-npm"' in workflow
    assert '"${npm_prefix}/bin" >> "${GITHUB_PATH}"' in workflow
    assert '"${RUNNER_TEMP}" >> "${GITHUB_PATH}"' in workflow
