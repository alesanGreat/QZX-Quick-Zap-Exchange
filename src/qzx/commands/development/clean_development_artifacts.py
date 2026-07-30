#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
CleanDevelopmentArtifacts Command - Finds and optionally removes development caches,
dependency directories, and generated build artifacts.
"""

import fnmatch
import os
import shutil

from qzx.core.command_base import CommandBase


class CleanDevelopmentArtifactsCommand(CommandBase):
    """
    Identify and optionally remove known development-generated directories.
    """

    name = "cleanDevelopmentArtifacts"
    description = (
        "Finds development caches, dependency directories, and generated build "
        "artifacts; preview is the default"
    )
    category = "development"
    requires_explicit_approval = True
    backup_target_parameter = "scan_path"

    parameters = [
        {
            'name': 'scan_path',
            'description': 'Directory to scan (defaults to the current working directory)',
            'required': False,
            'default': '.',
            'type': 'str',
        },
        {
            'name': 'dry_run',
            'description': 'Preview matching directories without deleting them',
            'required': False,
            'default': True,
            'type': 'bool',
        },
        {
            'name': 'max_depth',
            'description': 'Maximum directory depth to inspect (must be at least 1)',
            'required': False,
            'default': 4,
            'type': 'int',
        }
    ]

    examples = [
        {
            'command': 'qzx cleanDevelopmentArtifacts',
            'description': 'Preview generated development directories below the current directory'
        },
        {
            'command': 'qzx cleanDevelopmentArtifacts . --dry-run false',
            'description': 'Back up the current directory, then remove every matched generated directory'
        }
    ]

    # Direct targets are generated state, but some are expensive to recreate.
    # Their presence still requires a real preview and a fail-closed backup.
    CACHE_TARGETS = {
        "node_modules",
        "__pycache__",
        ".pytest_cache",
        ".next",
        ".nuxt",
        ".docusaurus",
        ".turbo",
        ".gradle",
        ".sass-cache",
        ".tscache"
    }
    
    # Target folder names that need safety verification before deletion
    CONDITIONAL_TARGETS = {
        "dist": ["package.json", "vite.config.js", "vite.config.ts", "webpack.config.js"],
        "build": ["package.json", "setup.py", "CMakeLists.txt"],
        "target": ["Cargo.toml"],
        "bin": ["*.csproj", "*.sln"],
        "obj": ["*.csproj", "*.sln"]
    }

    def validate_safety_backup_target(self, target, values):
        """Reject invalid and dangerously broad backup targets."""
        absolute = os.path.abspath(os.fspath(target))
        if not os.path.exists(absolute):
            return self._path_error(
                "path_not_found",
                f"Path '{target}' does not exist.",
                absolute,
            )
        if not os.path.isdir(absolute):
            return self._path_error(
                "path_not_directory",
                f"Path '{target}' is not a directory.",
                absolute,
            )
        drive, tail = os.path.splitdrive(absolute)
        normalized_tail = tail.rstrip(os.sep)
        if normalized_tail == "":
            return {
                "success": False,
                "error_code": "filesystem_root_refused",
                "error": f"Refusing to clean filesystem root '{absolute}'.",
                "message": (
                    "A filesystem root is too broad for cleanDevelopmentArtifacts. Choose "
                    "a project directory, or use the explicit QZX safety bypass "
                    "only if this broad target is genuinely intended."
                ),
                "details": {
                    "scan_path": absolute,
                    "drive": drive or os.path.sep,
                    "dry_run": False,
                },
            }
        return None

    def execute(self, scan_path='.', dry_run=True, max_depth=4):
        """
        Scan for generated development directories and optionally remove them.

        Args:
            scan_path (str): The starting directory path
            dry_run (bool): Whether to skip actual deletion
            max_depth (int): Traversal depth limit

        Returns:
            Dictionary with results and details
        """
        abs_path = os.path.abspath(scan_path)

        if not os.path.exists(abs_path):
            return self._path_error(
                "path_not_found",
                f"Path '{scan_path}' does not exist.",
                abs_path,
            )

        if not os.path.isdir(abs_path):
            return self._path_error(
                "path_not_directory",
                f"Path '{scan_path}' is not a directory.",
                abs_path,
            )

        if isinstance(dry_run, str):
            normalized = dry_run.strip().lower()
            if normalized in {"true", "yes", "y", "1", "t", "on"}:
                is_dry_run = True
            elif normalized in {"false", "no", "n", "0", "f", "off"}:
                is_dry_run = False
            else:
                return self._argument_error(
                    "invalid_dry_run",
                    f"Invalid dry_run value: {dry_run!r}.",
                    abs_path,
                    dry_run=dry_run,
                    max_depth=max_depth,
                )
        else:
            is_dry_run = bool(dry_run)

        try:
            depth_limit = int(max_depth)
        except (TypeError, ValueError):
            return self._argument_error(
                "invalid_max_depth",
                f"max_depth must be an integer of at least 1, got {max_depth!r}.",
                abs_path,
                dry_run=is_dry_run,
                max_depth=max_depth,
            )
        if depth_limit < 1:
            return self._argument_error(
                "invalid_max_depth",
                f"max_depth must be at least 1, got {depth_limit}.",
                abs_path,
                dry_run=is_dry_run,
                max_depth=depth_limit,
            )

        found_folders = []
        identified_bytes = 0

        base_depth = abs_path.count(os.sep)

        try:
            for root, dirs, files in os.walk(abs_path, topdown=True):
                current_depth = root.count(os.sep) - base_depth
                if current_depth >= depth_limit:
                    dirs.clear()
                    continue

                for skip_dir in [".git", ".svn", ".hg"]:
                    if skip_dir in dirs:
                        dirs.remove(skip_dir)

                matched_dirs = []
                for d in list(dirs):
                    full_d_path = os.path.join(root, d)
                    is_match = False
                    reason = ""
                    
                    # Direct match
                    if d in self.CACHE_TARGETS:
                        is_match = True
                        reason = f"Direct cache target name '{d}'"
                    elif d in self.CONDITIONAL_TARGETS:
                        triggers = self.CONDITIONAL_TARGETS[d]
                        for trigger in triggers:
                            if "*" in trigger:
                                if any(fnmatch.fnmatch(f, trigger) for f in files):
                                    is_match = True
                                    reason = f"Conditional target '{d}' matched by file pattern '{trigger}'"
                                    break
                            else:
                                if trigger in files:
                                    is_match = True
                                    reason = f"Conditional target '{d}' matched by parent file '{trigger}'"
                                    break

                    if is_match:
                        matched_dirs.append((full_d_path, d, reason))
                        dirs.remove(d)

                for full_path, name, reason in matched_dirs:
                    size = self._get_dir_size(full_path)
                    found_folders.append({
                        "path": full_path,
                        "relative_path": os.path.relpath(full_path, abs_path),
                        "name": name,
                        "reason": reason,
                        "size_bytes": size,
                        "size_readable": self._format_bytes(size)
                    })
                    identified_bytes += size

            deleted_folders = []
            deleted_bytes = 0
            deletion_failures = []
            errors = []

            if not is_dry_run:
                for item in found_folders:
                    target_path = item["path"]
                    try:
                        self._remove_directory(target_path)
                        deleted_folders.append(target_path)
                        deleted_bytes += item["size_bytes"]
                    except Exception as exc:
                        error = (
                            f"Failed to delete '{target_path}': "
                            f"{type(exc).__name__}: {exc}"
                        )
                        errors.append(error)
                        deletion_failures.append({
                            "path": target_path,
                            "error_type": type(exc).__name__,
                            "error": str(exc),
                        })

            identified_readable = self._format_bytes(identified_bytes)
            deleted_readable = self._format_bytes(deleted_bytes)
            if is_dry_run:
                message = (
                    f"Previewed '{abs_path}' and found {len(found_folders)} "
                    f"generated development directorie(s), totaling "
                    f"{identified_readable}. Nothing was deleted."
                )
            elif deletion_failures:
                message = (
                    f"Cleaned {len(deleted_folders)} of {len(found_folders)} "
                    f"matched directorie(s) below '{abs_path}', recovering "
                    f"{deleted_readable}. {len(deletion_failures)} deletion(s) "
                    "failed; review deletion_failures and restore from the "
                    "reported safety backup if needed."
                )
            else:
                message = (
                    f"Removed {len(deleted_folders)} generated development "
                    f"directorie(s) below '{abs_path}', recovering "
                    f"{deleted_readable}."
                )

            success = not deletion_failures
            return {
                "success": success,
                "status": (
                    "preview"
                    if is_dry_run
                    else ("success" if success else "partial_failure")
                ),
                "scan_path": abs_path,
                "dry_run": is_dry_run,
                "max_depth": depth_limit,
                "total_folders_found": len(found_folders),
                "total_bytes_identified": identified_bytes,
                "total_space_identified_readable": identified_readable,
                "total_bytes_saved": deleted_bytes,
                "total_space_saved_readable": deleted_readable,
                "found_folders": found_folders,
                "deleted_folders": deleted_folders,
                "deletion_failures": deletion_failures,
                "errors": errors,
                "message": message,
            }

        except Exception as exc:
            return {
                "success": False,
                "error_code": "scan_failed",
                "error": f"{type(exc).__name__}: {exc}",
                "message": (
                    f"Could not inspect generated development directories "
                    f"below '{abs_path}': {exc}"
                ),
                "details": {
                    "scan_path": abs_path,
                    "dry_run": is_dry_run,
                    "max_depth": depth_limit,
                },
            }

    @staticmethod
    def _path_error(error_code, message, path):
        return {
            "success": False,
            "error_code": error_code,
            "error": message,
            "message": message,
            "details": {"scan_path": path},
        }

    @staticmethod
    def _argument_error(
        error_code,
        message,
        scan_path,
        *,
        dry_run,
        max_depth,
    ):
        return {
            "success": False,
            "error_code": error_code,
            "error": message,
            "message": message,
            "details": {
                "scan_path": scan_path,
                "dry_run": dry_run,
                "max_depth": max_depth,
            },
        }

    def _get_dir_size(self, path):
        """Calculates total size of a directory in bytes"""
        total_size = 0
        try:
            for root, _, files in os.walk(path):
                for f in files:
                    fp = os.path.join(root, f)
                    try:
                        if not os.path.islink(fp):
                            total_size += os.path.getsize(fp)
                    except OSError:
                        pass
        except Exception:
            pass
        return total_size

    @staticmethod
    def _remove_directory(path):
        """Remove one selected directory through an explicit test boundary."""
        shutil.rmtree(path)
