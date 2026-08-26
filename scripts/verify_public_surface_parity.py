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
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import tarfile
from typing import Any, Callable
from urllib.parse import quote, urlsplit
from urllib.request import Request, urlopen
import zipfile


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
    expected: str = "reachable and parseable public surface",
) -> None:
    checks.append(
        {
            "surface": surface,
            "check": "reachable_and_parseable",
            "success": False,
            "expected": expected,
            "actual": f"{type(error).__name__}: {error}",
        }
    )


def _command_entries(document: Any) -> list[dict[str, Any]]:
    """Validate the official schema-v2 command-index envelope."""
    if not isinstance(document, dict):
        raise ValueError("Command index must contain one JSON object.")
    if document.get("schema_version") != 2:
        raise ValueError(
            f"Unsupported command-index schema: {document.get('schema_version')!r}."
        )
    entries = document.get("commands")
    if not isinstance(entries, list) or not entries:
        raise ValueError("Command index must contain a non-empty commands list.")

    seen: set[str] = set()
    for index, entry in enumerate(entries):
        if not isinstance(entry, dict):
            raise ValueError(f"Command index entry {index} must be an object.")
        name = entry.get("name")
        if not isinstance(name, str) or not name.strip():
            raise ValueError(
                f"Command index entry {index} must have one non-empty name."
            )
        canonical = name.casefold()
        if canonical in seen:
            raise ValueError(f"Command index contains duplicate command {name!r}.")
        seen.add(canonical)
    names = [entry["name"] for entry in entries]
    if names != sorted(names, key=lambda name: (name.casefold(), name)):
        raise ValueError("Command index entries are not deterministically ordered.")
    return entries


def _command_names(document: Any) -> list[str]:
    return [entry["name"] for entry in _command_entries(document)]


def _manifest_command_names(manifest: dict[str, Any]) -> list[str]:
    names = manifest["channels"]["published"]["wheel"]["command_names"]
    if not isinstance(names, list) or not names:
        raise ValueError("Published manifest command_names must be a non-empty list.")
    if any(not isinstance(name, str) or not name.strip() for name in names):
        raise ValueError("Published manifest command_names must contain text only.")
    folded = [name.casefold() for name in names]
    if len(set(folded)) != len(folded):
        raise ValueError("Published manifest command_names contains duplicates.")
    return names


def _manifest_onboarding(
    manifest: dict[str, Any],
    *,
    command_names: list[str],
) -> dict[str, Any]:
    """Validate the exact read-only onboarding contract carried by QZX."""
    onboarding = manifest.get("onboarding")
    urls = manifest.get("urls")
    if not isinstance(onboarding, dict) or onboarding.get("schema_version") != 1:
        raise ValueError("Product manifest must contain onboarding schema version 1.")
    if onboarding.get("default_risk") != "read_only":
        raise ValueError("Product onboarding must remain read-only by default.")
    if not isinstance(urls, dict):
        raise ValueError("Product manifest URLs must be an object.")
    for key_name in ("documentation_url_key", "security_url_key"):
        url_key = onboarding.get(key_name)
        url = urls.get(url_key) if isinstance(url_key, str) else None
        if not isinstance(url, str) or not url.startswith("https://"):
            raise ValueError(
                f"Onboarding {key_name} must resolve to one HTTPS product URL."
            )

    expected_stages = ("first_success", "explore", "understand")
    steps = onboarding.get("steps")
    if not isinstance(steps, list) or len(steps) != len(expected_stages):
        raise ValueError("Product onboarding must contain exactly three steps.")
    available_commands = set(command_names)
    for expected_stage, step in zip(expected_stages, steps, strict=True):
        if not isinstance(step, dict) or step.get("stage") != expected_stage:
            raise ValueError(
                "Product onboarding stages must be first_success, explore, and "
                "understand in that order."
            )
        command = step.get("command")
        if command not in available_commands:
            raise ValueError(
                f"Onboarding command {command!r} is absent from the command index."
            )
        arguments = step.get("arguments")
        if not isinstance(arguments, list) or any(
            not isinstance(argument, str) or not argument.strip()
            for argument in arguments
        ):
            raise ValueError(
                f"Onboarding step {expected_stage!r} has invalid arguments."
            )
        if not isinstance(step.get("machine_output"), bool):
            raise ValueError(
                f"Onboarding step {expected_stage!r} must declare machine_output."
            )
        purpose = step.get("purpose")
        if not isinstance(purpose, dict) or any(
            not isinstance(purpose.get(language), str)
            or not purpose[language].strip()
            for language in ("en", "es")
        ):
            raise ValueError(
                f"Onboarding step {expected_stage!r} needs bilingual purpose text."
            )
    return json.loads(json.dumps(onboarding, ensure_ascii=False))


