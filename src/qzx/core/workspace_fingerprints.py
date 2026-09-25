"""Bounded fingerprints for workspace files and directory trees."""

from __future__ import annotations

import os
from pathlib import Path


def fingerprint_path(
    path,
    *,
    path_type,
    entry_type,
    file_hasher,
    canonical_digest,
    error_type,
):
    """Fingerprint a regular file or an entire non-traversing directory tree."""
    target = Path(path)
    target_type = path_type(target)
    if target_type == "file":
        return _file_fingerprint(target, file_hasher)
    if target_type == "directory":
        return _directory_fingerprint(
            target,
            entry_type=entry_type,
            file_hasher=file_hasher,
            canonical_digest=canonical_digest,
            error_type=error_type,
        )
    raise error_type(
        "unsupported_entry_type",
        "Path '{}' is not a regular file or directory.".format(target),
        {"path": str(target), "type": target_type},
    )


def _file_fingerprint(path, file_hasher):
    return {
        "type": "file",
        "size_bytes": path.stat(follow_symlinks=False).st_size,
        "sha256": file_hasher(path),
    }


def _directory_fingerprint(
    path,
    *,
    entry_type,
    file_hasher,
    canonical_digest,
    error_type,
):
    records = _directory_records(
        path,
        entry_type=entry_type,
        file_hasher=file_hasher,
        error_type=error_type,
    )
    return {
        "type": "directory",
        "size_bytes": sum(record.get("size_bytes", 0) for record in records),
        "entries": len(records),
        "tree_sha256": canonical_digest(records),
    }


def _directory_records(path, *, entry_type, file_hasher, error_type):
    records = []
    stack = [path]
    while stack:
        directory = stack.pop()
        entries = _sorted_entries(directory)
        child_directories = []
        for entry in entries:
            record, child = _entry_record(
                entry,
                path,
                entry_type=entry_type,
                file_hasher=file_hasher,
                error_type=error_type,
            )
            records.append(record)
            if child is not None:
                child_directories.append(child)
        stack.extend(reversed(child_directories))
    return records


def _sorted_entries(directory):
    with os.scandir(directory) as scanner:
        return sorted(scanner, key=lambda item: (item.name.casefold(), item.name))


def _entry_record(entry, base, *, entry_type, file_hasher, error_type):
    entry_path = Path(entry.path)
    relative = entry_path.relative_to(base).as_posix()
    child_type = entry_type(entry)
    if child_type == "directory":
        return {"path": relative, "type": "directory"}, entry_path
    if child_type == "file":
        return _file_record(entry, entry_path, relative, file_hasher), None
    if child_type == "symlink":
        return {
            "path": relative,
            "type": "symlink",
            "target": os.readlink(entry_path),
        }, None
    raise error_type(
        "special_entry_refused",
        "Directory '{}' contains unsupported special entry '{}'.".format(
            base,
            relative,
        ),
        {"path": str(entry_path), "type": child_type},
    )


def _file_record(entry, entry_path, relative, file_hasher):
    return {
        "path": relative,
        "type": "file",
        "size_bytes": entry.stat(follow_symlinks=False).st_size,
        "sha256": file_hasher(entry_path),
    }
