"""Filesystem mutation workflow for touchFile."""

from __future__ import annotations

import os


_TRUE_VALUES = {"true", "yes", "y", "1"}


def _boolean(value):
    if isinstance(value, str):
        return value.lower() in _TRUE_VALUES
    return bool(value)


def _message(path, existed, content):
    if existed:
        return (
            f"File '{path}' updated with new content"
            if content
            else f"File '{path}' timestamp updated"
        )
    return (
        f"File '{path}' created with content"
        if content
        else f"Empty file '{path}' created"
    )


def execute_touch_file(path, create_dirs=False, content=""):
    """Create a file or update its timestamp/content."""
    try:
        create_dirs = _boolean(create_dirs)
        directory = os.path.dirname(path)
        if directory and create_dirs and not os.path.exists(directory):
            os.makedirs(directory)
        existed = os.path.exists(path)
        mode = "w" if content else "a"
        with open(path, mode, encoding="utf-8") as handle:
            if content:
                handle.write(content)
        result = {
            "path": os.path.abspath(path),
            "success": True,
            "existed": existed,
            "created": not existed,
            "size": os.path.getsize(path),
            "mode": oct(os.stat(path).st_mode)[-3:],
            "content_added": bool(content),
        }
        result["message"] = _message(path, existed, content)
        return result
    except Exception as exc:
        return {"success": False, "path": path, "error": str(exc)}
