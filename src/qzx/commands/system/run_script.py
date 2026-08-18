#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Run one explicitly selected local script with bounded retained output."""

import locale
import os
import platform
import signal
import shutil
import subprocess
import sys
import tempfile

from qzx.core.command_base import CommandBase


class RunScriptCommand(CommandBase):
    """Execute a supported script without pretending to sandbox its behavior."""

    name = "runScript"
    description = (
        "Executes one explicit Python, Bash, or Windows Batch script with a "
        "timeout and bounded retained output"
    )
    category = "system"
    requires_explicit_approval = True

    timeout_seconds = 60
    retained_output_bytes = 1024 * 1024

    parameters = [
        {
            "name": "script_path",
            "description": "Path to the local script to execute",
            "required": True,
        },
        {
            "name": "args",
            "description": (
                "Arguments passed to the script; QZX does not add their values "
                "to result metadata, but the script can print them in captured output"
            ),
            "required": False,
            "default": [],
            "is_variadic": True,
        },
    ]

    examples = [
        {
            "command": "qzx runScript myscript.py --yolo",
            "description": (
                "Execute a reviewed Python script when its mutation targets "
                "cannot be determined"
            ),
        },
        {
            "command": "qzx runScript myscript.py arg1 arg2 --yolo",
            "description": (
                "Execute with two arguments without QZX adding their values to "
                "result metadata"
            ),
        },
        {
            "command": (
                "qzx runScript script.sh "
                "--dangerously-bypass-approvals-and-sandbox"
            ),
            "description": "Execute a reviewed Bash script without a safety backup",
        },
    ]

    def execute(self, script_path, *args):
        """Execute a supported script and return a bounded structured result."""
        try:
            absolute_script = os.path.abspath(os.fspath(script_path))
        except TypeError:
            return self._failure(
                "invalid_script_path",
                "script_path must be a filesystem path.",
                script_path=str(script_path),
            )

        if not os.path.exists(absolute_script):
            return self._failure(
                "script_not_found",
                f"Script does not exist: {absolute_script}",
                script_path=absolute_script,
            )
        if not os.path.isfile(absolute_script):
            return self._failure(
                "script_not_regular_file",
                f"Script path is not a regular file: {absolute_script}",
                script_path=absolute_script,
            )

        try:
            command, script_type = self._command_for_script(absolute_script, args)
        except ValueError as exc:
            return self._failure(
                "unsupported_script_type",
                str(exc),
                script_path=absolute_script,
            )

        with tempfile.TemporaryFile() as stdout_file, tempfile.TemporaryFile() as stderr_file:
            try:
                process = subprocess.Popen(
                    command,
                    stdin=subprocess.DEVNULL,
                    stdout=stdout_file,
                    stderr=stderr_file,
                    **self._process_group_options(),
                )
                exit_code = process.wait(timeout=self.timeout_seconds)
            except subprocess.TimeoutExpired:
                termination = self._terminate_process_tree(process)
                stdout = self._read_capture(stdout_file)
                stderr = self._read_capture(stderr_file)
                return {
                    "success": False,
                    "message": (
                        f"{script_type} script '{os.path.basename(absolute_script)}' "
                        f"exceeded the {self.timeout_seconds}-second timeout."
                    ),
                    "error": "Script execution timed out.",
                    "error_code": "script_timeout",
                    "script": self._script_info(
                        absolute_script,
                        script_type,
                        len(args),
                    ),
                    "execution": {
                        "timeout_seconds": self.timeout_seconds,
                        "exit_code": None,
                        "timed_out": True,
                        "termination": termination,
                    },
                    "stdout": stdout,
                    "stderr": stderr,
                }
            except OSError as exc:
                return self._failure(
                    "script_start_failed",
                    f"Could not start the {script_type} script: {exc}",
                    script_path=absolute_script,
                    script_type=script_type,
                )

            stdout = self._read_capture(stdout_file)
            stderr = self._read_capture(stderr_file)

        success = exit_code == 0
        if success:
            message = (
                f"Executed {script_type} script "
                f"'{os.path.basename(absolute_script)}' successfully."
            )
        else:
            message = (
                f"{script_type} script '{os.path.basename(absolute_script)}' "
                f"exited with code {exit_code}."
            )
        result = {
            "success": success,
            "message": message,
            "script": self._script_info(
                absolute_script,
                script_type,
                len(args),
            ),
            "execution": {
                "timeout_seconds": self.timeout_seconds,
                "exit_code": exit_code,
                "timed_out": False,
            },
            "stdout": stdout,
            "stderr": stderr,
        }
        if not success:
            result["error"] = "Script returned a non-zero exit code."
            result["error_code"] = "script_failed"
        return result

    @staticmethod
    def _command_for_script(script_path, args):
        suffix = os.path.splitext(script_path)[1].lower()
        normalized_args = [str(argument) for argument in args]
        system = platform.system().lower()
        if suffix == ".py":
            return [sys.executable, script_path, *normalized_args], "Python"
        if suffix == ".sh" and system != "windows":
            bash = shutil.which("bash")
            if not bash:
                raise ValueError("Bash is not available in PATH.")
            return [bash, script_path, *normalized_args], "Bash"
        if suffix in {".bat", ".cmd"} and system == "windows":
            return [script_path, *normalized_args], "Windows Batch"
        supported = ".py on every platform, .sh outside Windows, and .bat/.cmd on Windows"
        raise ValueError(
            f"Unsupported script type '{suffix or '(none)'}'; supported types are {supported}."
        )

    def _read_capture(self, capture):
        size = capture.tell()
        capture.seek(0)
        retained = capture.read(self.retained_output_bytes)
        encoding = locale.getpreferredencoding(False) or "utf-8"
        return {
            "text": retained.decode(encoding, errors="replace"),
            "bytes_produced": size,
            "bytes_retained": len(retained),
            "truncated": size > len(retained),
            "retention_limit_bytes": self.retained_output_bytes,
        }

    @staticmethod
    def _process_group_options():
        """Isolate a script so a timeout can stop descendants with it."""
        if os.name == "nt":
            return {
                "creationflags": getattr(
                    subprocess,
                    "CREATE_NEW_PROCESS_GROUP",
                    0,
                )
            }
        return {"start_new_session": True}

    @staticmethod
    def _terminate_process_tree(process):
        """Stop a timed-out script and its descendants when the OS permits."""
        method = "process_kill_fallback"
        process_tree_confirmed = False

        if os.name == "nt":
            taskkill = shutil.which("taskkill.exe") or shutil.which("taskkill")
            if taskkill:
                try:
                    completed = subprocess.run(
                        [taskkill, "/PID", str(process.pid), "/T", "/F"],
                        stdin=subprocess.DEVNULL,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                        timeout=10,
                        check=False,
                    )
                    method = "taskkill_tree"
                    process_tree_confirmed = completed.returncode == 0
                except (OSError, subprocess.TimeoutExpired):
                    pass
        else:
            try:
                os.killpg(process.pid, signal.SIGKILL)
                method = "process_group_kill"
                process_tree_confirmed = True
            except (OSError, ProcessLookupError):
                pass

        if process.poll() is None:
            try:
                process.kill()
            except OSError:
                pass
        try:
            process.wait(timeout=5)
        except (OSError, subprocess.TimeoutExpired):
            pass

        return {
            "attempted": True,
            "scope": "process_tree",
            "method": method,
            "process_tree_confirmed": process_tree_confirmed,
            "root_process_stopped": process.poll() is not None,
        }

    @staticmethod
    def _script_info(script_path, script_type, argument_count):
        return {
            "path": script_path,
            "name": os.path.basename(script_path),
            "directory": os.path.dirname(script_path),
            "size_bytes": os.path.getsize(script_path),
            "type": script_type,
            "argument_count": argument_count,
            "argument_values_in_metadata": False,
            "captured_output_may_contain_argument_values": True,
            "working_directory": os.getcwd(),
        }

    @staticmethod
    def _failure(error_code, message, **details):
        return {
            "success": False,
            "message": message,
            "error": message,
            "error_code": error_code,
            "details": details,
        }
