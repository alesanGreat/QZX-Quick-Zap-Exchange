"""Tests for the focused, structured findFiles contract."""

import os

import pytest

from qzx.commands.file.find_files import FindFilesCommand


@pytest.fixture
def command():
    return FindFilesCommand()


def test_find_files_without_recursion_returns_rich_metadata(command, tmp_path):
    (tmp_path / "test.txt").write_text("root", encoding="utf-8")
    nested = tmp_path / "nested"
    nested.mkdir()
    (nested / "nested.txt").write_text("nested", encoding="utf-8")

    result = command.execute(
        search_path=str(tmp_path),
        pattern="*.txt",
        recursive=False,
    )

    assert result["success"] is True
    assert result["recursive"] == "none"
    assert result["matched_count"] == 1
    assert result["count"] == 1
    assert result["results"][0]["name"] == "test.txt"
    assert result["results"][0]["relative_path"] == "test.txt"
    assert result["results"][0]["size_bytes"] == 4
    assert result["results"][0]["depth"] == 0
    assert result["warnings"] == []


def test_find_files_recurses_and_skips_excluded_directories(command, tmp_path):
    (tmp_path / "root.py").write_text("root", encoding="utf-8")
    included = tmp_path / "src"
    included.mkdir()
    (included / "included.py").write_text("included", encoding="utf-8")
    excluded = tmp_path / ".venv"
    excluded.mkdir()
    (excluded / "excluded.py").write_text("excluded", encoding="utf-8")

    result = command.execute(
        search_path=str(tmp_path),
        pattern="*.py",
        recursive="-r",
        exclude_dirs=".venv",
    )

    assert result["success"] is True
    assert result["recursive"] == "unlimited"
    assert {entry["name"] for entry in result["results"]} == {
        "root.py",
        "included.py",
    }
    nested_result = next(
        entry for entry in result["results"] if entry["name"] == "included.py"
    )
    assert nested_result["depth"] == 1


def test_find_files_filters_sorts_and_limits_after_matching(command, tmp_path):
    (tmp_path / "small.bin").write_bytes(b"12")
    (tmp_path / "medium.bin").write_bytes(b"12345")
    (tmp_path / "large.bin").write_bytes(b"123456789")

    result = command.execute(
        search_path=str(tmp_path),
        pattern="*.bin",
        min_size="2B",
        max_size="10B",
        sort_by="size",
        descending="true",
        limit="2",
    )

    assert result["success"] is True
    assert result["matched_count"] == 3
    assert result["matched_size_bytes"] == 16
    assert result["count"] == 2
    assert result["total_size_bytes"] == 14
    assert result["truncated"] is True
    assert [entry["name"] for entry in result["results"]] == [
        "large.bin",
        "medium.bin",
    ]
    assert result["sort"] == {"by": "size", "descending": True}


def test_find_files_filters_by_modification_window(command, tmp_path):
    old_file = tmp_path / "old.txt"
    old_file.write_text("old", encoding="utf-8")
    os.utime(old_file, (946684800, 946684800))
    (tmp_path / "today.txt").write_text("today", encoding="utf-8")

    result = command.execute(
        search_path=str(tmp_path),
        pattern="*.txt",
        modified_after="today",
    )

    assert result["success"] is True
    assert [entry["name"] for entry in result["results"]] == ["today.txt"]


@pytest.mark.parametrize(
    ("arguments", "error_code"),
    [
        ({"recursive": "sometimes"}, "invalid_parameter"),
        ({"min_size": "-1MB"}, "invalid_parameter"),
        ({"max_size": "huge"}, "invalid_parameter"),
        ({"modified_after": "30/07/2026"}, "invalid_parameter"),
        ({"descending": "perhaps"}, "invalid_parameter"),
        ({"limit": 0}, "invalid_parameter"),
        ({"sort_by": "date"}, "invalid_sort"),
        (
            {"min_size": "2MiB", "max_size": "1MiB"},
            "invalid_size_range",
        ),
        (
            {
                "modified_after": "2026-07-30",
                "modified_before": "2026-07-01",
            },
            "invalid_date_range",
        ),
    ],
)
def test_find_files_rejects_invalid_filters(
    command, tmp_path, arguments, error_code
):
    result = command.execute(search_path=str(tmp_path), **arguments)

    assert result["success"] is False
    assert result["error_code"] == error_code
    assert result["message"]
    assert result["error"] == result["message"]


def test_find_files_reports_missing_directory(command, tmp_path):
    missing = tmp_path / "missing"

    result = command.execute(search_path=str(missing))

    assert result["success"] is False
    assert result["error_code"] == "path_not_found"
    assert str(missing) in result["message"]


def test_format_bytes_uses_unambiguous_binary_units(command):
    assert command._format_bytes(0) == "0.00 B"
    assert command._format_bytes(1023) == "1023.00 B"
    assert command._format_bytes(1024) == "1.00 KiB"
    assert command._format_bytes(1024**2) == "1.00 MiB"
    assert command._format_bytes(1024**3) == "1.00 GiB"
