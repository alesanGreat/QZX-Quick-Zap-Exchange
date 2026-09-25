"""Portable host snapshot collection for getSystemInfo."""

from __future__ import annotations

import os
import platform
import sys

from qzx import __version__


def _platform_details(info, system_name):
    if system_name == "Windows":
        info["windows"] = {
            "edition": platform.win32_edition(),
            "version": list(platform.win32_ver()),
        }
        return
    if system_name == "Linux":
        linux_info = {"libc": list(platform.libc_ver())}
        try:
            linux_info["distribution"] = platform.freedesktop_os_release()
        except OSError:
            pass
        info["linux"] = linux_info
        return
    if system_name == "Darwin":
        info["macos"] = {"version": list(platform.mac_ver())}


def collect_core_info(command, include_environment):
    """Collect the portable, low-cost system information surface."""
    system_name = platform.system()
    machine = platform.machine()
    info = {
        "qzx": {"version": __version__},
        "os": system_name,
        "os_version": platform.version(),
        "os_release": platform.release(),
        "machine": machine,
        "processor": platform.processor() or "unknown",
        "architecture": {
            "bits": 64 if sys.maxsize > 2**32 else 32,
            "machine": machine,
        },
        "platform": sys.platform,
        "python": {
            "version": platform.python_version(),
            "implementation": platform.python_implementation(),
            "compiler": platform.python_compiler(),
            "build": list(platform.python_build()),
        },
        "network": {"hostname": platform.node() or "unknown"},
        "user": {
            "username": command._current_username(),
            "home_directory": os.path.expanduser("~"),
        },
        "environment": {
            "current_directory": os.getcwd(),
            "variables_included": include_environment,
        },
    }
    if include_environment:
        info["environment"]["environment_variables"] = (
            command._get_important_env_vars()
        )
    _platform_details(info, system_name)
    return info
