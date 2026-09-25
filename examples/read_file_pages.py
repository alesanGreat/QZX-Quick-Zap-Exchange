#!/usr/bin/env python
"""Read a file in checked QZX pages; emit a compact summary, not the whole file.

QZX — Quick Zap Exchange, created and maintained by Alejandro Sánchez.
Run from a source checkout: python examples/read_file_pages.py --demo --page-bytes 32
This example requires the development readFile pagination interface.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from typing import Iterator

DEMO_TEXT = "Alejandro Sánchez\r\nDiseño 日本語 😀\nAutomatización sin pérdida de texto.\n"
REQUIRED_OPTIONS = {"file_path", "max_lines", "max_bytes", "offset", "encoding", "expected_fingerprint"}


class ReadWorkflowError(RuntimeError):
    """The consumer refuses incomplete, changed or inconsistent file evidence."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


def _environment() -> dict[str, str]:
    environment = dict(os.environ)
    source = Path(__file__).resolve().parents[1] / "src"
    if (source / "qzx" / "__init__.py").is_file():
        environment["PYTHONPATH"] = str(source)
    # The demonstration does not create telemetry events or contact a service.
    environment.update(QZX_TELEMETRY="0", DO_NOT_TRACK="1", PYTHONDONTWRITEBYTECODE="1", PYTHONUTF8="1")
    return environment


