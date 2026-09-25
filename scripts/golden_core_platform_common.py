"""Shared identity, sanitization, and environment helpers for Golden Core evidence."""

from __future__ import annotations

import getpass
import hashlib
import json
import os
import platform
import re
import subprocess
from pathlib import Path
from typing import Any


_LOOPBACK_URL_PATTERN = re.compile(r"http://127\.0\.0\.1:\d+")


def canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def sha256_value(value: Any) -> str:
    return "sha256:" + hashlib.sha256(canonical_json_bytes(value)).hexdigest()


def source_revision(project_root: Path) -> str:
    github_sha = os.environ.get("GITHUB_SHA", "").strip()
    if re.fullmatch(r"[a-f0-9]{40}", github_sha):
        return github_sha
    completed = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=project_root,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
        timeout=30,
    )
    revision = completed.stdout.strip()
    if (
        completed.returncode != 0
        or re.fullmatch(r"[a-f0-9]{40}", revision) is None
    ):
        raise RuntimeError("Unable to identify the QZX source revision.")
    return revision


def path_variants(value: str) -> set[str]:
    normalized = value.rstrip("/\\")
    if normalized == "":
        return set()
    return {
        normalized,
        normalized.replace("\\", "/"),
        normalized.replace("/", "\\"),
    }


def replacement_pairs(
    fixture_root: Path,
    project_root: Path,
) -> list[tuple[str, str]]:
    candidates = [
        (str(fixture_root.resolve()), "<fixture-root>"),
        (str(project_root.resolve()), "<checkout>"),
        (str(Path.home().resolve()), "<home>"),
        (os.environ.get("RUNNER_TEMP", ""), "<runner-temp>"),
        (os.environ.get("RUNNER_TOOL_CACHE", ""), "<runner-tool-cache>"),
        (os.environ.get("GITHUB_WORKSPACE", ""), "<checkout>"),
        (platform.node(), "<hostname>"),
        (getpass.getuser(), "<user>"),
    ]
    values = []
    for raw, replacement in candidates:
        if not raw:
            continue
        for variant in path_variants(str(raw)) or {str(raw)}:
            values.append((variant, replacement))
    return sorted(set(values), key=lambda item: len(item[0]), reverse=True)


def sanitize_text(value: str, replacements: list[tuple[str, str]]) -> str:
    replacement_map = {}
    for source, replacement in replacements:
        for candidate in (source, source.casefold()):
            if candidate:
                replacement_map.setdefault(candidate, replacement)

    sanitized = value
    if replacement_map:
        sources = sorted(replacement_map, key=lambda item: (-len(item), item))
        pattern = re.compile("|".join(re.escape(source) for source in sources))
        sanitized = pattern.sub(
            lambda match: replacement_map[match.group(0)],
            value,
        )
    return _LOOPBACK_URL_PATTERN.sub(
        "http://127.0.0.1:<ephemeral-port>",
        sanitized,
    )


def sanitize_value(value: Any, replacements: list[tuple[str, str]]) -> Any:
    if isinstance(value, str):
        return sanitize_text(value, replacements)
    if isinstance(value, list):
        return [sanitize_value(item, replacements) for item in value]
    if isinstance(value, dict):
        return {
            str(key): sanitize_value(item, replacements)
            for key, item in value.items()
        }
    return value


def environment_facts(
    environment_id: str,
    environment_name: str,
) -> dict[str, Any]:
    return {
        "id": environment_id,
        "name": environment_name,
        "system": platform.system(),
        "release": platform.release(),
        "version": platform.version(),
        "machine": platform.machine(),
        "processor": platform.processor(),
        "python": {
            "implementation": platform.python_implementation(),
            "version": platform.python_version(),
            "architecture": platform.architecture()[0],
        },
        "github": {
            "repository": os.environ.get("GITHUB_REPOSITORY"),
            "workflow": os.environ.get("GITHUB_WORKFLOW"),
            "run_id": os.environ.get("GITHUB_RUN_ID"),
            "run_attempt": os.environ.get("GITHUB_RUN_ATTEMPT"),
            "job": os.environ.get("GITHUB_JOB"),
            "runner_os": os.environ.get("RUNNER_OS"),
            "runner_arch": os.environ.get("RUNNER_ARCH"),
        },
    }
