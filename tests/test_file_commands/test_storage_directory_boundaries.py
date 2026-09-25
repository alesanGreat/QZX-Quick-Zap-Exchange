"""A requested scan must not traverse directory aliases or mistake cloud tags for links."""

import os
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


def test_denied_directory_keeps_partial_filename_evidence_without_acl_mutation(
    tmp_path,
):
    readable = tmp_path / "readable.bin"
    readable.write_bytes(b"readable")
    denied = tmp_path / "synthetic-denied"
    denied.mkdir()

    def finder(*, file_path_pattern, on_error, **_options):
        root = os.path.dirname(file_path_pattern)
        if os.path.normcase(root) == os.path.normcase(str(denied)):
            on_error(PermissionError(13, "synthetic root denial", root))
            return
        yield str(readable)
        on_error(
            PermissionError(13, "synthetic child denial", str(denied))
        )

    command = FindFilesCommand(finder=finder)
    result = command.execute(tmp_path, recursive=1)
    denied_root = command.execute(denied, recursive=False)

    assert result["success"] and result["partial"]
    assert result["count"] == 1
    assert result["skipped_search_paths"] == 1
    assert not denied_root["success"]


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