def _dereference_tag_commit(tag_name: str, get_json: JsonFetcher) -> str:
    reference = get_json(_github_api(f"git/ref/tags/{quote(tag_name, safe='')}"))
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


def _download_record_bytes(
    record: dict[str, Any],
    *,
    url_field: str,
    label: str,
    get_bytes: BytesFetcher,
) -> bytes:
    url = record.get(url_field)
    if not isinstance(url, str) or not url:
        raise ValueError(f"{label} has no {url_field} URL.")
    payload = get_bytes(url)
    if not isinstance(payload, bytes) or not payload:
        raise ValueError(f"{label} returned no artifact bytes.")
    return payload


def _declared_sha256(record: dict[str, Any]) -> str | None:
    digest = record.get("digest")
    if isinstance(digest, str) and digest.startswith("sha256:"):
        value = digest.removeprefix("sha256:").lower()
        if len(value) == 64:
            return value
    nested = record.get("digests")
    if isinstance(nested, dict):
        value = nested.get("sha256")
        if isinstance(value, str) and len(value) == 64:
            return value.lower()
    return None


def _archive_json_member(payload: bytes, filename: str, suffix: str) -> Any:
    """Read one JSON member from a wheel or source distribution without extracting."""
    if filename.endswith(".whl"):
        with zipfile.ZipFile(io.BytesIO(payload)) as archive:
            matches = [name for name in archive.namelist() if name.endswith(suffix)]
            if len(matches) != 1:
                raise ValueError(
                    f"{filename} must contain exactly one {suffix}; found {matches!r}."
                )
            member = archive.getinfo(matches[0])
            if member.file_size > MAX_METADATA_MEMBER_BYTES:
                raise ValueError(
                    f"{matches[0]} exceeds the metadata verification limit."
                )
            raw = archive.read(member)
    elif filename.endswith(".tar.gz"):
        with tarfile.open(fileobj=io.BytesIO(payload), mode="r:gz") as archive:
            members = [
                member
                for member in archive.getmembers()
                if member.isfile() and member.name.endswith(suffix)
            ]
            if len(members) != 1:
                raise ValueError(
                    f"{filename} must contain exactly one {suffix}; "
                    f"found {[member.name for member in members]!r}."
                )
            member = members[0]
            if member.size > MAX_METADATA_MEMBER_BYTES:
                raise ValueError(
                    f"{member.name} exceeds the metadata verification limit."
                )
            extracted = archive.extractfile(member)
            if extracted is None:
                raise ValueError(f"Unable to read {member.name} from {filename}.")
            raw = extracted.read(MAX_METADATA_MEMBER_BYTES + 1)
            if len(raw) > MAX_METADATA_MEMBER_BYTES:
                raise ValueError(
                    f"{member.name} exceeds the metadata verification limit."
                )
    else:
        raise ValueError(f"Unsupported distribution artifact: {filename}.")
    return json.loads(raw.decode("utf-8"))


