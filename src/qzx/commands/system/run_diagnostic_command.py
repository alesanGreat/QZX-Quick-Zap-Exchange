#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Run narrowly constrained, read-only native system diagnostics."""

import datetime
import locale
import os
import re
import subprocess
import threading
import time
from typing import ClassVar

from qzx.core.command_base import CommandBase


def _subprocess_output_encoding():
    """Return the encoding used by redirected native console output."""
    if os.name == "nt":
        try:
            import ctypes

            code_page = ctypes.windll.kernel32.GetOEMCP()
            if code_page:
                return "cp{}".format(code_page)
        except (AttributeError, OSError):
            pass
    return locale.getpreferredencoding(False) or "utf-8"


class _BoundedStreamCapture:
    """Drain one pipe continuously while retaining only a byte budget."""

    def __init__(self, limit):
        self.limit = limit
        self.chunks = []
        self.retained_bytes = 0
        self.observed_bytes = 0
        self.read_error = None

    def consume(self, stream):
        try:
            while True:
                chunk = stream.read(8192)
                if not chunk:
                    break
                self.observed_bytes += len(chunk)
                remaining = self.limit - self.retained_bytes
                if remaining > 0:
                    retained = chunk[:remaining]
                    self.chunks.append(retained)
                    self.retained_bytes += len(retained)
        except (OSError, ValueError) as exc:
            self.read_error = "{}: {}".format(type(exc).__name__, exc)

    @property
    def truncated(self):
        return self.observed_bytes > self.retained_bytes

    def text(self):
        payload = b"".join(self.chunks)
        text = payload.decode(
            _subprocess_output_encoding(),
            errors="replace",
        )
        if self.truncated:
            text += "\n… output truncated by QZX …"
        return text


def _run_bounded_process(
    argv,
    *,
    timeout_seconds,
    stdout_limit,
    stderr_limit,
    cwd=None,
    env=None,
):
    """Execute a trusted argv while bounding memory during pipe drainage."""
    creation_flags = 0
    if os.name == "nt":
        creation_flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)

    started = time.perf_counter()
    process = subprocess.Popen(
        argv,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        shell=False,
        creationflags=creation_flags,
        start_new_session=(os.name != "nt"),
        cwd=cwd,
        env=env,
    )
    stdout_capture = _BoundedStreamCapture(stdout_limit)
    stderr_capture = _BoundedStreamCapture(stderr_limit)
    readers = [
        threading.Thread(
            target=stdout_capture.consume,
            args=(process.stdout,),
            name="qzx-diagnostic-stdout",
            daemon=True,
        ),
        threading.Thread(
            target=stderr_capture.consume,
            args=(process.stderr,),
            name="qzx-diagnostic-stderr",
            daemon=True,
        ),
    ]
    for reader in readers:
        reader.start()

    timed_out = False
    try:
        return_code = process.wait(timeout=timeout_seconds)
    except subprocess.TimeoutExpired:
        timed_out = True
        process.kill()
        try:
            return_code = process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            return_code = None
    finally:
        for reader in readers:
            reader.join(timeout=5)
        for stream in (process.stdout, process.stderr):
            if stream is not None:
                try:
                    stream.close()
                except OSError:
                    pass
        for reader in readers:
            reader.join(timeout=1)
        for reader, capture in zip(
            readers,
            (stdout_capture, stderr_capture),
        ):
            if reader.is_alive() and capture.read_error is None:
                capture.read_error = (
                    "{} did not terminate after its pipe was closed.".format(
                        reader.name
                    )
                )

    return {
        "return_code": return_code,
        "timed_out": timed_out,
        "duration_seconds": round(time.perf_counter() - started, 6),
        "stdout": stdout_capture.text(),
        "stderr": stderr_capture.text(),
        "stdout_observed_bytes": stdout_capture.observed_bytes,
        "stderr_observed_bytes": stderr_capture.observed_bytes,
        "stdout_retained_bytes": stdout_capture.retained_bytes,
        "stderr_retained_bytes": stderr_capture.retained_bytes,
        "stdout_truncated": stdout_capture.truncated,
        "stderr_truncated": stderr_capture.truncated,
        "reader_errors": [
            error
            for error in (
                stdout_capture.read_error,
                stderr_capture.read_error,
            )
            if error
        ],
    }


