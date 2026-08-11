#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Regression tests for immutable and maintainable GitHub Action references."""

from __future__ import annotations

import re
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
GITHUB_ROOT = REPOSITORY_ROOT / ".github"
ROOT_ACTION = REPOSITORY_ROOT / "action.yml"
NESTED_ACTION = GITHUB_ROOT / "actions" / "result-contract-conformance" / "action.yml"
DEPENDABOT_CONFIG = GITHUB_ROOT / "dependabot.yml"
FULL_COMMIT_SHA = re.compile(r"^[0-9a-f]{40}$")


def _github_action_files() -> list[Path]:
    """Return workflows and Composite Action metadata that can execute Actions."""

    files = list((GITHUB_ROOT / "workflows").rglob("*.yml"))
    files.extend((GITHUB_ROOT / "workflows").rglob("*.yaml"))
    files.extend((GITHUB_ROOT / "actions").rglob("action.yml"))
    files.extend((GITHUB_ROOT / "actions").rglob("action.yaml"))
    files.extend(
        path
        for path in (REPOSITORY_ROOT / "action.yml", REPOSITORY_ROOT / "action.yaml")
        if path.is_file()
    )
    return sorted(set(files))


def _external_action_reference(line: str) -> tuple[str, str] | None:
    """Parse an external ``uses: owner/repository@ref`` line when present."""

    stripped = line.strip()
    if not stripped.startswith("uses:"):
        return None

    value = stripped.partition(":")[2].strip().strip("'\"")
    value = value.split(" #", 1)[0].strip()
    if value.startswith(("./", "docker://")):
        return None
    if "@" not in value:
        return value, ""

    action, ref = value.rsplit("@", 1)
    return action, ref


def test_external_github_actions_use_full_commit_shas():
    files = _github_action_files()
    assert files, "Expected at least one GitHub workflow or Composite Action."

    violations = []
    for path in files:
        relative_path = path.relative_to(REPOSITORY_ROOT)
        for line_number, line in enumerate(
            path.read_text(encoding="utf-8").splitlines(), start=1
        ):
            parsed = _external_action_reference(line)
            if parsed is None:
                continue
            action, ref = parsed
            if not FULL_COMMIT_SHA.fullmatch(ref):
                violations.append(
                    f"{relative_path}:{line_number}: {action}@{ref or '<missing-ref>'}"
                )

    assert violations == [], (
        "External GitHub Actions must use immutable full commit SHAs:\n"
        + "\n".join(violations)
    )


def test_workflow_branch_pushes_do_not_duplicate_pull_request_ci():
    """Run branch CI through pull_request and reserve push CI for main."""

    workflow_files = sorted((GITHUB_ROOT / "workflows").glob("*.yml"))
    workflow_files.extend(sorted((GITHUB_ROOT / "workflows").glob("*.yaml")))
    assert workflow_files, "Expected at least one GitHub workflow."

    expected_trigger_block = (
        "on:\n"
        "  push:\n"
        "    branches:\n"
        "      - main\n"
        "  pull_request:\n"
        "  workflow_dispatch:\n"
    )
    violations = []
    for path in workflow_files:
        text = path.read_text(encoding="utf-8")
        if expected_trigger_block not in text:
            violations.append(str(path.relative_to(REPOSITORY_ROOT)))

    assert violations == [], (
        "Workflows must validate PRs once and reserve push-triggered CI for main: "
        + ", ".join(violations)
    )


def test_root_action_matches_nested_compatibility_entrypoint():
    """Keep the new root Action and the historical nested entrypoint equivalent."""

    assert ROOT_ACTION.is_file(), "QZX must expose its public Action at repository root."
    assert NESTED_ACTION.is_file(), "The historical nested Action entrypoint is missing."

    root_text = ROOT_ACTION.read_text(encoding="utf-8")
    nested_text = NESTED_ACTION.read_text(encoding="utf-8")
    normalized_root = root_text.replace(
        'python "$GITHUB_ACTION_PATH/.github/actions/result-contract-conformance/run.py"',
        'python "$GITHUB_ACTION_PATH/run.py"',
    )
    assert normalized_root == nested_text, (
        "Root and nested Result Contract Action metadata drifted. Keep inputs, outputs, "
        "runtime setup, and immutable dependency pins synchronized."
    )


def test_dependabot_tracks_github_action_version_updates():
    """Ensure pinned Actions have an automated version-update path."""

    text = DEPENDABOT_CONFIG.read_text(encoding="utf-8")
    assert re.search(r'^version:\s*2\s*$', text, flags=re.MULTILINE)
    block = re.search(
        r'(?ms)^\s*-\s+package-ecosystem:\s*["\']github-actions["\']\s*$'
        r'(?P<body>.*?)(?=^\s*-\s+package-ecosystem:|\Z)',
        text,
    )
    assert block is not None, "Dependabot must monitor the github-actions ecosystem."
    body = block.group("body")
    assert re.search(r'^\s+directory:\s*["\']/["\']\s*$', body, flags=re.MULTILINE)
    assert re.search(
        r'^\s+interval:\s*["\']weekly["\']\s*$', body, flags=re.MULTILINE
    )
    for required_group_fragment in (
        "artifact-actions:",
        '- "actions/upload-artifact"',
        '- "actions/download-artifact"',
        "vm-actions:",
        '- "vmactions/*"',
    ):
        assert required_group_fragment in body
    assert '- "actions/*"' not in body, (
        "Do not couple every GitHub Action into one update PR; keep groups bounded."
    )