def run_qzx(arguments: list[str], *, process_runner=subprocess.run) -> dict:
    completed = process_runner(
        [sys.executable, "-B", "-m", "qzx", *arguments, "--json"],
        capture_output=True, env=_environment(), shell=False,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    try:
        result = json.loads(completed.stdout)
    except (UnicodeError, ValueError) as exc:
        raise ReadWorkflowError("invalid_cli_output", "QZX did not return one JSON result. Check this Python environment.") from exc
    if not isinstance(result, dict):
        raise ReadWorkflowError("invalid_cli_output", "QZX returned a non-object result.")
    if completed.returncode or result.get("success") is not True:
        raise ReadWorkflowError(str(result.get("error_code", "qzx_failed")), str(result.get("message", "QZX failed.")))
    return result


def require_pagination(*, qzx_runner=run_qzx) -> None:
    result = qzx_runner(["help", "readFile"])
    parameters = result.get("details", {}).get("parameters", [])
    names = {item.get("name") for item in parameters if isinstance(item, dict)}
    if not REQUIRED_OPTIONS <= names:
        raise ReadWorkflowError(
            "pagination_unavailable",
            "This example requires readFile with max_bytes, offset and expected_fingerprint. "
            "Use a development checkout that includes the paginated reader; an older installed QZX is insufficient.",
        )


def _arguments(options: dict) -> list[str]:
    arguments = ["readFile"]
    for name, value in options.items():
        if name not in REQUIRED_OPTIONS:
            raise ReadWorkflowError("invalid_continuation", "Unknown option in next_read.")
        if value is not None:
            arguments.extend(["--" + name.replace("_", "-"), str(value)])
    return arguments


def _page_details(result: dict, expected_offset: int, expected_fingerprint) -> dict:
    details = result.get("details")
    if not isinstance(details, dict) or not isinstance(result.get("content"), str):
        raise ReadWorkflowError("invalid_page", "Missing text or page metadata.")
    if type(details.get("read_complete")) is not bool or type(details.get("bytes_consumed")) is not int:
        raise ReadWorkflowError("invalid_page", "Invalid completion or byte count.")
    if details.get("offset") != expected_offset or details["bytes_consumed"] < 0:
        raise ReadWorkflowError("invalid_page", "A page repeated or skipped source bytes.")
    fingerprint = details.get("fingerprint_token")
    if not isinstance(fingerprint, str) or not fingerprint:
        raise ReadWorkflowError("invalid_page", "The stat fingerprint token is missing.")
    if expected_fingerprint is not None and fingerprint != expected_fingerprint:
        raise ReadWorkflowError("changed_file", "The file changed between pages; discard this traversal.")
    return details


def _require_same_limits(continuation, path, budget, max_lines):
    expected = {"file_path": path, "max_bytes": budget, "max_lines": max_lines}
    if any(continuation[key] != value for key, value in expected.items()):
        raise ReadWorkflowError("invalid_continuation", "Continuation changed the target or limits.")


def _next_page(details: dict, path: str, budget: int, max_lines) -> dict | None:
    continuation = details.get("next_read")
    if details["read_complete"]:
        if continuation is not None:
            raise ReadWorkflowError("invalid_continuation", "An EOF page must not request another read.")
        return None
    if not isinstance(continuation, dict) or set(continuation) != REQUIRED_OPTIONS:
        raise ReadWorkflowError("invalid_continuation", "A partial page must provide complete next_read options.")
    expected = details["offset"] + details["bytes_consumed"]
    _require_same_limits(continuation, path, budget, max_lines)
    if details["bytes_consumed"] <= 0 or continuation["offset"] != expected:
        raise ReadWorkflowError("invalid_continuation", "Continuation changed the target, limits or source position.")
    if continuation["expected_fingerprint"] != details["fingerprint_token"]:
        raise ReadWorkflowError("invalid_continuation", "Continuation dropped the file-change guard.")
    if continuation["encoding"] != details.get("encoding"):
        raise ReadWorkflowError("invalid_continuation", "Continuation changed the detected encoding.")
    return continuation


def read_pages(
    path: Path,
    *,
    page_bytes=65536,
    max_lines=None,
    encoding="auto",
    max_pages=10000,
    qzx_runner=run_qzx,
) -> Iterator[dict]:
    if type(max_pages) is not int or max_pages < 1 or max_lines == 0:
        raise ReadWorkflowError("invalid_limits", "max_pages must be positive; a full traversal cannot use max_lines=0.")
    options = {"file_path": os.path.abspath(path), "max_bytes": page_bytes,
               "max_lines": max_lines, "encoding": encoding, "offset": 0}
    fingerprint = None
    for _ in range(max_pages):
        result = qzx_runner(_arguments(options))
        details = _page_details(result, options["offset"], fingerprint)
        continuation = _next_page(details, options["file_path"], page_bytes, max_lines)
        yield result
        if continuation is None:
            return
        fingerprint = details["fingerprint_token"]
        options = continuation
    raise ReadWorkflowError("page_limit_reached", "The traversal is incomplete. Increase --max-pages intentionally or inspect fewer pages.")


def summarize(
    path: Path, *, emit_pages=False, qzx_runner=run_qzx, **limits
) -> dict:
    digest = hashlib.sha256()
    pages = characters = consumed = 0
    for result in read_pages(path, qzx_runner=qzx_runner, **limits):
        pages += 1
        text = result["content"]
        digest.update(text.encode("utf-8"))
        characters += len(text)
        consumed += result["details"]["bytes_consumed"]
        if emit_pages:
            print(json.dumps({"event": "page", "result": result}, ensure_ascii=True))
    return {
        "success": True, "message": "Read every page without replacing text or mixing observed file versions.",
        "pages": pages, "decoded_characters": characters, "source_bytes_consumed": consumed,
        "decoded_utf8_sha256": digest.hexdigest(), "read_complete": True,
        "fingerprint_scope": "path, size, mtime_ns, device, inode; not an immutable snapshot or content proof",
    }


def _positive(value: str) -> int:
    number = int(value)
    if number < 1:
        raise argparse.ArgumentTypeError("Use a positive integer.")
    return number


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", nargs="?", type=Path)
    parser.add_argument("--demo", action="store_true", help="Read a generated multilingual UTF-16 fixture instead of personal data.")
    parser.add_argument("--page-bytes", type=_positive, default=65536)
    parser.add_argument("--max-lines", type=_positive)
    parser.add_argument("--max-pages", type=_positive, default=10000)
    parser.add_argument("--encoding", default="auto")
    parser.add_argument("--emit-pages", action="store_true", help="Emit JSON Lines page events before the final summary; content is not redacted.")
    args = parser.parse_args(argv)
    if args.demo == (args.path is not None):
        parser.error("Choose exactly one file path or --demo.")
    return args


def _run_selected(args, *, qzx_runner=run_qzx) -> dict:
    limits = {"page_bytes": args.page_bytes, "max_lines": args.max_lines,
              "encoding": args.encoding, "max_pages": args.max_pages, "emit_pages": args.emit_pages}
    if not args.demo:
        return summarize(args.path, qzx_runner=qzx_runner, **limits)
    with tempfile.TemporaryDirectory(prefix="qzx-read-demo-") as directory:
        fixture = Path(directory) / "multilingual.txt"
        fixture.write_bytes(DEMO_TEXT.encode("utf-16"))
        summary = summarize(fixture, qzx_runner=qzx_runner, **limits)
    expected = hashlib.sha256(DEMO_TEXT.encode("utf-8")).hexdigest()
    if summary["decoded_utf8_sha256"] != expected:
        raise ReadWorkflowError("demo_mismatch", "The demonstration did not reproduce the exact source text.")
    summary["demo_verified"] = True
    return summary


def main(argv=None) -> int:
    args = parse_args(argv)
    try:
        require_pagination()
        result = _run_selected(args)
    except (ReadWorkflowError, OSError) as exc:
        result = {"success": False, "error_code": getattr(exc, "code", "workflow_failed"), "message": str(exc)}
    print(json.dumps(result, ensure_ascii=True))
    return 0 if result["success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
