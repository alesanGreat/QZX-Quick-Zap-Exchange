#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Fail closed when local source, GitHub, PyPI, or qzx.yumbale.com diverge.

This verifier is intentionally read-only. A QZX release is complete only when
all public surfaces expose the same immutable source commit, package version,
command inventory, and byte-identical distribution artifacts. The verifier also
opens the published wheel and source distribution so metadata cannot claim an
inventory that differs from the commands users actually install.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
from typing import Any, Callable
from urllib.parse import urlsplit
from urllib.request import Request, urlopen


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.public_surface_parity_flow import (  # noqa: E402
    verify_public_surface_parity as _verify_public_surface_parity,
)

MANIFEST_PATH = (
    PROJECT_ROOT / "src" / "qzx" / "resources" / "product-manifest.json"
)
COMMAND_INDEX_PATH = (
    PROJECT_ROOT / "src" / "qzx" / "resources" / "command-index.json"
)
GITHUB_REPOSITORY = "alesanGreat/QZX-Quick-Zap-Exchange"
WEBSITE_COMMANDS_URL = "https://qzx.yumbale.com/data/commands.json"
PYPI_PROJECT = "qzx"
USER_AGENT = "QZX-public-surface-parity/2"
MAX_ARTIFACT_BYTES = 128 * 1024 * 1024
MAX_METADATA_MEMBER_BYTES = 8 * 1024 * 1024
COMMAND_INDEX_MEMBER = "qzx/resources/command-index.json"
PRODUCT_MANIFEST_MEMBER = "qzx/resources/product-manifest.json"

JsonFetcher = Callable[[str], Any]
BytesFetcher = Callable[[str], bytes]


def _request_headers(
    url: str,
    *,
    accept: str = "application/json",
) -> dict[str, str]:
    """Build request headers without disclosing GitHub credentials elsewhere."""
    headers = {
        "Accept": accept,
        "User-Agent": USER_AGENT,
    }
    host = (urlsplit(url).hostname or "").lower()
    token = (
        os.environ.get("GH_TOKEN")
        or os.environ.get("GITHUB_TOKEN")
        or ""
    ).strip()
    if host == "api.github.com" and token:
        headers["Authorization"] = f"Bearer {token}"
        headers["X-GitHub-Api-Version"] = "2022-11-28"
    return headers


def fetch_json(url: str, *, timeout: float = 30.0) -> Any:
    request = Request(url, headers=_request_headers(url))
    with urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def fetch_bytes(url: str, *, timeout: float = 60.0) -> bytes:
    request = Request(
        url,
        headers=_request_headers(url, accept="application/octet-stream"),
    )
    with urlopen(request, timeout=timeout) as response:
        declared_length = response.headers.get("Content-Length")
        if declared_length is not None and int(declared_length) > MAX_ARTIFACT_BYTES:
            raise ValueError(
                f"Artifact exceeds the {MAX_ARTIFACT_BYTES}-byte verification limit."
            )
        payload = response.read(MAX_ARTIFACT_BYTES + 1)
    if len(payload) > MAX_ARTIFACT_BYTES:
        raise ValueError(
            f"Artifact exceeds the {MAX_ARTIFACT_BYTES}-byte verification limit."
        )
    return payload


def _git_head(repository: Path = PROJECT_ROOT) -> str:
    completed = subprocess.run(
        ["git", "-C", str(repository), "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError(
            completed.stderr.strip() or "Unable to resolve the local Git revision."
        )
    revision = completed.stdout.strip()
    if len(revision) != 40:
        raise RuntimeError(f"Unexpected Git revision: {revision!r}")
    return revision


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def verify_public_surface_parity(
    *,
    manifest: dict[str, Any],
    command_index: dict[str, Any],
    expected_version: str,
    expected_commit: str,
    get_json: JsonFetcher = fetch_json,
    get_bytes: BytesFetcher = fetch_bytes,
    require_main: bool = True,
) -> dict[str, Any]:
    """Verify public release surfaces through the semantic parity workflow."""
    return _verify_public_surface_parity(
        manifest=manifest,
        command_index=command_index,
        expected_version=expected_version,
        expected_commit=expected_commit,
        get_json=get_json,
        get_bytes=get_bytes,
        require_main=require_main,
    )


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--expected-version")
    parser.add_argument("--expected-commit")
    parser.add_argument("--manifest", type=Path, default=MANIFEST_PATH)
    parser.add_argument("--command-index", type=Path, default=COMMAND_INDEX_PATH)
    parser.add_argument(
        "--pre-main",
        action="store_true",
        help=(
            "Verify tag, GitHub Release, PyPI, and website before advancing main. "
            "The final transaction must run again without this flag."
        ),
    )
    parser.add_argument("--json", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        manifest = _load_json(args.manifest.resolve())
        command_index = _load_json(args.command_index.resolve())
        expected_version = (
            args.expected_version or manifest["channels"]["published"]["version"]
        )
        expected_commit = (
            args.expected_commit or os.environ.get("GITHUB_SHA") or _git_head()
        )
        if not isinstance(expected_version, str) or not expected_version:
            raise ValueError("Expected version must be non-empty text.")
        if not isinstance(expected_commit, str) or len(expected_commit) != 40:
            raise ValueError("Expected commit must be one full 40-character SHA.")
        result = verify_public_surface_parity(
            manifest=manifest,
            command_index=command_index,
            expected_version=expected_version,
            expected_commit=expected_commit,
            require_main=not args.pre_main,
        )
    except Exception as error:
        result = {
            "success": False,
            "message": f"Public surface parity verifier failed: {error}",
            "error_type": type(error).__name__,
            "mismatches": [],
        }

    if args.json:
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    else:
        prefix = "[OK]" if result["success"] else "[BLOCKED]"
        print(f"{prefix} {result['message']}")
        for mismatch in result.get("mismatches", []):
            print(
                "  - {surface}/{check}: expected {expected!r}, got {actual!r}".format(
                    **mismatch
                )
            )
    return 0 if result["success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
