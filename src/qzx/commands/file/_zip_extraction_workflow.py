"""Staging and commit workflow for extractZip."""

from __future__ import annotations

import os
import shutil
import tempfile
import zipfile
from pathlib import Path


def execute_extract(
    command,
    zip_path,
    target_path=".",
    overwrite=False,
    max_files=10000,
    max_total_size_mb=1024,
):
    """Validate, stage, and commit extraction of one ZIP archive."""
    request, failure = _prepare_request(
        command,
        zip_path,
        target_path,
        overwrite,
        max_files,
        max_total_size_mb,
    )
    if failure is not None:
        return failure

    state = _initial_state()
    try:
        failure = _stage_validated_archive(command, request, state)
        if failure is not None:
            return failure
        _commit_staged_archive(command, request, state)
        return _success_result(command, request, state)
    except Exception as exc:
        _rollback_partial(command, request, state)
        return command._error(
            "extraction_failed",
            f"{type(exc).__name__}: {exc}",
            f"ZIP extraction failed before it could complete: {exc}",
            zip_path=request["absolute_zip"],
            target_path=request["absolute_target"],
            partial_output_removed=not request["overwrite"],
        )
    finally:
        if state["staging_root"] is not None:
            shutil.rmtree(state["staging_root"], ignore_errors=True)


def _prepare_request(
    command,
    zip_path,
    target_path,
    overwrite,
    max_files,
    max_total_size_mb,
):
    source_failure = command._validate_archive_source(zip_path)
    if source_failure is not None:
        return None, source_failure

    overwrite, failure = _normalized_overwrite(command, overwrite)
    if failure is not None:
        return None, failure
    limits, failure = _normalized_limits(
        command,
        max_files,
        max_total_size_mb,
    )
    if failure is not None:
        return None, failure

    absolute_zip = os.path.abspath(str(zip_path).strip())
    absolute_target = os.path.abspath(str(target_path).strip() or ".")
    target_existed = os.path.lexists(absolute_target)
    failure = _target_failure(command, absolute_target, target_existed)
    if failure is not None:
        return None, failure

    return {
        "absolute_zip": absolute_zip,
        "absolute_target": absolute_target,
        "target_root": Path(absolute_target),
        "target_existed": target_existed,
        "overwrite": overwrite,
        **limits,
    }, None


def _normalized_overwrite(command, overwrite):
    if not isinstance(overwrite, str):
        return overwrite, None
    parsed = command._parse_bool(overwrite)
    if parsed is not None:
        return parsed, None
    return None, command._error(
        "invalid_overwrite",
        f"Invalid overwrite value: {overwrite}",
        f"overwrite must be true or false; received '{overwrite}'.",
        overwrite=overwrite,
    )


def _normalized_limits(command, max_files, max_total_size_mb):
    try:
        max_files = int(max_files)
        max_total_size_mb = int(max_total_size_mb)
    except (TypeError, ValueError):
        return None, command._error(
            "invalid_limit",
            "Archive limits must be integers.",
            "max_files and max_total_size_mb must be positive integers.",
            max_files=max_files,
            max_total_size_mb=max_total_size_mb,
        )
    if max_files <= 0 or max_total_size_mb <= 0:
        return None, command._error(
            "invalid_limit",
            "Archive limits must be greater than zero.",
            "max_files and max_total_size_mb must be greater than zero.",
            max_files=max_files,
            max_total_size_mb=max_total_size_mb,
        )
    return {
        "max_files": max_files,
        "max_total_size_mb": max_total_size_mb,
        "max_total_bytes": max_total_size_mb * 1024 * 1024,
    }, None


def _target_failure(command, absolute_target, target_existed):
    if not target_existed:
        return None
    if os.path.islink(absolute_target) or not os.path.isdir(absolute_target):
        return command._error(
            "invalid_target",
            f"Extraction target is not a real directory: {absolute_target}",
            (
                f"Target '{absolute_target}' must be a directory and cannot "
                "be a symbolic link."
            ),
            target_path=absolute_target,
        )
    return None


def _initial_state():
    return {
        "staging_root": None,
        "created_files": [],
        "created_directories": [],
        "replaced_files": 0,
        "validated": None,
    }


def _stage_validated_archive(command, request, state):
    with zipfile.ZipFile(request["absolute_zip"], "r") as archive:
        validated, failure = command._validated_members(
            archive,
            request["target_root"],
            request["max_files"],
            request["max_total_bytes"],
        )
        if failure is not None:
            return failure
        state["validated"] = validated

        failure = _conflict_failure(command, request, validated["entries"])
        if failure is not None:
            return failure

        state["staging_root"] = _new_staging_root(request["target_root"])
        _stage_entries(
            command,
            archive,
            validated["entries"],
            state["staging_root"],
            request["max_total_bytes"],
        )
    return None


