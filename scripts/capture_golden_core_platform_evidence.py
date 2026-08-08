#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Capture sanitized, reviewable Golden Core evidence on one real CI host."""

from __future__ import annotations

import argparse
import getpass
import hashlib
import json
import os
import platform
import re
import subprocess
import sys
import tempfile
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = PROJECT_ROOT / "src"
if str(SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(SOURCE_ROOT))
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import qzx  # noqa: E402
from qzx.core.result_contract import (  # noqa: E402
    RESULT_CONTRACT_SCHEMA_URL,
    result_contract_violations,
)
from scripts.verify_golden_core import (  # noqa: E402
    load_golden_core,
    validate_golden_core,
)


SCHEMA_VERSION = 1
EXPECTED_COMMAND_COUNT = 15
EXPECTED_QZX_COMMAND_COUNT = 87
_LOOPBACK_URL_PATTERN = re.compile(r"http://127\.0\.0\.1:\d+")


class EvidenceHttpHandler(BaseHTTPRequestHandler):
    """Serve one deterministic, authorized loopback response."""

    protocol_version = "HTTP/1.1"
    server_version = "QZX-platform-evidence"
    sys_version = ""

    def date_time_string(self, _timestamp=None):
        return "Sat, 08 Aug 2026 00:00:00 GMT"

    def do_GET(self):
        body = b"qzx-platform-evidence"
        self.send_response(200)
        self.send_header("Content-Type", "text/plain")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, _format, *_args):
        return


@contextmanager
def local_http_server():
    """Yield an HTTP URL bound only to the local loopback interface."""

    server = ThreadingHTTPServer(("127.0.0.1", 0), EvidenceHttpHandler)
    server.daemon_threads = True
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        host, port = server.server_address
        yield f"http://{host}:{port}/ok"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
        if thread.is_alive():
            raise RuntimeError("The platform-evidence HTTP server did not stop.")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        required=True,
        help="Destination JSON file for this one-host evidence record.",
    )
    parser.add_argument(
        "--environment-id",
        required=True,
        help="Stable matrix environment identifier.",
    )
    parser.add_argument(
        "--environment-name",
        required=True,
        help="Human-readable matrix environment name.",
    )
    return parser.parse_args()


def canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def sha256_value(value: Any) -> str:
    return "sha256:" + hashlib.sha256(canonical_json_bytes(value)).hexdigest()


def source_revision() -> str:
    github_sha = os.environ.get("GITHUB_SHA", "").strip()
    if re.fullmatch(r"[a-f0-9]{40}", github_sha):
        return github_sha
    completed = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
        timeout=30,
    )
    revision = completed.stdout.strip()
    if completed.returncode != 0 or re.fullmatch(r"[a-f0-9]{40}", revision) is None:
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


def replacement_pairs(fixture_root: Path) -> list[tuple[str, str]]:
    values: list[tuple[str, str]] = []
    candidates = [
        (str(fixture_root.resolve()), "<fixture-root>"),
        (str(PROJECT_ROOT.resolve()), "<checkout>"),
        (str(Path.home().resolve()), "<home>"),
        (os.environ.get("RUNNER_TEMP", ""), "<runner-temp>"),
        (os.environ.get("RUNNER_TOOL_CACHE", ""), "<runner-tool-cache>"),
        (os.environ.get("GITHUB_WORKSPACE", ""), "<checkout>"),
        (platform.node(), "<hostname>"),
        (getpass.getuser(), "<user>"),
    ]
    for raw, replacement in candidates:
        if not raw:
            continue
        for variant in path_variants(str(raw)) or {str(raw)}:
            values.append((variant, replacement))
    return sorted(set(values), key=lambda item: len(item[0]), reverse=True)


