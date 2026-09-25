"""QZX pytest fixtures that never create private/protected filesystem ACLs."""

from __future__ import annotations

import os
from pathlib import Path
import re
import shutil
import stat
import sys
import tempfile
import uuid

import pytest


_QZX_SAFE_TMP_MARKER = "QZX_INHERITABLE_TMP_V1"


def _remove_test_tree(path: Path) -> None:
    """Remove fixtures without leaving Git's Windows read-only objects behind."""

    def retry_writable(function, target, error):
        if os.name != "nt" or not isinstance(error, PermissionError):
            raise error
        os.chmod(target, stat.S_IWRITE)
        function(target)

    if sys.version_info >= (3, 12):
        shutil.rmtree(path, onexc=retry_writable)
        return

    def retry_writable_legacy(function, target, exc_info):
        retry_writable(function, target, exc_info[1])

    shutil.rmtree(path, onerror=retry_writable_legacy)


def _make_inheritable_directory(parent: Path, prefix: str) -> Path:
    """Create a unique temporary directory without pytest/tempfile mode 0o700."""

    parent = Path(parent)
    for _ in range(100):
        path = parent / f"{prefix}{uuid.uuid4().hex}"
        try:
            # On Windows/Python 3.13, mode=0o700 can create a protected ACL.
            # 0o777 preserves normal inherited ACLs. POSIX still applies umask.
            path.mkdir(mode=0o777)
            return path
        except FileExistsError:
            continue
    raise FileExistsError("Could not allocate a unique QZX test directory.")


@pytest.fixture(scope="session")
def qzx_test_temp_root():
    """Session root with normal inherited permissions and strict cleanup."""

    root = _make_inheritable_directory(
        Path(tempfile.gettempdir()).resolve(),
        f"qzx-pytest-{os.getpid()}-",
    )
    try:
        yield root
    finally:
        if root.exists():
            _remove_test_tree(root)


@pytest.fixture
def tmp_path(request, qzx_test_temp_root):
    """Drop-in tmp_path replacement that never asks pytest for mode=0o700."""

    name = re.sub(r"[^A-Za-z0-9._-]+", "_", request.node.name)[:40] or "test"
    path = _make_inheritable_directory(qzx_test_temp_root, f"{name}-")
    try:
        yield path
    finally:
        if path.exists():
            _remove_test_tree(path)