def _conflict_failure(command, request, entries):
    if not request["target_existed"]:
        return None
    conflicts = command._destination_conflicts(
        entries,
        request["target_root"],
    )
    if not conflicts or request["overwrite"]:
        return None
    return command._error(
        "destination_conflict",
        f"{len(conflicts)} archive destination(s) already exist.",
        (
            "Nothing was extracted because existing paths would be replaced. "
            "Choose an empty target or use --overwrite to create a backup first."
        ),
        conflicts=conflicts[:20],
        conflict_count=len(conflicts),
        target_path=request["absolute_target"],
    )


def _new_staging_root(target_root):
    target_parent = target_root.parent
    target_parent.mkdir(parents=True, exist_ok=True)
    return Path(
        tempfile.mkdtemp(
            prefix=".qzx-extract-",
            dir=str(target_parent),
        )
    )


def _stage_entries(
    command,
    archive,
    entries,
    staging_root,
    max_total_bytes,
):
    actual_total_bytes = 0
    for member, parts, is_directory in entries:
        staged_path = staging_root.joinpath(*parts)
        if is_directory:
            staged_path.mkdir(parents=True, exist_ok=True)
            continue
        staged_path.parent.mkdir(parents=True, exist_ok=True)
        member_bytes, actual_total_bytes = _copy_member(
            command,
            archive,
            member,
            staged_path,
            actual_total_bytes,
            max_total_bytes,
        )
        if member_bytes != member.file_size:
            raise zipfile.BadZipFile(
                "member size differs from its ZIP metadata: "
                f"{member.filename}"
            )


def _copy_member(
    command,
    archive,
    member,
    staged_path,
    actual_total_bytes,
    max_total_bytes,
):
    member_bytes = 0
    with archive.open(member, "r") as source:
        with staged_path.open("xb") as destination:
            while True:
                chunk = source.read(command._copy_chunk_size)
                if not chunk:
                    break
                member_bytes += len(chunk)
                actual_total_bytes += len(chunk)
                if actual_total_bytes > max_total_bytes:
                    raise ValueError(
                        "actual extracted data exceeded the configured size limit"
                    )
                destination.write(chunk)
    return member_bytes, actual_total_bytes


def _commit_staged_archive(command, request, state):
    if not request["target_existed"]:
        os.replace(state["staging_root"], request["target_root"])
        state["staging_root"] = None
        return
    _commit_into_existing(command, request, state)


def _commit_into_existing(command, request, state):
    entries = state["validated"]["entries"]
    directories = _required_directories(entries, request["target_root"])
    _commit_directories(command, request, state, directories)
    _commit_files(command, request, state, entries)


def _required_directories(entries, target_root):
    directories = {
        target_root.joinpath(*parts)
        for _member, parts, is_directory in entries
        if is_directory
    }
    for _member, parts, _is_directory in entries:
        destination = target_root.joinpath(*parts)
        directories.update(
            parent
            for parent in destination.parents
            if parent != target_root and target_root in parent.parents
        )
    return directories


def _commit_directories(command, request, state, directories):
    for directory in sorted(
        directories,
        key=lambda item: len(item.parts),
    ):
        if os.path.lexists(directory):
            if directory.is_dir():
                continue
            if not request["overwrite"]:
                raise FileExistsError(str(directory))
            command._remove_path(directory)
        directory.mkdir()
        state["created_directories"].append(directory)


def _commit_files(command, request, state, entries):
    for _member, parts, is_directory in entries:
        if is_directory:
            continue
        staged_path = state["staging_root"].joinpath(*parts)
        destination = request["target_root"].joinpath(*parts)
        if os.path.lexists(destination):
            if not request["overwrite"]:
                raise FileExistsError(str(destination))
            command._remove_path(destination)
            state["replaced_files"] += 1
        os.replace(staged_path, destination)
        state["created_files"].append(destination)


def _success_result(command, request, state):
    validated = state["validated"]
    total_bytes = validated["total_bytes"]
    readable_size = command._format_bytes(total_bytes)
    message = (
        f"Extracted {validated['file_count']:,} file(s) from "
        f"'{request['absolute_zip']}' to '{request['absolute_target']}' "
        f"({readable_size})."
    )
    if state["replaced_files"]:
        message += (
            f" Replaced {state['replaced_files']:,} existing file(s) after "
            "the required safety backup."
        )
    return {
        "success": True,
        "zip_path": request["absolute_zip"],
        "target_path": request["absolute_target"],
        "files_extracted": validated["file_count"],
        "directories_created": len(state["created_directories"]),
        "files_replaced": state["replaced_files"],
        "total_bytes_extracted": total_bytes,
        "total_size_readable": readable_size,
        "overwrite": bool(request["overwrite"]),
        "limits": {
            "max_files": request["max_files"],
            "max_total_size_mb": request["max_total_size_mb"],
        },
        "skipped_traversals": [],
        "message": message,
    }


def _rollback_partial(command, request, state):
    if request["overwrite"]:
        return
    for created_file in reversed(state["created_files"]):
        if os.path.lexists(created_file):
            command._remove_path(created_file)
    for created_directory in reversed(state["created_directories"]):
        try:
            created_directory.rmdir()
        except OSError:
            pass
