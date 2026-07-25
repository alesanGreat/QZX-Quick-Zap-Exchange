#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Tests for the FindBrokenSymlinks command
"""

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
        assert result["broken_symlinks_count"] == 1
        broken = result["broken_symlinks"][0]
        assert broken["path"] == str(broken_link)
        assert broken["target"] == str(tmp_path / "missing-target.txt")
        assert "broken-link.txt" in result["message"]
