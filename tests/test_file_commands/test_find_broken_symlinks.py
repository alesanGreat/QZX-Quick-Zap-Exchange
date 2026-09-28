#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Tests for the FindBrokenSymlinks command
"""

from qzx.commands.file._broken_symlink_scan import _broken_link, _build_result
from qzx.commands.file.find_broken_symlinks import FindBrokenSymlinksCommand

class TestFindBrokenSymlinksCommand:
    """
    Tests for the FindBrokenSymlinks command
    """
    
    def setup_method(self):
        """Setup for each test"""
        self.command = FindBrokenSymlinksCommand()
        
    def test_nonexistent_directory(self):
        """Test with a directory that does not exist"""
        result = self.command.execute("non_existent_folder_abc")
        assert result["success"] is False
        assert "does not exist" in result["error"]
        
    def test_file_instead_of_directory(self, tmp_path):
        """Test with a file path instead of a directory"""
        file_path = tmp_path / "test.txt"
        file_path.touch()
        
        result = self.command.execute(str(file_path))
        assert result["success"] is False
        assert "is not a directory" in result["error"]
        
    def test_broken_symlinks_scanning_uses_real_links(self, tmp_path):
        target = tmp_path / "target.txt"
        target.write_text("present", encoding="utf-8")
        valid_link = tmp_path / "valid-link.txt"
        broken_link = tmp_path / "broken-link.txt"
        valid_link.symlink_to(target)
        broken_link.symlink_to(tmp_path / "missing-target.txt")

        result = self.command.execute(str(tmp_path))

        assert result["success"] is True
        assert result["analysis_complete"] is True
        assert result["scan_issues"] == []
        assert result["broken_symlinks_count"] == 1
        broken = result["broken_symlinks"][0]
        assert broken["path"] == str(broken_link)
        assert broken["target"] == str(tmp_path / "missing-target.txt")
        assert "broken-link.txt" in result["message"]

    def test_zero_depth_scans_root_entries_without_descending(self, tmp_path):
        root_broken = tmp_path / "root-broken.txt"
        root_broken.symlink_to(tmp_path / "missing-root-target.txt")
        nested = tmp_path / "nested"
        nested.mkdir()
        nested_broken = nested / "nested-broken.txt"
        nested_broken.symlink_to(tmp_path / "missing-nested-target.txt")

        result = self.command.execute(str(tmp_path), max_depth="0")

        assert result["success"] is True
        assert result["broken_symlinks_count"] == 1
        assert result["broken_symlinks"][0]["path"] == str(root_broken)

    def test_broken_junction_contract_is_not_limited_to_symlinks(self, tmp_path):
        candidate = str(tmp_path / "broken-junction")

        def missing_target(_path):
            raise FileNotFoundError("synthetic missing target")

        item, issue = _broken_link(
            candidate,
            str(tmp_path),
            is_link=lambda _path: False,
            is_junction=lambda _path: True,
            stat_path=missing_target,
            read_link=lambda _path: "missing-junction-target",
        )

        assert issue is None
        assert item == {
            "path": candidate,
            "relative_path": "broken-junction",
            "target": "missing-junction-target",
        }

    def test_inspection_errors_cannot_produce_a_false_clean_result(self, tmp_path):
        candidate = str(tmp_path / "unreadable-link")

        def denied(_path):
            raise PermissionError("synthetic access denied")

        item, issue = _broken_link(
            candidate,
            str(tmp_path),
            is_link=lambda _path: True,
            is_junction=lambda _path: False,
            stat_path=denied,
        )

        assert item is None
        assert issue["path"] == "unreadable-link"
        assert issue["operation"] == "inspect_link"
        result = _build_result(str(tmp_path), [], [issue])
        assert result["success"] is False
        assert result["analysis_complete"] is False
        assert result["error_code"] == "symlink_scan_incomplete"
        assert "cannot claim the tree is clean" in result["message"]
