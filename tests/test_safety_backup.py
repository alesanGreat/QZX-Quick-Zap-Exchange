#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Tests for fail-closed backups around high-risk filesystem mutations."""

from datetime import datetime
import json
import re
import tarfile
import zipfile
from pathlib import Path

import pytest

from qzx.commands.file.delete_path import DeletePathCommand
from qzx.core.command_base import CommandBase
from qzx.core.safety_backup import create_safety_backup


class FileMutationFixtureCommand(CommandBase):
    maturity = "alpha"
    name = "fileMutationFixture"
    description = "Test-only filesystem mutation"
    requires_explicit_approval = True
    backup_target_parameter = "path"
    parameters = [
        {
            "name": "path",
            "description": "File to mutate",
            "required": True,
            "type": "str",
        }
    ]
    examples = []

    def execute(self, path):
        Path(path).write_text("mutated", encoding="utf-8")
        return {"success": True, "message": "File mutated."}


class NonFilesystemMutationFixtureCommand(CommandBase):
    maturity = "alpha"
    name = "nonFilesystemMutationFixture"
    description = "Test-only mutation without a restorable path"
    requires_explicit_approval = True
    parameters = []
    examples = []

    def execute(self):
        return {"success": True, "message": "Operation executed."}


def _configure_backup_directory(monkeypatch, backup_directory):
    monkeypatch.delenv("QZX_SAFETY", raising=False)
    monkeypatch.setenv("QZX_BACKUPS_PATH", str(backup_directory))
    monkeypatch.setenv("QZX_BACKUPS_FORMAT", "ZIP")
    monkeypatch.setenv("QZX_BACKUPS_COMPRESSION", "fastest")


def test_filesystem_mutation_creates_a_restorable_archive(monkeypatch, tmp_path):
    source = tmp_path / "source.txt"
    source.write_text("original", encoding="utf-8")
    backup_directory = tmp_path / "backups"
    _configure_backup_directory(monkeypatch, backup_directory)

    result = FileMutationFixtureCommand().invoke([str(source)])

    assert result["success"] is True
    assert source.read_text(encoding="utf-8") == "mutated"
    backup = result["meta"]["safety_backup"]
    assert backup["status"] == "created"
    archive_path = Path(backup["path"])
    assert archive_path.parent == backup_directory
    assert archive_path.exists()

    with zipfile.ZipFile(archive_path) as archive:
        assert archive.read("source.txt").decode("utf-8") == "original"
        manifest = json.loads(
            archive.read("__qzx_backup_manifest__.json").decode("utf-8")
        )
    assert manifest["command"] == "fileMutationFixture"
    assert manifest["source_path"] == str(source.resolve())


def test_yolo_bypasses_backup_but_is_recorded(monkeypatch, tmp_path):
    source = tmp_path / "source.txt"
    source.write_text("original", encoding="utf-8")
    backup_directory = tmp_path / "backups"
    _configure_backup_directory(monkeypatch, backup_directory)

    result = FileMutationFixtureCommand().invoke([str(source), "--yolo"])

    assert result["success"] is True
    assert result["meta"]["safety_backup"]["status"] == "bypassed"
    assert not backup_directory.exists()


def test_qzx_safety_yolo_bypasses_backup_globally(monkeypatch, tmp_path):
    source = tmp_path / "source.txt"
    source.write_text("original", encoding="utf-8")
    backup_directory = tmp_path / "backups"
    _configure_backup_directory(monkeypatch, backup_directory)
    monkeypatch.setenv("QZX_SAFETY", " yolo ")

    result = FileMutationFixtureCommand().invoke([str(source)])

    assert result["success"] is True
    assert source.read_text(encoding="utf-8") == "mutated"
    assert result["meta"]["safety_backup"] == {
        "status": "bypassed",
        "reason": "QZX_SAFETY=YOLO",
        "command": "fileMutationFixture",
    }
    assert not backup_directory.exists()


def test_qzx_safety_yolo_authorizes_an_operation_without_a_backup_target(
    monkeypatch,
):
    monkeypatch.delenv("QZX_SAFETY", raising=False)
    command = NonFilesystemMutationFixtureCommand()

    blocked = command.invoke([])
    monkeypatch.setenv("QZX_SAFETY", "YOLO")
    bypassed = command.invoke([])

    assert blocked["success"] is False
    assert blocked["error_code"] == "approval_required"
    assert bypassed["success"] is True
    assert bypassed["meta"]["safety_backup"]["reason"] == "QZX_SAFETY=YOLO"


