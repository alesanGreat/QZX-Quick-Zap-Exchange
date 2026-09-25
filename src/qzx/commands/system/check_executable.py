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
            "description": "Locate Node.js and explicitly request its --version output",
        },
    ]

    def __init__(self, path_lookup=shutil.which, runner=subprocess.run):
        self._path_lookup = path_lookup
        self._runner = runner

    def execute(self, executable, include_version=False):
        """Locate an executable and run it only after explicit opt-in."""
        requested = str(executable or "").strip()
        if not requested:
            return self._invalid_executable()
        version_requested = self._parse_bool(include_version)
        if version_requested is None:
            return self._invalid_boolean(requested, include_version)

        resolved = self._path_lookup(requested)
        if not resolved:
            return self._missing_result(requested, version_requested)
        resolved_path = str(Path(resolved).resolve())
        result = self._available_result(requested, resolved_path, version_requested)
        if not version_requested:
            return result
        return self._probe_version(result, requested, resolved_path)

    def _probe_version(self, result, requested, resolved_path):
        try:
            completed = self._runner(
                [resolved_path, "--version"],
                capture_output=True,
                text=True,
                errors="replace",
                timeout=3.0,
                check=False,
                shell=False,
                env=self._child_environment(resolved_path),
            )
        except (OSError, subprocess.SubprocessError) as exc:
            result["warnings"].append(
                {
                    "code": "version_probe_failed",
                    "message": "{}: {}".format(type(exc).__name__, exc),
                }
            )
            result["message"] += " Its explicitly requested --version probe failed."
            return result
        return self._apply_version_probe(result, requested, resolved_path, completed)

    def _apply_version_probe(self, result, requested, resolved_path, completed):
        complete_output = self._combined_output(completed)
        output = complete_output[:4096]
        result["version_checked"] = True
        result["version_probe"] = {
            "argument": "--version",
            "return_code": completed.returncode,
            "output": output,
            "output_truncated": len(complete_output) > 4096,
        }
        result["version"] = self._extract_version(output)
        if completed.returncode != 0:
            result["warnings"].append(
                {
                    "code": "version_probe_nonzero",
                    "message": f"--version exited with code {completed.returncode}.",
                }
            )
        result["message"] = self._version_message(
            requested,
            resolved_path,
            result["version"],
        )
        return result

    @staticmethod
    def _combined_output(completed):
        return "\n".join(
            part.strip()
            for part in (completed.stdout or "", completed.stderr or "")
            if part.strip()
        )

    @staticmethod
    def _child_environment(resolved_path):
        environment = {
            "PATH": os.path.dirname(resolved_path),
            "LC_ALL": "C",
            "LANG": "C",
        }
        if os.name == "nt":
            for name in ("SYSTEMROOT", "WINDIR", "COMSPEC"):
                value = os.environ.get(name)
                if value:
                    environment[name] = value
        return environment

    @staticmethod
    def _available_result(requested, resolved_path, version_requested):
        return {
            "success": True,
            "message": f"Executable '{requested}' is available at '{resolved_path}'.",
            "executable": requested,
            "available": True,
            "executable_path": resolved_path,
            "version_requested": version_requested,
            "version_checked": False,
            "version": None,
            "warnings": [],
        }

    @staticmethod
    def _missing_result(requested, version_requested):
        return {
            "success": True,
            "message": f"Executable '{requested}' is not available in the system PATH.",
            "executable": requested,
            "available": False,
            "version_requested": version_requested,
            "version_checked": False,
            "version": None,
        }

    @staticmethod
    def _invalid_executable():
        return {
            "success": False,
            "error_code": "invalid_executable",
            "error": "Executable name cannot be empty.",
            "message": "Provide an executable name or explicit path to inspect.",
        }

    @staticmethod
    def _invalid_boolean(requested, include_version):
        return {
            "success": False,
            "error_code": "invalid_boolean",
            "error": f"include_version must be true or false; got {include_version!r}.",
            "message": (
                "Use --include-version to request the version probe, or omit it "
                "for a lookup-only check."
            ),
            "executable": requested,
        }

    @staticmethod
    def _version_message(requested, resolved_path, version):
        if version:
            return (
                f"Executable '{requested}' is available at '{resolved_path}' "
                f"and reports version {version}."
            )
        return (
            f"Executable '{requested}' is available at '{resolved_path}', but its "
            "--version output did not contain a recognizable version."
        )

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
