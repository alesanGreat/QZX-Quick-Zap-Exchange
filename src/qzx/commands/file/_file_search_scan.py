"""Streaming metadata collection, bounded top-K selection, and explicit coverage."""

from __future__ import annotations

from dataclasses import dataclass, field
import datetime
import heapq
import os
import stat


@dataclass
class FileSearchScan:
    root: str
    matched_count: int = 0
    matched_size_bytes: int = 0
    skipped_unreadable: int = 0
    skipped_search_paths: int = 0
    skipped_special_files: int = 0
    file_warning_paths: list = field(default_factory=list)
    search_warning_paths: list = field(default_factory=list)
    root_error: str | None = None

    @property
    def partial(self):
        return bool(self.skipped_unreadable or self.skipped_search_paths)

    def search_error(self, error):
        self.skipped_search_paths += 1
        path = os.path.abspath(os.fsdecode(error.filename)) if error.filename else self.root
        if len(self.search_warning_paths) < 20:
            self.search_warning_paths.append(path)
        if os.path.normcase(path) == os.path.normcase(self.root):
            self.root_error = str(error)

    def unreadable_file(self, path):
        self.skipped_unreadable += 1
        if len(self.file_warning_paths) < 20:
            self.file_warning_paths.append(os.path.abspath(path))

    def warnings(self):
        warnings = []
        if self.skipped_unreadable:
            warnings.append(_warning(
                "unreadable_files_skipped", self.skipped_unreadable, self.file_warning_paths,
                "file(s) changed or could not provide readable metadata during the search",
            ))
        if self.skipped_search_paths:
            warnings.append(_warning(
                "search_paths_unreadable", self.skipped_search_paths, self.search_warning_paths,
                "path(s) could not be enumerated or inspected during the search",
            ))
        return warnings


def _warning(code, count, paths, explanation):
    return {
        "code": code, "message": f"Skipped {count} {explanation}.",
        "sample_paths": paths, "sample_truncated": count > len(paths),
    }


def collect_files(root, pattern, options, finder, format_bytes):
    scan = FileSearchScan(root)
    paths = finder(
        file_path_pattern=os.path.join(root, pattern), recursive=options.depth,
        exclude_patterns=options.exclude, exclude_dirs=options.exclude_dirs,
        file_type="f", on_error=scan.search_error,
    )
    records = _metadata_records(paths, options, scan, format_bytes)
    results = select_records(records, options.sort_by, options.descending, options.limit)
    if scan.root_error:
        raise OSError(scan.root_error)
    return scan, results


def _metadata_records(paths, options, scan, format_bytes):
    for path in paths:
        try:
            info = os.stat(path)
            if not stat.S_ISREG(info.st_mode):
                scan.skipped_special_files += 1
                continue
            if not _matches_metadata(info, options):
                continue
            record = _metadata_record(path, info, scan.root, format_bytes)
        except (OSError, ValueError, OverflowError):
            scan.unreadable_file(path)
            continue
        scan.matched_count += 1
        scan.matched_size_bytes += info.st_size
        yield record


def _matches_metadata(info, options):
    return not (
        options.min_bytes is not None and info.st_size < options.min_bytes
        or options.max_bytes is not None and info.st_size > options.max_bytes
        or options.after_timestamp is not None and info.st_mtime < options.after_timestamp
        or options.before_timestamp is not None and info.st_mtime >= options.before_timestamp
    )


def _metadata_record(path, info, root, format_bytes):
    absolute = os.path.abspath(path)
    relative = os.path.relpath(absolute, root)
    return {
        "name": os.path.basename(absolute), "path": absolute,
        "relative_path": relative, "depth": file_depth(relative),
        "size_bytes": info.st_size, "size_readable": format_bytes(info.st_size),
        "modified_timestamp": info.st_mtime,
        "modified_at": datetime.datetime.fromtimestamp(info.st_mtime).astimezone().isoformat(timespec="seconds"),
    }


def file_depth(relative_path):
    parent = os.path.dirname(relative_path)
    return 0 if not parent else len(parent.split(os.sep))


def select_records(records, sort_by, descending, limit):
    """Store only K records for a limited view while consuming all count evidence."""
    key = _sort_key(sort_by)
    if limit is None:
        return sorted(records, key=key, reverse=descending)
    select = heapq.nlargest if descending else heapq.nsmallest
    return select(limit, records, key=key)


def _sort_key(sort_by):
    primary_keys = {
        "path": lambda item: os.path.normcase(item["path"]),
        "name": lambda item: os.path.normcase(item["name"]),
        "size": lambda item: item["size_bytes"],
        "modified": lambda item: item["modified_timestamp"],
    }
    primary = primary_keys[sort_by]
    return lambda item: (primary(item), os.path.normcase(item["path"]), item["path"])
