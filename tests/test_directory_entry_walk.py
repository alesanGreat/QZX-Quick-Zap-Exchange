"""Real traversal and pruning contracts for retained DirEntry metadata."""

import os
from pathlib import Path

from qzx.core.file_search_entries import walk_directory_entries


def test_walk_matches_os_walk_and_keeps_real_entries(tmp_path):
    (tmp_path / "nested").mkdir()
    (tmp_path / "nested" / "app.py").write_text("pass\n", encoding="utf-8")
    (tmp_path / "data.json").write_text("{}\n", encoding="utf-8")
    expected = [(root, sorted(dirs), sorted(files)) for root, dirs, files in os.walk(tmp_path)]
    actual = []
    for root, dirs, files in walk_directory_entries(tmp_path):
        assert all(isinstance(entry, os.DirEntry) for entry in dirs + files)
        actual.append((root, sorted(entry.name for entry in dirs), sorted(entry.name for entry in files)))
    assert actual == expected


def test_pruned_directories_are_not_traversed(tmp_path):
    for name in ("keep", "skip"):
        (tmp_path / name).mkdir()
        (tmp_path / name / "source.py").write_text("pass\n", encoding="utf-8")
    roots = []
    for root, dirs, _ in walk_directory_entries(tmp_path):
        dirs[:] = [entry for entry in dirs if entry.name != "skip"]
        roots.append(Path(root).name)
    assert "keep" in roots
    assert "skip" not in roots


def test_directory_symlink_is_reported_but_not_followed(tmp_path):
    target = tmp_path / "target"
    target.mkdir()
    (target / "source.py").write_text("pass\n", encoding="utf-8")
    alias = tmp_path / "alias"
    alias.symlink_to(target, target_is_directory=True)
    rows = list(walk_directory_entries(tmp_path))
    assert {entry.name for entry in rows[0][1]} == {"target", "alias"}
    assert {Path(root).name for root, _, _ in rows} == {tmp_path.name, "target"}


def test_directory_replaced_by_link_during_yield_is_not_followed(tmp_path):
    child = tmp_path / "replace"
    child.mkdir()
    other = tmp_path / "outside"
    other.mkdir()
    (other / "source.py").write_text("pass\n", encoding="utf-8")
    walker = walk_directory_entries(tmp_path)
    next(walker)
    child.rmdir()
    child.symlink_to(other, target_is_directory=True)
    assert all(Path(root).name != "replace" for root, _, _ in walker)


def test_missing_directory_is_reported_to_error_callback(tmp_path):
    missing = tmp_path / "missing"
    errors = []
    list(walk_directory_entries(missing, errors.append))
    assert len(errors) == 1
    assert isinstance(errors[0], FileNotFoundError)
    assert Path(errors[0].filename) == missing
