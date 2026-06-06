#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Test for the CountLinesInFile command
"""

from unittest.mock import mock_open, patch

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
    
    def test_count_lines(self):
        """Test counting lines in files"""
        # File with normal and empty lines
        file_content = "Line 1\nLine 2\n\nLine 4\n"
        
        with patch("builtins.open", mock_open(read_data=file_content)):
            # Count all lines
            total_lines, non_empty, success, error = self.command._count_lines("test.txt", ignore_empty=False)
            assert total_lines == 4
            assert non_empty == 3
            assert success is True
            assert error is None
            
            # Count only non-empty lines
            total_lines, non_empty, success, error = self.command._count_lines("test.txt", ignore_empty=True)
            assert total_lines == 3
            assert non_empty == 3
            assert success is True
            assert error is None
    
    @patch("qzx.commands.file.count_lines_in_file.CountLinesInFileCommand._find_files")
    @patch("qzx.commands.file.count_lines_in_file.CountLinesInFileCommand._count_lines")
    def test_execute(self, mock_count_lines, mock_find_files):
        """Test the complete execution of the command"""
        # Configure mocks
        mock_find_files.return_value = ["file1.txt", "file2.py"]
        
        # Simulate line counting for each file
        def count_lines_side_effect(file_path, ignore_empty):
            if file_path == "file1.txt":
                return (5, 4, True, None)
            elif file_path == "file2.py":
                return (10, 8, True, None)
            return (0, 0, False, "Error")
        
        mock_count_lines.side_effect = count_lines_side_effect
        
        # Execute the command
        result = self.command.execute("*.txt", recursive="-r2")
        
        # Verify result
        assert result["success"] is True
        assert result["total_lines"] == 15
        assert result["total_non_empty_lines"] == 12
        assert result["total_empty_lines"] == 3
        assert result["files_analyzed"] == 2
        assert result["file_pattern"] == "*.txt"
        assert result["recursive"] == 2
        
        # Verify that the correct files were found
        mock_find_files.assert_called_once_with("*.txt", "-r2")
        
        # Verify extension statistics
        assert ".txt" in result["extension_stats"]
        assert ".py" in result["extension_stats"]
        assert result["extension_stats"][".txt"] == 5
        assert result["extension_stats"][".py"] == 10
