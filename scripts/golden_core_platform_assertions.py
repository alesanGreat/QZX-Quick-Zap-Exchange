"""Command-specific Golden Core evidence assertions."""

from __future__ import annotations

import hashlib
import platform

import qzx
from qzx.core.command_index import indexed_command_names


def command_assertions(
    name,
    document,
    *,
    expected_qzx_command_count=None,
):
    """Return invariant labels after validating one sanitized command result."""
    if expected_qzx_command_count is None:
        expected_qzx_command_count = len(indexed_command_names())
    assertions = [
        "exit_code=0",
        "result_contract_v1",
        "success=true",
        f"meta.command={name}",
    ]
    handler = _ASSERTION_HANDLERS.get(name)
    if handler is not None:
        handler(document, assertions, expected_qzx_command_count)
    return assertions


def _version(document, assertions, _count):
    if document.get("version") != qzx.__version__:
        raise AssertionError(
            "version did not report the installed QZX version."
        )
    if "system_info" in document or "qzx_info" in document:
        raise AssertionError(
            "version duplicated host or capability discovery data."
        )
    assertions.append("version_matches_package")


def _list_commands(document, assertions, count):
    if document.get("summary", {}).get("commands") != count:
        raise AssertionError(
            f"listCommands did not report {count} commands."
        )
    assertions.append(f"command_count={count}")


def _help(document, assertions, _count):
    if document.get("details", {}).get("name") != "findFiles":
        raise AssertionError("help did not describe findFiles.")
    assertions.append("describes=findFiles")


def _date_time(document, assertions, _count):
    if (
        document.get("output_format") != "iso"
        or not isinstance(document.get("output"), str)
        or document.get("output") != document.get("iso_format")
    ):
        raise AssertionError(
            "getCurrentDateTime did not expose ISO output."
        )
    assertions.append("iso_datetime_present")


def _current_directory(document, assertions, _count):
    if document.get("current_dir") != "<fixture-root>":
        raise AssertionError(
            "getCurrentDirectory did not observe the fixture root."
        )
    assertions.append("current_dir=<fixture-root>")


def _system_info(document, assertions, _count):
    if document.get("system_info", {}).get("os") != platform.system():
        raise AssertionError(
            "getSystemInfo did not report the real host OS."
        )
    assertions.append("os_matches_runner")


def _disk_space(document, assertions, _count):
    if not isinstance(
        document.get("disk_info", {}).get("total_bytes"),
        int,
    ):
        raise AssertionError("getDiskSpace did not expose raw capacity.")
    assertions.append("raw_capacity_present")


def _ram_info(document, assertions, _count):
    total = (
        document.get("ram_info", {})
        .get("virtual_memory", {})
        .get("total")
    )
    if not isinstance(total, int):
        raise AssertionError("getRamInfo did not expose raw memory capacity.")
    assertions.append("raw_memory_present")


def _list_files(document, assertions, _count):
    names = [item.get("name") for item in document.get("files", [])]
    if names != ["alpha.txt", "beta.txt"]:
        raise AssertionError(f"listFiles returned unexpected names: {names}")
    if document.get("recursive") is not True:
        raise AssertionError("listFiles did not report recursive=true.")
    assertions.extend(["recursive=true", "files=alpha.txt,beta.txt"])


def _find_files(document, assertions, _count):
    names = [item.get("name") for item in document.get("results", [])]
    if names != ["alpha.txt", "beta.txt"]:
        raise AssertionError(f"findFiles returned unexpected names: {names}")
    assertions.append("files=alpha.txt,beta.txt")


def _find_text(document, assertions, _count):
    if document.get("total_matches") != 2:
        raise AssertionError(
            "findText did not report two controlled matches."
        )
    assertions.append("matches=2")


def _file_hash(document, assertions, _count):
    expected = hashlib.sha256(
        b"QZX alpha evidence\nsecond line\n"
    ).hexdigest()
    if document.get("hash") != expected:
        raise AssertionError(
            "calculateFileHash returned an unexpected digest."
        )
    assertions.append("sha256_matches_fixture")


def _git_status(document, assertions, _count):
    changes = document.get("changes", {})
    valid = (
        document.get("branch") == "main"
        and "tracked.txt" in changes.get("modified", [])
        and "staged.txt" in changes.get("staged", [])
        and "untracked.txt" in changes.get("untracked", [])
    )
    if not valid:
        raise AssertionError(
            "getGitStatus did not report the fixture state."
        )
    assertions.append("branch_and_changes_verified")


def _diagnose_project(document, assertions, _count):
    observed = document.get("details", {}).get("path")
    if observed not in {
        "<fixture-root>/project",
        "<fixture-root>\\project",
    }:
        raise AssertionError(
            "diagnoseProject did not inspect the fixture project."
        )
    assertions.append("fixture_project_inspected")


def _url_status(document, assertions, _count):
    if (
        document.get("status_code") != 200
        or document.get("is_online") is not True
    ):
        raise AssertionError(
            "checkUrlStatus did not observe the loopback HTTP 200."
        )
    assertions.append("authorized_loopback_http_200")


_ASSERTION_HANDLERS = {
    "version": _version,
    "listCommands": _list_commands,
    "help": _help,
    "getCurrentDateTime": _date_time,
    "getCurrentDirectory": _current_directory,
    "getSystemInfo": _system_info,
    "getDiskSpace": _disk_space,
    "getRamInfo": _ram_info,
    "listFiles": _list_files,
    "findFiles": _find_files,
    "findText": _find_text,
    "calculateFileHash": _file_hash,
    "getGitStatus": _git_status,
    "diagnoseProject": _diagnose_project,
    "checkUrlStatus": _url_status,
}
