"""Whole-archive member validation for extractZip."""

from __future__ import annotations

import os


def validate_archive_members(
    command,
    archive,
    target_root,
    max_files,
    max_total_bytes,
):
    """Validate every central-directory member before any extraction write."""
    state = _collect_members(command, archive, target_root)
    _append_parent_file_conflicts(state)

    if state["unsafe_members"]:
        return None, _unsafe_failure(command, state["unsafe_members"])
    if state["file_count"] > max_files:
        return None, _file_limit_failure(
            command,
            state["file_count"],
            max_files,
        )
    if state["total_bytes"] > max_total_bytes:
        return None, _size_limit_failure(
            command,
            state["total_bytes"],
            max_total_bytes,
        )
    return {
        "entries": state["entries"],
        "file_count": state["file_count"],
        "total_bytes": state["total_bytes"],
    }, None


def _collect_members(command, archive, target_root):
    state = {
        "entries": [],
        "unsafe_members": [],
        "seen": set(),
        "file_paths": set(),
        "file_count": 0,
        "total_bytes": 0,
    }
    resolved_target = target_root.resolve(strict=False)
    for member in archive.infolist():
        item = _validated_member(
            command,
            member,
            target_root,
            resolved_target,
            state["seen"],
        )
        if item["unsafe"] is not None:
            state["unsafe_members"].append(item["unsafe"])
            continue
        if item["entry"] is None:
            continue
        state["entries"].append(item["entry"])
        if not item["is_directory"]:
            state["file_count"] += 1
            state["total_bytes"] += member.file_size
            state["file_paths"].add(item["comparison_key"])
    return state


def _validated_member(
    command,
    member,
    target_root,
    resolved_target,
    seen,
):
    parts, reason = command._member_parts(member)
    if reason is not None:
        return _member_result(
            unsafe={"member": member.filename, "reason": reason}
        )
    if not parts:
        return _member_result()

    relative_key = "/".join(parts)
    comparison_key = (
        relative_key.casefold() if os.name == "nt" else relative_key
    )
    if comparison_key in seen:
        return _member_result(
            unsafe={
                "member": member.filename,
                "reason": "duplicates another normalized member path",
            }
        )
    seen.add(comparison_key)

    member_target = target_root.joinpath(*parts)
    try:
        member_target.resolve(strict=False).relative_to(resolved_target)
    except ValueError:
        return _member_result(
            unsafe={
                "member": member.filename,
                "reason": "resolves outside the target directory",
            }
        )

    is_directory = member.is_dir()
    return _member_result(
        entry=(member, parts, is_directory),
        is_directory=is_directory,
        comparison_key=comparison_key,
    )


def _member_result(
    *,
    entry=None,
    unsafe=None,
    is_directory=False,
    comparison_key=None,
):
    return {
        "entry": entry,
        "unsafe": unsafe,
        "is_directory": is_directory,
        "comparison_key": comparison_key,
    }


def _append_parent_file_conflicts(state):
    for file_path in sorted(state["file_paths"]):
        components = file_path.split("/")
        for index in range(1, len(components)):
            if "/".join(components[:index]) not in state["file_paths"]:
                continue
            state["unsafe_members"].append(
                {
                    "member": file_path,
                    "reason": (
                        "requires treating another archived file as a directory"
                    ),
                }
            )
            break


def _unsafe_failure(command, unsafe_members):
    return command._error(
        "unsafe_archive_member",
        "The archive contains unsafe or ambiguous member paths.",
        (
            "Nothing was extracted because the ZIP contains unsafe or "
            "ambiguous entries."
        ),
        unsafe_members=unsafe_members[:20],
        unsafe_member_count=len(unsafe_members),
    )


def _file_limit_failure(command, file_count, max_files):
    return command._error(
        "archive_file_limit_exceeded",
        f"Archive contains {file_count} files; limit is {max_files}.",
        (
            f"Nothing was extracted because the archive contains "
            f"{file_count:,} files, above the {max_files:,}-file limit."
        ),
        files_in_archive=file_count,
        max_files=max_files,
    )


def _size_limit_failure(command, total_bytes, max_total_bytes):
    return command._error(
        "archive_size_limit_exceeded",
        (
            f"Archive expands to {total_bytes} bytes; limit is "
            f"{max_total_bytes} bytes."
        ),
        (
            "Nothing was extracted because the archive's declared "
            f"uncompressed size is {command._format_bytes(total_bytes)}, "
            "above the configured "
            f"{command._format_bytes(max_total_bytes)} limit."
        ),
        total_uncompressed_bytes=total_bytes,
        max_total_bytes=max_total_bytes,
    )
