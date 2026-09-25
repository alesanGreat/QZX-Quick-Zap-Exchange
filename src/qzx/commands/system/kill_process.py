#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""KillProcess Command - Terminates one explicitly identified process."""

import os

from qzx.commands.system._kill_process_workflow import execute_kill_process
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
        return execute_kill_process(
            self,
            pid,
            force,
            expected_create_time,
            wait_seconds,
        )

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
