import zipfile
from pathlib import Path

import pytest

from qzx.commands.file.copy_path import CopyPathCommand
from qzx.commands.file.move_path import MovePathCommand


@pytest.mark.parametrize(
    ("command_class", "verb"),
    [
        (CopyPathCommand, "copied"),
        (MovePathCommand, "moved"),
    ],
)
def test_force_replacement_backs_up_destination(
    command_class,
    verb,
    tmp_path,
    monkeypatch,
):
    source = tmp_path / "source.txt"
    destination = tmp_path / "destination.txt"
    backups = tmp_path / "backups"
    source.write_text("new content", encoding="utf-8")
    destination.write_text("original content", encoding="utf-8")
    monkeypatch.setenv("QZX_BACKUPS_PATH", str(backups))

    result = command_class().invoke(
        [str(source), str(destination), "--force"]
    )

    assert result["success"] is True
    assert verb in result["message"]
    assert destination.read_text(encoding="utf-8") == "new content"
    backup = result["meta"]["safety_backup"]
    assert backup["status"] == "created"
    with zipfile.ZipFile(backup["path"]) as archive:
        assert archive.read("destination.txt").decode("utf-8") == (
            "original content"
        )
    if command_class is MovePathCommand:
        assert not source.exists()
    else:
        assert source.read_text(encoding="utf-8") == "new content"


@pytest.mark.parametrize("command_class", [CopyPathCommand, MovePathCommand])
def test_force_rejects_same_source_and_destination_without_backup(
    command_class,
    tmp_path,
    monkeypatch,
):
    source = tmp_path / "same.txt"
    backups = tmp_path / "backups"
    source.write_text("keep me", encoding="utf-8")
    monkeypatch.setenv("QZX_BACKUPS_PATH", str(backups))

    result = command_class().invoke([str(source), str(source), "--force"])

    assert result["success"] is False
    assert result["error_code"] == "source_equals_destination"
    assert source.read_text(encoding="utf-8") == "keep me"
    assert not backups.exists()


def test_move_directory_moves_complete_tree(tmp_path):
    source = tmp_path / "source"
    destination = tmp_path / "destination"
    (source / "nested").mkdir(parents=True)
    (source / "nested" / "child.txt").write_text(
        "child",
        encoding="utf-8",
    )

    result = MovePathCommand().execute(str(source), str(destination))

    assert result["success"] is True
    assert result["details"]["verification"] == (
        "same-filesystem rename committed"
    )
    assert not source.exists()
    assert (destination / "nested" / "child.txt").read_text(
        encoding="utf-8"
    ) == "child"


@pytest.mark.parametrize("command_class", [CopyPathCommand, MovePathCommand])
def test_force_rejects_destination_that_contains_source_before_backup(
    command_class,
    tmp_path,
    monkeypatch,
):
    destination = tmp_path / "workspace"
    source = destination / "source.txt"
    backups = tmp_path / "backups"
    destination.mkdir()
    source.write_text("must survive", encoding="utf-8")
    monkeypatch.setenv("QZX_BACKUPS_PATH", str(backups))

    result = command_class().invoke(
        [str(source), str(destination), "--force"]
    )

    assert result["success"] is False
    assert result["error_code"] == "source_within_destination"
    assert source.read_text(encoding="utf-8") == "must survive"
    assert not backups.exists()


@pytest.mark.parametrize("command_class", [CopyPathCommand, MovePathCommand])
def test_destination_inside_source_is_rejected_before_parent_creation(
    command_class,
    tmp_path,
):
    source = tmp_path / "source"
    source.mkdir()
    (source / "keep.txt").write_text("keep", encoding="utf-8")
    destination = source / "nested" / "destination"

    result = command_class().execute(str(source), str(destination))

    assert result["success"] is False
    assert result["error_code"] == "destination_within_source"
    assert (source / "keep.txt").read_text(encoding="utf-8") == "keep"
    assert not destination.parent.exists()


def test_regular_file_copy_is_verified_with_sha256(tmp_path):
    source = tmp_path / "source.bin"
    destination = tmp_path / "destination.bin"
    source.write_bytes(bytes(range(256)) * 8)

    result = CopyPathCommand().execute(str(source), str(destination))

    assert result["success"] is True
    assert result["details"]["verification"] == "size and SHA-256 matched"
    assert len(result["details"]["sha256"]) == 64
    assert source.read_bytes() == destination.read_bytes()


@pytest.mark.parametrize("command_class", [CopyPathCommand, MovePathCommand])
def test_filesystem_root_is_protected(command_class, tmp_path):
    filesystem_root = Path(tmp_path.anchor)
    destination = tmp_path / "destination"

    result = command_class().execute(
        str(filesystem_root),
        str(destination),
    )

    assert result["success"] is False
    assert result["error_code"] == "filesystem_root_protected"
    assert not destination.exists()


def test_move_rejects_invalid_force_boolean_without_mutation(tmp_path):
    source = tmp_path / "source.txt"
    destination = tmp_path / "destination.txt"
    source.write_text("keep", encoding="utf-8")

    result = MovePathCommand().execute(
        str(source),
        str(destination),
        force="sometimes",
    )

    assert result["success"] is False
    assert result["error_code"] == "invalid_boolean"
    assert source.read_text(encoding="utf-8") == "keep"
    assert not destination.exists()
