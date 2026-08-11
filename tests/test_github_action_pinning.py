#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Regression tests for immutable external GitHub Action references."""

from __future__ import annotations

import re
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
GITHUB_ROOT = REPOSITORY_ROOT / ".github"
FULL_COMMIT_SHA = re.compile(r"^[0-9a-f]{40}$")


def _github_action_files() -> list[Path]:
    """Return workflows and Composite Action metadata that can execute Actions."""

    files = list((GITHUB_ROOT / "workflows").rglob("*.yml"))
    files.extend((GITHUB_ROOT / "workflows").rglob("*.yaml"))
    files.extend((GITHUB_ROOT / "actions").rglob("action.yml"))
    files.extend((GITHUB_ROOT / "actions").rglob("action.yaml"))
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
