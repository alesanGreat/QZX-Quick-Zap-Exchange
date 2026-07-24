#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Create fail-closed safety archives before high-risk QZX operations."""

from datetime import datetime, timedelta, timezone
import io
import json
import os
from pathlib import Path
import re
import stat
import tarfile
import zipfile


BACKUP_DIRECTORY_ENV = "QZX_BACKUPS_PATH"
BACKUP_FORMAT_ENV = "QZX_BACKUPS_FORMAT"
BACKUP_COMPRESSION_ENV = "QZX_BACKUPS_COMPRESSION"

SUPPORTED_FORMATS = {"ZIP", "TAR.GZ", "TAR"}
COMPRESSION_LEVELS = {
    "store": None,
    "none": None,
    "uncompressed": None,
    "fastest": 1,
    "fast": 3,
    "normal": 6,
    "default": 6,
    "balanced": 6,
    "maximum": 9,
    "max": 9,
    "best": 9,
    "optimal": 9,
}


class SafetyBackupConfigurationError(ValueError):
    """Raised when a QZX safety-backup environment setting is invalid."""


def _absolute_path(value):
    """Return a normalized absolute path without resolving symlink targets."""
    expanded = os.path.expandvars(os.path.expanduser(str(value)))
    return Path(os.path.abspath(expanded))


def _sanitize_fragment(value, fallback):
    """Make a cross-platform filename fragment from an arbitrary value."""
    sanitized = re.sub(r"[^A-Za-z0-9._-]+", "_", str(value))
    sanitized = re.sub(r"_+", "_", sanitized).strip("._-")
    return sanitized or fallback


def _path_fragment(source):
    """Return the last 30 characters of the sanitized absolute source path."""
    return _sanitize_fragment(source, "root")[-30:]


def _source_label(source):
    """Choose a portable top-level archive name for the source."""
    if source.name:
        return _sanitize_fragment(source.name, "source")
    anchor = _sanitize_fragment(source.anchor, "root")
    return anchor or "root"


def _parse_format(environ):
    raw_format = environ.get(BACKUP_FORMAT_ENV, "ZIP")
    backup_format = str(raw_format).strip().upper()
    if backup_format not in SUPPORTED_FORMATS:
        raise SafetyBackupConfigurationError(
            "{} must be one of ZIP, TAR.GZ, or TAR; received {!r}.".format(
                BACKUP_FORMAT_ENV,
                raw_format,
            )
        )
    return backup_format


def _parse_compression(environ):
    raw_compression = environ.get(BACKUP_COMPRESSION_ENV, "fastest")
    normalized = str(raw_compression).strip().lower()
    if normalized.isdigit():
        level = int(normalized)
        if 0 <= level <= 9:
            return normalized, level
    elif normalized in COMPRESSION_LEVELS:
        return normalized, COMPRESSION_LEVELS[normalized]

    raise SafetyBackupConfigurationError(
        (
            "{} must be store, fastest, fast, normal, maximum, an equivalent "
            "alias, or a numeric level from 0 through 9; received {!r}."
        ).format(BACKUP_COMPRESSION_ENV, raw_compression)
    )


def _is_relative_to(path, parent):
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False


def _excluded_from_source(path, source, backup_directory, archive_path):
    """Prevent an archive from recursively capturing its own destination."""
    if path == archive_path:
        return True
    if (
        source != backup_directory
        and _is_relative_to(backup_directory, source)
        and _is_relative_to(path, backup_directory)
    ):
        return True
    return False


def _write_zip_symlink(archive, source, arcname, mode):
    """Store a symlink itself instead of following its target."""
    info = zipfile.ZipInfo(arcname)
    info.create_system = 3
    info.compress_type = archive.compression
    info.external_attr = (mode & 0xFFFF) << 16
    archive.writestr(info, os.readlink(source).encode("utf-8"))


def _add_zip_path(
    archive,
    path,
    arcname,
    source,
    backup_directory,
    archive_path,
    skipped,
):
    if _excluded_from_source(path, source, backup_directory, archive_path):
        return

    path_stat = os.lstat(path)
    mode = path_stat.st_mode
    if stat.S_ISLNK(mode):
        _write_zip_symlink(archive, path, arcname, mode)
        return
    if stat.S_ISREG(mode):
        archive.write(path, arcname)
        return
    if not stat.S_ISDIR(mode):
        skipped.append(
            {
                "path": str(path),
                "reason": "unsupported_special_file",
            }
        )
        return

    archive.write(path, arcname.rstrip("/") + "/")
    with os.scandir(path) as entries:
        for entry in sorted(entries, key=lambda item: item.name):
            _add_zip_path(
                archive,
                Path(entry.path),
                "{}/{}".format(arcname.rstrip("/"), entry.name),
                source,
                backup_directory,
                archive_path,
                skipped,
            )


