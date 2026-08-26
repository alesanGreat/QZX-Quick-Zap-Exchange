"""Stable UTF-8 terminal boundaries for QZX command-line entry points."""

from __future__ import annotations

import sys
from typing import TextIO


def _configure_stream(stream: TextIO | None) -> None:
    """Prefer strict UTF-8 when the active text stream supports reconfiguration."""
    if stream is None:
        return
    reconfigure = getattr(stream, "reconfigure", None)
    if not callable(reconfigure):
        return
    try:
        reconfigure(encoding="utf-8", errors="strict")
    except (AttributeError, OSError, ValueError):
        # Embedded hosts and test capture streams may intentionally be immutable.
        # QZX's JSON writer still has its binary UTF-8 fallback in those cases.
        return


def configure_utf8_stdio() -> None:
    """Make human and structured CLI output reproducible across host code pages."""
    _configure_stream(sys.stdout)
    _configure_stream(sys.stderr)
