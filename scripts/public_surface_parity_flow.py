"""GitHub, PyPI, website, and artifact parity orchestration."""

from __future__ import annotations

import hashlib
from urllib.parse import quote

from scripts.public_surface_parity_artifacts import (
    verify_artifact_internals,
)
from scripts.public_surface_parity_helpers import (
    PYPI_PROJECT,
    WEBSITE_COMMANDS_URL,
    append_check,
    append_surface_error,
    command_names,
    declared_sha256,
    dereference_tag_commit,
    download_record_bytes,
    github_api,
    manifest_command_names,
    manifest_onboarding,
)


def verify_public_surface_parity(
    *,
    manifest,
    command_index,
    expected_version,
    expected_commit,
    get_json,
    get_bytes,
    require_main=True,
):
    """Verify all public QZX release surfaces against local source identity."""
    context = _parity_context(
        manifest,
        command_index,
        expected_version,
        expected_commit,
    )
    checks = []
    _source_checks(checks, context)
    if require_main:
        _github_main_checks(checks, context, get_json)
    github_digests = _github_release_checks(
        checks,
        context,
        get_json,
        get_bytes,
    )
    _pypi_checks(
        checks,
        context,
        github_digests,
        get_json,
        get_bytes,
    )
    _website_checks(checks, context, get_json)
    return _parity_result(checks, context)


def _parity_context(
    manifest,
    command_index,
    expected_version,
    expected_commit,
):
    index_commands = command_names(command_index)
    onboarding = manifest_onboarding(
        manifest,
        command_names=index_commands,
    )
    return {
        "manifest": manifest,
        "command_index": command_index,
        "published": manifest["channels"]["published"],
        "development": manifest["channels"]["development"],
        "manifest_commands": manifest_command_names(manifest),
        "index_commands": index_commands,
        "onboarding": onboarding,
        "expected_version": expected_version,
        "expected_commit": expected_commit,
        "wheel_name": f"qzx-{expected_version}-py3-none-any.whl",
        "sdist_name": f"qzx-{expected_version}.tar.gz",
        "tag_name": f"v{expected_version}",
    }


def _source_checks(checks, context):
    comparisons = [
        (
            "published_version",
            context["expected_version"],
            context["published"].get("version"),
            None,
        ),
        (
            "development_version",
            context["expected_version"],
            context["development"].get("version"),
            None,
        ),
        (
            "wheel_filename",
            context["wheel_name"],
            context["published"].get("wheel", {}).get("filename"),
            None,
        ),
        (
            "published_command_inventory",
            context["index_commands"],
            context["manifest_commands"],
            "The source manifest must describe the exact command index that "
            "will be packaged, without retired or development-only substitutions.",
        ),
    ]
    for name, expected, actual, detail in comparisons:
        append_check(
            checks,
            surface="source_manifest",
            name=name,
            expected=expected,
            actual=actual,
            detail=detail,
        )


def _github_main_checks(checks, context, get_json):
    try:
        main_commit = get_json(github_api("commits/main"))["sha"]
        append_check(
            checks,
            surface="github_main",
            name="source_commit",
            expected=context["expected_commit"],
            actual=main_commit,
        )
    except Exception as error:
        append_surface_error(
            checks,
            surface="github_main",
            error=error,
        )


def _github_release_checks(checks, context, get_json, get_bytes):
    try:
        release = get_json(
            github_api(
                f"releases/tags/{quote(context['tag_name'], safe='')}"
            )
        )
        _github_release_metadata(checks, context, release)
        digests = _github_asset_checks(
            checks,
            context,
            release,
            get_bytes,
        )
        commit = dereference_tag_commit(context["tag_name"], get_json)
        append_check(
            checks,
            surface="github_release",
            name="tag_source_commit",
            expected=context["expected_commit"],
            actual=commit,
        )
        return digests
    except Exception as error:
        append_surface_error(
            checks,
            surface="github_release",
            error=error,
        )
        return {}


def _github_release_metadata(checks, context, release):
    comparisons = [
        ("tag_name", context["tag_name"], release.get("tag_name")),
        ("published_not_draft", False, bool(release.get("draft"))),
        (
            "alpha_is_prerelease",
            "a" in context["expected_version"],
            bool(release.get("prerelease")),
        ),
    ]
    for name, expected, actual in comparisons:
        append_check(
            checks,
            surface="github_release",
            name=name,
            expected=expected,
            actual=actual,
        )


def _github_asset_checks(checks, context, release, get_bytes):
    filenames = {context["wheel_name"], context["sdist_name"]}
    assets = {
        asset.get("name"): asset
        for asset in release.get("assets", [])
        if isinstance(asset, dict) and isinstance(asset.get("name"), str)
    }
    append_check(
        checks,
        surface="github_release",
        name="distribution_assets",
        expected=sorted(filenames),
        actual=sorted(name for name in assets if name in filenames),
    )
    digests = {}
    for filename in (context["wheel_name"], context["sdist_name"]):
        asset = assets.get(filename)
        if not isinstance(asset, dict):
            continue
        payload = download_record_bytes(
            asset,
            url_field="browser_download_url",
            label=f"GitHub Release asset {filename}",
            get_bytes=get_bytes,
        )
        digest = hashlib.sha256(payload).hexdigest()
        digests[filename] = digest
        declared = declared_sha256(asset)
        if declared is not None:
            append_check(
                checks,
                surface="github_release",
                name=f"declared_sha256:{filename}",
                expected=digest,
                actual=declared,
            )
    return digests


