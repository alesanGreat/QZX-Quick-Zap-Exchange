import zipfile

import pytest

from qzx.commands.file.copy_file import CopyFileCommand
from qzx.commands.file.move_file import MoveFileCommand


@pytest.mark.parametrize(
    ("command_class", "verb"),
    [
        (CopyFileCommand, "copied"),
        (MoveFileCommand, "moved"),
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
    if command_class is MoveFileCommand:
        assert not source.exists()
    else:
        assert source.read_text(encoding="utf-8") == "new content"


@pytest.mark.parametrize("command_class", [CopyFileCommand, MoveFileCommand])
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
