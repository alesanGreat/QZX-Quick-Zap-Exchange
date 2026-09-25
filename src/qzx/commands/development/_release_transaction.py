"""Git preflight and atomic writes for ``prepareRelease``."""

import os
import subprocess
import tempfile
from pathlib import Path


def _run_git(project_path, arguments):
    return subprocess.run(
        ["git", *arguments], cwd=project_path, capture_output=True, text=True,
        encoding="utf-8", errors="replace", timeout=10, check=False,
    )


def git_state(project_path):
    result = {"available": False, "is_repository": False, "clean": False, "branch": None, "changes": [], "error": None}
    try:
        inside = _run_git(project_path, ["rev-parse", "--is-inside-work-tree"])
        result["available"] = True
        if inside.returncode != 0 or inside.stdout.strip() != "true":
            result["error"] = inside.stderr.strip() or "Path is not inside a Git worktree."
            return result
        result["is_repository"] = True
        status = _run_git(project_path, ["status", "--porcelain=v1", "--untracked-files=all"])
        if status.returncode != 0:
            result["error"] = status.stderr.strip() or "git status failed"
            return result
        changes = [line for line in status.stdout.splitlines() if line.strip()]
        result.update(changes=changes[:100], clean=not changes)
        branch = _run_git(project_path, ["branch", "--show-current"])
        if branch.returncode == 0:
            result["branch"] = branch.stdout.strip() or None
    except (OSError, subprocess.SubprocessError) as exc:
        result["error"] = f"{type(exc).__name__}: {exc}"
    return result


def _write_temporary(item):
    target = item["path"]
    target.parent.mkdir(parents=True, exist_ok=True)
    descriptor, name = tempfile.mkstemp(prefix=f".{target.name}.qzx-", suffix=".tmp", dir=target.parent)
    with os.fdopen(descriptor, "wb") as stream:
        stream.write(item["updated"])
        stream.flush()
        os.fsync(stream.fileno())
    if item.get("mode") is not None:
        os.chmod(name, item["mode"])
    return Path(name)


def _rollback(cls, replaced):
    errors = []
    for item in reversed(replaced):
        try:
            if item["original"] is None:
                item["path"].unlink(missing_ok=True)
            else:
                cls._atomic_restore(item["path"], item["original"])
        except Exception as exc:
            errors.append(f"{item['path']}: {type(exc).__name__}: {exc}")
    return errors


def replace_transaction(cls, files):
    temporary, replaced = {}, []
    try:
        for item in files:
            temporary[item["path"]] = _write_temporary(item)
        for item in files:
            os.replace(temporary.pop(item["path"]), item["path"])
            replaced.append(item)
        return {"success": True, "updated_files": [str(item["path"]) for item in files], "rollback_attempted": False, "rollback_succeeded": None, "changes_remaining": False}
    except Exception as exc:
        errors = _rollback(cls, replaced)
        return {
            "success": False, "error": f"{type(exc).__name__}: {exc}",
            "updated_files_before_failure": [str(item["path"]) for item in replaced],
            "rollback_attempted": bool(replaced), "rollback_succeeded": not errors,
            "rollback_errors": errors, "changes_remaining": bool(errors),
        }
    finally:
        for path in temporary.values():
            try:
                path.unlink(missing_ok=True)
            except OSError:
                pass


def atomic_restore(target, content):
    descriptor, name = tempfile.mkstemp(prefix=f".{target.name}.qzx-rollback-", suffix=".tmp", dir=target.parent)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(name, target)
    finally:
        try:
            os.unlink(name)
        except FileNotFoundError:
            pass
