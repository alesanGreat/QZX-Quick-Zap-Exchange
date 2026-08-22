#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Fail closed when GitHub, PyPI, and qzx.yumbale.com diverge.

This verifier is intentionally read-only.  A QZX release is complete only when
all public surfaces expose the same immutable source commit, package version,
command inventory, and byte-identical distribution artifacts.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
from typing import Any, Callable
from urllib.parse import quote
from urllib.request import Request, urlopen


PROJECT_ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = (
    PROJECT_ROOT / "src" / "qzx" / "resources" / "product-manifest.json"
)
COMMAND_INDEX_PATH = (
    PROJECT_ROOT / "src" / "qzx" / "resources" / "command-index.json"
)
GITHUB_REPOSITORY = "alesanGreat/QZX-Quick-Zap-Exchange"
WEBSITE_COMMANDS_URL = "https://qzx.yumbale.com/data/commands.json"
PYPI_PROJECT = "qzx"
USER_AGENT = "QZX-public-surface-parity/1"

JsonFetcher = Callable[[str], Any]
BytesFetcher = Callable[[str], bytes]


def _request_headers(*, accept: str = "application/json") -> dict[str, str]:
    headers = {
        "Accept": accept,
        "User-Agent": USER_AGENT,
    }
    token = os.environ.get("GITHUB_TOKEN", "").strip()
    if token:
        headers["Authorization"] = f"Bearer {token}"
        headers["X-GitHub-Api-Version"] = "2022-11-28"
    return headers


def fetch_json(url: str, *, timeout: float = 30.0) -> Any:
    request = Request(url, headers=_request_headers())
    with urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def fetch_bytes(url: str, *, timeout: float = 60.0) -> bytes:
    request = Request(
        url,
        headers=_request_headers(accept="application/octet-stream"),
    )
    with urlopen(request, timeout=timeout) as response:
        return response.read()


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


def _artifact_names(version: str) -> tuple[str, str]:
    return (
        f"qzx-{version}-py3-none-any.whl",
        f"qzx-{version}.tar.gz",
    )


def _github_api(path: str) -> str:
    return f"https://api.github.com/repos/{GITHUB_REPOSITORY}/{path.lstrip('/')}"


def _check(
    checks: list[dict[str, Any]],
    *,
    surface: str,
    name: str,
    expected: Any,
    actual: Any,
    detail: str | None = None,
) -> None:
    item: dict[str, Any] = {
        "surface": surface,
        "check": name,
        "success": actual == expected,
        "expected": expected,
        "actual": actual,
    }
    if detail:
        item["detail"] = detail
    checks.append(item)


def _surface_error(
    checks: list[dict[str, Any]],
    *,
    surface: str,
    error: Exception,
) -> None:
    checks.append(
        {
            "surface": surface,
            "check": "reachable_and_parseable",
            "success": False,
            "expected": "reachable JSON endpoint",
            "actual": f"{type(error).__name__}: {error}",
        }
    )


def _dereference_tag_commit(tag_name: str, get_json: JsonFetcher) -> str:
    reference = get_json(
        _github_api(f"git/ref/tags/{quote(tag_name, safe='')}")
    )
    target = reference["object"]
    visited: set[str] = set()
    while target.get("type") == "tag":
        object_sha = target["sha"]
        if object_sha in visited:
            raise ValueError("Git tag object cycle detected.")
        visited.add(object_sha)
        tag_object = get_json(_github_api(f"git/tags/{object_sha}"))
        target = tag_object["object"]
    if target.get("type") != "commit":
        raise ValueError(f"Tag resolves to {target.get('type')!r}, not a commit.")
    commit = target.get("sha")
    if not isinstance(commit, str) or len(commit) != 40:
        raise ValueError("Tag does not expose a full commit SHA.")
    return commit


def _asset_digest(
    asset: dict[str, Any],
    *,
    get_bytes: BytesFetcher,
) -> str:
    raw_digest = asset.get("digest")
    if isinstance(raw_digest, str) and raw_digest.startswith("sha256:"):
        digest = raw_digest.removeprefix("sha256:").lower()
        if len(digest) == 64:
            return digest
    download_url = asset.get("browser_download_url")
    if not isinstance(download_url, str) or not download_url:
        raise ValueError(f"Release asset {asset.get('name')!r} has no download URL.")
    return hashlib.sha256(get_bytes(download_url)).hexdigest()


