from pathlib import Path

from qzx.core.recursive_findfiles_utils import (
    find_files,
    parse_recursive_parameter,
)


def _relative_paths(paths, root):
    return {Path(path).relative_to(root).as_posix() for path in paths}


def test_parse_recursive_parameter():
    assert parse_recursive_parameter(None) == 0
    assert parse_recursive_parameter(False) == 0
    assert parse_recursive_parameter(True) is None
    assert parse_recursive_parameter("-r") is None
    assert parse_recursive_parameter("--recursive") is None
    assert parse_recursive_parameter("-r2") == 2
    assert parse_recursive_parameter("--recursive3") == 3
    assert parse_recursive_parameter("invalid") == 0


def test_find_files_without_recursion(tmp_path):
    (tmp_path / "root.txt").write_text("root", encoding="utf-8")
    nested = tmp_path / "nested"
    nested.mkdir()
    (nested / "nested.txt").write_text("nested", encoding="utf-8")

    results = find_files(str(tmp_path / "*.txt"), recursive=0, file_type="f")

    assert _relative_paths(results, tmp_path) == {"root.txt"}


def test_find_files_with_limited_and_unlimited_recursion(tmp_path):
    (tmp_path / "root.txt").write_text("root", encoding="utf-8")
    level_one = tmp_path / "one"
    level_one.mkdir()
    (level_one / "one.txt").write_text("one", encoding="utf-8")
    level_two = level_one / "two"
    level_two.mkdir()
    (level_two / "two.txt").write_text("two", encoding="utf-8")

    limited = find_files(str(tmp_path / "*.txt"), recursive=1, file_type="f")
    unlimited = find_files(str(tmp_path / "*.txt"), recursive=None, file_type="f")

    assert _relative_paths(limited, tmp_path) == {"root.txt", "one/one.txt"}
    assert _relative_paths(unlimited, tmp_path) == {
        "root.txt",
        "one/one.txt",
        "one/two/two.txt",
    }


def test_find_files_applies_exclusions(tmp_path):
    (tmp_path / "keep.txt").write_text("keep", encoding="utf-8")
    (tmp_path / "skip.log").write_text("skip", encoding="utf-8")
    ignored = tmp_path / "ignored"
    ignored.mkdir()
    (ignored / "hidden.txt").write_text("hidden", encoding="utf-8")

    recursive_results = find_files(
        str(tmp_path / "*"),
        recursive=None,
        file_type="f",
        exclude_patterns=["*.log"],
        exclude_dirs=["ignored"],
    )
    direct_results = find_files(
        str(tmp_path / "*"),
        recursive=0,
        file_type="f",
        exclude_patterns=["*.log"],
    )

    assert _relative_paths(recursive_results, tmp_path) == {"keep.txt"}
    assert _relative_paths(direct_results, tmp_path) == {"keep.txt"}
