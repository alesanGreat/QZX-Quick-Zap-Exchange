#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Tests for the FindDuplicateFiles command
"""

from qzx.commands.file.find_duplicate_files import FindDuplicateFilesCommand


class CollidingDigestFindDuplicateFilesCommand(FindDuplicateFilesCommand):
    """Deterministic boundary fake for the astronomically rare hash collision."""

    def _get_sha256(self, _filepath):
        return "collision"


def _write_duplicate_fixture(root):
    contents = {
        "dup_a1.txt": "A" * 20480,
        "dup_a2.txt": "A" * 20480,
        "dup_a3.txt": "A" * 20480,
        "dup_b1.txt": "B" * 30720,
        "dup_b2.txt": "B" * 30720,
        "diff_b3.txt": "C" * 30720,
        "tiny_dup1.txt": "D" * 2048,
        "tiny_dup2.txt": "D" * 2048,
    }
    for name, content in contents.items():
        (root / name).write_text(content, encoding="utf-8")
    git_dir = root / ".git"
    git_dir.mkdir()
    (git_dir / "dup_a4.txt").write_text("A" * 20480, encoding="utf-8")


class TestFindDuplicateFilesCommand:
    """
    Tests for the FindDuplicateFiles command
    """
    
    def setup_method(self):
        """Setup for each test"""
        self.command = FindDuplicateFilesCommand()
        
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
        
    def test_find_duplicates(self, tmp_path):
        """Find verified duplicate groups while respecting size and scope filters."""
        _write_duplicate_fixture(tmp_path)

        result = self.command.execute(str(tmp_path), min_size_kb=10)

        assert result["success"] is True
        assert result["total_groups"] == 2
        assert result["total_duplicate_files"] == 5
        assert result["reclaimable_bytes"] == 71680

        result_tiny = self.command.execute(str(tmp_path), min_size_kb=1)

        assert result_tiny["success"] is True
        assert result_tiny["total_groups"] == 3
        assert result_tiny["total_duplicate_files"] == 7
        assert result_tiny["reclaimable_bytes"] == 73728

    def test_digest_collision_does_not_create_false_duplicate_group(
        self,
        tmp_path,
    ):
        """A digest match alone must never prove that two files are identical."""
        (tmp_path / "first.bin").write_bytes(b"A" * 2048)
        (tmp_path / "second.bin").write_bytes(b"B" * 2048)

        result = CollidingDigestFindDuplicateFilesCommand().execute(
            str(tmp_path),
            min_size_kb=1,
        )

        assert result["success"] is True
        assert result["total_groups"] == 0
        assert result["duplicate_groups"] == {}
