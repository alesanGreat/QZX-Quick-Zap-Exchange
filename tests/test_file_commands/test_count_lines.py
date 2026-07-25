#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Test for the CountLinesInFile command
"""

from qzx.commands.file.count_lines_in_file import CountLinesInFileCommand

class TestCountLinesInFileCommand:
    """
    Tests for the CountLinesInFile command
    """
    
    def setup_method(self):
        """Setup for each test"""
        self.command = CountLinesInFileCommand()
    
    def test_parse_recursive_parameter(self):
        """Test interpretation of the recursive parameter"""
        # No recursion
        assert self.command._parse_recursive_parameter(None) == 0
        
        # Unlimited recursion
        assert self.command._parse_recursive_parameter("-r") is None
        assert self.command._parse_recursive_parameter("--recursive") is None
        
        # Specific depth recursion
        assert self.command._parse_recursive_parameter("-r3") == 3
        assert self.command._parse_recursive_parameter("--recursive2") == 2
        
        # Unrecognized format
        assert self.command._parse_recursive_parameter("invalid") == 0
    
    def test_find_files_single_file(self, tmp_path):
        """Test finding a single file"""
        file_path = tmp_path / "test.txt"
        file_path.write_text("content", encoding="utf-8")

        result = self.command._find_files(str(file_path))

        assert result == [str(file_path.resolve())]

    def test_find_files_directory_no_recursion(self, tmp_path):
        """Test finding files in a directory without recursion"""
        file1 = tmp_path / "file1.txt"
        file2 = tmp_path / "file2.txt"
        nested = tmp_path / "nested"
        nested.mkdir()
        nested_file = nested / "file3.txt"
        for path in (file1, file2, nested_file):
            path.write_text("content", encoding="utf-8")

        result = self.command._find_files(str(tmp_path), recursive=None)

        assert set(result) == {str(file1.resolve()), str(file2.resolve())}

    def test_find_files_recursive(self, tmp_path):
        """Test finding files recursively"""
        root_file = tmp_path / "file1.txt"
        nested = tmp_path / "nested"
        nested.mkdir()
        nested_file = nested / "file2.txt"
        for path in (root_file, nested_file):
            path.write_text("content", encoding="utf-8")

        result = self.command._find_files(str(tmp_path), recursive="-r")

        assert set(result) == {str(root_file.resolve()), str(nested_file.resolve())}
    
    def test_count_lines_reads_a_real_file(self, tmp_path):
        file_path = tmp_path / "test.txt"
        file_path.write_text("Line 1\nLine 2\n\nLine 4\n", encoding="utf-8")

        total_lines, non_empty, success, error = self.command._count_lines(
            str(file_path), ignore_empty=False
        )
        assert (total_lines, non_empty, success, error) == (4, 3, True, None)

        total_lines, non_empty, success, error = self.command._count_lines(
            str(file_path), ignore_empty=True
        )
        assert (total_lines, non_empty, success, error) == (3, 3, True, None)

    def test_execute_counts_real_matching_files(self, tmp_path):
        file1 = tmp_path / "file1.txt"
        file2 = tmp_path / "file2.txt"
        ignored = tmp_path / "ignored.py"
        file1.write_text("1\n2\n\n4\n5\n", encoding="utf-8")
        file2.write_text("1\n2\n3\n4\n5\n6\n7\n8\n9\n10\n", encoding="utf-8")
        ignored.write_text("not counted\n", encoding="utf-8")

        result = self.command.execute(
            str(tmp_path / "*.txt"), recursive="-r2"
        )

        assert result["success"] is True
        assert result["total_lines"] == 15
        assert result["total_non_empty_lines"] == 14
        assert result["total_empty_lines"] == 1
        assert result["files_analyzed"] == 2
        assert result["file_pattern"] == str(tmp_path / "*.txt")
        assert result["recursive"] == 2
        assert result["extension_stats"] == {".txt": 15}
