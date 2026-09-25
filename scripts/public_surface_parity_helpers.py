"""Manifest, artifact, and GitHub helpers for public-surface parity."""

from __future__ import annotations

import json
from typing import Any
from urllib.parse import quote


GITHUB_REPOSITORY = "alesanGreat/QZX-Quick-Zap-Exchange"
WEBSITE_COMMANDS_URL = "https://qzx.yumbale.com/data/commands.json"
PYPI_PROJECT = "qzx"
MAX_METADATA_MEMBER_BYTES = 8 * 1024 * 1024
COMMAND_INDEX_MEMBER = "qzx/resources/command-index.json"
PRODUCT_MANIFEST_MEMBER = "qzx/resources/product-manifest.json"


def github_api(path: str) -> str:
    return (
        f"https://api.github.com/repos/{GITHUB_REPOSITORY}/"
        f"{path.lstrip('/')}"
    )


def append_check(
    checks,
    *,
    surface,
    name,
    expected,
    actual,
    detail=None,
):
    item = {
        "surface": surface,
        "check": name,
        "success": actual == expected,
        "expected": expected,
        "actual": actual,
    }
    if detail:
        item["detail"] = detail
    checks.append(item)


def append_surface_error(
    checks,
    *,
    surface,
    error,
    expected="reachable and parseable public surface",
):
    checks.append(
        {
            "surface": surface,
            "check": "reachable_and_parseable",
            "success": False,
            "expected": expected,
            "actual": f"{type(error).__name__}: {error}",
        }
    )


def command_entries(document: Any) -> list[dict[str, Any]]:
    if not isinstance(document, dict):
        raise ValueError("Command index must contain one JSON object.")
    if document.get("schema_version") != 2:
        raise ValueError(
            f"Unsupported command-index schema: "
            f"{document.get('schema_version')!r}."
        )
    entries = document.get("commands")
    if not isinstance(entries, list) or not entries:
        raise ValueError(
            "Command index must contain a non-empty commands list."
        )
    _validate_command_entries(entries)
    return entries


def _validate_command_entries(entries):
    seen = set()
    for index, entry in enumerate(entries):
        if not isinstance(entry, dict):
            raise ValueError(
                f"Command index entry {index} must be an object."
            )
        name = entry.get("name")
        if not isinstance(name, str) or not name.strip():
            raise ValueError(
                f"Command index entry {index} must have one non-empty name."
            )
        canonical = name.casefold()
        if canonical in seen:
            raise ValueError(
                f"Command index contains duplicate command {name!r}."
            )
        seen.add(canonical)
    names = [entry["name"] for entry in entries]
    if names != sorted(names, key=lambda name: (name.casefold(), name)):
        raise ValueError(
            "Command index entries are not deterministically ordered."
        )


def command_names(document: Any) -> list[str]:
    return [entry["name"] for entry in command_entries(document)]


def manifest_command_names(manifest: dict[str, Any]) -> list[str]:
    names = manifest["channels"]["published"]["wheel"]["command_names"]
    if not isinstance(names, list) or not names:
        raise ValueError(
            "Published manifest command_names must be a non-empty list."
        )
    if any(
        not isinstance(name, str) or not name.strip()
        for name in names
    ):
        raise ValueError(
            "Published manifest command_names must contain text only."
        )
    folded = [name.casefold() for name in names]
    if len(set(folded)) != len(folded):
        raise ValueError(
            "Published manifest command_names contains duplicates."
        )
    return names


def manifest_onboarding(manifest, *, command_names):
    onboarding = manifest.get("onboarding")
    urls = manifest.get("urls")
    _validate_onboarding_root(onboarding, urls)
    _validate_onboarding_steps(onboarding.get("steps"), command_names)
    return json.loads(json.dumps(onboarding, ensure_ascii=False))


def _validate_onboarding_root(onboarding, urls):
    if (
        not isinstance(onboarding, dict)
        or onboarding.get("schema_version") != 1
    ):
        raise ValueError(
            "Product manifest must contain onboarding schema version 1."
        )
    if onboarding.get("default_risk") != "read_only":
        raise ValueError(
            "Product onboarding must remain read-only by default."
        )
    if not isinstance(urls, dict):
        raise ValueError("Product manifest URLs must be an object.")
    for key_name in ("documentation_url_key", "security_url_key"):
        url_key = onboarding.get(key_name)
        url = urls.get(url_key) if isinstance(url_key, str) else None
        if not isinstance(url, str) or not url.startswith("https://"):
            raise ValueError(
                f"Onboarding {key_name} must resolve to one HTTPS product URL."
            )


def _validate_onboarding_steps(steps, available_names):
    expected_stages = ("first_success", "explore", "understand")
    if not isinstance(steps, list) or len(steps) != len(expected_stages):
        raise ValueError(
            "Product onboarding must contain exactly three steps."
        )
    available = set(available_names)
    for expected_stage, step in zip(
        expected_stages,
        steps,
        strict=True,
    ):
        _validate_onboarding_step(expected_stage, step, available)


def _validate_onboarding_step(expected_stage, step, available):
    if not isinstance(step, dict) or step.get("stage") != expected_stage:
        raise ValueError(
            "Product onboarding stages must be first_success, explore, "
            "and understand in that order."
        )
    command = step.get("command")
    if command not in available:
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


def dereference_tag_commit(tag_name, get_json):
    reference = get_json(
        github_api(f"git/ref/tags/{quote(tag_name, safe='')}")
    )
    target = reference["object"]
    visited = set()
    while target.get("type") == "tag":
        object_sha = target["sha"]
        if object_sha in visited:
            raise ValueError("Git tag object cycle detected.")
        visited.add(object_sha)
        tag_object = get_json(github_api(f"git/tags/{object_sha}"))
        target = tag_object["object"]
    if target.get("type") != "commit":
        raise ValueError(
            f"Tag resolves to {target.get('type')!r}, not a commit."
        )
    commit = target.get("sha")
    if not isinstance(commit, str) or len(commit) != 40:
        raise ValueError("Tag does not expose a full commit SHA.")
    return commit


def download_record_bytes(
    record,
    *,
    url_field,
    label,
    get_bytes,
):
    url = record.get(url_field)
    if not isinstance(url, str) or not url:
        raise ValueError(f"{label} has no {url_field} URL.")
    payload = get_bytes(url)
    if not isinstance(payload, bytes) or not payload:
        raise ValueError(f"{label} returned no artifact bytes.")
    return payload


def declared_sha256(record):
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


