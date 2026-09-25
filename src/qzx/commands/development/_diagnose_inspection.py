"""Read-only project inspection phases for ``diagnoseProject``."""

import os
import subprocess
from pathlib import Path

from qzx.commands.development.find_unused_code import FindUnusedCodeCommand
from qzx.commands.development.trace_circular_imports import TraceCircularImportsCommand
from qzx.core.recursive_findfiles_utils import SOURCE_ANALYSIS_EXCLUDED_DIRECTORIES


def detect_technologies(project_root, root_names):
    technologies = []
    if {"pyproject.toml", "setup.py", "setup.cfg", "Pipfile"} & root_names or any(name.startswith("requirements") and name.endswith(".txt") for name in root_names):
        technologies.append("Python")
    markers = (("package.json", "Node.js"), ("tsconfig.json", "TypeScript"), ("Cargo.toml", "Rust"), ("go.mod", "Go"))
    technologies.extend(label for marker, label in markers if marker in root_names)
    if "composer.json" in root_names or any(entry.is_file() and entry.suffix.casefold() == ".php" for entry in project_root.iterdir()):
        technologies.append("PHP")
    if {"CMakeLists.txt", "Makefile", "meson.build"} & root_names:
        technologies.append("C/C++")
    if {"Dockerfile", "compose.yml", "compose.yaml", "docker-compose.yml", "docker-compose.yaml"} & root_names:
        technologies.append("Docker")
    return technologies


def inspect_environment(root_names):
    local = [name for name in (".env", ".env.local", ".env.development", ".env.test") if name in root_names]
    templates = [name for name in (".env.example", ".env.template", ".env.sample", "env.example") if name in root_names]
    return {
        "local_files": local, "template_files": templates,
        "local_configuration_present": bool(local), "template_present": bool(templates),
        "values_inspected": False,
        "note": "Only environment filenames are reported; diagnoseProject never reads or returns environment values.",
    }


def run_git(project_root, *arguments):
    try:
        result = subprocess.run(
            ["git", *arguments], cwd=project_root, capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=8, check=False,
        )
    except FileNotFoundError:
        return {"status": "unavailable", "stdout": "", "error": "Git is not installed or is not available on PATH."}
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"status": "unavailable", "stdout": "", "error": str(exc)}
    return {"status": "ok" if result.returncode == 0 else "error", "stdout": result.stdout.strip(), "error": result.stderr.strip()}


def _divergence(command, root, upstream):
    if not upstream:
        return None, None
    result = command._run_git(root, "rev-list", "--left-right", "--count", f"HEAD...{upstream}")
    parts = result["stdout"].split() if result["status"] == "ok" else []
    if len(parts) == 2 and all(part.isdigit() for part in parts):
        return int(parts[0]), int(parts[1])
    return None, None


def inspect_git(command, project_root):
    probe = command._run_git(project_root, "rev-parse", "--show-toplevel")
    if probe["status"] == "unavailable":
        return {"status": "unavailable", "reason": probe["error"]}
    if probe["status"] == "error":
        return {"status": "not_repository", "reason": "Git did not identify a repository for this path."}
    branch_result = command._run_git(project_root, "rev-parse", "--abbrev-ref", "HEAD")
    status = command._run_git(project_root, "status", "--porcelain=v1", "--untracked-files=all")
    if status["status"] != "ok":
        return {"status": "error", "repository_root": probe["stdout"], "reason": status.get("error") or "Git status failed.", "clean": None, "changed_count": None, "untracked_count": None}
    lines = status["stdout"].splitlines()
    untracked = sum(line.startswith("??") for line in lines)
    upstream_result = command._run_git(project_root, "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{upstream}")
    upstream = upstream_result["stdout"] if upstream_result["status"] == "ok" else None
    ahead, behind = _divergence(command, project_root, upstream)
    branch = branch_result["stdout"] if branch_result["status"] == "ok" else "unknown"
    return {
        "status": "inspected", "repository_root": probe["stdout"], "branch": branch,
        "detached_head": branch == "HEAD", "clean": not lines,
        "changed_count": len(lines) - untracked, "untracked_count": untracked,
        "upstream": upstream, "commits_ahead": ahead, "commits_behind": behind,
    }


def _unused_code(project_root):
    result = FindUnusedCodeCommand().execute(scan_path=str(project_root))
    if result.get("success"):
        count = result.get("candidate_symbols_count", 0)
        return {
            "status": "attention" if count else "passed",
            "candidate_symbols_count": count,
            "candidate_symbols": result.get("candidate_symbols", [])[:10],
            "interpretation": "Candidates have no statically visible references; review dynamic uses before removal.",
        }
    return {"status": "error", "error": result.get("message", "Unused-code analysis failed without an explanation.")}


def _circular_imports(project_root):
    result = TraceCircularImportsCommand().execute(scan_path=str(project_root))
    if result.get("success"):
        count = result.get("cycles_count", 0)
        return {"status": "attention" if count else "passed", "cycles_count": count, "cycles": result.get("cycles", [])}
    return {"status": "error", "error": result.get("message", "Circular-import analysis failed without an explanation.")}


def inspect_source(project_root):
    return {"unused_code": _unused_code(project_root), "circular_imports": _circular_imports(project_root)}


def _eligible_directories(root_path, directories, excluded):
    return [
        name for name in directories
        if name.casefold() not in excluded and not (root_path / name).is_symlink()
    ]


def scan_large_files(command, project_root):
    threshold, maximum = 1024 * 1024, 5000
    excluded = {name.casefold() for name in SOURCE_ANALYSIS_EXCLUDED_DIRECTORIES} | {".git", ".dropbox", ".dropbox.cache", "artifacts"}
    large, scanned, errors, complete = [], 0, 0, True
    for root, directories, files in os.walk(project_root):
        root_path = Path(root)
        directories[:] = _eligible_directories(root_path, directories, excluded)
        for filename in files:
            if scanned >= maximum:
                complete = False
                break
            scanned += 1
            path = root_path / filename
            try:
                size = path.stat().st_size
            except OSError:
                errors += 1
                continue
            if size > threshold:
                large.append({"path": str(path.relative_to(project_root)), "size_bytes": size, "size_formatted": command._format_bytes(size)})
        if not complete:
            break
    return {
        "scanned_file_count": scanned, "maximum_file_count": maximum,
        "scan_complete": complete, "error_count": errors,
        "large_file_threshold_bytes": threshold,
        "large_file_threshold_formatted": command._format_bytes(threshold),
        "large_file_count": len(large), "large_files": large,
    }
