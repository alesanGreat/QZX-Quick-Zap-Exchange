#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Normalize release-only metadata in QZX source-distribution archives."""

from __future__ import annotations

import os
import tarfile
import tempfile
from pathlib import Path


def normalize_sdist_launcher_mode(archive_path: Path) -> bool:
    """Store the top-level qzx.sh launcher as 0755 in a .tar.gz sdist."""
    archive_path = Path(archive_path)
    if not archive_path.name.endswith(".tar.gz"):
        return False

    temporary_path = None
    try:
        with tarfile.open(archive_path, "r:gz") as source:
            members = source.getmembers()
            launchers = [
                member
                for member in members
                if member.name.count("/") == 1
                and member.name.endswith("/qzx.sh")
                and member.isfile()
            ]
            if len(launchers) != 1:
                raise RuntimeError(
                    f"{archive_path.name} must contain exactly one top-level qzx.sh launcher."
                )
            if launchers[0].mode & 0o777 == 0o755:
                return False

            descriptor, temporary_name = tempfile.mkstemp(
                dir=archive_path.parent,
                prefix=f".{archive_path.name}.",
                suffix=".tmp",
            )
            os.close(descriptor)
            temporary_path = Path(temporary_name)
            with tarfile.open(temporary_path, "w:gz") as target:
                for member in members:
                    if member.name == launchers[0].name:
                        member.mode = 0o755
                    payload = source.extractfile(member) if member.isfile() else None
                    try:
                        target.addfile(member, payload)
                    finally:
                        if payload is not None:
                            payload.close()

        # Windows does not allow replacing an archive while tarfile still has it open.
        os.replace(temporary_path, archive_path)
        return True
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)
