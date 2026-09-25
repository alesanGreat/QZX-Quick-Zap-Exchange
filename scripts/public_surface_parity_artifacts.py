"""Inspect immutable wheel/sdist metadata for public-surface parity."""

from __future__ import annotations

import io
import json
import tarfile
import zipfile

from scripts.public_surface_parity_helpers import (
    COMMAND_INDEX_MEMBER,
    MAX_METADATA_MEMBER_BYTES,
    PRODUCT_MANIFEST_MEMBER,
    append_check,
    append_surface_error,
    command_names,
    manifest_command_names,
    manifest_onboarding,
)


def archive_json_member(
    payload,
    filename,
    suffix,
    *,
    max_member_bytes=MAX_METADATA_MEMBER_BYTES,
):
    if filename.endswith(".whl"):
        raw = _wheel_json_member(
            payload,
            filename,
            suffix,
            max_member_bytes,
        )
    elif filename.endswith(".tar.gz"):
        raw = _sdist_json_member(
            payload,
            filename,
            suffix,
            max_member_bytes,
        )
    else:
        raise ValueError(
            f"Unsupported distribution artifact: {filename}."
        )
    return json.loads(raw.decode("utf-8"))


def _wheel_json_member(payload, filename, suffix, limit):
    with zipfile.ZipFile(io.BytesIO(payload)) as archive:
        matches = [
            name for name in archive.namelist() if name.endswith(suffix)
        ]
        if len(matches) != 1:
            raise ValueError(
                f"{filename} must contain exactly one {suffix}; "
                f"found {matches!r}."
            )
        member = archive.getinfo(matches[0])
        if member.file_size > limit:
            raise ValueError(
                f"{matches[0]} exceeds the metadata verification limit."
            )
        return archive.read(member)


def _sdist_json_member(payload, filename, suffix, limit):
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
        if member.size > limit:
            raise ValueError(
                f"{member.name} exceeds the metadata verification limit."
            )
        extracted = archive.extractfile(member)
        if extracted is None:
            raise ValueError(
                f"Unable to read {member.name} from {filename}."
            )
        raw = extracted.read(limit + 1)
        if len(raw) > limit:
            raise ValueError(
                f"{member.name} exceeds the metadata verification limit."
            )
        return raw


def verify_artifact_internals(
    checks,
    *,
    filename,
    payload,
    expected_version,
    expected_commands,
    expected_command_index,
    expected_manifest,
    expected_onboarding,
):
    surface = (
        "pypi_wheel" if filename.endswith(".whl") else "pypi_sdist"
    )
    try:
        internal_index = archive_json_member(
            payload,
            filename,
            COMMAND_INDEX_MEMBER,
        )
        internal_manifest = archive_json_member(
            payload,
            filename,
            PRODUCT_MANIFEST_MEMBER,
        )
        _append_internal_checks(
            checks,
            surface=surface,
            internal_index=internal_index,
            internal_manifest=internal_manifest,
            expected_version=expected_version,
            expected_commands=expected_commands,
            expected_command_index=expected_command_index,
            expected_manifest=expected_manifest,
            expected_onboarding=expected_onboarding,
        )
    except Exception as error:
        append_surface_error(
            checks,
            surface=surface,
            error=error,
            expected=(
                "valid QZX command index and product manifest inside artifact"
            ),
        )


def _append_internal_checks(
    checks,
    *,
    surface,
    internal_index,
    internal_manifest,
    expected_version,
    expected_commands,
    expected_command_index,
    expected_manifest,
    expected_onboarding,
):
    internal_commands = command_names(internal_index)
    comparisons = _internal_comparisons(
        internal_index=internal_index,
        internal_manifest=internal_manifest,
        internal_commands=internal_commands,
        expected_version=expected_version,
        expected_commands=expected_commands,
        expected_command_index=expected_command_index,
        expected_manifest=expected_manifest,
        expected_onboarding=expected_onboarding,
    )
    for name, expected, actual, detail in comparisons:
        append_check(
            checks,
            surface=surface,
            name=name,
            expected=expected,
            actual=actual,
            detail=detail,
        )


def _internal_comparisons(
    *,
    internal_index,
    internal_manifest,
    internal_commands,
    expected_version,
    expected_commands,
    expected_command_index,
    expected_manifest,
    expected_onboarding,
):
    comparisons = _identity_comparisons(
        internal_index,
        internal_manifest,
        internal_commands,
        expected_commands,
        expected_command_index,
        expected_manifest,
    )
    comparisons.extend(
        _onboarding_version_comparisons(
            internal_manifest,
            internal_commands,
            expected_version,
            expected_onboarding,
        )
    )
    return comparisons


def _identity_comparisons(
    internal_index,
    internal_manifest,
    internal_commands,
    expected_commands,
    expected_command_index,
    expected_manifest,
):
    manifest_commands = manifest_command_names(internal_manifest)
    return [
        (
            "internal_command_index",
            expected_command_index,
            internal_index,
            "The complete packaged command index must equal the source index.",
        ),
        (
            "internal_product_manifest",
            expected_manifest,
            internal_manifest,
            "The complete packaged product manifest must equal the source manifest.",
        ),
        (
            "internal_command_inventory",
            expected_commands,
            internal_commands,
            None,
        ),
        (
            "internal_manifest_command_inventory",
            internal_commands,
            manifest_commands,
            "The manifest inside the distribution must describe the commands "
            "inside that same immutable distribution.",
        ),
    ]


def _onboarding_version_comparisons(
    internal_manifest,
    internal_commands,
    expected_version,
    expected_onboarding,
):
    onboarding = manifest_onboarding(
        internal_manifest,
        command_names=internal_commands,
    )
    channels = internal_manifest["channels"]
    return [
        ("internal_onboarding", expected_onboarding, onboarding, None),
        (
            "internal_published_version",
            expected_version,
            channels["published"].get("version"),
            None,
        ),
        (
            "internal_development_version",
            expected_version,
            channels["development"].get("version"),
            None,
        ),
    ]
