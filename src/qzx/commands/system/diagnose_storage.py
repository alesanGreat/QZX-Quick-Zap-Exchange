#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Diagnose storage pressure without changing or deleting filesystem content."""

import os

from qzx.core.command_base import CommandBase


class DiagnoseStorageCommand(CommandBase):
    """Combine capacity, large-file, and duplicate evidence into one workflow."""

    name = "diagnoseStorage"
    description = (
        "Diagnoses storage pressure by combining disk capacity, large-file "
        "discovery, and byte-verified duplicate analysis without deleting anything"
    )
    category = "system"

    parameters = [
        {
            "name": "path",
            "description": "Directory to diagnose (defaults to the current directory)",
            "required": False,
            "default": ".",
        },
        {
            "name": "min_file_size",
            "description": (
                "Minimum size for the large-file view, for example 100MiB or 1GB"
            ),
            "required": False,
            "default": "100MiB",
        },
        {
            "name": "max_files",
            "description": "Maximum number of largest files returned (1-1000)",
            "required": False,
            "default": 20,
            "type": "int",
        },
        {
            "name": "duplicate_min_size_kb",
            "description": (
                "Minimum file size in KB considered by the duplicate scan "
                "(defaults to 10240 = 10 MiB)"
            ),
            "required": False,
            "default": 10240,
            "type": "int",
        },
        {
            "name": "max_depth",
            "description": (
                "Maximum directory depth scanned for large and duplicate files "
                "(0-64; defaults to 6)"
            ),
            "required": False,
            "default": 6,
            "type": "int",
        },
        {
            "name": "include_duplicates",
            "description": (
                "Run the byte-verified duplicate scan in the same workflow "
                "(true/false; defaults to true)"
            ),
            "required": False,
            "default": True,
            "type": "bool",
        },
    ]

    examples = [
        {
            "command": "qzx diagnoseStorage",
            "description": (
                "Diagnose storage pressure in the current directory with bounded scans"
            ),
        },
        {
            "command": "qzx diagnoseStorage C:/ --max-depth 4 --max-files 30",
            "description": (
                "Inspect a Windows volume with a shallower scan and a larger top-file list"
            ),
        },
        {
            "command": (
                "qzx diagnoseStorage /home --include-duplicates false "
                "--min-file-size 500MiB"
            ),
            "description": (
                "Run a faster capacity and large-file diagnosis without hashing duplicates"
            ),
        },
    ]

    def __init__(
        self,
        *,
        disk_space_command=None,
        find_files_command=None,
        duplicate_files_command=None,
    ):
        """Allow deterministic probe injection while keeping normal use self-contained."""

        if disk_space_command is None:
            from qzx.commands.system.get_disk_space import GetDiskSpaceCommand

            disk_space_command = GetDiskSpaceCommand()
        if find_files_command is None:
            from qzx.commands.file.find_files import FindFilesCommand

            find_files_command = FindFilesCommand()
        if duplicate_files_command is None:
            from qzx.commands.file.find_duplicate_files import FindDuplicateFilesCommand

            duplicate_files_command = FindDuplicateFilesCommand()

        self._disk_space = disk_space_command
        self._find_files = find_files_command
        self._find_duplicates = duplicate_files_command

    def execute(
        self,
        path=".",
        min_file_size="100MiB",
        max_files=20,
        duplicate_min_size_kb=10240,
        max_depth=6,
        include_duplicates=True,
    ):
        """Run a bounded, read-only storage diagnosis for one directory tree."""

        try:
            target = os.path.abspath(os.fspath(path or "."))
        except TypeError:
            return self._failure(
                "invalid_path",
                "Path must be a filesystem path.",
                path=path,
            )

        if not os.path.exists(target):
            return self._failure(
                "path_not_found",
                f"Storage diagnosis path does not exist: {target}",
                path=target,
            )
        if not os.path.isdir(target):
            return self._failure(
                "not_a_directory",
                f"Storage diagnosis requires a directory: {target}",
                path=target,
            )

        try:
            max_files_value = self._bounded_int(max_files, "max_files", 1, 1000)
            duplicate_min_kb = self._bounded_int(
                duplicate_min_size_kb,
                "duplicate_min_size_kb",
                0,
                2**31 - 1,
            )
            max_depth_value = self._bounded_int(max_depth, "max_depth", 0, 64)
            include_duplicates_value = self._strict_bool(
                include_duplicates, "include_duplicates"
            )
        except ValueError as exc:
            return self._failure(
                "invalid_parameter",
                str(exc),
                path=target,
            )

        capacity = self._disk_space.execute(target)
        if not capacity.get("success"):
            return self._probe_failure("capacity", target, capacity)

        large_files = self._find_files.execute(
            search_path=target,
            pattern="*",
            recursive=max_depth_value,
            min_size=min_file_size,
            sort_by="size",
            descending=True,
            limit=max_files_value,
        )
        if not large_files.get("success"):
            return self._probe_failure("large_files", target, large_files)

        duplicate_result = None
        duplicate_status = "skipped"
        warnings = list(large_files.get("warnings") or [])
        partial = False
        if include_duplicates_value:
            duplicate_result = self._find_duplicates.execute(
                scan_path=target,
                min_size_kb=duplicate_min_kb,
                max_depth=max_depth_value,
            )
            if duplicate_result.get("success"):
                duplicate_status = "ok"
            else:
                duplicate_status = "failed"
                partial = True
                warnings.append(
                    {
                        "code": "duplicate_scan_failed",
                        "message": duplicate_result.get("message")
                        or duplicate_result.get("error")
                        or "Duplicate analysis failed.",
                    }
                )

        disk_info = capacity.get("disk_info") or {}
        percent_used = self._number_or_zero(disk_info.get("percent"))
        capacity_status = self._capacity_status(percent_used)
        free_bytes = int(disk_info.get("free_bytes") or 0)
        total_bytes = int(disk_info.get("total_bytes") or 0)

        duplicate_groups = 0
        duplicate_files = 0
        reclaimable_bytes = 0
        reclaimable_readable = self._format_bytes(0)
        if duplicate_status == "ok":
            duplicate_groups = int(duplicate_result.get("total_groups") or 0)
            duplicate_files = int(
                duplicate_result.get("total_duplicate_files") or 0
            )
            reclaimable_bytes = int(
                duplicate_result.get("reclaimable_bytes") or 0
            )
            reclaimable_readable = duplicate_result.get(
                "reclaimable_space_readable"
            ) or self._format_bytes(reclaimable_bytes)

        recommendations = self._recommendations(
            capacity_status=capacity_status,
            percent_used=percent_used,
            large_files=large_files,
            min_file_size=min_file_size,
            max_depth=max_depth_value,
            duplicate_status=duplicate_status,
            duplicate_groups=duplicate_groups,
            reclaimable_readable=reclaimable_readable,
        )

        assessment = {
            "capacity_status": capacity_status,
            "percent_used": percent_used,
            "total_bytes": total_bytes,
            "total_readable": disk_info.get("total")
            or self._format_bytes(total_bytes),
            "free_bytes": free_bytes,
            "free_readable": disk_info.get("free")
            or self._format_bytes(free_bytes),
            "large_files_matched": int(large_files.get("matched_count") or 0),
            "large_files_returned": int(large_files.get("count") or 0),
            "duplicate_groups": duplicate_groups,
            "duplicate_files": duplicate_files,
            "confirmed_reclaimable_bytes": reclaimable_bytes,
            "confirmed_reclaimable_readable": reclaimable_readable,
        }

        report = self._build_report(
            target=target,
            assessment=assessment,
            duplicate_status=duplicate_status,
            partial=partial,
        )
        message = (
            f"Storage diagnosis completed for '{target}': "
            f"{percent_used:g}% used with {assessment['free_readable']} free; "
            f"{assessment['large_files_matched']} file"
            f"{'s' if assessment['large_files_matched'] != 1 else ''} matched the "
            f"large-file threshold. "
        )
        if duplicate_status == "ok":
            message += (
                f"Confirmed {duplicate_groups} duplicate group"
                f"{'s' if duplicate_groups != 1 else ''} with up to "
                f"{reclaimable_readable} reclaimable if one copy per group is kept. "
            )
        elif duplicate_status == "skipped":
            message += "Duplicate analysis was skipped. "
        else:
            message += "Duplicate analysis failed, so the result is partial. "
        message += "QZX did not delete or modify any files."

        return {
            "success": True,
            "message": message,
            "path": target,
            "partial": partial,
            "read_only": True,
            "scan_scope": {
                "max_depth": max_depth_value,
                "large_file_min_size": min_file_size,
                "max_large_files_returned": max_files_value,
                "duplicate_scan_requested": include_duplicates_value,
                "duplicate_min_size_kb": duplicate_min_kb,
            },
            "probe_status": {
                "capacity": "ok",
                "large_files": "ok",
                "duplicates": duplicate_status,
            },
            "assessment": assessment,
            "capacity": capacity,
            "large_files": large_files,
            "duplicates": duplicate_result,
            "recommendations": recommendations,
            "warnings": warnings,
            "related_commands": [
                "getDiskSpace",
                "findFiles",
                "findDuplicateFiles",
                "getDiskHealth",
            ],
            "report": report,
        }

    def _recommendations(
        self,
        *,
        capacity_status,
        percent_used,
        large_files,
        min_file_size,
        max_depth,
        duplicate_status,
        duplicate_groups,
        reclaimable_readable,
    ):
        recommendations = []
        if capacity_status == "critical":
            recommendations.append(
                {
                    "priority": "high",
                    "action": "Review the largest files and confirmed duplicate groups before adding more data.",
                    "reason": f"The target filesystem is {percent_used:g}% used.",
                }
            )
        elif capacity_status == "attention":
            recommendations.append(
                {
                    "priority": "medium",
                    "action": "Review high-impact storage consumers before the filesystem becomes constrained.",
                    "reason": f"The target filesystem is {percent_used:g}% used.",
                }
            )

        if int(large_files.get("matched_count") or 0) > 0:
            recommendations.append(
                {
                    "priority": "review",
                    "action": "Inspect the returned large-file paths and decide which are intentional; size alone is never a deletion signal.",
                    "reason": (
                        f"Files at or above {min_file_size} were found within "
                        f"depth {max_depth}."
                    ),
                }
            )
        else:
            recommendations.append(
                {
                    "priority": "info",
                    "action": "If storage is still constrained, lower --min-file-size or increase --max-depth to broaden the evidence.",
                    "reason": f"No files met the {min_file_size} threshold in the scanned scope.",
                }
            )

        if duplicate_status == "ok" and duplicate_groups:
            recommendations.append(
                {
                    "priority": "review",
                    "action": "Review each duplicate group and keep at least one intentional copy before removing anything manually.",
                    "reason": (
                        f"Byte-for-byte verification found {duplicate_groups} group"
                        f"{'s' if duplicate_groups != 1 else ''} with up to "
                        f"{reclaimable_readable} reclaimable."
                    ),
                }
            )
        elif duplicate_status == "skipped":
            recommendations.append(
                {
                    "priority": "info",
                    "action": "Run again with --include-duplicates true when duplicate content is worth checking.",
                    "reason": "Duplicate hashing was explicitly skipped for this run.",
                }
            )

        recommendations.append(
            {
                "priority": "info",
                "action": "Use getDiskHealth separately only when hardware health is relevant; capacity pressure does not imply a failing disk.",
                "reason": "S.M.A.R.T. health and filesystem capacity are separate diagnostic questions.",
            }
        )
        return recommendations

    @staticmethod
    def _capacity_status(percent_used):
        if percent_used > 90:
            return "critical"
        if percent_used > 80:
            return "attention"
        return "comfortable"

    @staticmethod
    def _number_or_zero(value):
        try:
            return float(value)
        except (TypeError, ValueError):
            return 0.0

    @staticmethod
    def _bounded_int(value, name, minimum, maximum):
        try:
            parsed = int(value)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"{name} must be an integer.") from exc
        if parsed < minimum or parsed > maximum:
            raise ValueError(
                f"{name} must be between {minimum} and {maximum}."
            )
        return parsed

    @classmethod
    def _strict_bool(cls, value, name):
        parsed = cls._parse_bool(value)
        if parsed is None:
            raise ValueError(f"{name} must be true or false.")
        return parsed

    @staticmethod
    def _failure(error_code, message, **details):
        return {
            "success": False,
            "message": message,
            "error": message,
            "error_code": error_code,
            "details": details,
        }

    @classmethod
    def _probe_failure(cls, probe, target, result):
        message = result.get("message") or result.get("error") or "Unknown error"
        return cls._failure(
            f"{probe}_probe_failed",
            f"Storage diagnosis could not complete the {probe} probe: {message}",
            path=target,
            probe=probe,
            probe_result=result,
        )

    def _build_report(self, *, target, assessment, duplicate_status, partial):
        lines = [
            f"Storage diagnosis: {target}",
            (
                "Capacity: {}% used; {} free of {}. Status: {}."
            ).format(
                f"{assessment['percent_used']:g}",
                assessment["free_readable"],
                assessment["total_readable"],
                assessment["capacity_status"],
            ),
            (
                "Large files: {} matched; {} returned for review."
            ).format(
                assessment["large_files_matched"],
                assessment["large_files_returned"],
            ),
        ]
        if duplicate_status == "ok":
            lines.append(
                "Duplicates: {} verified group(s), {} duplicate file(s), up to {} reclaimable if one copy per group is kept.".format(
                    assessment["duplicate_groups"],
                    assessment["duplicate_files"],
                    assessment["confirmed_reclaimable_readable"],
                )
            )
        elif duplicate_status == "skipped":
            lines.append("Duplicates: skipped by request.")
        else:
            lines.append("Duplicates: scan failed; see warnings for the partial result.")
        lines.append(
            "Safety: read-only diagnosis; QZX did not delete or modify files."
        )
        if partial:
            lines.append("Result completeness: partial.")
        return "\n".join(lines)
