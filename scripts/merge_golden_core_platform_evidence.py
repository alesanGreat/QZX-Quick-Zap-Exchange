#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Validate and merge per-host QZX Golden Core platform evidence."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SCHEMA_VERSION = 1
EVIDENCE_TYPE = "qzx_golden_core_platform_run"
SUMMARY_TYPE = "qzx_golden_core_platform_summary"
REQUIRED_SYSTEMS = ("Windows", "Linux", "Darwin")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "inputs",
        nargs="+",
        type=Path,
        help="Evidence JSON files or directories containing them.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        required=True,
        help="Destination JSON file for the validated aggregate summary.",
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


def evidence_files(inputs: list[Path]) -> list[Path]:
    files: set[Path] = set()
    for candidate in inputs:
        if candidate.is_file():
            files.add(candidate.resolve())
        elif candidate.is_dir():
            files.update(path.resolve() for path in candidate.rglob("*.json"))
        else:
            raise FileNotFoundError(f"Evidence input does not exist: {candidate}")
    if not files:
        raise ValueError("No Golden Core platform evidence files were found.")
    return sorted(files)


def load_object(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        document = json.load(handle)
    if not isinstance(document, dict):
        raise ValueError(f"{path} must contain a JSON object.")
    return document


def verify_hash(document: dict[str, Any], field: str, context: str) -> None:
    observed = document.get(field)
    if not isinstance(observed, str):
        raise ValueError(f"{context} has no {field}.")
    payload = dict(document)
    payload.pop(field, None)
    expected = sha256_value(payload)
    if observed != expected:
        raise ValueError(
            f"{context} {field} mismatch: expected {expected}, observed {observed}."
        )


def validate_evidence(path: Path, document: dict[str, Any]) -> None:
    context = path.name
    if document.get("schema_version") != SCHEMA_VERSION:
        raise ValueError(f"{context} must use schema_version {SCHEMA_VERSION}.")
    if document.get("evidence_type") != EVIDENCE_TYPE:
        raise ValueError(f"{context} has an unexpected evidence_type.")
    verify_hash(document, "evidence_sha256", context)

    source_revision = document.get("source_revision")
    if (
        not isinstance(source_revision, str)
        or len(source_revision) != 40
        or any(character not in "0123456789abcdef" for character in source_revision)
    ):
        raise ValueError(f"{context} has an invalid source_revision.")
    if not isinstance(document.get("qzx_version"), str):
        raise ValueError(f"{context} has no qzx_version.")

    golden_core = document.get("golden_core")
    if not isinstance(golden_core, dict):
        raise ValueError(f"{context} has no Golden Core identity.")
    commands = golden_core.get("commands")
    if (
        golden_core.get("name") != "QZX Golden Core"
        or golden_core.get("status") != "candidate"
        or not isinstance(commands, list)
        or len(commands) != 15
        or any(not isinstance(name, str) or not name for name in commands)
        or len(set(commands)) != 15
    ):
        raise ValueError(f"{context} has an invalid Golden Core command set.")

    environment = document.get("environment")
    if not isinstance(environment, dict):
        raise ValueError(f"{context} has no environment object.")
    for field in ("id", "name", "system", "release", "machine"):
        if not isinstance(environment.get(field), str) or not environment[field]:
            raise ValueError(f"{context} environment.{field} is invalid.")
    python = environment.get("python")
    if (
        not isinstance(python, dict)
        or python.get("implementation") != "CPython"
        or not isinstance(python.get("version"), str)
        or not python["version"].startswith("3.13.")
    ):
        raise ValueError(f"{context} did not use standard CPython 3.13.x.")

    command_records = document.get("commands")
    if not isinstance(command_records, dict) or set(command_records) != set(commands):
        raise ValueError(f"{context} command evidence differs from Golden Core.")
    for command_name in commands:
        record = command_records[command_name]
        if not isinstance(record, dict):
            raise ValueError(f"{context}:{command_name} must be an object.")
        if record.get("exit_code") != 0:
            raise ValueError(f"{context}:{command_name} did not exit successfully.")
        result = record.get("result")
        if not isinstance(result, dict) or result.get("success") is not True:
            raise ValueError(f"{context}:{command_name} did not report success.")
        meta = result.get("meta")
        if (
            not isinstance(meta, dict)
            or meta.get("command") != command_name
            or meta.get("schema_version") != 1
        ):
            raise ValueError(f"{context}:{command_name} has invalid result metadata.")
        if record.get("result_sha256") != sha256_value(result):
            raise ValueError(f"{context}:{command_name} result hash is invalid.")
        assertions = record.get("assertions")
        if not isinstance(assertions, list) or len(assertions) < 5:
            raise ValueError(f"{context}:{command_name} has insufficient assertions.")

    summary = document.get("summary")
    if (
        not isinstance(summary, dict)
        or summary.get("command_count") != 15
        or summary.get("passed") != 15
        or summary.get("failed") != 0
        or summary.get("systems_observed") != [environment["system"]]
    ):
        raise ValueError(f"{context} has an invalid run summary.")

    scope = document.get("scope")
    if (
        not isinstance(scope, dict)
        or scope.get("success_only") is not True
        or scope.get("network") != "authorized loopback HTTP only"
        or scope.get("repository") != "disposable local Git fixture only"
    ):
        raise ValueError(f"{context} has an invalid evidence scope.")


def merge(paths: list[Path]) -> dict[str, Any]:
    documents: list[tuple[Path, dict[str, Any]]] = []
    for path in paths:
        document = load_object(path)
        validate_evidence(path, document)
        documents.append((path, document))

    revisions = {document["source_revision"] for _, document in documents}
    versions = {document["qzx_version"] for _, document in documents}
    command_sets = {
        tuple(document["golden_core"]["commands"])
        for _, document in documents
    }
    environment_ids = [document["environment"]["id"] for _, document in documents]
    if len(revisions) != 1:
        raise ValueError("Platform evidence spans multiple source revisions.")
    if len(versions) != 1:
        raise ValueError("Platform evidence spans multiple QZX versions.")
    if len(command_sets) != 1:
        raise ValueError("Platform evidence spans different Golden Core sets.")
    duplicates = sorted(
        identifier
        for identifier, count in Counter(environment_ids).items()
        if count > 1
    )
    if duplicates:
        raise ValueError(
            "Platform evidence has duplicate environment IDs: "
            + ", ".join(duplicates)
            + "."
        )

    systems = Counter(document["environment"]["system"] for _, document in documents)
    missing_systems = sorted(set(REQUIRED_SYSTEMS) - set(systems))
    if missing_systems:
        raise ValueError(
            "Platform evidence is missing declared systems: "
            + ", ".join(missing_systems)
            + "."
        )

    command_names = next(iter(command_sets))
    command_summary: dict[str, Any] = {}
    for command_name in command_names:
        observed_systems: dict[str, int] = defaultdict(int)
        result_hashes: dict[str, str] = {}
        for _, document in documents:
            environment = document["environment"]
            observed_systems[environment["system"]] += 1
            result_hashes[environment["id"]] = document["commands"][command_name][
                "result_sha256"
            ]
        command_summary[command_name] = {
            "environment_count": len(documents),
            "systems": dict(sorted(observed_systems.items())),
            "declared_systems_observed": all(
                system in observed_systems for system in REQUIRED_SYSTEMS
            ),
            "result_sha256_by_environment": dict(sorted(result_hashes.items())),
        }

    environments = []
    for path, document in sorted(
        documents,
        key=lambda item: item[1]["environment"]["id"],
    ):
        environment = document["environment"]
        environments.append(
            {
                "id": environment["id"],
                "name": environment["name"],
                "system": environment["system"],
                "release": environment["release"],
                "version": environment["version"],
                "machine": environment["machine"],
                "processor": environment["processor"],
                "python": environment["python"],
                "github": environment["github"],
                "captured_at": document["captured_at"],
                "evidence_sha256": document["evidence_sha256"],
                "source_file": path.name,
            }
        )

    summary = {
        "schema_version": SCHEMA_VERSION,
        "evidence_type": SUMMARY_TYPE,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_revision": next(iter(revisions)),
        "qzx_version": next(iter(versions)),
        "golden_core": {
            "name": "QZX Golden Core",
            "status": "candidate",
            "command_count": len(command_names),
            "commands": list(command_names),
        },
        "requirements": {
            "declared_systems": list(REQUIRED_SYSTEMS),
            "declared_systems_observed": True,
            "claim": (
                "This aggregate reports the observed GitHub-hosted runner "
                "environments and sanitized QZX command results. It is not a "
                "universal compatibility guarantee or Beta promotion."
            ),
        },
        "summary": {
            "environment_count": len(environments),
            "system_counts": dict(sorted(systems.items())),
            "command_count": len(command_names),
            "command_environment_runs": len(environments) * len(command_names),
            "failed_command_runs": 0,
        },
        "environments": environments,
        "commands": command_summary,
    }
    summary["aggregate_sha256"] = sha256_value(summary)
    return summary


def main() -> int:
    arguments = parse_args()
    paths = evidence_files(arguments.inputs)
    document = merge(paths)
    arguments.output.parent.mkdir(parents=True, exist_ok=True)
    arguments.output.write_text(
        json.dumps(document, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        "Merged {} environments and {} Golden Core command runs.".format(
            document["summary"]["environment_count"],
            document["summary"]["command_environment_runs"],
        )
    )
    print("Systems: {}".format(document["summary"]["system_counts"]))
    print("Aggregate SHA-256: {}".format(document["aggregate_sha256"]))
    print("Output: {}".format(arguments.output))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
