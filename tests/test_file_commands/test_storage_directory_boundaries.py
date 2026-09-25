"""A requested scan must not traverse directory aliases or mistake cloud tags for links."""

import os
import stat
import subprocess
from types import SimpleNamespace

from qzx.commands.file import _duplicate_inventory as duplicate_inventory
from qzx.commands.file.find_duplicate_files import FindDuplicateFilesCommand
from qzx.commands.file.find_files import FindFilesCommand
from qzx.core.recursive_findfiles_utils import find_files


def _tagged_directory(info, tag):
    fields = {
        name: getattr(info, name)
        for name in dir(info)
        if name.startswith("st_")
    }
    fields.update(st_file_attributes=0x400, st_reparse_tag=tag)
    return SimpleNamespace(**fields)


def test_non_surrogate_directory_reparse_point_is_not_treated_as_an_alias(
    tmp_path,
):
    child = tmp_path / "locally-available-cloud-folder"
    child.mkdir()
    (child / "a.bin").write_bytes(b"available" * 256)
    (child / "b.bin").write_bytes(b"available" * 256)
    original = duplicate_inventory.file_snapshot

    def cloud_snapshot(path):
        info = original(path)
        if path == str(child):
            return _tagged_directory(info, 0x9000001A)
        return info

    result = FindDuplicateFilesCommand(
        snapshot_reader=cloud_snapshot
    ).execute(tmp_path, 0, 1)

    assert result["total_groups"] == 1
    assert result["scan_statistics"]["directory_links_skipped"] == 0


def _directory_alias(link, target):
    if os.name == "nt":
        completed = subprocess.run(
            [
                "cmd.exe",
                "/d",
                "/c",
                "mklink",
                "/J",
                str(link),
                str(target),
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
        assert completed.returncode == 0, completed.stderr
    else:
        link.symlink_to(target, target_is_directory=True)


def test_native_directory_alias_is_listable_but_never_traversed(tmp_path):
    root, outside = tmp_path / "scan", tmp_path / "outside"
    root.mkdir()
    outside.mkdir()
    (root / "inside.bin").write_bytes(b"inside")
    (outside / "external.bin").write_bytes(b"external")
    alias = root / "shortcut"
    _directory_alias(alias, outside)

    result = FindFilesCommand().execute(root, recursive=2)
    directories = list(
        find_files(str(root / "*"), recursive=2, file_type="d")
    )

    assert result["success"] is True
    assert [item["name"] for item in result["results"]] == ["inside.bin"]
    assert str(alias) in directories
    assert (outside / "external.bin").read_bytes() == b"external"


if os.name != "nt" and hasattr(os, "geteuid") and os.geteuid() != 0:
    def test_native_denied_directory_keeps_partial_filename_evidence(
        tmp_path,
    ):
        (tmp_path / "readable.bin").write_bytes(b"readable")
        locked = tmp_path / "locked"
        locked.mkdir()
        (locked / "hidden.bin").write_bytes(b"hidden")
        locked.chmod(0)
        try:
            result = FindFilesCommand().execute(tmp_path, recursive=1)
            denied_root = FindFilesCommand().execute(
                locked, recursive=False
            )
        finally:
            locked.chmod(stat.S_IRWXU)

        assert result["success"] and result["partial"]
        assert result["count"] == 1
        assert result["skipped_search_paths"] == 1
        assert not denied_root["success"]
else:
    def test_denied_directory_fixture_scope_is_explicit():
        assert (
            os.name == "nt"
            or not hasattr(os, "geteuid")
            or os.geteuid() == 0
        )


if hasattr(os, "mkfifo"):
    def test_native_named_pipe_is_not_opened_or_counted_as_a_regular_file(
        tmp_path,
    ):
        os.mkfifo(tmp_path / "named-pipe")
        (tmp_path / "regular.bin").write_bytes(b"regular")

        result = FindFilesCommand().execute(tmp_path, recursive=1)

        assert result["success"] is True
        assert result["partial"] is False
        assert result["count"] == 1
        assert result["skipped_special_files"] == 1
else:
    def test_named_pipe_fixture_scope_is_explicit():
        assert not hasattr(os, "mkfifo")