def _pypi_checks(
    checks,
    context,
    github_digests,
    get_json,
    get_bytes,
):
    try:
        pypi = get_json(
            f"https://pypi.org/pypi/{PYPI_PROJECT}/"
            f"{quote(context['expected_version'], safe='')}/json"
        )
        _pypi_metadata_checks(checks, context, pypi)
        _pypi_artifact_checks(
            checks,
            context,
            pypi,
            github_digests,
            get_bytes,
        )
    except Exception as error:
        append_surface_error(checks, surface="pypi", error=error)


def _pypi_metadata_checks(checks, context, pypi):
    append_check(
        checks,
        surface="pypi",
        name="version",
        expected=context["expected_version"],
        actual=pypi.get("info", {}).get("version"),
    )
    append_check(
        checks,
        surface="pypi",
        name="requires_python",
        expected=context["published"].get("requires_python"),
        actual=pypi.get("info", {}).get("requires_python"),
    )


def _pypi_artifact_checks(
    checks,
    context,
    pypi,
    github_digests,
    get_bytes,
):
    filenames = {context["wheel_name"], context["sdist_name"]}
    files = {
        item.get("filename"): item
        for item in pypi.get("urls", [])
        if isinstance(item, dict) and isinstance(item.get("filename"), str)
    }
    append_check(
        checks,
        surface="pypi",
        name="distribution_files",
        expected=sorted(filenames),
        actual=sorted(name for name in files if name in filenames),
    )
    for filename in (context["wheel_name"], context["sdist_name"]):
        record = files.get(filename)
        if not isinstance(record, dict):
            continue
        _pypi_artifact_record(
            checks,
            context,
            record,
            filename,
            github_digests,
            get_bytes,
        )


def _pypi_artifact_record(
    checks,
    context,
    record,
    filename,
    github_digests,
    get_bytes,
):
    payload = download_record_bytes(
        record,
        url_field="url",
        label=f"PyPI artifact {filename}",
        get_bytes=get_bytes,
    )
    digest = hashlib.sha256(payload).hexdigest()
    append_check(
        checks,
        surface="pypi",
        name=f"declared_sha256:{filename}",
        expected=digest,
        actual=declared_sha256(record),
    )
    if filename in github_digests:
        append_check(
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
    verify_artifact_internals(
        checks,
        filename=filename,
        payload=payload,
        expected_version=context["expected_version"],
        expected_commands=context["index_commands"],
        expected_command_index=context["command_index"],
        expected_manifest=context["manifest"],
        expected_onboarding=context["onboarding"],
    )


def _website_checks(checks, context, get_json):
    try:
        separator = "&" if "?" in WEBSITE_COMMANDS_URL else "?"
        website = get_json(
            f"{WEBSITE_COMMANDS_URL}{separator}"
            f"qzx_parity={context['expected_commit'][:12]}"
        )
        metadata = website.get("metadata", {})
        _website_metadata_checks(checks, context, metadata)
        website_commands = website.get("commands", {})
        actual = (
            sorted(
                website_commands,
                key=lambda command: (command.casefold(), command),
            )
            if isinstance(website_commands, dict)
            else None
        )
        append_check(
            checks,
            surface="website",
            name="command_inventory",
            expected=context["index_commands"],
            actual=actual,
        )
    except Exception as error:
        append_surface_error(checks, surface="website", error=error)


def _website_metadata_checks(checks, context, metadata):
    names = context["index_commands"]
    identity_mapping = {name: name for name in names}
    expected_values = {
        "development_version": context["expected_version"],
        "published_version": context["expected_version"],
        "documentation_commit": context["expected_commit"],
        "documentation_branch": "main",
        "documented_command_count": len(names),
        "published_wheel_entry_count": len(names),
        "published_capability_count": len(names),
        "retired_published_entry_count": 0,
        "retired_published_names": [],
        "development_only_count": 0,
        "published_name_to_canonical": identity_mapping,
        "onboarding": context["onboarding"],
    }
    for name, expected in expected_values.items():
        append_check(
            checks,
            surface="website",
            name=name,
            expected=expected,
            actual=metadata.get(name),
        )


def _parity_result(checks, context):
    failed = [check for check in checks if not check["success"]]
    return {
        "success": not failed,
        "message": (
            "Local source, GitHub, PyPI, and qzx.yumbale.com are synchronized."
            if not failed
            else (
                f"Public surface parity failed with "
                f"{len(failed)} mismatch(es)."
            )
        ),
        "expected": {
            "version": context["expected_version"],
            "commit": context["expected_commit"],
            "tag": context["tag_name"],
            "artifacts": [
                context["wheel_name"],
                context["sdist_name"],
            ],
            "command_count": len(context["index_commands"]),
            "command_names": context["index_commands"],
            "onboarding": context["onboarding"],
        },
        "checks": checks,
        "mismatches": failed,
    }
