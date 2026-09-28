"""Bounded executable-availability probes shared by scaffold commands."""

from __future__ import annotations

import subprocess
from collections.abc import Callable
from typing import Any

DEFAULT_TOOL_PROBE_TIMEOUT_SECONDS = 5.0


def probe_tool(
    argv: list[str],
    *,
    runner: Callable[..., Any] | None = None,
    timeout: float = DEFAULT_TOOL_PROBE_TIMEOUT_SECONDS,
    accept_nonzero_output: bool = False,
) -> bool:
    """Return whether a tool responds within the probe budget.

    Normal version probes require a zero exit code. Tools such as MSVC cl.exe
    may use a non-zero code for a help/banner invocation, so callers can
    explicitly accept non-empty output for that case.
    """

    if runner is None:
        runner = subprocess.run

    try:
        completed = runner(
            argv,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
            timeout=timeout,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False

    if completed.returncode == 0:
        return True
    if not accept_nonzero_output:
        return False
    return bool(completed.stdout or completed.stderr)
