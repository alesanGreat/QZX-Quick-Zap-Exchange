"""Fresh canonical path identities without redundant display normalization."""

from __future__ import annotations

import os
from pathlib import Path

try:
    from nt import _getfinalpathname as _get_final_path
except ImportError:  # POSIX and Python implementations without the Windows hook.
    _get_final_path = None


def _canonical_path_key(path: str | os.PathLike[str], final_path_resolver) -> str:
    """Resolve one identity with an explicit native boundary for deterministic tests."""
    raw = os.fspath(path)
    if not isinstance(raw, str):
        raise TypeError("canonical_path_key requires a text path")
    if final_path_resolver is not None:
        try:
            return os.path.normcase(final_path_resolver(os.path.abspath(raw)))
        except (OSError, ValueError):
            pass
    return os.path.normcase(str(Path(raw).resolve()))


def canonical_path_key(path: str | os.PathLike[str]) -> str:
    """Resolve links on every call; return an opaque key, not a display path.

    CPython's Windows realpath resolves an existing path once, then opens it
    again to check whether the extended prefix can be removed for display.
    Identity comparisons can retain that prefix and avoid the second open.
    Missing paths, access errors and unsupported runtimes use pathlib's full
    portable behavior. No filesystem identities or analysis results are cached.
    """
    return _canonical_path_key(path, _get_final_path)
