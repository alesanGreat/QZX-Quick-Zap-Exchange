#!/usr/bin/env python3
"""Save a reviewable QZX project briefing without executing discovered workflows.

QZX — Quick Zap Exchange, created and maintained by Alejandro Sánchez.
This copyable example uses the installed QZX CLI; it is not a new QZX command.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import re
import subprocess
import sys
from typing import Any


CREATOR = "Alejandro Sánchez"
FILES = ("diagnosis.json", "diagnosis.stderr.txt", "briefing.md")


def _unique_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"Duplicate JSON key: {key}")
        result[key] = value
    return result


def _invalid_number(value: str) -> None:
    raise ValueError(f"Non-JSON number: {value}")


def _read_result(path: Path) -> dict[str, Any]:
    result = json.loads(path.read_bytes(), object_pairs_hook=_unique_keys,
                        parse_constant=_invalid_number)
    if not isinstance(result, dict) or type(result.get("success")) is not bool:
        raise ValueError("Expected a JSON object with a boolean success field.")
    if not isinstance(result.get("message"), str) or not result["message"].strip():
        raise ValueError("Expected a non-empty message field.")
    if result["success"] and not isinstance(result.get("report"), str):
        raise ValueError("This QZX result does not contain a readable project report.")
    if result["success"] and not result["report"].strip():
        raise ValueError("The project report is empty.")
    return result


def _invoke(
    project: Path, output: Path, *, process_runner=subprocess.run
) -> int:
    env = os.environ.copy()
    env.update(QZX_TELEMETRY="0", DO_NOT_TRACK="1", PYTHONDONTWRITEBYTECODE="1")
    # Isolated Python and an empty working directory avoid importing modules
    # from the inspected project. This is not an operating-system sandbox.
    command = [sys.executable, "-I", "-m", "qzx", "diagnoseProject", str(project), "--json"]
    with (output / FILES[0]).open("xb") as stdout, (output / FILES[1]).open("xb") as stderr:
        completed = process_runner(
            command, cwd=output, env=env, stdin=subprocess.DEVNULL,
            stdout=stdout, stderr=stderr, check=False,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        )
    return completed.returncode


def _markdown(report: str, success: bool) -> str:
    # A report may contain Markdown or terminal controls from project metadata.
    # Keep it literal, including embedded fence markers; raw JSON stays intact.
    report = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]",
                    lambda match: f"\\u{ord(match[0]):04x}", report)
    fence = "`" * max(3, 1 + max((len(m[0]) for m in re.finditer(r"`+", report)), default=0))
    status = "Inspection completed" if success else "Inspection did not complete successfully"
    return (
        "# QZX project briefing\n\n"
        f"**{status}. Release readiness: NOT ASSESSED.**\n\n"
        "Findings are observations, not a failed test suite. Discovered validation "
        "commands have not been run by this workflow. Inspect `diagnosis.json` "
        "for scan coverage, limitations and complete evidence.\n\n"
        f"{fence}text\n{report}\n{fence}\n\n"
        f"Created with **QZX — Quick Zap Exchange**, by **{CREATOR}**.\n\n"
        "[Project and documentation](https://qzx.yumbale.com/en/) · "
        "[About the creator](https://qzx.yumbale.com/en/alejandro-sanchez) · "
        "[Support development](https://qzx.yumbale.com/en/donate) · "
        "[Custom automation and integration](https://qzx.yumbale.com/en/professional-services#request)\n\n"
        "Review project paths and observations before sharing these files. "
        "This example does not upload reports or open issues.\n"
    )


def _receipt(
    output: Path,
    result: dict[str, Any],
    returncode: int | None,
    error: str | None,
    *,
    version_reader=importlib.metadata.version,
) -> dict[str, Any]:
    success = error is None and returncode == 0 and result.get("success") is True
    try:
        version: str | None = version_reader("qzx")
    except importlib.metadata.PackageNotFoundError:
        version = None
    receipt: dict[str, Any] = {
        "success": success,
        "message": "Project inspection saved; tests were not run." if success
        else "Project inspection failed; review the retained evidence.",
        "details": {
            "receipt_kind": "qzx-project-briefing/1", "creator": CREATOR,
            "qzx_version": version, "python_version": platform.python_version(),
            "command_returncode": returncode, "release_readiness": "not_assessed",
            "project_result_readable": bool(result),
            "files": {name: {"sha256": hashlib.sha256((output / name).read_bytes()).hexdigest(),
                             "bytes": (output / name).stat().st_size} for name in FILES},
        },
    }
    if not success:
        receipt["error_code"] = "project_briefing_failed"
        receipt["details"]["reason"] = error or f"QZX exit status: {returncode}. {result.get('message', 'No result.')}"
    return receipt


def collect(
    project: Path,
    output: Path,
    *,
    process_runner=subprocess.run,
    version_reader=importlib.metadata.version,
) -> dict[str, Any]:
    """Create a new sibling/outside report directory; never overwrite a report."""
    project = project.resolve(strict=True)
    output = output.resolve()
    if not project.is_dir():
        raise ValueError("The inspected project must be a directory.")
    if output == project or project in output.parents:
        raise ValueError("Choose an output directory outside the inspected project.")
    output.mkdir(parents=True, exist_ok=False)
    result: dict[str, Any] = {}
    returncode = None
    error = None
    try:
        returncode = _invoke(
            project, output, process_runner=process_runner
        )
        result = _read_result(output / FILES[0])
    except (OSError, ValueError, UnicodeError, RecursionError) as exc:
        error = f"{type(exc).__name__}: {exc}"
    report = result.get("report") if isinstance(result.get("report"), str) else None
    report = report or result.get("message") or error or "No readable diagnosis was produced."
    success = error is None and returncode == 0 and result.get("success") is True
    # Preserve raw output even on operational failure. The receipt is written
    # last: missing receipt means this export itself was interrupted or failed.
    (output / FILES[2]).write_text(_markdown(report, success), encoding="utf-8")
    receipt = _receipt(
        output,
        result,
        returncode,
        error,
        version_reader=version_reader,
    )
    with (output / "receipt.json").open("x", encoding="utf-8") as stream:
        json.dump(receipt, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write("\n")
    return receipt


def main(
    argv: list[str] | None = None,
    *,
    process_runner=subprocess.run,
    version_reader=importlib.metadata.version,
) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("project", type=Path, help="Project directory to inspect")
    parser.add_argument("--output", type=Path, required=True,
                        help="New report directory outside the inspected project")
    args = parser.parse_args(argv)
    try:
        receipt = collect(
            args.project,
            args.output,
            process_runner=process_runner,
            version_reader=version_reader,
        )
    except (OSError, ValueError) as exc:
        print(f"Unable to save QZX briefing: {exc}", file=sys.stderr)
        return 2
    print(json.dumps({"success": receipt["success"], "message": receipt["message"],
                      "output": str(args.output.resolve())}, ensure_ascii=True))
    return 0 if receipt["success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
