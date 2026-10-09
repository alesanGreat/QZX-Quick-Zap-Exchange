"""Current-user snapshot assembly for getCurrentUser."""

from __future__ import annotations

import getpass
import os

import psutil


def _normalized_username(username):
    if not username:
        return ""
    return (
        str(username)
        .replace("/", "\\")
        .rsplit("\\", 1)[-1]
        .casefold()
    )


def _username():
    try:
        return getpass.getuser()
    except Exception:
        try:
            return os.getlogin()
        except Exception:
            return "Unknown"


def _environment():
    values = {
        "USER": os.environ.get("USER"),
        "USERNAME": os.environ.get("USERNAME"),
        "USERPROFILE": os.environ.get("USERPROFILE"),
        "HOME": os.environ.get("HOME"),
        "LOGNAME": os.environ.get("LOGNAME"),
    }
    return {key: value for key, value in values.items() if value is not None}


def _process_rss(process):
    try:
        return process.memory_info().rss
    except psutil.Error:
        return 0


def _user_processes(command, result):
    try:
        current_process = psutil.Process()
        if hasattr(current_process, "username"):
            result["user_id"] = current_process.username()
        usernames = {
            _normalized_username(result["username"]),
            _normalized_username(result.get("user_id")),
        }
        usernames.discard("")
        # Filter by owner first: reading memory_info for every process is
        # slow on Windows because protected processes fall back to a full
        # system snapshot per call. The user's own processes are cheap.
        processes = [
            process
            for process in psutil.process_iter(["username"])
            if hasattr(process, "info")
            and _normalized_username(process.info.get("username")) in usernames
        ]
        total_memory = sum(_process_rss(process) for process in processes)
        result["processes"] = {
            "count": len(processes),
            "total_memory_usage": total_memory,
            "total_memory_usage_readable": command._format_bytes(total_memory),
        }
    except Exception:
        pass


def _message(result):
    username = result.get("username", "Unknown")
    home = result.get("home_directory", "Unknown")
    shell = result.get("shell", "Unknown shell")
    count = result.get("processes", {}).get("count", 0)
    memory = result.get("processes", {}).get(
        "total_memory_usage_readable", "Unknown"
    )
    message = f"Current user: {username}. Home directory: {home}. Shell: {shell}."
    if count > 0:
        message += f" User has {count} running processes using {memory} of memory."
    return message


def execute_current_user(command):
    """Return one structured snapshot of the active user."""
    try:
        result = {
            "username": _username(),
            "home_directory": os.path.expanduser("~"),
            "environment_variables": _environment(),
            "processes": {},
        }
        shell = os.environ.get("SHELL", os.environ.get("COMSPEC"))
        if shell:
            result["shell"] = shell
        _user_processes(command, result)
        try:
            result["current_directory"] = os.getcwd()
        except Exception:
            pass
        result["success"] = True
        result["message"] = _message(result)
        return result
    except Exception as exc:
        return {
            "success": False,
            "error": f"Error getting current user information: {str(exc)}",
            "message": f"Failed to retrieve current user information: {str(exc)}",
        }