def test_invalid_backup_configuration_fails_closed(monkeypatch, tmp_path):
    source = tmp_path / "source.txt"
    source.write_text("original", encoding="utf-8")
    monkeypatch.delenv("QZX_SAFETY", raising=False)
    monkeypatch.setenv("QZX_BACKUPS_PATH", str(tmp_path / "backups"))
    monkeypatch.setenv("QZX_BACKUPS_FORMAT", "RAR")

    result = FileMutationFixtureCommand().invoke([str(source)])

    assert result["success"] is False
    assert result["error_code"] == "safety_backup_failed"
    assert source.read_text(encoding="utf-8") == "original"


def test_delete_apply_archives_content_before_removal(monkeypatch, tmp_path):
    source = tmp_path / "delete-me.txt"
    source.write_text("recoverable", encoding="utf-8")
    backup_directory = tmp_path / "backups"
    _configure_backup_directory(monkeypatch, backup_directory)

    result = DeletePathCommand().invoke(
        [str(source), "--dry_run", "false", "--apply"]
    )

    assert result["success"] is True
    assert not source.exists()
    archive_path = Path(result["meta"]["safety_backup"]["path"])
    with zipfile.ZipFile(archive_path) as archive:
        assert archive.read("delete-me.txt").decode("utf-8") == "recoverable"


def test_delete_rejects_protected_target_before_backup(monkeypatch, tmp_path):
    backup_directory = tmp_path / "backups"
    _configure_backup_directory(monkeypatch, backup_directory)

    result = DeletePathCommand().invoke(
        [str(Path.cwd()), "--dry_run", "false", "--apply"]
    )

    assert result["success"] is False
    assert result["error_code"] == "protected_path"
    assert not backup_directory.exists()


def test_default_archive_name_and_fastest_zip_compression(tmp_path):
    source = tmp_path / "folder with unsafe ! characters" / "data"
    source.mkdir(parents=True)
    (source / "item.txt").write_text("important", encoding="utf-8")
    backup_directory = tmp_path / "archives"
    fixed_time = datetime(2026, 7, 23, 1, 2, 3)
    sanitized = re.sub(r"[^A-Za-z0-9._-]+", "_", str(source.absolute()))
    sanitized = re.sub(r"_+", "_", sanitized).strip("._-")

    result = create_safety_backup(
        "deletePath",
        source,
        environ={"QZX_BACKUPS_PATH": str(backup_directory)},
        now=fixed_time,
    )

    archive_path = Path(result["path"])
    assert archive_path.name == (
        "QZX-Backup-260723010203-{}-deletePath.zip".format(
            sanitized[-30:]
        )
    )
    assert result["format"] == "ZIP"
    assert result["compression"] == "fastest"
    with zipfile.ZipFile(archive_path) as archive:
        assert archive.read("data/item.txt") == b"important"
        assert (
            archive.getinfo("data/item.txt").compress_type
            == zipfile.ZIP_DEFLATED
        )


@pytest.mark.parametrize(
    ("backup_format", "compression", "extension", "read_mode"),
    [
        ("TAR.GZ", "maximum", ".tar.gz", "r:gz"),
        ("TAR", "store", ".tar", "r:"),
    ],
)
def test_tar_formats_and_compression_are_configurable(
    tmp_path,
    backup_format,
    compression,
    extension,
    read_mode,
):
    source = tmp_path / "source"
    source.mkdir()
    (source / "item.txt").write_text("important", encoding="utf-8")

    result = create_safety_backup(
        "prepareRelease",
        source,
        environ={
            "QZX_BACKUPS_PATH": str(tmp_path / "archives"),
            "QZX_BACKUPS_FORMAT": backup_format,
            "QZX_BACKUPS_COMPRESSION": compression,
        },
        now=datetime(2026, 7, 23, 1, 2, 3),
    )

    assert result["path"].endswith(extension)
    assert result["format"] == backup_format
    with tarfile.open(result["path"], read_mode) as archive:
        archived_file = archive.extractfile("source/item.txt")
        assert archived_file is not None
        assert archived_file.read() == b"important"


def test_backup_destination_inside_source_is_excluded(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    (source / "item.txt").write_text("important", encoding="utf-8")
    backup_directory = source / "QZX-Backups"

    result = create_safety_backup(
        "prepareRelease",
        source,
        environ={"QZX_BACKUPS_PATH": str(backup_directory)},
        now=datetime(2026, 7, 23, 1, 2, 3),
    )

    with zipfile.ZipFile(result["path"]) as archive:
        names = archive.namelist()
    assert "source/item.txt" in names
    assert not any("QZX-Backups" in name for name in names)
