"""Safe orchestration for ``prepareRelease``."""

import os
from datetime import date
from pathlib import Path


def failure(error_code, message, **details):
    return {"success": False, "error_code": error_code, "error": message, "message": message, "details": details}


def invalid_bool(command, name, value, project_path):
    return command._failure(
        f"invalid_{name}", f"{name} must be true or false, got {value!r}.",
        path=str(project_path), parameter=name, value=value,
    )


def validate_backup_target(command, target, _values):
    project_path = Path(os.path.abspath(os.fspath(target)))
    if not project_path.exists():
        return command._failure("path_not_found", f"Project path '{project_path}' does not exist.", path=str(project_path))
    if not project_path.is_dir():
        return command._failure("path_not_directory", f"Project path '{project_path}' is not a directory.", path=str(project_path))
    return None


def _path_and_flags(command, path, dry_run, update_changelog, require_clean_git):
    project = Path(os.path.abspath(os.fspath(path)))
    if not project.exists():
        return None, command._failure("path_not_found", f"Project path '{project}' does not exist.", path=str(project))
    if not project.is_dir():
        return None, command._failure("path_not_directory", f"Project path '{project}' is not a directory.", path=str(project))
    values = []
    for name, raw in (("dry_run", dry_run), ("update_changelog", update_changelog), ("require_clean_git", require_clean_git)):
        parsed = command._parse_bool(raw)
        if parsed is None:
            return None, command._invalid_bool(name, raw, project)
        values.append(parsed)
    return (project, *values), None


def _version_plan(command, project, bump, manifest, new_version):
    bump_value = str(bump).strip().lower()
    if bump_value not in {"patch", "minor", "major"}:
        return None, command._failure(
            "invalid_bump", f"bump must be patch, minor, or major; got {bump!r}. No default was substituted.",
            path=str(project), bump=bump,
        )
    selected = command._select_manifest(project, manifest)
    if not selected["success"]:
        return None, selected
    updated = command._manifest_update(
        selected["path"], selected["manifest_type"], bump_value, new_version
    )
    if not updated["success"]:
        return None, updated
    return (bump_value, selected, updated), None


def _release_notes(command, release_notes, project):
    notes = str(release_notes).strip() if release_notes is not None else ""
    if len(notes) > 20_000:
        return None, command._failure(
            "release_notes_too_large", "release_notes must not exceed 20,000 characters.",
            path=str(project), characters=len(notes),
        )
    return notes, None


def _blockers(git_state, require_clean_git, update_changelog, notes):
    blockers = []
    if require_clean_git and not git_state["is_repository"]:
        blockers.append("The project is not a Git worktree or Git is unavailable.")
    elif require_clean_git and not git_state["clean"]:
        blockers.append("The Git worktree contains tracked or untracked changes.")
    if update_changelog and not notes:
        blockers.append("Reviewed release_notes are required to update CHANGELOG.md.")
    return blockers


def _changelog(command, project, update, notes, version):
    path = project / "CHANGELOG.md"
    if update and path.is_symlink():
        return None, command._failure(
            "changelog_symlink_refused", "CHANGELOG.md must not be a symbolic link.",
            path=str(project), changelog=str(path),
        )
    if not update or not notes:
        return {"path": path, "content": None, "prefix": b""}, None
    raw = path.read_bytes() if path.is_file() else b""
    prefix = b"\xef\xbb\xbf" if raw.startswith(b"\xef\xbb\xbf") else b""
    current = raw[len(prefix) :].decode("utf-8")
    newline = "\r\n" if "\r\n" in current else "\n"
    entry = f"## [{version}] - {date.today().isoformat()}\n\n{notes}\n\n"
    return {"path": path, "content": entry.replace("\n", newline) + current, "prefix": prefix}, None


def _plan(command, project, selected, updated, bump, new_version, update_changelog, git_state, blockers):
    changelog = project / "CHANGELOG.md"
    return {
        "project_path": str(project), "manifest": str(selected["path"]),
        "manifest_type": selected["manifest_type"], "old_version": updated["old_version"],
        "new_version": updated["new_version"],
        "version_source": "explicit" if new_version not in (None, "") else bump,
        "update_changelog": update_changelog,
        "changelog": str(changelog) if update_changelog else None,
        "git": git_state, "ready_to_apply": not blockers, "blockers": blockers,
        "excluded_stages": list(command.excluded_stages),
    }


def _preview(plan, selected, updated):
    return {
        "success": True, "status": "preview", "dry_run": True,
        "changes_applied": False, "plan": plan,
        "message": f"Prepared a preview from {updated['old_version']} to {updated['new_version']} using {selected['path'].name}. No files, commits, tags, builds, packages, or deployments were changed.",
    }


def _blocked(plan):
    return {
        "success": False, "status": "blocked",
        "error_code": "release_preconditions_failed",
        "error": "Release preparation preconditions failed.",
        "dry_run": False, "changes_applied": False, "plan": plan,
        "message": "Release metadata was not changed. Resolve every item in plan.blockers and preview the operation again.",
    }


def _transaction_files(selected, updated, changelog, update_changelog):
    manifest = selected["path"]
    files = [{"path": manifest, "original": manifest.read_bytes(), "updated": updated["content_bytes"], "mode": manifest.stat().st_mode}]
    if update_changelog:
        path = changelog["path"]
        files.append({
            "path": path, "original": path.read_bytes() if path.exists() else None,
            "updated": changelog["prefix"] + changelog["content"].encode("utf-8"),
            "mode": path.stat().st_mode if path.exists() else None,
        })
    return files


def _applied_result(plan, updated, update_changelog, transaction):
    plan["transaction"] = transaction
    if not transaction["success"]:
        return {
            "success": False, "status": "failed", "error_code": "release_metadata_write_failed",
            "error": transaction["error"], "dry_run": False,
            "changes_applied": transaction["changes_remaining"], "plan": plan,
            "message": "Release metadata could not be applied atomically. Rollback was attempted; inspect plan.transaction and use the QZX safety backup if any change remains.",
        }
    changed = " and CHANGELOG.md" if update_changelog else ""
    return {
        "success": True, "status": "prepared", "dry_run": False,
        "changes_applied": True, "plan": plan,
        "message": f"Prepared release metadata from {updated['old_version']} to {updated['new_version']}. QZX changed only the selected manifest{changed}; tests, build, commit, tag, publication, and deployment remain separate operator-controlled stages.",
    }


def execute_prepare_release(command, bump="patch", path=".", dry_run=True, new_version=None, release_notes=None, update_changelog=True, require_clean_git=True, manifest=None):
    values, failure = _path_and_flags(command, path, dry_run, update_changelog, require_clean_git)
    if failure:
        return failure
    project, dry_run, update_changelog, require_clean_git = values
    version_data, failure = _version_plan(command, project, bump, manifest, new_version)
    if failure:
        return failure
    bump, selected, updated = version_data
    notes, failure = _release_notes(command, release_notes, project)
    if failure:
        return failure
    git_state = command._git_state(project)
    blockers = _blockers(git_state, require_clean_git, update_changelog, notes)
    changelog, failure = _changelog(command, project, update_changelog, notes, updated["new_version"])
    if failure:
        return failure
    plan = _plan(command, project, selected, updated, bump, new_version, update_changelog, git_state, blockers)
    if dry_run:
        return _preview(plan, selected, updated)
    if blockers:
        return _blocked(plan)
    files = _transaction_files(selected, updated, changelog, update_changelog)
    transaction = command._replace_transaction(files)
    return _applied_result(plan, updated, update_changelog, transaction)
