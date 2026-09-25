#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Find and optionally remove generated development directories."""

import os

from qzx.commands.development._development_cleanup_support import (
    execute_cleanup,
    get_dir_size,
    remove_directory,
)
from qzx.core.command_base import CommandBase


class CleanDevelopmentArtifactsCommand(CommandBase):
    """Identify and optionally remove known generated directories."""

    name = "cleanDevelopmentArtifacts"
    description = "Finds development caches, dependency directories, and generated build artifacts; preview is the default"
    category = "development"
    requires_explicit_approval = True
    backup_target_parameter = "scan_path"
    parameters = [
        {"name": "scan_path", "description": "Directory to scan (defaults to the current working directory)", "required": False, "default": ".", "type": "str"},
        {"name": "dry_run", "description": "Preview matching directories without deleting them", "required": False, "default": True, "type": "bool"},
        {"name": "max_depth", "description": "Maximum directory depth to inspect (must be at least 1)", "required": False, "default": 4, "type": "int"},
    ]
    examples = [
        {"command": "qzx cleanDevelopmentArtifacts", "description": "Preview generated development directories below the current directory"},
        {"command": "qzx cleanDevelopmentArtifacts . --dry-run false", "description": "Back up the current directory, then remove every matched generated directory"},
    ]
    CACHE_TARGETS = {"node_modules", "__pycache__", ".pytest_cache", ".next", ".nuxt", ".docusaurus", ".turbo", ".gradle", ".sass-cache", ".tscache"}
    CONDITIONAL_TARGETS = {
        "dist": ["package.json", "vite.config.js", "vite.config.ts", "webpack.config.js"],
        "build": ["package.json", "setup.py", "CMakeLists.txt"],
        "target": ["Cargo.toml"], "bin": ["*.csproj", "*.sln"],
        "obj": ["*.csproj", "*.sln"],
    }
    _get_dir_size = get_dir_size
    _remove_directory = remove_directory

    def validate_safety_backup_target(self, target, values):
        """Reject invalid and dangerously broad backup targets."""
        absolute = os.path.abspath(os.fspath(target))
        if not os.path.exists(absolute):
            return self._path_error("path_not_found", f"Path '{target}' does not exist.", absolute)
        if not os.path.isdir(absolute):
            return self._path_error("path_not_directory", f"Path '{target}' is not a directory.", absolute)
        drive, tail = os.path.splitdrive(absolute)
        if tail.rstrip(os.sep) == "":
            return {
                "success": False, "error_code": "filesystem_root_refused",
                "error": f"Refusing to clean filesystem root '{absolute}'.",
                "message": "A filesystem root is too broad for cleanDevelopmentArtifacts. Choose a project directory, or use the explicit QZX safety bypass only if this broad target is genuinely intended.",
                "details": {"scan_path": absolute, "drive": drive or os.path.sep, "dry_run": False},
            }
        return None

    def execute(self, scan_path=".", dry_run=True, max_depth=4):
        """Scan for generated directories and optionally remove them."""
        return execute_cleanup(self, scan_path, dry_run, max_depth)

    @staticmethod
    def _path_error(error_code, message, path):
        return {"success": False, "error_code": error_code, "error": message, "message": message, "details": {"scan_path": path}}

    @staticmethod
    def _argument_error(error_code, message, scan_path, *, dry_run, max_depth):
        return {"success": False, "error_code": error_code, "error": message, "message": message, "details": {"scan_path": scan_path, "dry_run": dry_run, "max_depth": max_depth}}