def _add_tar_path(
    archive,
    path,
    arcname,
    source,
    backup_directory,
    archive_path,
    skipped,
):
    if _excluded_from_source(path, source, backup_directory, archive_path):
        return

    path_stat = os.lstat(path)
    mode = path_stat.st_mode
    if not (
        stat.S_ISLNK(mode)
        or stat.S_ISREG(mode)
        or stat.S_ISDIR(mode)
    ):
        skipped.append(
            {
                "path": str(path),
                "reason": "unsupported_special_file",
            }
        )
        return

    archive.add(path, arcname=arcname, recursive=False)
    if stat.S_ISDIR(mode) and not stat.S_ISLNK(mode):
        with os.scandir(path) as entries:
            for entry in sorted(entries, key=lambda item: item.name):
                _add_tar_path(
                    archive,
                    Path(entry.path),
                    "{}/{}".format(arcname.rstrip("/"), entry.name),
                    source,
                    backup_directory,
                    archive_path,
                    skipped,
                )


def _manifest_bytes(manifest):
    return json.dumps(
        manifest,
        indent=2,
        ensure_ascii=False,
        sort_keys=True,
    ).encode("utf-8")


def _write_zip(
    archive_path,
    source,
    backup_directory,
    compression_name,
    compression_level,
    manifest,
):
    compression = (
        zipfile.ZIP_STORED
        if compression_level is None
        else zipfile.ZIP_DEFLATED
    )
    kwargs = {
        "mode": "x",
        "compression": compression,
        "strict_timestamps": False,
    }
    if compression_level is not None:
        kwargs["compresslevel"] = compression_level

    skipped = []
    with zipfile.ZipFile(archive_path, **kwargs) as archive:
        if os.path.lexists(source):
            _add_zip_path(
                archive,
                source,
                _source_label(source),
                source,
                backup_directory,
                archive_path,
                skipped,
            )
        manifest["skipped_entries"] = skipped
        archive.writestr(
            "__qzx_backup_manifest__.json",
            _manifest_bytes(manifest),
        )


def _write_tar(
    archive_path,
    source,
    backup_directory,
    backup_format,
    compression_name,
    compression_level,
    manifest,
):
    mode = "x:gz" if backup_format == "TAR.GZ" else "x"
    kwargs = {}
    if backup_format == "TAR.GZ":
        kwargs["compresslevel"] = (
            0 if compression_level is None else compression_level
        )

    skipped = []
    with tarfile.open(archive_path, mode, **kwargs) as archive:
        if os.path.lexists(source):
            _add_tar_path(
                archive,
                source,
                _source_label(source),
                source,
                backup_directory,
                archive_path,
                skipped,
            )
        manifest["skipped_entries"] = skipped
        manifest_content = _manifest_bytes(manifest)
        manifest_info = tarfile.TarInfo("__qzx_backup_manifest__.json")
        manifest_info.size = len(manifest_content)
        manifest_info.mode = 0o600
        manifest_info.mtime = int(datetime.now(timezone.utc).timestamp())
        archive.addfile(manifest_info, io.BytesIO(manifest_content))


def create_safety_backup(command_name, source_path, environ=None, now=None):
    """
    Archive ``source_path`` using the configured QZX safety-backup policy.

    The destination is created if needed. Configuration or archive errors are
    deliberately propagated so callers can stop the dangerous operation.
    """
    environ = os.environ if environ is None else environ
    source = _absolute_path(source_path)
    backup_format = _parse_format(environ)
    compression_name, compression_level = _parse_compression(environ)

    configured_directory = environ.get(BACKUP_DIRECTORY_ENV)
    backup_directory = _absolute_path(
        configured_directory
        if configured_directory
        else Path.home() / "QZX-Backups"
    )
    directory_was_created = not backup_directory.exists()
    backup_directory.mkdir(parents=True, exist_ok=True)
    if directory_was_created and os.name != "nt":
        backup_directory.chmod(0o700)

    extension = {
        "ZIP": ".zip",
        "TAR.GZ": ".tar.gz",
        "TAR": ".tar",
    }[backup_format]
    command_fragment = _sanitize_fragment(command_name, "command")
    timestamp = now or datetime.now()
    source_exists = os.path.lexists(source)

    for offset in range(60):
        candidate_timestamp = timestamp + timedelta(seconds=offset)
        filename = "QZX-Backup-{}-{}-{}{}".format(
            candidate_timestamp.strftime("%y%m%d%H%M%S"),
            _path_fragment(source),
            command_fragment,
            extension,
        )
        archive_path = backup_directory / filename
        if archive_path.exists():
            continue

        effective_compression = (
            "store"
            if backup_format == "TAR" or compression_level is None
            else compression_name
        )
        manifest = {
            "schema_version": 1,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "command": str(command_name),
            "source_path": str(source),
            "source_exists": source_exists,
            "archive_format": backup_format,
            "compression": effective_compression,
        }

        try:
            if backup_format == "ZIP":
                _write_zip(
                    archive_path,
                    source,
                    backup_directory,
                    compression_name,
                    compression_level,
                    manifest,
                )
            else:
                _write_tar(
                    archive_path,
                    source,
                    backup_directory,
                    backup_format,
                    compression_name,
                    compression_level,
                    manifest,
                )
            if os.name != "nt":
                archive_path.chmod(0o600)
            return {
                "status": "created",
                "path": str(archive_path),
                "source_path": str(source),
                "source_exists": source_exists,
                "format": backup_format,
                "compression": effective_compression,
                "size_bytes": archive_path.stat().st_size,
            }
        except FileExistsError:
            continue
        except Exception:
            if archive_path.exists():
                archive_path.unlink()
            raise

    raise FileExistsError(
        "Could not allocate a unique QZX backup filename after 60 attempts."
    )
