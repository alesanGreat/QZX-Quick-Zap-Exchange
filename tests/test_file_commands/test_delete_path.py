"""Focused behavioral tests for deletePath workflow branches."""

from qzx.commands.file.delete_path import DeletePathCommand


def test_delete_path_limited_depth_removes_shallow_tree(tmp_path):
    target = tmp_path / "tree"
    child = target / "child"
    child.mkdir(parents=True)
    (child / "item.txt").write_text("temporary", encoding="utf-8")

    result = DeletePathCommand().execute(
        target,
        recursive=1,
        dry_run=False,
        apply=True,
    )

    assert result["success"] is True
    assert result["details"]["recursive"] == 1
    assert not target.exists()


def test_delete_path_nonrecursive_nonempty_directory_fails_closed(tmp_path):
    target = tmp_path / "tree"
    target.mkdir()
    item = target / "item.txt"
    item.write_text("keep", encoding="utf-8")

    result = DeletePathCommand().execute(
        target,
        recursive=False,
        dry_run=False,
        apply=True,
    )

    assert result["success"] is False
    assert result["error_code"] == "delete_failed"
    assert item.read_text(encoding="utf-8") == "keep"
