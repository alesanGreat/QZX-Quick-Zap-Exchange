"""Disposable filesystem, project, and Git fixtures for Golden Core evidence."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path


def run_git(arguments: list[str], cwd: Path, environment=None) -> None:
    process_environment = dict(os.environ)
    if environment:
        process_environment.update(environment)
    completed = subprocess.run(
        ["git", *arguments],
        cwd=cwd,
        env=process_environment,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
        timeout=30,
    )
    if completed.returncode != 0:
        raise RuntimeError(
            "Git fixture failed: git {} (exit {}). stderr: {}".format(
                " ".join(arguments),
                completed.returncode,
                completed.stderr.strip(),
            )
        )


def create_fixtures(root: Path) -> dict[str, Path]:
    files = _create_file_fixture(root)
    project = _create_project_fixture(root)
    repository = _create_git_fixture(root)
    return {
        "files": files,
        "project": project,
        "repository": repository,
    }


def _create_file_fixture(root):
    files = root / "files"
    (files / "nested").mkdir(parents=True)
    (files / "alpha.txt").write_bytes(
        b"QZX alpha evidence\nsecond line\n"
    )
    (files / "nested" / "beta.txt").write_bytes(
        b"prefix qzx suffix\n"
    )
    (files / "ignored.log").write_text("unrelated\n", encoding="utf-8")
    return files


def _create_project_fixture(root):
    project = root / "project"
    (project / "src").mkdir(parents=True)
    (project / "tests").mkdir()
    (project / "pyproject.toml").write_text(
        "[project]\n"
        'name = "qzx-platform-evidence"\n'
        'version = "1.0.0"\n'
        'dependencies = ["httpx>=0.28"]\n\n'
        "[tool.pytest.ini_options]\n"
        'testpaths = ["tests"]\n\n'
        "[tool.ruff]\n"
        'target-version = "py313"\n',
        encoding="utf-8",
    )
    (project / "src" / "app.py").write_text(
        "def greet(name: str) -> str:\n    return f'Hello, {name}!'\n",
        encoding="utf-8",
    )
    (project / "tests" / "test_app.py").write_text(
        "from app import greet\n\n\ndef test_greet():\n"
        "    assert greet('QZX') == 'Hello, QZX!'\n",
        encoding="utf-8",
    )
    return project


def _create_git_fixture(root):
    repository = root / "repository"
    repository.mkdir()
    _configure_repository(repository)
    (repository / "tracked.txt").write_text(
        "QZX controlled Git evidence\n",
        encoding="utf-8",
    )
    run_git(["add", "tracked.txt"], repository)
    run_git(
        ["commit", "-m", "Create controlled QZX evidence fixture"],
        repository,
        environment=_fixed_git_environment(),
    )
    run_git(
        [
            "remote",
            "add",
            "origin",
            "https://example.invalid/qzx-evidence.git",
        ],
        repository,
    )
    _dirty_repository(repository)
    return repository


def _configure_repository(repository):
    run_git(["init", "--initial-branch=main"], repository)
    run_git(["config", "user.name", "QZX Evidence Fixture"], repository)
    run_git(
        ["config", "user.email", "qzx-evidence@example.invalid"],
        repository,
    )
    run_git(["config", "core.autocrlf", "false"], repository)
    run_git(["config", "commit.gpgsign", "false"], repository)


def _fixed_git_environment():
    return {
        "GIT_AUTHOR_NAME": "QZX Evidence Fixture",
        "GIT_AUTHOR_EMAIL": "qzx-evidence@example.invalid",
        "GIT_COMMITTER_NAME": "QZX Evidence Fixture",
        "GIT_COMMITTER_EMAIL": "qzx-evidence@example.invalid",
        "GIT_AUTHOR_DATE": "2026-08-08T00:00:00+00:00",
        "GIT_COMMITTER_DATE": "2026-08-08T00:00:00+00:00",
    }


def _dirty_repository(repository):
    (repository / "tracked.txt").write_text(
        "QZX controlled Git evidence\nmodified working tree\n",
        encoding="utf-8",
    )
    (repository / "staged.txt").write_text(
        "staged evidence\n",
        encoding="utf-8",
    )
    run_git(["add", "staged.txt"], repository)
    (repository / "untracked.txt").write_text(
        "untracked evidence\n",
        encoding="utf-8",
    )
