"""Bounded-depth inventory of independent regular files for duplicate analysis."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
import os
import stat

from qzx.core.filesystem_references import is_path_reference


EXCLUDED_DIRECTORIES = frozenset({".git", "node_modules", ".venv", "env"})
WARNING_SAMPLE_LIMIT = 20
_STATISTICS = (
    "directories_scanned", "files_seen", "independent_files", "files_hashed", "hash_attempts",
    "byte_comparisons", "hardlink_aliases_skipped", "below_minimum_skipped",
    "file_links_skipped", "special_files_skipped", "directory_links_skipped",
    "excluded_directories", "depth_limited_directories", "offline_files_skipped",
)


@dataclass(frozen=True)
class FileCandidate:
    """Observed identity and change markers, not an atomic filesystem snapshot."""

    path: str
    size: int
    signature: tuple


def file_signature(info: os.stat_result) -> tuple:
    """Ignore access time: reading a file must not invalidate its own evidence."""
    return (
        info.st_dev, info.st_ino, info.st_mode, info.st_size,
        info.st_mtime_ns, info.st_ctime_ns, info.st_nlink,
        getattr(info, "st_file_attributes", 0), getattr(info, "st_reparse_tag", 0),
    )


def file_snapshot(path: str) -> os.stat_result:
    """Use os.stat, not cached DirEntry.stat with zero Windows file identities."""
    return os.stat(path, follow_symlinks=False)


@dataclass
class DuplicateInventory:
    root: str
    min_bytes: float
    max_depth: int
    files_by_size: dict = field(default_factory=dict)
    identities: dict = field(default_factory=dict)
    hardlink_aliases: list = field(default_factory=list)
    warnings: list = field(default_factory=list)
    warning_counts: Counter = field(default_factory=Counter)
    statistics: dict = field(default_factory=lambda: dict.fromkeys(_STATISTICS, 0))
    _reported_issues: set = field(default_factory=set)

    @property
    def partial(self) -> bool:
        return bool(self.warning_counts)

    @property
    def warning_count(self) -> int:
        return sum(self.warning_counts.values())

    def problem(self, code: str, message: str, path: str) -> None:
        """Keep exact issue counts with a bounded, deduplicated diagnostic sample."""
        identity = (code, path)
        if identity in self._reported_issues:
            return
        self._reported_issues.add(identity)
        self.warning_counts[code] += 1
        if len(self.warnings) < WARNING_SAMPLE_LIMIT:
            self.warnings.append({"code": code, "message": message, "path": path})

    def walk_error(self, error: OSError) -> None:
        path = os.fsdecode(error.filename) if error.filename else self.root
        self.problem("directory_unreadable", str(error), path)


def collect_inventory(
    root: str,
    min_bytes: float,
    max_depth: int,
    *,
    walk_factory=os.walk,
    snapshot_reader=file_snapshot,
) -> DuplicateInventory:
    """Process the boundary directory's files with explicit filesystem boundaries."""
    inventory = DuplicateInventory(root, min_bytes, max_depth)
    walk = walk_factory(
        root, topdown=True, onerror=inventory.walk_error, followlinks=False
    )
    for folder, directories, filenames in walk:
        inventory.statistics["directories_scanned"] += 1
        relative = os.path.relpath(folder, root)
        depth = 0 if relative == "." else len(relative.split(os.sep))
        _prune_directories(
            inventory, folder, directories, depth, snapshot_reader
        )
        for filename in sorted(filenames):
            _add_file(inventory, os.path.join(folder, filename), snapshot_reader)
    return inventory


def _prune_directories(inventory, folder, directories, depth, snapshot_reader):
    if depth >= inventory.max_depth:
        inventory.statistics["depth_limited_directories"] += len(directories)
        directories.clear()
        return
    retained = []
    for name in sorted(directories):
        if name.casefold() in EXCLUDED_DIRECTORIES:
            inventory.statistics["excluded_directories"] += 1
            continue
        path = os.path.join(folder, name)
        try:
            info = snapshot_reader(path)
        except OSError as exc:
            inventory.problem("directory_unreadable", str(exc), path)
            continue
        if _directory_link(info):
            inventory.statistics["directory_links_skipped"] += 1
        else:
            retained.append(name)
    directories[:] = retained


def _directory_link(info) -> bool:
    # Reparse points used for local cloud data are not necessarily aliases.
    return is_path_reference(info)


def _add_file(inventory, path, snapshot_reader):
    inventory.statistics["files_seen"] += 1
    try:
        info = snapshot_reader(path)
    except OSError as exc:
        inventory.problem("file_unreadable", str(exc), path)
        return
    if not _eligible_file(inventory, path, info):
        return
    identity = (info.st_dev, info.st_ino)
    previous = inventory.identities.get(identity)
    if previous is not None:
        inventory.hardlink_aliases.append({"path": path, "same_file_as": previous})
        inventory.statistics["hardlink_aliases_skipped"] += 1
        return
    inventory.identities[identity] = path
    candidate = FileCandidate(path, info.st_size, file_signature(info))
    inventory.files_by_size.setdefault(info.st_size, []).append(candidate)
    inventory.statistics["independent_files"] += 1


def _eligible_file(inventory, path, info) -> bool:
    if stat.S_ISLNK(info.st_mode):
        inventory.statistics["file_links_skipped"] += 1
        return False
    if not stat.S_ISREG(info.st_mode):
        inventory.statistics["special_files_skipped"] += 1
        return False
    if info.st_size < inventory.min_bytes:
        inventory.statistics["below_minimum_skipped"] += 1
        return False
    if _offline_file(info):
        inventory.statistics["offline_files_skipped"] += 1
        inventory.problem(
            "offline_file_skipped", "File content is offline; it was not downloaded.", path
        )
        return False
    if not info.st_ino:
        inventory.problem(
            "file_identity_unavailable",
            "Cannot distinguish this file from hardlink aliases on this filesystem.", path,
        )
        return False
    return True


def _offline_file(info) -> bool:
    # Avoid unexpected hydration of cloud placeholders while diagnosing storage.
    offline = getattr(stat, "FILE_ATTRIBUTE_OFFLINE", 0x1000)
    recall_on_read = 0x400000  # FILE_ATTRIBUTE_RECALL_ON_DATA_ACCESS
    return bool(getattr(info, "st_file_attributes", 0) & (offline | recall_on_read))