class RunDiagnosticCommand(CommandBase):
    """Execute one read-only diagnostic with a strict argument grammar."""

    name = "runDiagnosticCommand"
    aliases = []
    description = (
        "Runs a strictly read-only native system diagnostic from a "
        "platform-specific allowlist"
    )
    category = "system"

    result_schema: ClassVar[dict[str, object]] = {
        "type": "object",
        "properties": {
            "success": {"type": "boolean"},
            "message": {"type": "string"},
            "error": {
                "oneOf": [
                    {"type": "string"},
                    {"type": "null"},
                ]
            },
            "error_code": {"type": "string"},
            "stdout": {"type": "string"},
            "stderr": {"type": "string"},
            "details": {
                "type": "object",
                "additionalProperties": True,
            },
        },
        "additionalProperties": True,
    }

    parameters = [
        {
            "name": "command",
            "description": (
                "Read-only diagnostic. Windows: hostname, ipconfig, netstat, "
                "whoami. Unix: cal, date, free, hostname, netstat, ss, "
                "uname, uptime, whoami"
            ),
            "required": True,
            "type": "str",
        },
        {
            "name": "args",
            "description": (
                "Arguments accepted by QZX's command-specific read-only grammar"
            ),
            "required": False,
            "default": [],
            "type": "str",
            "is_variadic": True,
        },
    ]

    examples = [
        {
            "command": "qzx runDiagnosticCommand hostname",
            "description": "Read the local system host name",
        },
        {
            "command": "qzx runDiagnosticCommand whoami",
            "description": "Read the current operating-system user",
        },
        {
            "command": "qzx runDiagnosticCommand uname -a",
            "description": "Read Unix kernel and architecture details",
        },
        {
            "command": "qzx runDiagnosticCommand ipconfig /all",
            "description": "Read the complete Windows network configuration",
        },
        {
            "command": "qzx runDiagnosticCommand netstat -an",
            "description": (
                "List connections numerically without name resolution"
            ),
        },
    ]

    TIMEOUT_SECONDS = 20
    STDOUT_LIMIT_BYTES = 128 * 1024
    STDERR_LIMIT_BYTES = 32 * 1024

    _COMMON_NO_ARGUMENTS = {"hostname", "whoami"}
    _WINDOWS_COMMANDS = {
        "hostname",
        "ipconfig",
        "netstat",
        "whoami",
    }
    _UNIX_COMMANDS = {
        "cal",
        "date",
        "free",
        "hostname",
        "netstat",
        "ss",
        "uname",
        "uptime",
        "whoami",
    }
    _TRUSTED_UNIX_DIRECTORIES = (
        "/usr/bin",
        "/bin",
        "/usr/sbin",
        "/sbin",
    )

    def execute(self, command, *args):
        command_name = str(command).strip().lower()
        argument_list = [str(value) for value in args]
        system_name = "windows" if os.name == "nt" else "unix"
        available = (
            self._WINDOWS_COMMANDS
            if system_name == "windows"
            else self._UNIX_COMMANDS
        )
        command_details = {
            "name": command_name,
            "args": argument_list,
            "platform_family": system_name,
            "shell": False,
            "timeout_seconds": self.TIMEOUT_SECONDS,
            "stdout_limit_bytes": self.STDOUT_LIMIT_BYTES,
            "stderr_limit_bytes": self.STDERR_LIMIT_BYTES,
        }

        if (
            not command_name
            or command_name != os.path.basename(command_name)
            or "/" in command_name
            or "\\" in command_name
            or "\x00" in command_name
        ):
            return self._failure(
                "invalid_command_name",
                "A diagnostic command must be one bare executable name.",
                "Choose a name from the platform-specific allowlist.",
                command_details,
                allowed_commands=sorted(available),
            )

        if command_name not in available:
            return self._failure(
                "command_not_allowlisted",
                "Command '{}' is outside the read-only diagnostic "
                "allowlist.".format(command_name),
                (
                    "Use a dedicated QZX command. Network checks belong to "
                    "checkDns, checkUrlStatus, or getNetworkConfig; paths and "
                    "files belong to the dedicated file commands; processes "
                    "and sessions belong to listProcesses or getCurrentUser."
                ),
                command_details,
                allowed_commands=sorted(available),
            )

        argument_error = self._validate_arguments(
            command_name,
            argument_list,
            system_name,
        )
        if argument_error is not None:
            return self._failure(
                "arguments_not_allowlisted",
                argument_error,
                (
                    "Use only the documented read-only form, or run the "
                    "native utility directly after reviewing its effects."
                ),
                command_details,
            )

        executable = self._trusted_executable(command_name, system_name)
        if executable is None:
            return self._failure(
                "trusted_executable_not_found",
                "No trusted system copy of '{}' was found.".format(
                    command_name
                ),
                (
                    "Install the operating-system diagnostic in a standard "
                    "system directory; QZX does not execute PATH or "
                    "current-directory substitutes."
                ),
                command_details,
            )
        command_details["executable"] = executable
        working_directory = os.path.dirname(executable)
        command_details["working_directory"] = working_directory
        command_details["environment_policy"] = "minimal_trusted"
        command_details["started_at"] = datetime.datetime.now(
            datetime.timezone.utc
        ).isoformat()

        try:
            execution = _run_bounded_process(
                [executable, *argument_list],
                timeout_seconds=self.TIMEOUT_SECONDS,
                stdout_limit=self.STDOUT_LIMIT_BYTES,
                stderr_limit=self.STDERR_LIMIT_BYTES,
                cwd=working_directory,
                env=self._diagnostic_environment(
                    executable,
                    system_name,
                ),
            )
        except OSError as exc:
            return self._failure(
                "command_execution_failed",
                "{}: {}".format(type(exc).__name__, exc),
                "Verify the trusted system executable and retry.",
                command_details,
            )

        execution_details = {
            "command": command_details,
            "exit_code": execution["return_code"],
            "duration_seconds": execution["duration_seconds"],
            "output": {
                "stdout_observed_bytes": execution[
                    "stdout_observed_bytes"
                ],
                "stderr_observed_bytes": execution[
                    "stderr_observed_bytes"
                ],
                "stdout_retained_bytes": execution[
                    "stdout_retained_bytes"
                ],
                "stderr_retained_bytes": execution[
                    "stderr_retained_bytes"
                ],
                "stdout_truncated": execution["stdout_truncated"],
                "stderr_truncated": execution["stderr_truncated"],
            },
        }
        if execution["reader_errors"]:
            execution_details["reader_errors"] = execution["reader_errors"]

        if execution["timed_out"]:
            return {
                "success": False,
                "error_code": "command_timeout",
                "error": (
                    "Diagnostic command exceeded {} seconds.".format(
                        self.TIMEOUT_SECONDS
                    )
                ),
                "message": (
                    "QZX terminated '{}' after its bounded diagnostic "
                    "window. Narrow the requested view and retry."
                ).format(command_name),
                "stdout": execution["stdout"],
                "stderr": execution["stderr"],
                "details": execution_details,
            }

        if execution["reader_errors"]:
            return {
                "success": False,
                "error_code": "output_capture_failed",
                "error": "; ".join(execution["reader_errors"]),
                "message": (
                    "The read-only diagnostic finished, but QZX could not "
                    "capture its complete bounded output. Treat the result as "
                    "incomplete and retry."
                ),
                "stdout": execution["stdout"],
                "stderr": execution["stderr"],
                "details": execution_details,
            }

        success = execution["return_code"] == 0
        return {
            "success": success,
            "message": (
                "Read-only diagnostic '{}' completed successfully in {:.3f} "
                "seconds; {} stdout bytes and {} stderr bytes were observed."
            ).format(
                command_name,
                execution["duration_seconds"],
                execution["stdout_observed_bytes"],
                execution["stderr_observed_bytes"],
            ) if success else (
                "Read-only diagnostic '{}' exited with code {} after {:.3f} "
                "seconds. Review stderr and verify that its options are "
                "supported on this operating system."
            ).format(
                command_name,
                execution["return_code"],
                execution["duration_seconds"],
            ),
            "error": (
                None
                if success
                else execution["stderr"].strip()
                or "The native diagnostic returned a non-zero exit status."
            ),
            "stdout": execution["stdout"],
            "stderr": execution["stderr"],
            "details": execution_details,
        }

    @classmethod
    def _validate_arguments(cls, command_name, arguments, system_name):
        if any("\x00" in argument for argument in arguments):
            return "Arguments cannot contain NUL bytes."
        if command_name in cls._COMMON_NO_ARGUMENTS and arguments:
            return "'{}' accepts no arguments through QZX.".format(
                command_name
            )

        if system_name == "windows":
            return cls._validate_windows_arguments(command_name, arguments)
        return cls._validate_unix_arguments(command_name, arguments)

    @staticmethod
    def _validate_windows_arguments(command_name, arguments):
        if command_name == "ipconfig":
            return (
                None
                if arguments in ([], ["/all"])
                else "ipconfig permits only no arguments or '/all'; release, "
                "renew, flush, and registration operations are blocked."
            )
        if command_name == "netstat":
            valid = (
                bool(arguments)
                and all(
                    re.fullmatch(r"-[aners]+", argument.lower())
                    for argument in arguments
                )
                and any(
                    "n" in argument.lower()[1:]
                    for argument in arguments
                )
            )
            return (
                None
                if valid
                else "Windows netstat requires numeric output (-n) and "
                "accepts only combined read-only flags from -a, -n, -e, -r, "
                "and -s. Name resolution, process attribution, and remote "
                "targets are blocked."
            )
        return None if not arguments else "This diagnostic accepts no arguments."

    @staticmethod
    def _validate_unix_arguments(command_name, arguments):
        if command_name == "date":
            return (
                None
                if not arguments
                else "'{}' is restricted to its local default view.".format(
                    command_name
                )
            )
        if command_name == "uname":
            valid = all(
                re.fullmatch(r"-[asnrvmpio]+", argument)
                for argument in arguments
            )
            return (
                None
                if valid
                else "uname accepts only combined read-only short flags."
            )
        if command_name == "uptime":
            return (
                None
                if not arguments or arguments in (["-p"], ["-s"])
                else "uptime permits only its default view, '-p', or '-s'."
            )
        if command_name == "free":
            valid = all(
                argument in {"-b", "-k", "-m", "-g", "-h", "-t", "-w"}
                for argument in arguments
            )
            return (
                None
                if valid
                else "free accepts only unit and summary display flags."
            )
        if command_name == "netstat":
            valid = (
                bool(arguments)
                and all(
                    re.fullmatch(r"-[anrtul]+", argument)
                    for argument in arguments
                )
                and any("n" in argument[1:] for argument in arguments)
            )
            return (
                None
                if valid
                else "netstat requires numeric output (-n) and accepts only "
                "combined local read-only flags without process attribution."
            )
        if command_name == "ss":
            valid = (
                bool(arguments)
                and all(
                    re.fullmatch(r"-[alntusemoi]+", argument)
                    for argument in arguments
                )
                and any("n" in argument[1:] for argument in arguments)
            )
            return (
                None
                if valid
                else "ss requires numeric output (-n) and accepts only local "
                "network-socket display flags; socket-kill, Unix-domain "
                "paths, filter expressions, name resolution, and process "
                "attribution are blocked."
            )
        if command_name == "cal":
            valid = (
                len(arguments) <= 2
                and all(argument.isdigit() for argument in arguments)
            )
            return (
                None
                if valid
                else "cal accepts at most numeric month and year operands."
            )
        return None if not arguments else "This diagnostic accepts no arguments."

    @classmethod
    def _trusted_executable(cls, command_name, system_name):
        if system_name == "windows":
            system_directory = cls._windows_system_directory()
            if system_directory is None:
                return None
            candidate = os.path.join(
                system_directory,
                command_name + ".exe",
            )
            return candidate if os.path.isfile(candidate) else None

        trusted_roots = {
            os.path.realpath(directory)
            for directory in cls._TRUSTED_UNIX_DIRECTORIES
            if os.path.isdir(directory)
        }
        for directory in cls._TRUSTED_UNIX_DIRECTORIES:
            candidate = os.path.join(directory, command_name)
            if not os.path.isfile(candidate) or not os.access(
                candidate,
                os.X_OK,
            ):
                continue
            resolved = os.path.realpath(candidate)
            if os.path.dirname(resolved) in trusted_roots:
                return resolved
        return None

    @staticmethod
    def _windows_system_directory():
        """Ask Windows for System32 without trusting process environment."""
        try:
            import ctypes

            buffer = ctypes.create_unicode_buffer(32768)
            kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
            get_system_directory = kernel32.GetSystemDirectoryW
            get_system_directory.argtypes = [
                ctypes.POINTER(ctypes.c_wchar),
                ctypes.c_uint,
            ]
            get_system_directory.restype = ctypes.c_uint
            length = get_system_directory(buffer, len(buffer))
        except (AttributeError, OSError):
            return None
        if length == 0 or length >= len(buffer):
            return None
        return buffer.value

    @classmethod
    def _diagnostic_environment(cls, executable, system_name):
        """Provide only non-secret environment needed by trusted utilities."""
        executable_directory = os.path.dirname(executable)
        if system_name == "windows":
            windows_directory = os.path.dirname(executable_directory)
            return {
                "SystemRoot": windows_directory,
                "WINDIR": windows_directory,
                "PATH": executable_directory,
                "PATHEXT": ".COM;.EXE;.BAT;.CMD",
            }

        environment = {
            "PATH": os.pathsep.join(cls._TRUSTED_UNIX_DIRECTORIES),
        }
        for name in ("LANG", "LC_ALL", "LC_CTYPE"):
            value = os.environ.get(name)
            if value and "\x00" not in value and len(value) <= 4096:
                environment[name] = value
        return environment

    @staticmethod
    def _failure(
        error_code,
        error,
        message,
        command_details,
        **extra_details,
    ):
        details = {"command": command_details}
        details.update(extra_details)
        return {
            "success": False,
            "error_code": error_code,
            "error": error,
            "message": message,
            "details": details,
        }
