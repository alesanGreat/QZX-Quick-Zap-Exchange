"""Coarse local interaction evidence for QZX usage telemetry."""

from __future__ import annotations

import ctypes
import os
import sys


RECENT_INPUT_SECONDS = 300


def _stream_is_tty(stream):
    try:
        return bool(stream.isatty())
    except (AttributeError, OSError, ValueError):
        return False


def _foreground_terminal():
    """Return True/False when foreground ownership is observable, else None."""
    if os.name == "nt":
        try:
            user32 = ctypes.windll.user32
            kernel32 = ctypes.windll.kernel32
            console = kernel32.GetConsoleWindow()
            if not console:
                return None
            foreground = user32.GetForegroundWindow()
            return bool(foreground and foreground == console)
        except Exception:
            return None
    try:
        for stream in (sys.stdin, sys.stdout, sys.stderr):
            fileno = stream.fileno()
            if os.isatty(fileno):
                return os.tcgetpgrp(fileno) == os.getpgrp()
    except (AttributeError, OSError, ValueError):
        return None
    return None


def _recent_os_input():
    """Return coarse recent-input evidence on Windows; never input data."""
    if os.name != "nt":
        return None
    try:
        class LASTINPUTINFO(ctypes.Structure):
            _fields_ = [
                ("cbSize", ctypes.c_uint),
                ("dwTime", ctypes.c_uint),
            ]

        info = LASTINPUTINFO()
        info.cbSize = ctypes.sizeof(info)
        if not ctypes.windll.user32.GetLastInputInfo(ctypes.byref(info)):
            return None
        now = ctypes.windll.kernel32.GetTickCount()
        idle_ms = (int(now) - int(info.dwTime)) & 0xFFFFFFFF
        return idle_ms <= RECENT_INPUT_SECONDS * 1000
    except Exception:
        return None


def interaction_snapshot():
    """Return only coarse TTY, foreground, and recent-input booleans."""
    stdin_tty = _stream_is_tty(sys.stdin)
    stdout_tty = _stream_is_tty(sys.stdout)
    stderr_tty = _stream_is_tty(sys.stderr)
    return {
        "interactive": bool(stdin_tty and (stdout_tty or stderr_tty)),
        "foreground": _foreground_terminal(),
        "recent_input": _recent_os_input(),
    }
