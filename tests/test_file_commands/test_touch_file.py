"""Tests for the touchFile command."""

from qzx.commands.file.touch_file import TouchFileCommand


def test_touch_file_writes_utf8_content_and_creates_parent_directories(tmp_path):
    file_path = tmp_path / "nested" / "greeting.txt"
    content = "QZX — café — 你好"

    result = TouchFileCommand().execute(
        str(file_path),
        create_dirs="true",
        content=content,
    )

    assert result["success"] is True
    assert result["created"] is True
    assert result["existed"] is False
    assert result["content_added"] is True
    assert result["size"] == len(content.encode("utf-8"))
    assert file_path.read_bytes() == content.encode("utf-8")


def test_touch_file_creates_an_empty_file(tmp_path):
    file_path = tmp_path / "empty.txt"

    result = TouchFileCommand().execute(str(file_path))

    assert result["success"] is True
    assert result["created"] is True
    assert result["content_added"] is False
    assert result["size"] == 0
    assert file_path.read_bytes() == b""
