"""Streaming and link-safety tests for isDirectoryEmpty."""

from __future__ import annotations

import os
from pathlib import Path

from qzx.commands.file.is_directory_empty import IsDirectoryEmptyCommand


def test_missing_and_file_targets_have_stable_error_codes(tmp_path):
    command = IsDirectoryEmptyCommand()
    file_target = tmp_path / "file.txt"
    file_target.write_text("content", encoding="utf-8")

    missing = command.execute(tmp_path / "missing")
    not_directory = command.execute(file_target)

    assert missing["success"] is False
    assert missing["error_code"] == "directory_not_found"
    assert not_directory["success"] is False
    assert not_directory["error_code"] == "not_a_directory"


def test_empty_directory_has_zeroed_complete_evidence(tmp_path):
    target = tmp_path / "empty"
    target.mkdir()

    result = IsDirectoryEmptyCommand().execute(target)

    assert result["success"] is True
    assert result["is_empty"] is True
    assert result["item_count"] == 0
    assert result["file_count"] == 0
    assert result["directory_count"] == 0
    assert result["symlink_count"] == 0
    assert result["details"]["scan_complete"] is True
    assert result["details"]["total_entries"] == 0


def test_hidden_entries_are_explicitly_ignored_or_included(tmp_path):
    target = tmp_path / "hidden-only"
    target.mkdir()
    (target / ".secret").write_text("hidden", encoding="utf-8")

    ignored = IsDirectoryEmptyCommand().execute(target)
    included = IsDirectoryEmptyCommand().execute(target, include_hidden=True)

    assert ignored["success"] is True
    assert ignored["is_empty"] is True
    assert ignored["item_count"] == 0
    assert ignored["details"]["total_entries"] == 1
    assert ignored["details"]["ignored_hidden_entries"] == 1
    assert ignored["details"]["hidden_policy"] == "ignored_for_emptiness"
    assert included["success"] is True
    assert included["is_empty"] is False
    assert included["item_count"] == 1
    assert included["file_count"] == 1
    assert included["details"]["hidden_policy"] == "included"


def test_injected_platform_hidden_policy_is_applied_without_materializing_names(
    tmp_path,
):
    target = tmp_path / "entries"
    target.mkdir()
    (target / "visible.txt").touch()
    (target / "platform-hidden.txt").touch()

    command = IsDirectoryEmptyCommand(
        hidden_predicate=lambda entry: entry.name == "platform-hidden.txt"
    )
    result = command.execute(target)

    assert result["success"] is True
    assert result["is_empty"] is False
    assert result["item_count"] == 1
    assert result["file_count"] == 1
    assert result["details"]["total_entries"] == 2
    assert result["details"]["ignored_hidden_entries"] == 1


def test_files_directories_and_links_are_counted_without_following_links(tmp_path):
    target = tmp_path / "root"
    target.mkdir()
    (target / "file.txt").touch()
    child = target / "child"
    child.mkdir()
    (child / "nested.txt").touch()
    link = target / "child-link"
    link.symlink_to(child, target_is_directory=True)

    result = IsDirectoryEmptyCommand().execute(target, include_hidden=True)

    assert result["success"] is True
    assert result["is_empty"] is False
    assert result["item_count"] == 3
    assert result["file_count"] == 1
    assert result["directory_count"] == 1
    assert result["symlink_count"] == 1
    assert result["details"]["symbolic_links_followed_inside_directory"] is False
    assert result["details"]["total_entries"] == 3


def test_root_symlink_requires_explicit_review(tmp_path):
    target = tmp_path / "target"
    target.mkdir()
    (target / "visible.txt").touch()
    link = tmp_path / "reviewed-link"
    link.symlink_to(target, target_is_directory=True)

    blocked = IsDirectoryEmptyCommand().execute(link)
    followed = IsDirectoryEmptyCommand().execute(link, follow_symlinks=True)

    assert blocked["success"] is False
    assert blocked["error_code"] == "symlink_path_blocked"
    assert blocked["details"]["blocked_component"] == str(link.absolute())
    assert followed["success"] is True
    assert followed["is_empty"] is False
    assert followed["details"]["target"]["followed_symlink"] is True
    assert followed["analyzed_path"] == str(target.resolve())


def test_directory_mutation_prevents_a_stale_emptiness_conclusion(tmp_path):
    target = tmp_path / "changing"
    target.mkdir()

    class MutatingScandir:
        def __init__(self, directory):
            self.directory = Path(directory)
            self.entries = None

        def __enter__(self):
            self.entries = os.scandir(self.directory)
            return self

        def __iter__(self):
            yield from self.entries
            (self.directory / "late-entry.txt").touch()
            current = self.directory.stat().st_mtime_ns
            os.utime(
                self.directory,
                ns=(current + 1_000_000_000, current + 1_000_000_000),
            )

        def __exit__(self, exc_type, exc, traceback):
            self.entries.close()
            return False

    result = IsDirectoryEmptyCommand(scandir=MutatingScandir).execute(target)

    assert result["success"] is False
    assert result["error_code"] == "directory_changed_during_scan"
    assert "did not publish an emptiness conclusion" in result["message"]
    assert result["details"]["directory_stable_during_scan"] is False
    assert result["details"]["scan_complete"] is False


def test_scandir_failure_is_structured(tmp_path):
    target = tmp_path / "blocked"
    target.mkdir()

    def refuse_scan(_path):
        raise PermissionError("synthetic directory denial")

    result = IsDirectoryEmptyCommand(scandir=refuse_scan).execute(target)

    assert result["success"] is False
    assert result["error_code"] == "directory_scan_failed"
    assert result["error"] == "PermissionError: synthetic directory denial"
    assert result["details"]["scan_complete"] is False


def test_hidden_metadata_failure_is_bounded_but_entry_still_counts(tmp_path):
    target = tmp_path / "entries"
    target.mkdir()
    (target / "present.txt").touch()

    def fail_hidden_check(_entry):
        raise OSError("synthetic hidden metadata failure")

    result = IsDirectoryEmptyCommand(
        hidden_predicate=fail_hidden_check
    ).execute(target)

    assert result["success"] is True
    assert result["is_empty"] is False
    assert result["item_count"] == 1
    assert result["details"]["scan_complete"] is False
    assert result["details"]["scan_error_count"] == 1
    assert result["details"]["scan_error_samples"] == [
        {
            "path": str(target / "present.txt"),
            "phase": "hidden_attribute",
            "error_type": "OSError",
            "error": "synthetic hidden metadata failure",
        }
    ]
    assert result["warnings"]


def test_invalid_booleans_and_paths_are_rejected_without_scanning(tmp_path):
    command = IsDirectoryEmptyCommand()

    invalid_hidden = command.execute(tmp_path, include_hidden="sometimes")
    invalid_follow = command.execute(tmp_path, follow_symlinks="sometimes")
    raw_bytes = command.execute(os.fsencode(tmp_path))
    empty = command.execute("")
    nul = command.execute("bad\x00path")

    assert invalid_hidden["error_code"] == "invalid_include_hidden"
    assert invalid_follow["error_code"] == "invalid_follow_symlinks"
    assert raw_bytes["error_code"] == "invalid_directory_path"
    assert empty["error_code"] == "invalid_directory_path"
    assert nul["error_code"] == "invalid_directory_path"
