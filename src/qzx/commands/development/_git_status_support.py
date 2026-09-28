"""Cohesive Git-status collection for :mod:`get_git_status`."""

import os
import subprocess


def _failure(message):
    return {"success": False, "error": message, "message": message}


def _validate_repository_path(repo_path):
    absolute = os.path.abspath(repo_path)
    if not os.path.exists(absolute):
        return None, _failure(f"Path '{repo_path}' does not exist.")
    if not os.path.isdir(absolute):
        return None, _failure(
            f"'{repo_path}' is not a directory. Git status requires a directory path."
        )
    return absolute, None


def _git_available():
    try:
        subprocess.run(
            ["git", "--version"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True,
        )
        return True
    except (subprocess.SubprocessError, FileNotFoundError):
        return False


def _is_git_worktree(path):
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--is-inside-work-tree"],
            cwd=path,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=False,
        )
    except Exception:
        return False
    return result.returncode == 0 and result.stdout.strip() == "true"


def _tracking_state(command, path):
    tracking = command._run_git(
        ["git", "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}"],
        path,
    )
    ahead = behind = 0
    if tracking:
        counts = command._run_git(
            ["git", "rev-list", "--left-right", "--count", "HEAD...@{u}"],
            path,
        )
        parts = counts.split("\t") if counts else []
        if len(parts) == 2:
            try:
                ahead, behind = map(int, parts)
            except ValueError:
                pass
    return tracking, ahead, behind


def _changes(command, path):
    names = ("staged", "modified", "untracked", "deleted", "renamed")
    groups = {name: [] for name in names}
    rows = command._run_git(
        ["git", "status", "--porcelain"], path, split_lines=True
    )
    for line in rows:
        if len(line) < 4:
            continue
        status, file_name = line[:2], line[3:]
        x, y = status
        if x in ("M", "A", "D", "R", "C"):
            groups["staged"].append(file_name)
        if y == "M":
            groups["modified"].append(file_name)
        elif y == "D" or (x == "D" and y == " "):
            groups["deleted"].append(file_name)
        elif status == "??":
            groups["untracked"].append(file_name)
    return groups


def _remotes(command, path):
    remotes = {}
    rows = command._run_git(["git", "remote", "-v"], path, split_lines=True)
    for line in rows:
        parts = line.split()
        if len(parts) < 2:
            continue
        purpose = parts[2].strip("()") if len(parts) >= 3 else "fetch"
        remotes.setdefault(parts[0], {})[purpose] = parts[1]
    return remotes


def _recent_commits(command, path):
    rows = command._run_git(
        ["git", "log", "-n", "5", "--pretty=format:%h|%an|%ad|%s", "--date=short"],
        path,
        split_lines=True,
    )
    commits = []
    for row in rows:
        parts = row.split("|", 3)
        if len(parts) == 4:
            commits.append(
                dict(zip(("hash", "author", "date", "subject"), parts, strict=True))
            )
    return commits


def _message(path, branch, tracking, ahead, behind, changes, commits):
    text = f"Git Repository Status for '{path}':\n- Branch: {branch or 'Detached HEAD'}\n"
    text += (
        f"- Tracking: {tracking} (Ahead: {ahead}, Behind: {behind})\n"
        if tracking
        else "- Tracking: None\n"
    )
    counts = [len(changes[name]) for name in ("staged", "modified", "untracked", "deleted")]
    text += "- Uncommitted Changes: Staged={}, Modified={}, Untracked={}, Deleted={}\n".format(*counts)
    if commits:
        latest = commits[0]
        text += (
            f"- Latest Commit: [{latest['hash']}] {latest['subject']} by "
            f"{latest['author']} ({latest['date']})"
        )
    return text


def _repository_result(command, path, branch, tracking, ahead, behind):
    changes = _changes(command, path)
    commits = _recent_commits(command, path)
    names = ("staged", "modified", "untracked", "deleted")
    counts = {f"{name}_count": len(changes[name]) for name in names}
    counts["total_changes"] = sum(counts.values())
    return {
        "success": True,
        "is_git_repository": True,
        "repo_path": path,
        "branch": branch,
        "tracking_branch": tracking or None,
        "sync_status": {
            "ahead": ahead,
            "behind": behind,
            "in_sync": ahead == behind == 0 if tracking else True,
        },
        "changes": changes,
        "changes_summary": counts,
        "remotes": _remotes(command, path),
        "recent_commits": commits,
        "message": _message(path, branch, tracking, ahead, behind, changes, commits),
    }


def execute_git_status(command, repo_path="."):
    """Collect the complete public result while preserving command seams."""
    path, error = _validate_repository_path(repo_path)
    if error:
        return error
    if not _git_available():
        return _failure("Git is not installed or not available in the system PATH.")
    if not _is_git_worktree(path):
        return {
            "success": True,
            "is_git_repository": False,
            "repo_path": path,
            "message": f"Directory '{path}' is not a Git repository.",
        }
    try:
        branch = command._run_git(["git", "branch", "--show-current"], path)
        branch = branch or command._run_git(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"], path
        )
        tracking, ahead, behind = _tracking_state(command, path)
        return _repository_result(command, path, branch, tracking, ahead, behind)
    except Exception as exc:
        return _failure(f"Failed to retrieve git status: {exc}")


def run_git(_command, cmd, cwd, split_lines=False):
    """Run one read-only Git command and normalize its stdout."""
    try:
        result = subprocess.run(
            cmd, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, check=False,
        )
        if result.returncode != 0:
            return [] if split_lines else ""
        if split_lines:
            return [line.rstrip("\r\n") for line in result.stdout.splitlines() if line.strip()]
        return result.stdout.strip()
    except Exception:
        return [] if split_lines else ""
