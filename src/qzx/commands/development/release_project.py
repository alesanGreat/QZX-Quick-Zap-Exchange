#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""ReleaseProject Command - Plans or prepares version metadata safely."""

import json
import os
import re
import subprocess
import tempfile
from datetime import date
from pathlib import Path

from packaging.version import InvalidVersion, Version

from qzx.core.command_base import CommandBase


class ReleaseProjectCommand(CommandBase):
    """Prepare version metadata without committing, tagging, or publishing."""

    name = "releaseProject"
    description = (
        "Plans a release metadata update and can atomically update one "
        "manifest plus CHANGELOG.md; it never builds, commits, tags, or "
        "publishes"
    )
    category = "development"
    requires_explicit_approval = True
    backup_target_parameter = "path"

    parameters = [
        {
            "name": "bump",
            "description": "Version increment: patch, minor, or major",
            "required": False,
            "default": "patch",
            "type": "str",
        },
        {
            "name": "path",
            "description": "Project directory to prepare",
            "required": False,
            "default": ".",
            "type": "str",
        },
        {
            "name": "dry_run",
            "description": "Preview the exact metadata changes without writing",
            "required": False,
            "default": True,
            "type": "bool",
        },
        {
            "name": "new_version",
            "description": (
                "Explicit target version; recommended for pre-releases and "
                "projects that do not use three-part SemVer"
            ),
            "required": False,
            "default": None,
            "type": "str",
        },
        {
            "name": "release_notes",
            "description": (
                "Reviewed changelog text; required when applying with "
                "update_changelog=true"
            ),
            "required": False,
            "default": None,
            "type": "str",
        },
        {
            "name": "update_changelog",
            "description": "Prepend a reviewed entry to CHANGELOG.md",
            "required": False,
            "default": True,
            "type": "bool",
        },
        {
            "name": "require_clean_git",
            "description": (
                "Require the project to be a clean Git worktree before "
                "applying changes"
            ),
            "required": False,
            "default": True,
            "type": "bool",
        },
        {
            "name": "manifest",
            "description": (
                "Explicit supported manifest path relative to the project "
                "when automatic detection would be ambiguous"
            ),
            "required": False,
            "default": None,
            "type": "str",
        },
    ]

    examples = [
        {
            "command": "qzx releaseProject",
            "description": (
                "Preview the next patch version and all release-preparation "
                "preconditions"
            ),
        },
        {
            "command": (
                'qzx releaseProject --new-version 2.0.0rc1 '
                '--release-notes "Release candidate with reviewed fixes" '
                "--dry-run false"
            ),
            "description": (
                "Back up a clean project, then atomically prepare an explicit "
                "Python pre-release without committing or tagging"
            ),
        },
    ]

    supported_manifests = {
        "package.json": "npm",
        "pyproject.toml": "python",
        "Cargo.toml": "rust",
    }
    excluded_stages = [
        "run tests",
        "build distributions",
        "commit changes",
        "create or push tags",
        "publish packages",
        "create a hosted release",
        "deploy",
    ]

    def validate_safety_backup_target(self, target, values):
        """Require one real project directory for a live preparation."""
        project_path = Path(os.path.abspath(os.fspath(target)))
        if not project_path.exists():
            return self._failure(
                "path_not_found",
                f"Project path '{project_path}' does not exist.",
                path=str(project_path),
            )
        if not project_path.is_dir():
            return self._failure(
                "path_not_directory",
                f"Project path '{project_path}' is not a directory.",
                path=str(project_path),
            )
        return None

    def execute(
        self,
        bump="patch",
        path=".",
        dry_run=True,
        new_version=None,
        release_notes=None,
        update_changelog=True,
        require_clean_git=True,
        manifest=None,
    ):
        """Build a deterministic plan and optionally apply its metadata edits."""
        project_path = Path(os.path.abspath(os.fspath(path)))
        if not project_path.exists():
            return self._failure(
                "path_not_found",
                f"Project path '{project_path}' does not exist.",
                path=str(project_path),
            )
        if not project_path.is_dir():
            return self._failure(
                "path_not_directory",
                f"Project path '{project_path}' is not a directory.",
                path=str(project_path),
            )

        dry_run_value = self._strict_bool(dry_run)
        changelog_value = self._strict_bool(update_changelog)
        clean_git_value = self._strict_bool(require_clean_git)
        if dry_run_value is None:
            return self._invalid_bool("dry_run", dry_run, project_path)
        if changelog_value is None:
            return self._invalid_bool(
                "update_changelog",
                update_changelog,
                project_path,
            )
        if clean_git_value is None:
            return self._invalid_bool(
                "require_clean_git",
                require_clean_git,
                project_path,
            )

        bump_value = str(bump).strip().lower()
        if bump_value not in {"patch", "minor", "major"}:
            return self._failure(
                "invalid_bump",
                (
                    f"bump must be patch, minor, or major; got {bump!r}. "
                    "No default was substituted."
                ),
                path=str(project_path),
                bump=bump,
            )

        manifest_result = self._select_manifest(project_path, manifest)
        if not manifest_result["success"]:
            return manifest_result
        manifest_path = manifest_result["path"]
        manifest_type = manifest_result["manifest_type"]

        content_result = self._manifest_update(
            manifest_path,
            manifest_type,
            bump_value,
            new_version,
        )
        if not content_result["success"]:
            return content_result

        notes = str(release_notes).strip() if release_notes is not None else ""
        if len(notes) > 20_000:
            return self._failure(
                "release_notes_too_large",
                "release_notes must not exceed 20,000 characters.",
                path=str(project_path),
                characters=len(notes),
            )
        git_state = self._git_state(project_path)
        blockers = []
        if clean_git_value:
            if not git_state["is_repository"]:
                blockers.append(
                    "The project is not a Git worktree or Git is unavailable."
                )
            elif not git_state["clean"]:
                blockers.append(
                    "The Git worktree contains tracked or untracked changes."
                )
        if changelog_value and not notes:
            blockers.append(
                "Reviewed release_notes are required to update CHANGELOG.md."
            )

        changelog_path = project_path / "CHANGELOG.md"
        changelog_content = None
        changelog_prefix = b""
        changelog_newline = "\n"
        if changelog_value and changelog_path.is_symlink():
            return self._failure(
                "changelog_symlink_refused",
                "CHANGELOG.md must not be a symbolic link.",
                path=str(project_path),
                changelog=str(changelog_path),
            )
        if changelog_value and notes:
            if changelog_path.is_file():
                changelog_raw = changelog_path.read_bytes()
                changelog_prefix = (
                    b"\xef\xbb\xbf"
                    if changelog_raw.startswith(b"\xef\xbb\xbf")
                    else b""
                )
                current_changelog = changelog_raw[
                    len(changelog_prefix):
                ].decode("utf-8")
                changelog_newline = (
                    "\r\n" if "\r\n" in current_changelog else "\n"
                )
            else:
                current_changelog = ""
            entry = (
                f"## [{content_result['new_version']}] - {date.today().isoformat()}\n\n"
                f"{notes}\n\n"
            )
            changelog_content = (
                entry.replace("\n", changelog_newline) + current_changelog
            )

        plan = {
            "project_path": str(project_path),
            "manifest": str(manifest_path),
            "manifest_type": manifest_type,
            "old_version": content_result["old_version"],
            "new_version": content_result["new_version"],
            "version_source": (
                "explicit" if new_version not in (None, "") else bump_value
            ),
            "update_changelog": changelog_value,
            "changelog": str(changelog_path) if changelog_value else None,
            "git": git_state,
            "ready_to_apply": not blockers,
            "blockers": blockers,
            "excluded_stages": list(self.excluded_stages),
        }

        if dry_run_value:
            return {
                "success": True,
                "status": "preview",
                "dry_run": True,
                "changes_applied": False,
                "plan": plan,
                "message": (
                    f"Prepared a preview from {content_result['old_version']} "
                    f"to {content_result['new_version']} using "
                    f"{manifest_path.name}. No files, commits, tags, builds, "
                    "packages, or deployments were changed."
                ),
            }

        if blockers:
            return {
                "success": False,
                "status": "blocked",
                "error_code": "release_preconditions_failed",
                "error": "Release preparation preconditions failed.",
                "dry_run": False,
                "changes_applied": False,
                "plan": plan,
                "message": (
                    "Release metadata was not changed. Resolve every item in "
                    "plan.blockers and preview the operation again."
                ),
            }

        files = [
            {
                "path": manifest_path,
                "original": manifest_path.read_bytes(),
                "updated": content_result["content_bytes"],
                "mode": manifest_path.stat().st_mode,
            }
        ]
        if changelog_value:
            files.append(
                {
                    "path": changelog_path,
                    "original": (
                        changelog_path.read_bytes()
                        if changelog_path.exists()
                        else None
                    ),
                    "updated": (
                        changelog_prefix
                        + changelog_content.encode("utf-8")
                    ),
                    "mode": (
                        changelog_path.stat().st_mode
                        if changelog_path.exists()
                        else None
                    ),
                }
            )

        transaction = self._replace_transaction(files)
        if not transaction["success"]:
            plan["transaction"] = transaction
            return {
                "success": False,
                "status": "failed",
                "error_code": "release_metadata_write_failed",
                "error": transaction["error"],
                "dry_run": False,
                "changes_applied": transaction["changes_remaining"],
                "plan": plan,
                "message": (
                    "Release metadata could not be applied atomically. "
                    "Rollback was attempted; inspect plan.transaction and use "
                    "the QZX safety backup if any change remains."
                ),
            }

        plan["transaction"] = transaction
        return {
            "success": True,
            "status": "prepared",
            "dry_run": False,
            "changes_applied": True,
            "plan": plan,
            "message": (
                f"Prepared release metadata from "
                f"{content_result['old_version']} to "
                f"{content_result['new_version']}. QZX changed only the "
                "selected manifest"
                f"{' and CHANGELOG.md' if changelog_value else ''}; tests, "
                "build, commit, tag, publication, and deployment remain "
                "separate operator-controlled stages."
            ),
        }

    def _select_manifest(self, project_path, requested_manifest):
        if requested_manifest not in (None, ""):
            candidate = (project_path / os.fspath(requested_manifest)).resolve()
            try:
                candidate.relative_to(project_path.resolve())
            except ValueError:
                return self._failure(
                    "manifest_outside_project",
                    "The selected manifest must remain inside the project.",
                    path=str(project_path),
                    manifest=str(candidate),
                )
            manifest_type = self.supported_manifests.get(candidate.name)
            if manifest_type is None:
                return self._failure(
                    "unsupported_manifest",
                    (
                        f"Unsupported manifest '{candidate.name}'. Choose "
                        "package.json, pyproject.toml, or Cargo.toml."
                    ),
                    path=str(project_path),
                    manifest=str(candidate),
                )
            if not candidate.is_file() or candidate.is_symlink():
                return self._failure(
                    "manifest_not_regular_file",
                    "The selected manifest must be an existing regular file.",
                    path=str(project_path),
                    manifest=str(candidate),
                )
            return {
                "success": True,
                "path": candidate,
                "manifest_type": manifest_type,
            }

        candidates = [
            (project_path / filename, manifest_type)
            for filename, manifest_type in self.supported_manifests.items()
            if (project_path / filename).is_file()
            and not (project_path / filename).is_symlink()
        ]
        if not candidates:
            return self._failure(
                "manifest_not_found",
                (
                    "No supported release manifest was found. Add or select "
                    "package.json, pyproject.toml, or Cargo.toml."
                ),
                path=str(project_path),
            )
        if len(candidates) > 1:
            return self._failure(
                "ambiguous_manifest",
                (
                    "Multiple supported manifests were found. Select one "
                    "explicitly with --manifest."
                ),
                path=str(project_path),
                manifests=[str(item[0]) for item in candidates],
            )
        selected_path, selected_type = candidates[0]
        return {
            "success": True,
            "path": selected_path,
            "manifest_type": selected_type,
        }

    def _manifest_update(
        self,
        manifest_path,
        manifest_type,
        bump,
        requested_version,
    ):
        try:
            original_bytes = manifest_path.read_bytes()
            encoding_prefix = (
                b"\xef\xbb\xbf"
                if original_bytes.startswith(b"\xef\xbb\xbf")
                else b""
            )
            source = original_bytes[len(encoding_prefix):].decode("utf-8")
            if manifest_type == "npm":
                document = json.loads(source)
                old_version = document.get("version")
                if not isinstance(old_version, str) or not old_version.strip():
                    raise ValueError("package.json has no top-level string version")
                target = self._target_version(
                    old_version,
                    requested_version,
                    bump,
                    manifest_type,
                )
                document["version"] = target
                newline = "\r\n" if "\r\n" in source else "\n"
                content = json.dumps(
                    document,
                    ensure_ascii=False,
                    indent=2,
                ).replace("\n", newline)
                if source.endswith(("\n", "\r\n")):
                    content += newline
            else:
                section = "project" if manifest_type == "python" else "package"
                section_match = re.search(
                    rf"(?ms)^\[{re.escape(section)}\]\s*$.*?(?=^\[|\Z)",
                    source,
                )
                if section_match is None:
                    raise ValueError(
                        f"{manifest_path.name} has no [{section}] section"
                    )
                version_match = re.search(
                    r"(?m)^(\s*version\s*=\s*)([\"'])([^\"']+)\2(\s*(?:#.*)?)$",
                    section_match.group(0),
                )
                if version_match is None:
                    raise ValueError(
                        f"[{section}] has no static version assignment"
                    )
                old_version = version_match.group(3)
                target = self._target_version(
                    old_version,
                    requested_version,
                    bump,
                    manifest_type,
                )
                absolute_start = section_match.start() + version_match.start(3)
                absolute_end = section_match.start() + version_match.end(3)
                content = source[:absolute_start] + target + source[absolute_end:]
        except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as exc:
            return self._failure(
                "invalid_manifest",
                (
                    f"Could not read a static version from "
                    f"'{manifest_path}': {exc}"
                ),
                manifest=str(manifest_path),
                manifest_type=manifest_type,
            )
        return {
            "success": True,
            "old_version": old_version,
            "new_version": target,
            "content": content,
            "content_bytes": encoding_prefix + content.encode("utf-8"),
        }

    def _target_version(
        self,
        old_version,
        requested_version,
        bump,
        manifest_type,
    ):
        if manifest_type == "python":
            try:
                current = Version(old_version)
            except InvalidVersion as exc:
                raise ValueError(
                    f"current version is not valid PEP 440: {old_version!r}"
                ) from exc
            if requested_version not in (None, ""):
                try:
                    target = Version(str(requested_version).strip())
                except InvalidVersion as exc:
                    raise ValueError(
                        f"target version is not valid PEP 440: {requested_version!r}"
                    ) from exc
                if target <= current:
                    raise ValueError(
                        f"target version {target} must be newer than {current}"
                    )
                return str(target)
            return self._bump_python_version(current, bump)

        current_parts = self._semver_parts(old_version)
        if requested_version not in (None, ""):
            target_text = str(requested_version).strip()
            target_parts = self._semver_parts(target_text)
            if self._semver_key(target_parts) <= self._semver_key(current_parts):
                raise ValueError(
                    f"target version {target_text} must be newer than {old_version}"
                )
            return target_text
        return self._bump_semver(old_version, bump)

    @staticmethod
    def _bump_python_version(version, bump):
        release = list(version.release)
        while len(release) < 3:
            release.append(0)
        if bump == "major":
            release = [release[0] + 1, 0, 0]
        elif bump == "minor":
            release = [release[0], release[1] + 1, 0]
        else:
            release[-1] += 1
        return ".".join(str(part) for part in release)

    @classmethod
    def _bump_semver(cls, version_str, bump):
        major, minor, patch, _suffix = cls._semver_parts(version_str)
        if bump == "major":
            return f"{major + 1}.0.0"
        if bump == "minor":
            return f"{major}.{minor + 1}.0"
        return f"{major}.{minor}.{patch + 1}"

    @staticmethod
    def _semver_parts(version):
        match = re.fullmatch(
            r"(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)"
            r"(?:-([0-9A-Za-z.-]+))?(?:\+[0-9A-Za-z.-]+)?",
            str(version).strip(),
        )
        if match is None:
            raise ValueError(f"version is not valid SemVer: {version!r}")
        return (
            int(match.group(1)),
            int(match.group(2)),
            int(match.group(3)),
            match.group(4),
        )

    @staticmethod
    def _semver_key(parts):
        major, minor, patch, prerelease = parts
        stable_rank = 1 if prerelease is None else 0
        return major, minor, patch, stable_rank, prerelease or ""

    @staticmethod
    def _git_state(project_path):
        result = {
            "available": False,
            "is_repository": False,
            "clean": False,
            "branch": None,
            "changes": [],
            "error": None,
        }
        try:
            inside = subprocess.run(
                ["git", "rev-parse", "--is-inside-work-tree"],
                cwd=project_path,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=10,
                check=False,
            )
            result["available"] = True
            if inside.returncode != 0 or inside.stdout.strip() != "true":
                result["error"] = (
                    inside.stderr.strip() or "Path is not inside a Git worktree."
                )
                return result
            result["is_repository"] = True
            status = subprocess.run(
                ["git", "status", "--porcelain=v1", "--untracked-files=all"],
                cwd=project_path,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=10,
                check=False,
            )
            if status.returncode != 0:
                result["error"] = status.stderr.strip() or "git status failed"
                return result
            changes = [
                line
                for line in status.stdout.splitlines()
                if line.strip()
            ]
            result["changes"] = changes[:100]
            result["clean"] = not changes
            branch = subprocess.run(
                ["git", "branch", "--show-current"],
                cwd=project_path,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=10,
                check=False,
            )
            if branch.returncode == 0:
                result["branch"] = branch.stdout.strip() or None
        except (OSError, subprocess.SubprocessError) as exc:
            result["error"] = f"{type(exc).__name__}: {exc}"
        return result

    @classmethod
    def _replace_transaction(cls, files):
        temporary = {}
        replaced = []
        try:
            for item in files:
                target = item["path"]
                target.parent.mkdir(parents=True, exist_ok=True)
                descriptor, temporary_name = tempfile.mkstemp(
                    prefix=f".{target.name}.qzx-",
                    suffix=".tmp",
                    dir=target.parent,
                )
                with os.fdopen(descriptor, "wb") as stream:
                    stream.write(item["updated"])
                    stream.flush()
                    os.fsync(stream.fileno())
                if item.get("mode") is not None:
                    os.chmod(temporary_name, item["mode"])
                temporary[target] = Path(temporary_name)
            for item in files:
                target = item["path"]
                os.replace(temporary.pop(target), target)
                replaced.append(item)
            return {
                "success": True,
                "updated_files": [str(item["path"]) for item in files],
                "rollback_attempted": False,
                "rollback_succeeded": None,
                "changes_remaining": False,
            }
        except Exception as exc:
            rollback_errors = []
            for item in reversed(replaced):
                try:
                    if item["original"] is None:
                        item["path"].unlink(missing_ok=True)
                    else:
                        cls._atomic_restore(item["path"], item["original"])
                except Exception as rollback_exc:
                    rollback_errors.append(
                        f"{item['path']}: {type(rollback_exc).__name__}: "
                        f"{rollback_exc}"
                    )
            return {
                "success": False,
                "error": f"{type(exc).__name__}: {exc}",
                "updated_files_before_failure": [
                    str(item["path"]) for item in replaced
                ],
                "rollback_attempted": bool(replaced),
                "rollback_succeeded": not rollback_errors,
                "rollback_errors": rollback_errors,
                "changes_remaining": bool(rollback_errors),
            }
        finally:
            for temporary_path in temporary.values():
                try:
                    temporary_path.unlink(missing_ok=True)
                except OSError:
                    pass

    @staticmethod
    def _atomic_restore(target, content):
        descriptor, temporary_name = tempfile.mkstemp(
            prefix=f".{target.name}.qzx-rollback-",
            suffix=".tmp",
            dir=target.parent,
        )
        try:
            with os.fdopen(descriptor, "wb") as stream:
                stream.write(content)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary_name, target)
        finally:
            try:
                os.unlink(temporary_name)
            except FileNotFoundError:
                pass

    @staticmethod
    def _strict_bool(value):
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            normalized = value.strip().lower()
            if normalized in {"true", "yes", "y", "1", "on"}:
                return True
            if normalized in {"false", "no", "n", "0", "off"}:
                return False
        return None

    def _invalid_bool(self, name, value, project_path):
        return self._failure(
            f"invalid_{name}",
            f"{name} must be true or false, got {value!r}.",
            path=str(project_path),
            parameter=name,
            value=value,
        )

    @staticmethod
    def _failure(error_code, message, **details):
        return {
            "success": False,
            "error_code": error_code,
            "error": message,
            "message": message,
            "details": details,
        }
