"""Distinguish path aliases from locally available, non-surrogate reparse points."""

from __future__ import annotations

import stat


# The N bit marks a reparse point that names another filesystem entity.
# A cloud placeholder can have FILE_ATTRIBUTE_REPARSE_POINT without this bit.
# https://learn.microsoft.com/en-us/windows/win32/fileio/reparse-point-tags
_NAME_SURROGATE_BIT = 0x20000000


def is_path_reference(info) -> bool:
    """Recognize symbolic links and Windows junctions using an lstat-style result."""
    return stat.S_ISLNK(info.st_mode) or bool(
        getattr(info, "st_reparse_tag", 0) & _NAME_SURROGATE_BIT
    )
