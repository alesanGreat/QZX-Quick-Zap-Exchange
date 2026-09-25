#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Diagnose PATH health and locate shadowed executable candidates."""

import os
import platform

from qzx.core.command_base import CommandBase


class CheckSystemPathCommand(CommandBase):
    """Inspect PATH directories and optional executable resolution order."""

    name = "checkSystemPath"
    description = "Diagnoses the system PATH variable, lists broken or duplicate folders, and locates all instances of a binary"
    category = "system"

    parameters = [
        {
            "name": "binary_name",
            "description": "Optional binary name to search for (e.g. python, node, git)",
            "required": False,
            "default": "",
        }
    ]

    examples = [
        {
            "command": "qzx checkSystemPath",
            "description": "Inspect system PATH directories for duplicates, errors, and invalid folder paths",
        },
        {
            "command": "qzx checkSystemPath python",
            "description": "Diagnose PATH and list all physical locations of python executables, in order of execution precedence",
        },
    ]

    def execute(self, binary_name=""):
        """Diagnose PATH entries and optionally locate matching executables."""
        is_windows = platform.system().lower() == "windows"
        path_sep = ";" if is_windows else ":"
        path_env = os.environ.get("PATH", "")
        if not path_env:
            return {
                "success": False,
                "error": "PATH environment variable is empty or not set.",
                "message": "PATH environment variable is empty.",
            }

        path_dirs = path_env.split(path_sep)
        valid_dirs, broken_dirs, duplicate_dirs = self._analyze_paths(
            path_dirs,
            is_windows,
        )
        bin_search = str(binary_name or "").strip()
        matches = self._find_binary(valid_dirs, bin_search, is_windows)
        summary = {
            "total_entries": len(path_dirs),
            "valid_count": len(valid_dirs),
            "broken_count": len(broken_dirs),
            "duplicate_count": len(duplicate_dirs),
        }
        return {
            "success": True,
            "binary_searched": bin_search or None,
            "path_summary": summary,
            "broken_paths": broken_dirs,
            "duplicate_paths": duplicate_dirs,
            "binary_matches": matches,
            "message": self._message(summary, broken_dirs, bin_search, matches),
        }

    @staticmethod
    def _analyze_paths(path_dirs, is_windows):
        valid_dirs = []
        broken_dirs = []
        duplicate_dirs = []
        seen = set()
        for index, raw_entry in enumerate(path_dirs):
            entry = raw_entry.strip()
            if not entry:
                continue
            if entry.startswith('"') and entry.endswith('"'):
                entry = entry[1:-1]
            resolved = os.path.normpath(os.path.abspath(entry))
            comparison = resolved.lower() if is_windows else resolved
            item = {"index": index, "raw_path": entry, "resolved_path": resolved}
            if comparison in seen:
                duplicate_dirs.append(item)
                continue
            seen.add(comparison)
            if os.path.isdir(resolved):
                valid_dirs.append(item)
            elif os.path.exists(resolved):
                item["reason"] = "Path exists but is a file, not a directory."
                broken_dirs.append(item)
            else:
                item["reason"] = "Directory does not exist."
                broken_dirs.append(item)
        return valid_dirs, broken_dirs, duplicate_dirs

    def _find_binary(self, valid_dirs, bin_search, is_windows):
        if not bin_search:
            return []
        matches = []
        extensions = self._extensions(bin_search, is_windows)
        for item in valid_dirs:
            match = self._match_in_directory(
                item,
                bin_search,
                extensions,
                is_windows,
            )
            if match:
                matches.append(match)
        return matches

    @staticmethod
    def _extensions(bin_search, is_windows):
        if not is_windows:
            return [""]
        executable_extensions = [".exe", ".cmd", ".bat", ".ps1", ".lnk"]
        _, target_ext = os.path.splitext(bin_search.lower())
        if target_ext in executable_extensions:
            return [""]
        return executable_extensions + [""]

    @staticmethod
    def _match_in_directory(item, bin_search, extensions, is_windows):
        directory = item["resolved_path"]
        for extension in extensions:
            file_name = bin_search + extension
            full_path = os.path.join(directory, file_name)
            try:
                if not os.path.isfile(full_path):
                    continue
                if not (os.access(full_path, os.X_OK) or is_windows):
                    continue
                return {
                    "path_index": item["index"],
                    "directory": directory,
                    "filename": file_name,
                    "full_path": full_path,
                    "size_bytes": os.path.getsize(full_path),
                }
            except OSError:
                continue
        return None

    @classmethod
    def _message(cls, summary, broken_dirs, bin_search, matches):
        message = (
            "PATH Diagnostics Summary:\n"
            f"- Total entries in PATH: {summary['total_entries']}\n"
            f"- Valid directories: {summary['valid_count']}\n"
            f"- Broken paths: {summary['broken_count']}\n"
            f"- Duplicate entries: {summary['duplicate_count']}\n"
        )
        message += cls._broken_message(broken_dirs)
        message += cls._binary_message(bin_search, matches)
        return message

    @staticmethod
    def _broken_message(broken_dirs):
        if not broken_dirs:
            return ""
        lines = ["\n[WARNING] Broken entries identified:"]
        for item in broken_dirs[:5]:
            lines.append(
                f"  - Index {item['index']}: '{item['raw_path']}' ({item['reason']})"
            )
        if len(broken_dirs) > 5:
            lines.append(f"  ... and {len(broken_dirs) - 5} more.")
        return "\n".join(lines) + "\n"

    @staticmethod
    def _binary_message(bin_search, matches):
        if not bin_search:
            return ""
        lines = [f"\nBinary resolution search for '{bin_search}':"]
        if not matches:
            lines.append(
                f"- [ERROR] No executables named '{bin_search}' found on current PATH."
            )
            return "\n".join(lines) + "\n"
        lines.append(f"- Found {len(matches)} location(s) on PATH:")
        for index, match in enumerate(matches):
            prefix = "  >>> [First choice]" if index == 0 else "      [Shadowed]"
            lines.append(f"{prefix} {match['full_path']}")
        return "\n".join(lines) + "\n"
