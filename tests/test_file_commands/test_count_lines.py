#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Test for the CountLinesInFile command
"""

import os
import pytest
from unittest.mock import patch, mock_open, MagicMock
from Commands.FileCommands.CountLinesInFile import CountLinesInFileCommand

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
    
    @patch('os.path.isfile')
    @patch('os.path.isdir')
    def test_find_files_single_file(self, mock_isdir, mock_isfile):
        """Test finding a single file"""
        mock_isfile.return_value = True
        mock_isdir.return_value = False
        
        file_path = "test.txt"
        result = self.command._find_files(file_path)
        
        assert result == [file_path]
        mock_isfile.assert_called_once_with(file_path)
    
    @patch('os.walk')
    @patch('os.path.isfile')
    @patch('os.path.isdir')
    @patch('os.listdir')
    def test_find_files_directory_no_recursion(self, mock_listdir, mock_isdir, mock_isfile, mock_walk):
        """Test finding files in a directory without recursion"""
        mock_isfile.return_value = False
        mock_isdir.return_value = True
        mock_listdir.return_value = ["file1.txt", "file2.txt"]
        
        # Simulate files as actual files
        def fake_isfile(path):
            return os.path.basename(path) in ["file1.txt", "file2.txt"]
        
        # Use the fake function for isfile method
        mock_isfile.side_effect = fake_isfile
        
        dir_path = "test_dir"
        result = self.command._find_files(dir_path, recursive=None)
        
        assert len(result) == 2
        assert os.path.join(dir_path, "file1.txt") in result
        assert os.path.join(dir_path, "file2.txt") in result
        
        mock_isdir.assert_called_once_with(dir_path)
        mock_listdir.assert_called_once_with(dir_path)
        
        # Verify that walk was not called
        mock_walk.assert_not_called()
    
    @patch('os.walk')
    @patch('os.path.isfile')
    @patch('os.path.isdir')
    def test_find_files_recursive(self, mock_isdir, mock_isfile, mock_walk):
        """Test finding files recursively"""
        mock_isfile.return_value = False
        mock_isdir.return_value = True
        
        mock_walk.return_value = [
            ("test_dir", ["subdir"], ["file1.txt"]),
            ("test_dir/subdir", [], ["file2.txt"])
        ]
        
        dir_path = "test_dir"
        result = self.command._find_files(dir_path, recursive="-r")
        
        assert len(result) == 2
        assert os.path.join("test_dir", "file1.txt") in result
        assert os.path.join("test_dir/subdir", "file2.txt") in result
        
        mock_isdir.assert_called_once_with(dir_path)
        mock_walk.assert_called_once_with(dir_path)
    
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
    
    @patch('Commands.FileCommands.CountLinesInFile.CountLinesInFileCommand._find_files')
    @patch('Commands.FileCommands.CountLinesInFile.CountLinesInFileCommand._count_lines')
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