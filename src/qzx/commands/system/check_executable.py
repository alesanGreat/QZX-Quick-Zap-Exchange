"""Locate one executable and optionally probe its conventional version flag."""

from __future__ import annotations

import os
from pathlib import Path
import re
import shutil
import subprocess

from qzx.core.command_base import CommandBase


class CheckExecutableCommand(CommandBase):
    """Inspect PATH without executing the discovered program by default."""

    name = "checkExecutable"
    description = (
        "Locates an executable in the system PATH and optionally reads its "
        "conventional --version output"
    )
    category = "system"

    parameters = [
        {
            "name": "executable",
            "description": (
                "Executable name or explicit path to locate "
                "(for example: git, node, or docker)"
            ),
            "required": True,
            "type": "str",
        },
        {
            "name": "include_version",
            "description": (
                "Run the exact resolved executable once with --version; "
                "disabled by default"
            ),
            "required": False,
            "default": False,
            "type": "bool",
        },
    ]

    examples = [
        {
            "command": "qzx checkExecutable git",
            "description": "Locate Git without executing it",
        },
        {
            "command": "qzx checkExecutable node --include-version",
            "description": (
                "Locate Node.js and explicitly request its --version output"
            ),
        },
    ]

    def __init__(self, path_lookup=shutil.which, runner=subprocess.run):
        self._path_lookup = path_lookup
        self._runner = runner

    @staticmethod
    def _extract_version(output):
        match = re.search(
            r"(?:version\s+)?"
            r"(v?\d+(?:\.\d+){1,3}"
            r"(?:[-+][A-Za-z0-9._-]+)?)",
            output,
            re.IGNORECASE,
        )
        return match.group(1) if match else None

    def execute(self, executable, include_version=False):
        """Locate an executable and run it only after explicit opt-in."""
        requested = str(executable or "").strip()
        if not requested:
            return {
                "success": False,
                "error_code": "invalid_executable",
                "error": "Executable name cannot be empty.",
                "message": (
                    "Provide an executable name or explicit path to inspect."
                ),
            }

        version_requested = self._parse_bool(include_version)
        if version_requested is None:
            return {
                "success": False,
                "error_code": "invalid_boolean",
                "error": (
                    "include_version must be true or false; got {!r}.".format(
                        include_version
                    )
                ),
                "message": (
                    "Use --include-version to request the version probe, or "
                    "omit it for a lookup-only check."
                ),
                "executable": requested,
            }

        resolved = self._path_lookup(requested)
        if not resolved:
            return {
                "success": True,
                "message": (
                    "Executable '{}' is not available in the system PATH."
                ).format(requested),
                "executable": requested,
                "available": False,
                "version_requested": version_requested,
                "version_checked": False,
                "version": None,
            }

        resolved_path = str(Path(resolved).resolve())
        result = {
            "success": True,
            "message": "Executable '{}' is available at '{}'.".format(
                requested,
                resolved_path,
            ),
            "executable": requested,
            "available": True,
            "executable_path": resolved_path,
            "version_requested": version_requested,
            "version_checked": False,
            "version": None,
            "warnings": [],
        }
        if not version_requested:
            return result

        child_environment = {
            "PATH": os.path.dirname(resolved_path),
            "LC_ALL": "C",
            "LANG": "C",
        }
        if os.name == "nt":
            for name in ("SYSTEMROOT", "WINDIR", "COMSPEC"):
                value = os.environ.get(name)
                if value:
                    child_environment[name] = value

        try:
            completed = self._runner(
                [resolved_path, "--version"],
                capture_output=True,
                text=True,
                errors="replace",
                timeout=3.0,
                check=False,
                shell=False,
                env=child_environment,
            )
        except (OSError, subprocess.SubprocessError) as exc:
            result["warnings"].append(
                {
                    "code": "version_probe_failed",
                    "message": "{}: {}".format(type(exc).__name__, exc),
                }
            )
            result["message"] += (
                " Its explicitly requested --version probe failed."
            )
            return result

        output = "\n".join(
            part.strip()
            for part in (completed.stdout or "", completed.stderr or "")
            if part.strip()
        )[:4096]
        result["version_checked"] = True
        result["version_probe"] = {
            "argument": "--version",
            "return_code": completed.returncode,
            "output": output,
            "output_truncated": len(
                "\n".join(
                    part.strip()
                    for part in (
                        completed.stdout or "",
                        completed.stderr or "",
                    )
                    if part.strip()
                )
            )
            > 4096,
        }
        result["version"] = self._extract_version(output)
        if completed.returncode != 0:
            result["warnings"].append(
                {
                    "code": "version_probe_nonzero",
                    "message": (
                        "--version exited with code {}."
                    ).format(completed.returncode),
                }
            )

        if result["version"]:
            result["message"] = (
                "Executable '{}' is available at '{}' and reports version {}."
            ).format(requested, resolved_path, result["version"])
        else:
            result["message"] = (
                "Executable '{}' is available at '{}', but its --version "
                "output did not contain a recognizable version."
            ).format(requested, resolved_path)
        return result
