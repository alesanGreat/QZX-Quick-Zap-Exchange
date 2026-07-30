#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""One-time, local-only presentation state for the QZX attribution."""

import os
import sys

from qzx._build_info import ATTRIBUTION


_MARKER_FILENAME = "attribution-shown-v1"


def state_directory(environ=None):
    """Return the platform-standard directory for non-sensitive QZX state."""
    environ = os.environ if environ is None else environ
    override = environ.get("QZX_STATE_DIR")
    if override:
        return os.path.expanduser(override)

    if os.name == "nt" and environ.get("LOCALAPPDATA"):
        return os.path.join(environ["LOCALAPPDATA"], "qzx")
    if sys.platform == "darwin":
        return os.path.expanduser(
            os.path.join("~", "Library", "Application Support", "qzx")
        )

    base = environ.get("XDG_STATE_HOME")
    if base:
        return os.path.join(base, "qzx")
    return os.path.expanduser(os.path.join("~", ".local", "state", "qzx"))


def claim_first_run_attribution(environ=None, directory=None):
    """
    Atomically claim the one-time attribution presentation.

    When local state cannot be persisted, returning ``True`` favors showing the
    attribution instead of silently losing the required first-run disclosure.
    """
    environ = os.environ if environ is None else environ
    marker_directory = (
        os.fspath(directory)
        if directory is not None
        else state_directory(environ)
    )
    marker = os.path.join(marker_directory, _MARKER_FILENAME)
    try:
        os.makedirs(marker_directory, exist_ok=True)
        descriptor = os.open(
            marker,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL,
            0o600,
        )
        try:
            pending = (ATTRIBUTION + "\n").encode("utf-8")
            while pending:
                pending = pending[os.write(descriptor, pending):]
        finally:
            os.close(descriptor)
        try:
            os.chmod(marker, 0o600)
        except OSError:
            pass
        return True
    except FileExistsError:
        return False
    except OSError:
        return True
