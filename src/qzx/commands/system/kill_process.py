#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""KillProcess Command - Terminates one explicitly identified process."""

import os
import platform

from qzx.core.command_base import CommandBase


class KillProcessCommand(CommandBase):
    """Terminate one process by PID and verify that it exited."""

    name = "killProcess"
    description = (
        "Terminates one explicitly identified process and verifies that it "
        "exited"
    )
    category = "system"
    requires_explicit_approval = True

    parameters = [
        {
            'name': 'pid',
            'description': 'Positive process ID to terminate',
            'required': True,
            'type': 'int',
        },
        {
            'name': 'force',
            'description': 'Use an immediate forced kill instead of graceful termination',
            'required': False,
            'default': False,
            'type': 'bool',
        },
        {
            'name': 'expected_create_time',
            'description': (
                'Optional process creation timestamp observed immediately '
                'before termination; prevents PID-reuse mistakes'
            ),
            'required': False,
            'default': None,
            'type': 'float',
        },
        {
            'name': 'wait_seconds',
            'description': 'Seconds to wait for verified process exit (0.1 to 60)',
            'required': False,
            'default': 5.0,
            'type': 'float',
        },
    ]

    examples = [
        {
            'command': (
                'qzx killProcess 1234 --expected-create-time 1750000000.25 '
                '--yolo'
            ),
            'description': (
                'Terminate exactly the previously inspected process and '
                'verify that it exits'
            ),
        },
        {
            'command': (
                'qzx killProcess 1234 --force '
                '--dangerously-bypass-approvals-and-sandbox'
            ),
            'description': (
                'Force-kill PID 1234 when graceful termination is not '
                'appropriate'
            ),
        },
    ]

    protected_process_names = {
        "csrss.exe",
        "idle",
        "launchd",
        "lsass.exe",
        "registry",
        "services.exe",
        "smss.exe",
        "system",
        "systemd",
        "wininit.exe",
        "winlogon.exe",
    }

    def execute(
        self,
        pid,
        force=False,
        expected_create_time=None,
        wait_seconds=5.0,
    ):
        """Terminate the requested process and wait for observable exit."""
        try:
            parsed_pid = int(pid)
        except (TypeError, ValueError):
            return self._failure(
                "invalid_pid",
                f"PID must be a positive integer, got {pid!r}.",
                pid=pid,
            )
        if parsed_pid <= 0:
            return self._failure(
                "invalid_pid",
                f"PID must be a positive integer, got {parsed_pid}.",
                pid=parsed_pid,
            )

        force_value = self._parse_bool(force)
        if force_value is None:
            return self._failure(
                "invalid_force",
                f"force must be true or false, got {force!r}.",
                pid=parsed_pid,
            )

        try:
            wait_value = float(wait_seconds)
        except (TypeError, ValueError):
            return self._failure(
                "invalid_wait_seconds",
                f"wait_seconds must be a number from 0.1 to 60, got {wait_seconds!r}.",
                pid=parsed_pid,
            )
        if not 0.1 <= wait_value <= 60:
            return self._failure(
                "invalid_wait_seconds",
                f"wait_seconds must be from 0.1 to 60, got {wait_value}.",
                pid=parsed_pid,
            )

        expected_time = None
        if expected_create_time not in (None, ""):
            try:
                expected_time = float(expected_create_time)
            except (TypeError, ValueError):
                return self._failure(
                    "invalid_expected_create_time",
                    (
                        "expected_create_time must be a positive timestamp, "
                        f"got {expected_create_time!r}."
                    ),
                    pid=parsed_pid,
                )
            if expected_time <= 0:
                return self._failure(
                    "invalid_expected_create_time",
                    "expected_create_time must be a positive timestamp.",
                    pid=parsed_pid,
                )

        try:
            import psutil
        except ImportError:
            return self._failure(
                "missing_dependency",
                (
                    "killProcess requires psutil. Install QZX with its normal "
                    "runtime dependencies before retrying."
                ),
                pid=parsed_pid,
            )

        try:
            process = psutil.Process(parsed_pid)
            create_time = process.create_time()
            process_name = process.name()
        except psutil.NoSuchProcess:
            return self._failure(
                "process_not_found",
                f"Process PID {parsed_pid} does not exist or already exited.",
                pid=parsed_pid,
            )
        except psutil.AccessDenied:
            return self._failure(
                "process_inspection_denied",
                (
                    f"QZX could not inspect PID {parsed_pid}. Run with the "
                    "operating-system privileges required for that process."
                ),
                pid=parsed_pid,
            )

        protected_reason = self._protected_reason(
            process,
            process_name,
            psutil,
        )
        if protected_reason is not None:
            return self._failure(
                "protected_process",
                protected_reason,
                pid=parsed_pid,
                name=process_name,
                create_time=create_time,
            )

        if (
            expected_time is not None
            and abs(create_time - expected_time) > 0.001
        ):
            return self._failure(
                "process_identity_changed",
                (
                    f"PID {parsed_pid} now has creation time {create_time}, "
                    f"not the expected {expected_time}. No signal was sent."
                ),
                pid=parsed_pid,
                name=process_name,
                expected_create_time=expected_time,
                observed_create_time=create_time,
            )

        process_details = self._process_details(
            process,
            process_name,
            create_time,
            force_value,
            platform.system(),
            psutil,
        )

        try:
            if force_value:
                process.kill()
                method = "kill"
            else:
                process.terminate()
                method = "terminate"
            exit_code = process.wait(timeout=wait_value)
        except psutil.NoSuchProcess:
            method = "kill" if force_value else "terminate"
            exit_code = None
        except psutil.TimeoutExpired:
            return {
                "success": False,
                "error_code": "process_still_running",
                "error": (
                    f"PID {parsed_pid} did not exit within "
                    f"{wait_value:.3g} seconds."
                ),
                "message": (
                    f"QZX sent {('kill' if force_value else 'terminate')} to "
                    f"PID {parsed_pid}, but could not verify exit within "
                    f"{wait_value:.3g} seconds. Inspect it again before "
                    "deciding whether to force termination."
                ),
                "process": process_details,
                "termination": {
                    "requested_method": "kill" if force_value else "terminate",
                    "wait_seconds": wait_value,
                    "verified_exited": False,
                },
            }
        except psutil.AccessDenied:
            return self._failure(
                "termination_denied",
                (
                    f"Access was denied while terminating PID {parsed_pid}. "
                    "Use the operating-system privileges required for that "
                    "process."
                ),
                **process_details,
            )
        except Exception as exc:
            return self._failure(
                "termination_failed",
                (
                    f"Could not terminate PID {parsed_pid}: "
                    f"{type(exc).__name__}: {exc}"
                ),
                **process_details,
            )

        return {
            "success": True,
            "status": "terminated",
            "process": process_details,
            "termination": {
                "method": method,
                "wait_seconds": wait_value,
                "verified_exited": True,
                "exit_code": exit_code,
            },
            "message": (
                f"Process {parsed_pid} ({process_name}) was terminated with "
                f"{method}; QZX verified that it exited."
            ),
        }

    def _protected_reason(self, process, process_name, psutil_module):
        pid = process.pid
        if pid in {0, 1, os.getpid(), os.getppid()}:
            return (
                f"Refusing to terminate protected PID {pid}: it is a system "
                "process, QZX itself, or QZX's invoking parent."
            )
        try:
            ancestor_pids = {parent.pid for parent in psutil_module.Process().parents()}
        except (psutil_module.Error, OSError):
            ancestor_pids = set()
        if pid in ancestor_pids:
            return (
                f"Refusing to terminate PID {pid}: it is an ancestor of the "
                "running QZX process."
            )
        if str(process_name).strip().lower() in self.protected_process_names:
            return (
                f"Refusing to terminate protected process '{process_name}' "
                f"(PID {pid})."
            )
        return None

    def _process_details(
        self,
        process,
        process_name,
        create_time,
        force,
        os_name,
        psutil_module,
    ):
        details = {
            "pid": process.pid,
            "name": process_name,
            "create_time": create_time,
            "forced": force,
            "os": os_name,
            "user": None,
            "executable": None,
            "command": [],
        }
        try:
            details["user"] = process.username()
            details["executable"] = process.exe()
            details["command"] = process.cmdline()
            memory = process.memory_info()
            details["memory"] = {
                "rss_bytes": memory.rss,
                "rss_formatted": self._format_bytes(memory.rss),
            }
        except (
            psutil_module.AccessDenied,
            psutil_module.NoSuchProcess,
            psutil_module.ZombieProcess,
        ):
            pass
        return details

    @staticmethod
    def _failure(error_code, message, **details):
        return {
            "success": False,
            "error_code": error_code,
            "error": message,
            "message": message,
            "details": details,
        }
