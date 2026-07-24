#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""One-time, local-only presentation state for the QZX attribution."""

import os
import platform
from pathlib import Path

from qzx.identity import product_attribution


_MARKER_FILENAME = "attribution-shown-v1"


def state_directory(environ=None):
    """Return the platform-standard directory for non-sensitive QZX state."""
    environ = os.environ if environ is None else environ
    override = environ.get("QZX_STATE_DIR")
    if override:
        return Path(override).expanduser()

    system = platform.system().lower()
    if system == "windows":
        base = environ.get("LOCALAPPDATA")
        if base:
            return Path(base) / "qzx"
    elif system == "darwin":
        return Path.home() / "Library" / "Application Support" / "qzx"

    xdg_state_home = environ.get("XDG_STATE_HOME")
    if xdg_state_home:
        return Path(xdg_state_home) / "qzx"
    return Path.home() / ".local" / "state" / "qzx"


def claim_first_run_attribution(environ=None, directory=None):
    """
    Atomically claim the one-time attribution presentation.

    When local state cannot be persisted, returning ``True`` favors showing the
    attribution instead of silently losing the required first-run disclosure.
    """
    marker_directory = (
        Path(directory)
        if directory is not None
        else state_directory(environ)
    )
    marker = marker_directory / _MARKER_FILENAME
    try:
        marker_directory.mkdir(parents=True, exist_ok=True)
        with marker.open("x", encoding="utf-8", newline="\n") as handle:
            handle.write(product_attribution())
            handle.write("\n")
        try:
            os.chmod(marker, 0o600)
        except OSError:
            pass
        return True
    except FileExistsError:
        return False
    except OSError:
        return True