def _verify_artifact_internals(
    checks: list[dict[str, Any]],
    *,
    filename: str,
    payload: bytes,
    expected_version: str,
    expected_commands: list[str],
    expected_command_index: dict[str, Any],
    expected_manifest: dict[str, Any],
    expected_onboarding: dict[str, Any],
) -> None:
    surface = "pypi_wheel" if filename.endswith(".whl") else "pypi_sdist"
    try:
        internal_index = _archive_json_member(
            payload,
            filename,
            COMMAND_INDEX_MEMBER,
        )
        internal_manifest = _archive_json_member(
            payload,
            filename,
            PRODUCT_MANIFEST_MEMBER,
        )
        internal_commands = _command_names(internal_index)
        internal_manifest_commands = _manifest_command_names(internal_manifest)
        internal_onboarding = _manifest_onboarding(
            internal_manifest,
            command_names=internal_commands,
        )
        published = internal_manifest["channels"]["published"]
        development = internal_manifest["channels"]["development"]
        _check(
            checks,
            surface=surface,
            name="internal_command_index",
            expected=expected_command_index,
            actual=internal_index,
            detail=(
                "The complete packaged command index must equal the source index."
            ),
        )
        _check(
            checks,
            surface=surface,
            name="internal_product_manifest",
            expected=expected_manifest,
            actual=internal_manifest,
            detail=(
                "The complete packaged product manifest must equal the source "
                "manifest."
            ),
        )
        _check(
            checks,
            surface=surface,
            name="internal_command_inventory",
            expected=expected_commands,
            actual=internal_commands,
        )
        _check(
            checks,
            surface=surface,
            name="internal_manifest_command_inventory",
            expected=internal_commands,
            actual=internal_manifest_commands,
            detail=(
                "The manifest inside the distribution must describe the commands "
                "inside that same immutable distribution."
            ),
        )
        _check(
            checks,
            surface=surface,
            name="internal_onboarding",
            expected=expected_onboarding,
            actual=internal_onboarding,
        )
        _check(
            checks,
            surface=surface,
            name="internal_published_version",
            expected=expected_version,
            actual=published.get("version"),
        )
        _check(
            checks,
            surface=surface,
            name="internal_development_version",
            expected=expected_version,
            actual=development.get("version"),
        )
    except Exception as error:
        _surface_error(
            checks,
            surface=surface,
            error=error,
            expected="valid QZX command index and product manifest inside artifact",
        )


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
    checks: list[dict[str, Any]] = []
    published = manifest["channels"]["published"]
    development = manifest["channels"]["development"]
    manifest_commands = _manifest_command_names(manifest)
    index_commands = _command_names(command_index)
    onboarding = _manifest_onboarding(manifest, command_names=index_commands)
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
        expected=index_commands,
        actual=manifest_commands,
        detail=(
            "The source manifest must describe the exact command index that will "
            "be packaged, without retired or development-only substitutions."
        ),
    )

    github_digests: dict[str, str] = {}
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
        release = get_json(_github_api(f"releases/tags/{quote(tag_name, safe='')}"))
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
            expected=[wheel_name, sdist_name],
            actual=sorted(name for name in assets if name in {wheel_name, sdist_name}),
        )
        for filename in (wheel_name, sdist_name):
            asset = assets.get(filename)
            if not isinstance(asset, dict):
                continue
            payload = _download_record_bytes(
                asset,
                url_field="browser_download_url",
                label=f"GitHub Release asset {filename}",
                get_bytes=get_bytes,
            )
            digest = hashlib.sha256(payload).hexdigest()
            github_digests[filename] = digest
            declared = _declared_sha256(asset)
            if declared is not None:
                _check(
                    checks,
                    surface="github_release",
                    name=f"declared_sha256:{filename}",
                    expected=digest,
                    actual=declared,
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
        _check(
            checks,
            surface="pypi",
            name="requires_python",
            expected=published.get("requires_python"),
            actual=pypi.get("info", {}).get("requires_python"),
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
            expected=[wheel_name, sdist_name],
            actual=sorted(name for name in files if name in {wheel_name, sdist_name}),
        )
        for filename in (wheel_name, sdist_name):
            record = files.get(filename)
            if not isinstance(record, dict):
                continue
            payload = _download_record_bytes(
                record,
                url_field="url",
                label=f"PyPI artifact {filename}",
                get_bytes=get_bytes,
            )
            digest = hashlib.sha256(payload).hexdigest()
            _check(
                checks,
                surface="pypi",
                name=f"declared_sha256:{filename}",
                expected=digest,
                actual=_declared_sha256(record),
            )
            if filename in github_digests:
                _check(
                    checks,
                    surface="artifact_parity",
                    name=filename,
                    expected=digest,
                    actual=github_digests[filename],
                    detail=(
                        "PyPI and GitHub Release must expose byte-identical "
                        "distribution artifacts."
                    ),
                )
            _verify_artifact_internals(
                checks,
                filename=filename,
                payload=payload,
                expected_version=expected_version,
                expected_commands=index_commands,
                expected_command_index=command_index,
                expected_manifest=manifest,
                expected_onboarding=onboarding,
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
        identity_mapping = {name: name for name in index_commands}
        website_checks = {
            "development_version": expected_version,
            "published_version": expected_version,
            "documentation_commit": expected_commit,
            "documentation_branch": "main",
            "documented_command_count": len(index_commands),
            "published_wheel_entry_count": len(index_commands),
            "published_capability_count": len(index_commands),
            "retired_published_entry_count": 0,
            "retired_published_names": [],
            "development_only_count": 0,
            "published_name_to_canonical": identity_mapping,
            "onboarding": onboarding,
        }
        for name, expected in website_checks.items():
            _check(
                checks,
                surface="website",
                name=name,
                expected=expected,
                actual=metadata.get(name),
            )
        _check(
            checks,
            surface="website",
            name="command_inventory",
            expected=index_commands,
            actual=(
                sorted(
                    website_commands,
                    key=lambda command: (command.casefold(), command),
                )
                if isinstance(website_commands, dict)
                else None
            ),
        )
    except Exception as error:
        _surface_error(checks, surface="website", error=error)

    failed = [check for check in checks if not check["success"]]
    return {
        "success": not failed,
        "message": (
            "Local source, GitHub, PyPI, and qzx.yumbale.com are synchronized."
            if not failed
            else f"Public surface parity failed with {len(failed)} mismatch(es)."
        ),
        "expected": {
            "version": expected_version,
            "commit": expected_commit,
            "tag": tag_name,
            "artifacts": [wheel_name, sdist_name],
            "command_count": len(index_commands),
            "command_names": index_commands,
            "onboarding": onboarding,
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
