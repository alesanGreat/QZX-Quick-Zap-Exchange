"""createZip request preparation and atomic archive workflow."""

from __future__ import annotations

import fnmatch
import os
import tempfile
import zipfile

from qzx.core.path_operation_utils import file_sha256


DEFAULT_EXCLUDES = {
    ".git",
    "node_modules",
    "__pycache__",
    ".venv",
    "env",
    "dist",
    "build",
}


def prepare_create_zip_request(
    command,
    zip_path,
    source_path,
    exclude_patterns,
    overwrite,
):
    """Validate public arguments and build an immutable-enough request."""
    if not str(zip_path).strip() or not str(source_path).strip():
        return None, command._error(
            "parameters_required",
            "Both zip_path and source_path parameters are required.",
            "Both ZIP destination and source path must be set.",
        )
    if isinstance(overwrite, str):
        parsed_overwrite = command._parse_bool(overwrite)
        if parsed_overwrite is None:
            return None, command._error(
                "invalid_overwrite",
                f"Invalid overwrite value: {overwrite}",
                f"overwrite must be true or false; received '{overwrite}'.",
                overwrite=overwrite,
            )
        overwrite = parsed_overwrite

    absolute_source = os.path.abspath(str(source_path).strip())
    absolute_zip = os.path.abspath(str(zip_path).strip())
    failure = command._validate_source(absolute_source, absolute_zip)
    if failure is not None:
        return None, failure
    failure = _destination_failure(command, absolute_zip, overwrite)
    if failure is not None:
        return None, failure
    return {
        "absolute_source": absolute_source,
        "absolute_zip": absolute_zip,
        "overwrite": bool(overwrite),
        "excludes": _exclude_patterns(exclude_patterns),
        "compression": _compression_method(),
    }, None


def _destination_failure(command, absolute_zip, overwrite):
    if os.path.isdir(absolute_zip) and not os.path.islink(absolute_zip):
        return command._error(
            "destination_is_directory",
            f"ZIP destination is a directory: {absolute_zip}",
            f"Choose a ZIP file path instead of '{absolute_zip}'.",
            zip_path=absolute_zip,
        )
    if os.path.lexists(absolute_zip) and not overwrite:
        return command._error(
            "destination_exists",
            f"ZIP destination already exists: {absolute_zip}",
            (
                f"ZIP destination '{absolute_zip}' already exists. Use "
                "--overwrite to replace it after a safety backup."
            ),
            zip_path=absolute_zip,
            overwrite=False,
        )
    return None


def _exclude_patterns(exclude_patterns):
    if exclude_patterns is None:
        return set(DEFAULT_EXCLUDES)
    return {
        pattern.strip()
        for pattern in str(exclude_patterns).split(",")
        if pattern.strip()
    }


def _compression_method():
    try:
        import zlib  # noqa: F401

        return zipfile.ZIP_DEFLATED
    except ImportError:
        return zipfile.ZIP_STORED


def create_zip_archive(command, request):
    """Create a sibling temporary archive and atomically publish it."""
    temporary_zip = None
    try:
        temporary_zip = _new_temporary_zip(request["absolute_zip"])
        stats = _write_archive_contents(command, request, temporary_zip)
        return _publish_archive(command, request, temporary_zip, stats)
    except Exception as exc:
        return command._error(
            "compression_failed",
            f"{type(exc).__name__}: {exc}",
            (
                "ZIP compression failed before the destination was replaced: "
                f"{exc}"
            ),
            zip_path=request["absolute_zip"],
            source_path=request["absolute_source"],
            prior_destination_preserved=True,
        )
    finally:
        if temporary_zip and os.path.exists(temporary_zip):
            os.unlink(temporary_zip)


def _new_temporary_zip(absolute_zip):
    zip_directory = os.path.dirname(absolute_zip)
    if zip_directory:
        os.makedirs(zip_directory, exist_ok=True)
    descriptor, temporary_zip = tempfile.mkstemp(
        prefix=".qzx-compress-",
        suffix=".zip.part",
        dir=zip_directory or None,
    )
    os.close(descriptor)
    return temporary_zip


def _write_archive_contents(command, request, temporary_zip):
    absolute_source = request["absolute_source"]
    stats = {"total_files": 0, "original_size": 0, "skipped_symlinks": []}
    with zipfile.ZipFile(
        temporary_zip,
        "w",
        compression=request["compression"],
        allowZip64=True,
    ) as archive:
        if os.path.isfile(absolute_source):
            archive.write(absolute_source, os.path.basename(absolute_source))
            stats["original_size"] = os.path.getsize(absolute_source)
            stats["total_files"] = 1
        else:
            _archive_directory(command, archive, request, temporary_zip, stats)
    return stats


def _archive_directory(command, archive, request, temporary_zip, stats):
    absolute_source = request["absolute_source"]
    excludes = request["excludes"]
    for root, directories, files in os.walk(absolute_source, followlinks=False):
        directories[:] = [
            directory
            for directory in directories
            if not os.path.islink(os.path.join(root, directory))
            and directory not in excludes
            and not any(fnmatch.fnmatch(directory, pattern) for pattern in excludes)
        ]
        for filename in files:
            if filename in excludes or any(
                fnmatch.fnmatch(filename, pattern) for pattern in excludes
            ):
                continue
            full_path = os.path.join(root, filename)
            if os.path.islink(full_path):
                stats["skipped_symlinks"].append(
                    os.path.relpath(full_path, absolute_source)
                )
                continue
            if command._same_filesystem_object(
                full_path,
                request["absolute_zip"],
            ) or command._same_filesystem_object(full_path, temporary_zip):
                continue
            archive_name = os.path.relpath(full_path, absolute_source)
            archive.write(full_path, archive_name)
            stats["original_size"] += os.path.getsize(full_path)
            stats["total_files"] += 1


def _publish_archive(command, request, temporary_zip, stats):
    compressed_size = os.path.getsize(temporary_zip)
    archive_sha256 = file_sha256(temporary_zip)
    os.replace(temporary_zip, request["absolute_zip"])

    original_size = stats["original_size"]
    ratio = (
        (1 - compressed_size / original_size) * 100
        if original_size > 0
        else 0
    )
    message = _success_message(
        command,
        request,
        stats,
        compressed_size,
        archive_sha256,
    )
    return {
        "success": True,
        "zip_path": request["absolute_zip"],
        "source_path": request["absolute_source"],
        "files_archived": stats["total_files"],
        "original_bytes": original_size,
        "compressed_bytes": compressed_size,
        "compression_ratio_percent": round(ratio, 2),
        "sha256": archive_sha256,
        "overwrite": request["overwrite"],
        "skipped_symlinks": stats["skipped_symlinks"],
        "message": message,
    }


def _success_message(command, request, stats, compressed_size, archive_sha256):
    readable_original = command._format_bytes(stats["original_size"])
    readable_compressed = command._format_bytes(compressed_size)
    message = (
        f"Archived {stats['total_files']:,} file(s) from "
        f"'{request['absolute_source']}' to '{request['absolute_zip']}' "
        f"({readable_original} → {readable_compressed}, "
        f"SHA-256 {archive_sha256})."
    )
    if stats["skipped_symlinks"]:
        message += (
            f" Skipped {len(stats['skipped_symlinks']):,} symbolic link(s) "
            "to keep archive boundaries explicit."
        )
    return message
