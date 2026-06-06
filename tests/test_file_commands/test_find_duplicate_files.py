#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Tests for the FindDuplicateFiles command
"""

import os
from qzx.commands.file.find_duplicate_files import FindDuplicateFilesCommand

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
        """Test scanning files and locating duplicate groups based on content hashing and size filtering"""
        # Create structure:
        # root/
        #   dup_a1.txt (20KB - content A)
        #   dup_a2.txt (20KB - content A)
        #   dup_a3.txt (20KB - content A)
        #   dup_b1.txt (30KB - content B)
        #   dup_b2.txt (30KB - content B)
        #   diff_b3.txt (30KB - content C, same size but different content!)
        #   tiny_dup1.txt (2KB - content D, should be ignored by default min_size_kb=10)
        #   tiny_dup2.txt (2KB - content D, ignored)
        #   .git/
        #     dup_a4.txt (20KB - content A, inside ignored dir, should not be scanned!)
        
        content_a = "A" * 20480  # 20 KB
        content_b = "B" * 30720  # 30 KB
        content_c = "C" * 30720  # 30 KB
        content_d = "D" * 2048   # 2 KB
        
        with open(tmp_path / "dup_a1.txt", "w") as f:
            f.write(content_a)
        with open(tmp_path / "dup_a2.txt", "w") as f:
            f.write(content_a)
        with open(tmp_path / "dup_a3.txt", "w") as f:
            f.write(content_a)
            
        with open(tmp_path / "dup_b1.txt", "w") as f:
            f.write(content_b)
        with open(tmp_path / "dup_b2.txt", "w") as f:
            f.write(content_b)
        with open(tmp_path / "diff_b3.txt", "w") as f:
            f.write(content_c)
            
        with open(tmp_path / "tiny_dup1.txt", "w") as f:
            f.write(content_d)
        with open(tmp_path / "tiny_dup2.txt", "w") as f:
            f.write(content_d)
            
        git_dir = tmp_path / ".git"
        git_dir.mkdir()
        with open(git_dir / "dup_a4.txt", "w") as f:
            f.write(content_a)
            
        # 1. Run scan with default min_size_kb = 10
        result = self.command.execute(str(tmp_path), min_size_kb=10)
        
        assert result["success"] is True
        # We expect 2 duplicate groups: Group A (3 files), Group B (2 files).
        # diff_b3 has same size but different content, so not duplicate.
        # tiny_dup files are under 10KB, so skipped.
        # git dir is skipped.
        assert result["total_groups"] == 2
        assert result["total_duplicate_files"] == 5
        
        # Calculate expected reclaimable bytes:
        # Group A: 20KB * (3 - 1) = 40KB
        # Group B: 30KB * (2 - 1) = 30KB
        # Total = 70KB = 71680 bytes
        assert result["reclaimable_bytes"] == 71680
        
        # 2. Run scan with min_size_kb = 1 (to include tiny files)
        result_tiny = self.command.execute(str(tmp_path), min_size_kb=1)
        assert result_tiny["success"] is True
        # Group A (3 files), Group B (2 files), Group D (2 files). Total groups = 3
        assert result_tiny["total_groups"] == 3
        assert result_tiny["total_duplicate_files"] == 7
        
        # Group D reclaimable: 2KB * (2 - 1) = 2KB. New total reclaimable = 72KB = 73728 bytes
        assert result_tiny["reclaimable_bytes"] == 73728
