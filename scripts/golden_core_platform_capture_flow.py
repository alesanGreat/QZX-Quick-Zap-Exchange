"""Orchestrate one-host Golden Core platform evidence capture."""

from __future__ import annotations

import tempfile
from datetime import datetime, timezone
from pathlib import Path

import qzx
from qzx.core.command_loader import CommandLoader
from qzx.core.implementation_digest import command_implementation_digest
from qzx.core.result_contract import RESULT_CONTRACT_SCHEMA_URL
from scripts.golden_core_platform_common import (
    environment_facts,
    replacement_pairs,
    sha256_value,
    source_revision,
)
from scripts.golden_core_platform_execution import run_qzx
from scripts.golden_core_platform_fixtures import create_fixtures
from scripts.verify_golden_core import load_golden_core, validate_golden_core


PROJECT_ROOT = Path(__file__).resolve().parents[1]
EXPECTED_COMMAND_COUNT = 15
SCHEMA_VERSION = 2


def capture_platform_evidence(
    environment_id: str,
    environment_name: str,
    *,
    local_http_server,
):
    """Capture all selected Golden Core commands on one real host."""
    registry, selected = _validated_registry()
    loader = CommandLoader()
    records = _capture_records(
        selected,
        loader,
        local_http_server,
    )
    environment = environment_facts(environment_id, environment_name)
    result = _evidence_document(
        registry,
        selected,
        environment,
        records,
    )
    result["evidence_sha256"] = sha256_value(result)
    return result


def _validated_registry():
    registry = load_golden_core()
    errors = validate_golden_core(registry)
    if errors:
        raise RuntimeError(
            "Golden Core registry is invalid: " + "; ".join(errors)
        )
    selected = [item["name"] for item in registry["commands"]]
    if len(selected) != EXPECTED_COMMAND_COUNT:
        raise RuntimeError(
            "Golden Core no longer contains exactly 15 commands."
        )
    return registry, selected


def _capture_records(selected, loader, local_http_server):
    with tempfile.TemporaryDirectory(
        prefix="qzx-golden-core-"
    ) as temporary:
        fixture_root = Path(temporary).resolve()
        fixtures = create_fixtures(fixture_root)
        replacements = replacement_pairs(fixture_root, PROJECT_ROOT)
        with local_http_server() as local_url:
            commands = _command_plan(
                fixture_root,
                fixtures,
                local_url,
            )
            _validate_command_selection(selected, commands)
            return _run_selected_commands(
                selected,
                commands,
                loader,
                replacements,
            )


def _validate_command_selection(selected, commands):
    if set(commands) != set(selected):
        raise RuntimeError(
            "Platform evidence command set differs from Golden Core: "
            f"expected {selected}, observed {sorted(commands)}."
        )


def _run_selected_commands(selected, commands, loader, replacements):
    records = {}
    for name in selected:
        arguments, cwd = commands[name]
        record = run_qzx(
            name,
            arguments,
            cwd=cwd,
            replacements=replacements,
        )
        command = loader.get_command(name)
        if command is None:
            raise RuntimeError(
                f"Golden Core command '{name}' could not be loaded."
            )
        record["implementation_digest"] = command_implementation_digest(
            type(command)
        )
        records[name] = record
    return records


def _command_plan(fixture_root, fixtures, local_url):
    commands = {}
    commands.update(_identity_command_plan(fixture_root))
    commands.update(_file_command_plan(fixture_root, fixtures))
    commands.update(_project_command_plan(fixture_root, fixtures, local_url))
    return commands


def _identity_command_plan(fixture_root):
    return {
        "version": (["version"], fixture_root),
        "listCommands": (["listCommands"], fixture_root),
        "help": (["help", "findFiles"], fixture_root),
        "getCurrentDateTime": (
            ["getCurrentDateTime", "--output-format", "iso"],
            fixture_root,
        ),
        "getCurrentDirectory": (["getCurrentDirectory"], fixture_root),
        "getSystemInfo": (["getSystemInfo"], fixture_root),
        "getDiskSpace": (
            ["getDiskSpace", str(fixture_root)],
            fixture_root,
        ),
        "getRamInfo": (["getRamInfo"], fixture_root),
    }


def _file_command_plan(fixture_root, fixtures):
    files = fixtures["files"]
    return {
        "listFiles": (
            ["listFiles", str(files), "*.txt", "-r"],
            fixture_root,
        ),
        "findFiles": (
            ["findFiles", str(files), "*.txt", "-r"],
            fixture_root,
        ),
        "findText": (
            [
                "findText",
                "QZX",
                str(files),
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
        "calculateFileHash": (
            [
                "calculateFileHash",
                str(files / "alpha.txt"),
                "sha256",
            ],
            fixture_root,
        ),
    }


def _project_command_plan(fixture_root, fixtures, local_url):
    return {
        "getGitStatus": (
            ["getGitStatus", str(fixtures["repository"])],
            fixture_root,
        ),
        "diagnoseProject": (
            ["diagnoseProject", str(fixtures["project"])],
            fixture_root,
        ),
        "checkUrlStatus": (
            ["checkUrlStatus", local_url, "5"],
            fixture_root,
        ),
    }


def _evidence_document(registry, selected, environment, records):
    return {
        "schema_version": SCHEMA_VERSION,
        "evidence_type": "qzx_golden_core_platform_run",
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "source_revision": source_revision(PROJECT_ROOT),
        "qzx_version": qzx.__version__,
        "result_contract": RESULT_CONTRACT_SCHEMA_URL,
        "golden_core": _golden_core_identity(registry, selected),
        "environment": environment,
        "commands": records,
        "summary": _summary(records, environment),
        "scope": _scope(),
    }


def _golden_core_identity(registry, selected):
    return {
        "name": registry["name"],
        "status": registry["status"],
        "selected_on": registry["selected_on"],
        "command_count": len(selected),
        "commands": selected,
    }


def _summary(records, environment):
    return {
        "command_count": len(records),
        "passed": len(records),
        "failed": 0,
        "systems_observed": [environment["system"]],
    }


def _scope():
    return {
        "success_only": True,
        "network": "authorized loopback HTTP only",
        "repository": "disposable local Git fixture only",
        "secrets": (
            "environment values and private project data are not requested"
        ),
        "claim": (
            "This record proves only the observed QZX version, source "
            "revision, host environment, fixtures, arguments, and results."
        ),
    }
