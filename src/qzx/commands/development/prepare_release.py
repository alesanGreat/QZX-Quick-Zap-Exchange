#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Plan or prepare version metadata safely."""

from qzx.core.command_base import CommandBase

from ._release_command import (
    execute_prepare_release,
    failure,
    invalid_bool,
    validate_backup_target,
)
from ._release_transaction import atomic_restore, git_state, replace_transaction
from ._release_versions import (
    bump_python_version,
    bump_semver,
    manifest_update,
    select_manifest,
    semver_key,
    semver_parts,
    target_version,
)


class PrepareReleaseCommand(CommandBase):
    """Prepare version metadata without committing, tagging, or publishing."""

    name = "prepareRelease"
    description = (
        "Plans a release metadata update and can atomically update one manifest "
        "plus CHANGELOG.md; it never builds, commits, tags, or publishes"
    )
    category = "development"
    requires_explicit_approval = True
    backup_target_parameter = "path"
    parameters = [
        {"name": "bump", "description": "Version increment: patch, minor, or major", "required": False, "default": "patch", "type": "str"},
        {"name": "path", "description": "Project directory to prepare", "required": False, "default": ".", "type": "str"},
        {"name": "dry_run", "description": "Preview the exact metadata changes without writing", "required": False, "default": True, "type": "bool"},
        {"name": "new_version", "description": "Explicit target version; recommended for pre-releases and projects that do not use three-part SemVer", "required": False, "default": None, "type": "str"},
        {"name": "release_notes", "description": "Reviewed changelog text; required when applying with update_changelog=true", "required": False, "default": None, "type": "str"},
        {"name": "update_changelog", "description": "Prepend a reviewed entry to CHANGELOG.md", "required": False, "default": True, "type": "bool"},
        {"name": "require_clean_git", "description": "Require the project to be a clean Git worktree before applying changes", "required": False, "default": True, "type": "bool"},
        {"name": "manifest", "description": "Explicit supported manifest path relative to the project when automatic detection would be ambiguous", "required": False, "default": None, "type": "str"},
    ]
    examples = [
        {"command": "qzx prepareRelease", "description": "Preview the next patch version and all release-preparation preconditions"},
        {"command": "qzx prepareRelease --new-version 2.0.0rc1 --release-notes \"Release candidate with reviewed fixes\" --dry-run false", "description": "Back up a clean project, then atomically prepare an explicit Python pre-release without committing or tagging"},
    ]
    supported_manifests = {
        "package.json": "npm", "pyproject.toml": "python", "Cargo.toml": "rust",
    }
    excluded_stages = [
        "run tests", "build distributions", "commit changes", "create or push tags",
        "publish packages", "create a hosted release", "deploy",
    ]

    _select_manifest = select_manifest
    _manifest_update = manifest_update
    _target_version = target_version
    _bump_python_version = staticmethod(bump_python_version)
    _bump_semver = classmethod(bump_semver)
    _semver_parts = staticmethod(semver_parts)
    _semver_key = staticmethod(semver_key)
    _git_state = staticmethod(git_state)
    _replace_transaction = classmethod(replace_transaction)
    _atomic_restore = staticmethod(atomic_restore)
    _invalid_bool = invalid_bool
    _failure = staticmethod(failure)

    def validate_safety_backup_target(self, target, values):
        return validate_backup_target(self, target, values)

    def execute(self, bump="patch", path=".", dry_run=True, new_version=None, release_notes=None, update_changelog=True, require_clean_git=True, manifest=None):
        return execute_prepare_release(
            self, bump, path, dry_run, new_version, release_notes,
            update_changelog, require_clean_git, manifest,
        )