def verify_public_surface_parity(
    *,
    manifest: dict[str, Any],
    command_index: list[dict[str, Any]],
    expected_version: str,
    expected_commit: str,
    get_json: JsonFetcher = fetch_json,
    get_bytes: BytesFetcher = fetch_bytes,
    require_main: bool = True,
) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    published = manifest["channels"]["published"]
    development = manifest["channels"]["development"]
    manifest_commands = published["wheel"]["command_names"]
    index_commands = [entry["name"] for entry in command_index]
    wheel_name, sdist_name = _artifact_names(expected_version)
    tag_name = f"v{expected_version}"

    _check(
        checks,
        surface="source_manifest",
        name="published_version",
        expected=expected_version,
        actual=published.get("version"),
    )
    _check(
        checks,
        surface="source_manifest",
        name="development_version",
        expected=expected_version,
        actual=development.get("version"),
    )
    _check(
        checks,
        surface="source_manifest",
        name="wheel_filename",
        expected=wheel_name,
        actual=published.get("wheel", {}).get("filename"),
    )
    _check(
        checks,
        surface="source_manifest",
        name="published_command_inventory",
        expected=sorted(index_commands),
        actual=sorted(manifest_commands),
    )

    github_asset_digests: dict[str, str] = {}
    if require_main:
        try:
            main_commit = get_json(_github_api("commits/main"))["sha"]
            _check(
                checks,
                surface="github_main",
                name="source_commit",
                expected=expected_commit,
                actual=main_commit,
            )
        except Exception as error:
            _surface_error(checks, surface="github_main", error=error)

    try:
        release = get_json(
            _github_api(f"releases/tags/{quote(tag_name, safe='')}")
        )
        _check(
            checks,
            surface="github_release",
            name="tag_name",
            expected=tag_name,
            actual=release.get("tag_name"),
        )
        _check(
            checks,
            surface="github_release",
            name="published_not_draft",
            expected=False,
            actual=bool(release.get("draft")),
        )
        _check(
            checks,
            surface="github_release",
            name="alpha_is_prerelease",
            expected=("a" in expected_version),
            actual=bool(release.get("prerelease")),
        )
        assets = {
            asset.get("name"): asset
            for asset in release.get("assets", [])
            if isinstance(asset, dict) and isinstance(asset.get("name"), str)
        }
        _check(
            checks,
            surface="github_release",
            name="distribution_assets",
            expected=sorted((wheel_name, sdist_name)),
            actual=sorted(name for name in assets if name in {wheel_name, sdist_name}),
        )
        for filename in (wheel_name, sdist_name):
            if filename in assets:
                github_asset_digests[filename] = _asset_digest(
                    assets[filename],
                    get_bytes=get_bytes,
                )
        tag_commit = _dereference_tag_commit(tag_name, get_json)
        _check(
            checks,
            surface="github_release",
            name="tag_source_commit",
            expected=expected_commit,
            actual=tag_commit,
        )
    except Exception as error:
        _surface_error(checks, surface="github_release", error=error)

    pypi_digests: dict[str, str] = {}
    try:
        pypi = get_json(
            f"https://pypi.org/pypi/{PYPI_PROJECT}/{quote(expected_version, safe='')}/json"
        )
        _check(
            checks,
            surface="pypi",
            name="version",
            expected=expected_version,
            actual=pypi.get("info", {}).get("version"),
        )
        files = {
            item.get("filename"): item
            for item in pypi.get("urls", [])
            if isinstance(item, dict) and isinstance(item.get("filename"), str)
        }
        _check(
            checks,
            surface="pypi",
            name="distribution_files",
            expected=sorted((wheel_name, sdist_name)),
            actual=sorted(name for name in files if name in {wheel_name, sdist_name}),
        )
        for filename in (wheel_name, sdist_name):
            digest = files.get(filename, {}).get("digests", {}).get("sha256")
            if isinstance(digest, str):
                pypi_digests[filename] = digest.lower()
        for filename in (wheel_name, sdist_name):
            if filename in pypi_digests and filename in github_asset_digests:
                _check(
                    checks,
                    surface="artifact_parity",
                    name=filename,
                    expected=pypi_digests[filename],
                    actual=github_asset_digests[filename],
                    detail="PyPI SHA-256 must equal the GitHub Release asset SHA-256.",
                )
    except Exception as error:
        _surface_error(checks, surface="pypi", error=error)

    try:
        separator = "&" if "?" in WEBSITE_COMMANDS_URL else "?"
        website = get_json(
            f"{WEBSITE_COMMANDS_URL}{separator}qzx_parity={expected_commit[:12]}"
        )
        metadata = website.get("metadata", {})
        website_commands = website.get("commands", {})
        _check(
            checks,
            surface="website",
            name="development_version",
            expected=expected_version,
            actual=metadata.get("development_version"),
        )
        _check(
            checks,
            surface="website",
            name="published_version",
            expected=expected_version,
            actual=metadata.get("published_version"),
        )
        _check(
            checks,
            surface="website",
            name="documentation_commit",
            expected=expected_commit,
            actual=metadata.get("documentation_commit"),
        )
        _check(
            checks,
            surface="website",
            name="documentation_branch",
            expected="main",
            actual=metadata.get("documentation_branch"),
        )
        _check(
            checks,
            surface="website",
            name="documented_command_count",
            expected=len(index_commands),
            actual=metadata.get("documented_command_count"),
        )
        _check(
            checks,
            surface="website",
            name="command_inventory",
            expected=sorted(index_commands),
            actual=sorted(website_commands) if isinstance(website_commands, dict) else None,
        )
    except Exception as error:
        _surface_error(checks, surface="website", error=error)

    failed = [check for check in checks if not check["success"]]
    return {
        "success": not failed,
        "message": (
            "GitHub, PyPI, and qzx.yumbale.com are synchronized."
            if not failed
            else f"Public surface parity failed with {len(failed)} mismatch(es)."
        ),
        "expected": {
            "version": expected_version,
            "commit": expected_commit,
            "tag": tag_name,
            "artifacts": [wheel_name, sdist_name],
            "command_count": len(index_commands),
        },
        "checks": checks,
        "mismatches": failed,
    }


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
            args.expected_version
            or manifest["channels"]["published"]["version"]
        )
        expected_commit = (
            args.expected_commit
            or os.environ.get("GITHUB_SHA")
            or _git_head()
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