def sanitize_text(value: str, replacements: list[tuple[str, str]]) -> str:
    sanitized = value
    for source, replacement in replacements:
        sanitized = sanitized.replace(source, replacement)
        sanitized = sanitized.replace(source.casefold(), replacement)
    sanitized = _LOOPBACK_URL_PATTERN.sub(
        "http://127.0.0.1:<ephemeral-port>",
        sanitized,
    )
    return sanitized


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
    files = root / "files"
    (files / "nested").mkdir(parents=True)
    (files / "alpha.txt").write_bytes(
        b"QZX alpha evidence\nsecond line\n"
    )
    (files / "nested" / "beta.txt").write_bytes(
        b"prefix qzx suffix\n"
    )
    (files / "ignored.log").write_text("unrelated\n", encoding="utf-8")

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

    repository = root / "repository"
    repository.mkdir()
    run_git(["init", "--initial-branch=main"], repository)
    run_git(["config", "user.name", "QZX Evidence Fixture"], repository)
    run_git(
        ["config", "user.email", "qzx-evidence@example.invalid"],
        repository,
    )
    run_git(["config", "core.autocrlf", "false"], repository)
    run_git(["config", "commit.gpgsign", "false"], repository)
    (repository / "tracked.txt").write_text(
        "QZX controlled Git evidence\n",
        encoding="utf-8",
    )
    run_git(["add", "tracked.txt"], repository)
    fixed_environment = {
        "GIT_AUTHOR_NAME": "QZX Evidence Fixture",
        "GIT_AUTHOR_EMAIL": "qzx-evidence@example.invalid",
        "GIT_COMMITTER_NAME": "QZX Evidence Fixture",
        "GIT_COMMITTER_EMAIL": "qzx-evidence@example.invalid",
        "GIT_AUTHOR_DATE": "2026-08-08T00:00:00+00:00",
        "GIT_COMMITTER_DATE": "2026-08-08T00:00:00+00:00",
    }
    run_git(
        ["commit", "-m", "Create controlled QZX evidence fixture"],
        repository,
        environment=fixed_environment,
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
    return {
        "files": files,
        "project": project,
        "repository": repository,
    }


def command_assertions(name: str, document: dict[str, Any]) -> list[str]:
    assertions = [
        "exit_code=0",
        "result_contract_v1",
        "success=true",
        f"meta.command={name}",
    ]
    if name == "version":
        if document.get("version") != qzx.__version__:
            raise AssertionError("version did not report the installed QZX version.")
        if document.get("qzx_info", {}).get("command_count") != EXPECTED_QZX_COMMAND_COUNT:
            raise AssertionError("version did not report 87 commands.")
        assertions.extend(["version_matches_package", "command_count=87"])
    elif name == "listCommands":
        if document.get("summary", {}).get("commands") != EXPECTED_QZX_COMMAND_COUNT:
            raise AssertionError("listCommands did not report 87 commands.")
        assertions.append("command_count=87")
    elif name == "help":
        if document.get("details", {}).get("name") != "findFiles":
            raise AssertionError("help did not describe findFiles.")
        assertions.append("describes=findFiles")
    elif name == "getCurrentDateTime":
        if (
            document.get("output_format") != "iso"
            or not isinstance(document.get("output"), str)
            or document.get("output") != document.get("iso_format")
        ):
            raise AssertionError("getCurrentDateTime did not expose ISO output.")
        assertions.append("iso_datetime_present")
    elif name == "getCurrentDirectory":
        if document.get("current_dir") != "<fixture-root>":
            raise AssertionError("getCurrentDirectory did not observe the fixture root.")
        assertions.append("current_dir=<fixture-root>")
    elif name == "systemInfo":
        if document.get("system_info", {}).get("os") != platform.system():
            raise AssertionError("systemInfo did not report the real host OS.")
        assertions.append("os_matches_runner")
    elif name == "getDiskSpace":
        if not isinstance(document.get("disk_info", {}).get("total_bytes"), int):
            raise AssertionError("getDiskSpace did not expose raw capacity.")
        assertions.append("raw_capacity_present")
    elif name == "getRamInfo":
        if not isinstance(
            document.get("ram_info", {}).get("virtual_memory", {}).get("total"),
            int,
        ):
            raise AssertionError("getRamInfo did not expose raw memory capacity.")
        assertions.append("raw_memory_present")
    elif name == "listFiles":
        names = [item.get("name") for item in document.get("files", [])]
        if names != ["alpha.txt", "beta.txt"]:
            raise AssertionError(f"listFiles returned unexpected names: {names}")
        if document.get("recursive") is not True:
            raise AssertionError("listFiles did not report recursive=true.")
        assertions.extend(["recursive=true", "files=alpha.txt,beta.txt"])
    elif name == "findFiles":
        names = [item.get("name") for item in document.get("results", [])]
        if names != ["alpha.txt", "beta.txt"]:
            raise AssertionError(f"findFiles returned unexpected names: {names}")
        assertions.append("files=alpha.txt,beta.txt")
    elif name == "findText":
        if document.get("total_matches") != 2:
            raise AssertionError("findText did not report two controlled matches.")
        assertions.append("matches=2")
    elif name == "getFileHash":
        expected = hashlib.sha256(
            b"QZX alpha evidence\nsecond line\n"
        ).hexdigest()
        if document.get("hash") != expected:
            raise AssertionError("getFileHash returned an unexpected digest.")
        assertions.append("sha256_matches_fixture")
    elif name == "getGitStatus":
        changes = document.get("changes", {})
        if (
            document.get("branch") != "main"
            or "tracked.txt" not in changes.get("modified", [])
            or "staged.txt" not in changes.get("staged", [])
            or "untracked.txt" not in changes.get("untracked", [])
        ):
            raise AssertionError("getGitStatus did not report the fixture state.")
        assertions.append("branch_and_changes_verified")
    elif name == "projectDoctor":
        observed_path = document.get("details", {}).get("path")
        if observed_path not in {
            "<fixture-root>/project",
            "<fixture-root>\\project",
        }:
            raise AssertionError("projectDoctor did not inspect the fixture project.")
        assertions.append("fixture_project_inspected")
    elif name == "checkUrlStatus":
        if document.get("status_code") != 200 or document.get("is_online") is not True:
            raise AssertionError("checkUrlStatus did not observe the loopback HTTP 200.")
        assertions.append("authorized_loopback_http_200")
    return assertions


def run_qzx(
    name: str,
    arguments: list[str],
    *,
    cwd: Path,
    replacements: list[tuple[str, str]],
) -> dict[str, Any]:
    command = [sys.executable, "-B", "-m", "qzx", *arguments, "--json"]
    environment = dict(os.environ)
    environment["QZX_TELEMETRY"] = "0"
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    started = time.monotonic()
    completed = subprocess.run(
        command,
        cwd=cwd,
        env=environment,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
        timeout=90,
    )
    elapsed_ms = round((time.monotonic() - started) * 1000, 3)
    if completed.returncode != 0:
        raise RuntimeError(
            f"{name} exited with {completed.returncode}: {completed.stderr.strip()}"
        )
    try:
        document = json.loads(completed.stdout)
    except json.JSONDecodeError as exception:
        raise RuntimeError(f"{name} did not print one JSON document.") from exception
    if not isinstance(document, dict):
        raise RuntimeError(f"{name} did not print a JSON object.")
    violations = result_contract_violations(document)
    if violations:
        raise RuntimeError(f"{name} violated Result Contract v1: {violations}")
    if document.get("success") is not True:
        raise RuntimeError(f"{name} reported failure: {document.get('message')}")
    meta = document.get("meta")
    if not isinstance(meta, dict) or meta.get("command") != name:
        raise RuntimeError(f"{name} returned the wrong meta.command.")

    sanitized = sanitize_value(document, replacements)
    assertions = command_assertions(name, sanitized)
    stderr = sanitize_text(completed.stderr.strip(), replacements)
    return {
        "arguments": sanitize_value(arguments, replacements),
        "exit_code": completed.returncode,
        "elapsed_ms": elapsed_ms,
        "stderr": stderr,
        "result_sha256": sha256_value(sanitized),
        "assertions": assertions,
        "result": sanitized,
    }


def environment_facts(environment_id: str, environment_name: str) -> dict[str, Any]:
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


def capture(environment_id: str, environment_name: str) -> dict[str, Any]:
    registry = load_golden_core()
    registry_errors = validate_golden_core(registry)
    if registry_errors:
        raise RuntimeError("Golden Core registry is invalid: " + "; ".join(registry_errors))
    selected = [item["name"] for item in registry["commands"]]
    if len(selected) != EXPECTED_COMMAND_COUNT:
        raise RuntimeError("Golden Core no longer contains exactly 15 commands.")

    with tempfile.TemporaryDirectory(prefix="qzx-golden-core-") as temporary:
        fixture_root = Path(temporary).resolve()
        fixtures = create_fixtures(fixture_root)
        replacements = replacement_pairs(fixture_root)
        records: dict[str, dict[str, Any]] = {}
        with local_http_server() as local_url:
            commands = {
                "version": (["version"], fixture_root),
                "listCommands": (["listCommands"], fixture_root),
                "help": (["help", "findFiles"], fixture_root),
                "getCurrentDateTime": (
                    ["getCurrentDateTime", "--output-format", "iso"],
                    fixture_root,
                ),
                "getCurrentDirectory": (["getCurrentDirectory"], fixture_root),
                "systemInfo": (["systemInfo"], fixture_root),
                "getDiskSpace": (["getDiskSpace", str(fixture_root)], fixture_root),
                "getRamInfo": (["getRamInfo"], fixture_root),
                "listFiles": (
                    ["listFiles", str(fixtures["files"]), "*.txt", "-r"],
                    fixture_root,
                ),
                "findFiles": (
                    ["findFiles", str(fixtures["files"]), "*.txt", "-r"],
                    fixture_root,
                ),
                "findText": (
                    [
                        "findText",
                        "QZX",
                        str(fixtures["files"]),
                        "-r",
                        "--regex=false",
                        "--case-sensitive=false",
                        "--file-pattern=*.txt",
                        "--context-lines=1",
                        "--max-matches=10",
                        "--colored=false",
                    ],
                    fixture_root,
                ),
                "getFileHash": (
                    [
                        "getFileHash",
                        str(fixtures["files"] / "alpha.txt"),
                        "sha256",
                    ],
                    fixture_root,
                ),
                "getGitStatus": (
                    ["getGitStatus", str(fixtures["repository"])],
                    fixture_root,
                ),
                "projectDoctor": (
                    ["projectDoctor", str(fixtures["project"])],
                    fixture_root,
                ),
                "checkUrlStatus": (
                    ["checkUrlStatus", local_url, "5"],
                    fixture_root,
                ),
            }
            if set(commands) != set(selected):
                raise RuntimeError(
                    "Platform evidence command set differs from Golden Core: "
                    f"expected {selected}, observed {sorted(commands)}."
                )
            for name in selected:
                arguments, cwd = commands[name]
                records[name] = run_qzx(
                    name,
                    arguments,
                    cwd=cwd,
                    replacements=replacements,
                )

    environment = environment_facts(environment_id, environment_name)
    result = {
        "schema_version": SCHEMA_VERSION,
        "evidence_type": "qzx_golden_core_platform_run",
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "source_revision": source_revision(),
        "qzx_version": qzx.__version__,
        "result_contract": RESULT_CONTRACT_SCHEMA_URL,
        "golden_core": {
            "name": registry["name"],
            "status": registry["status"],
            "selected_on": registry["selected_on"],
            "command_count": len(selected),
            "commands": selected,
        },
        "environment": environment,
        "commands": records,
        "summary": {
            "command_count": len(records),
            "passed": len(records),
            "failed": 0,
            "systems_observed": [environment["system"]],
        },
        "scope": {
            "success_only": True,
            "network": "authorized loopback HTTP only",
            "repository": "disposable local Git fixture only",
            "secrets": "environment values and private project data are not requested",
            "claim": (
                "This record proves only the observed QZX version, source "
                "revision, host environment, fixtures, arguments, and results."
            ),
        },
    }
    result["evidence_sha256"] = sha256_value(result)
    return result


def main() -> int:
    arguments = parse_args()
    document = capture(arguments.environment_id, arguments.environment_name)
    arguments.output.parent.mkdir(parents=True, exist_ok=True)
    arguments.output.write_bytes(
        (json.dumps(document, ensure_ascii=False, indent=2) + "\n").encode(
            "utf-8"
        )
    )
    print(
        "Captured {} Golden Core commands on {} ({}).".format(
            document["summary"]["passed"],
            document["environment"]["name"],
            document["environment"]["system"],
        )
    )
    print("Evidence SHA-256: {}".format(document["evidence_sha256"]))
    print("Output: {}".format(arguments.output))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
