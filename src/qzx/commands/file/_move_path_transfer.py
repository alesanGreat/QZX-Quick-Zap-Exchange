"""Low-level movePath transfer and recovery helpers."""

from __future__ import annotations

import os
import shutil
import stat
import uuid
from pathlib import Path

from qzx.core.path_operation_utils import file_sha256


def perform_move(source, destination, same_filesystem):
    """Commit a same-filesystem rename or verified staged file/link move."""
    if same_filesystem:
        return _rename_move(source, destination)
    return _cross_filesystem_move(source, destination)


def _rename_move(source, destination):
    try:
        os.rename(source, destination)
    except OSError as exc:
        return {
            "success": False,
            "error": f"{type(exc).__name__}: {exc}",
            "verification": "not_completed",
        }
    return {
        "success": True,
        "verification": "same-filesystem rename committed",
    }


def _cross_filesystem_move(source, destination):
    temporary = destination.with_name(
        f".{destination.name}.qzx-move-stage-{uuid.uuid4().hex}"
    )
    try:
        verification = _stage_source(source, temporary)
        os.replace(temporary, destination)
        os.unlink(source)
        return {
            "success": True,
            "verification": verification,
        }
    except OSError as exc:
        return {
            "success": False,
            "error": f"{type(exc).__name__}: {exc}",
            "verification": "failed",
            "temporary_path": str(temporary),
        }


def _stage_source(source, temporary):
    source_mode = os.lstat(source).st_mode
    if stat.S_ISLNK(source_mode):
        link_target = os.readlink(source)
        os.symlink(
            link_target,
            temporary,
            target_is_directory=os.path.isdir(source),
        )
        if os.readlink(temporary) != link_target:
            raise OSError("staged symbolic-link target did not match")
        return "symbolic-link target matched"

    source_size = os.path.getsize(source)
    source_digest = file_sha256(source)
    shutil.copy2(source, temporary)
    if (
        os.path.getsize(temporary) != source_size
        or file_sha256(temporary) != source_digest
    ):
        raise OSError("staged file failed size or SHA-256 verification")
    return "size and SHA-256 matched"


def recover_failed_replacement(
    command,
    source,
    destination,
    previous,
    temporary,
):
    """Clean staging and restore a previously staged destination."""
    errors = []
    _cleanup_temporary(command, temporary, errors)
    _cleanup_uncommitted_destination(
        command,
        source,
        destination,
        errors,
    )
    restored = _restore_previous_destination(
        previous,
        destination,
        errors,
    )
    source_preserved = os.path.lexists(source)
    success = restored and source_preserved and not errors
    return {
        "success": success,
        "source_preserved": source_preserved,
        "previous_destination_restored": restored,
        "errors": errors,
        "message": (
            "The source and previous destination were preserved."
            if success
            else "Manual recovery may be required; inspect recovery details."
        ),
    }


def _cleanup_temporary(command, temporary, errors):
    temporary_path = Path(temporary) if temporary else None
    if temporary_path is None or not os.path.lexists(temporary_path):
        return
    try:
        command._remove_existing_destination(temporary_path)
    except OSError as exc:
        errors.append(
            f"could not remove temporary entry '{temporary_path}': {exc}"
        )


def _cleanup_uncommitted_destination(
    command,
    source,
    destination,
    errors,
):
    if not (
        os.path.lexists(destination)
        and os.path.lexists(source)
    ):
        return
    try:
        command._remove_existing_destination(destination)
    except OSError as exc:
        errors.append(f"could not remove uncommitted destination: {exc}")


def _restore_previous_destination(previous, destination, errors):
    if previous is None:
        return True
    if not os.path.lexists(destination):
        try:
            os.rename(previous, destination)
            return True
        except OSError as exc:
            errors.append(f"could not restore previous destination: {exc}")
            return False
    errors.append(
        (
            f"previous destination remains staged at '{previous}' "
            "because the destination path is occupied"
        )
    )
    return False
