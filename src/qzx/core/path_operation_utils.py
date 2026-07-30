"""Shared fail-closed helpers for filesystem copy and move operations."""

from __future__ import annotations

import hashlib
import os
from pathlib import Path
import stat


def path_variants(path):
    """Return normalized lexical and symlink-resolved forms of one path."""
    absolute = os.path.abspath(os.fspath(path))
    return {
        os.path.normcase(os.path.normpath(absolute)),
        os.path.normcase(os.path.normpath(os.path.realpath(absolute))),
    }


def same_or_nested_path_relationship(source, destination):
    """Describe overlap between two paths, considering symlinked ancestors."""
    source_variants = path_variants(source)
    destination_variants = path_variants(destination)
    if source_variants & destination_variants:
        return "same"
    for source_path in source_variants:
        for destination_path in destination_variants:
            if _is_within(destination_path, source_path):
                return "destination_within_source"
            if _is_within(source_path, destination_path):
                return "source_within_destination"
    return "separate"


def is_filesystem_root(path):
    """Return whether a path identifies the root of a filesystem."""
    absolute = os.path.normpath(os.path.abspath(os.fspath(path)))
    parent = os.path.dirname(absolute)
    return os.path.normcase(parent) == os.path.normcase(absolute)


def destination_device(destination):
    """Return the device containing a destination or its nearest parent."""
    candidate = Path(os.path.abspath(os.fspath(destination)))
    if os.path.lexists(candidate):
        return candidate.stat(follow_symlinks=False).st_dev
    candidate = candidate.parent
    while not os.path.lexists(candidate):
        parent = candidate.parent
        if parent == candidate:
            raise OSError(
                f"No existing parent was found for destination '{destination}'."
            )
        candidate = parent
    return candidate.stat(follow_symlinks=False).st_dev


def file_sha256(path):
    """Hash one regular file without loading it all into memory."""
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def files_identical(first_path, second_path, chunk_size=1024 * 1024):
    """Compare two regular, non-symlink files without trusting a digest."""
    first_path = Path(first_path)
    second_path = Path(second_path)
    first_stat = first_path.stat(follow_symlinks=False)
    second_stat = second_path.stat(follow_symlinks=False)
    if (
        not stat.S_ISREG(first_stat.st_mode)
        or not stat.S_ISREG(second_stat.st_mode)
        or first_stat.st_size != second_stat.st_size
    ):
        return False
    with first_path.open("rb") as first, second_path.open("rb") as second:
        while True:
            first_chunk = first.read(chunk_size)
            second_chunk = second.read(chunk_size)
            if first_chunk != second_chunk:
                return False
            if not first_chunk:
                return True


def _is_within(candidate, parent):
    try:
        common = os.path.commonpath([candidate, parent])
    except ValueError:
        return False
    return (
        os.path.normcase(common) == os.path.normcase(parent)
        and os.path.normcase(candidate) != os.path.normcase(parent)
    )
