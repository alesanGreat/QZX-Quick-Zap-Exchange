#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Test for the FindText command
"""

import os
import re
import pytest
from unittest.mock import patch, mock_open, Mock
from Commands.FileCommands.FindText import FindTextCommand

class TestFindTextCommand:
    """
    Tests for the FindText command
    """
    
    def setup_method(self):
        """Setup for each test"""
        self.command = FindTextCommand()
    
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
    
    def test_search_file_simple(self):
        """Test searching a file with simple pattern"""
        file_content = "Line 1: test\nLine 2: example\nLine 3: test example\nLine 4\n"
        
        with patch("builtins.open", mock_open(read_data=file_content)):
            # Test simple search
            result = self.command._search_file(
                "test.txt", "test", False, True, 0, False, False, False
            )
            
            assert result["matches"] == 2
            assert len(result["lines"]) == 2
            assert result["lines"][0]["line_num"] == 1
            assert result["lines"][1]["line_num"] == 3
    
    def test_search_file_regex(self):
        """Test searching a file with regex pattern"""
        file_content = "Line 1: test\nLine 2: example\nLine 3: test example\nLine 4\n"
        
        with patch("builtins.open", mock_open(read_data=file_content)):
            # Test regex search
            result = self.command._search_file(
                "test.txt", re.compile(r"Line \d:"), True, True, 0, False, False, False
            )
            
            assert result["matches"] == 3
            assert len(result["lines"]) == 3
            assert result["lines"][0]["line_num"] == 1
            assert result["lines"][1]["line_num"] == 2
            assert result["lines"][2]["line_num"] == 3
    
    def test_search_file_case_insensitive(self):
        """Test case-insensitive search"""
        file_content = "Line 1: TEST\nLine 2: test\nLine 3: Test\nLine 4\n"
        
        with patch("builtins.open", mock_open(read_data=file_content)):
            # Test case insensitive
            result = self.command._search_file(
                "test.txt", "test", False, False, 0, False, False, False
            )
            
            assert result["matches"] == 3
            assert len(result["lines"]) == 3
    
    def test_search_file_with_context(self):
        """Test searching with context lines"""
        file_content = "Line 1\nLine 2: test\nLine 3\nLine 4\nLine 5: test\nLine 6\n"
        
        with patch("builtins.open", mock_open(read_data=file_content)):
            # Test with context
            result = self.command._search_file(
                "test.txt", "test", False, True, 1, False, False, False
            )
            
            assert result["matches"] == 2
            assert len(result["lines"]) == 6  # 2 matches + 4 context lines
            
            # Check context lines
            assert result["lines"][0]["line_num"] == 1
            assert not result["lines"][0]["is_match"]
            assert result["lines"][1]["line_num"] == 2
            assert result["lines"][1]["is_match"]
            assert result["lines"][2]["line_num"] == 3
            assert not result["lines"][2]["is_match"]
    
    def test_search_file_invert_match(self):
        """Test inverting match results"""
        file_content = "Line 1: test\nLine 2: example\nLine 3: test\nLine 4\n"
        
        with patch("builtins.open", mock_open(read_data=file_content)):
            # Test invert match
            result = self.command._search_file(
                "test.txt", "test", False, True, 0, True, False, False
            )
            
            assert result["matches"] == 2  # Lines without "test"
            assert len(result["lines"]) == 2
            assert result["lines"][0]["line_num"] == 2
            assert result["lines"][1]["line_num"] == 4
    
    def test_search_file_count_only(self):
        """Test count-only mode"""
        file_content = "Line 1: test\nLine 2: example\nLine 3: test\nLine 4\n"
        
        with patch("builtins.open", mock_open(read_data=file_content)):
            # Test count only
            result = self.command._search_file(
                "test.txt", "test", False, True, 0, False, True, False
            )
            
            assert result["matches"] == 2
            assert "lines" not in result
    
    @patch('os.path.isfile')
    @patch('os.path.isdir')
    @patch('os.walk')
    def test_execute_single_file(self, mock_walk, mock_isdir, mock_isfile):
        """Test executing search on a single file"""
        mock_isfile.return_value = True
        mock_isdir.return_value = False
        
        file_content = "Line 1: test\nLine 2: example\nLine 3: test\nLine 4\n"
        
        with patch("builtins.open", mock_open(read_data=file_content)):
            # Execute command on a single file
            result = self.command.execute("test", "test.txt")
            
            assert result["success"] is True
            assert result["pattern"] == "test"
            assert result["target"] == "test.txt"
            assert result["files_searched"] == 1
            assert result["files_with_matches"] == 1
            assert result["total_matches"] == 2
    
    @patch('os.path.isfile')
    @patch('os.path.isdir')
    @patch('os.walk')
    @patch('fnmatch.fnmatch')
    def test_execute_directory(self, mock_fnmatch, mock_walk, mock_isdir, mock_isfile):
        """Test executing search on a directory"""
        mock_isfile.side_effect = lambda path: not path.endswith('dir')
        mock_isdir.side_effect = lambda path: path.endswith('dir')
        
        # Configure walk to return files
        mock_walk.return_value = [
            ("test_dir", [], ["file1.txt", "file2.py"])
        ]
        
        # Configure fnmatch to match all files
        mock_fnmatch.return_value = True
        
        # Mock the _search_file method to return controlled results
        with patch.object(self.command, '_search_file') as mock_search_file:
            mock_search_file.side_effect = [
                {"file": "test_dir/file1.txt", "matches": 3, "lines": [{"line_num": 1, "content": "test", "is_match": True}]},
                {"file": "test_dir/file2.py", "matches": 2, "lines": [{"line_num": 1, "content": "test", "is_match": True}]}
            ]
            
            # Execute command on a directory
            result = self.command.execute("test", "test_dir", recursive="-r")
            
            assert result["success"] is True
            assert result["pattern"] == "test"
            assert result["target"] == "test_dir"
            assert result["recursive"] == "unlimited"
            assert result["files_searched"] == 2
            assert result["files_with_matches"] == 2
            assert result["total_matches"] == 5 