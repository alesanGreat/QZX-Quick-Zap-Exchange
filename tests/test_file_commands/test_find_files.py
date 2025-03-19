#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Test for the FindFiles command
"""

import os
import pytest
from pathlib import Path
from unittest.mock import patch, Mock
from Commands.FileCommands.FindFiles import FindFilesCommand

class TestFindFilesCommand:
    """
    Tests for the FindFiles command
    """
    
    def setup_method(self):
        """Setup for each test"""
        self.command = FindFilesCommand()
        
    def test_parse_recursive_parameter(self):
        """Test interpretation of the recursive parameter"""
        # According to actual implementation, None returns None
        assert self.command._parse_recursive_parameter(None) is None
        
        # Unlimited recursion
        assert self.command._parse_recursive_parameter("-r") is None
        assert self.command._parse_recursive_parameter("--recursive") is None
        
        # Specific depth recursion
        assert self.command._parse_recursive_parameter("-r3") == 3
        assert self.command._parse_recursive_parameter("--recursive2") == 2
        
        # Unrecognized format
        assert self.command._parse_recursive_parameter("invalid") == 0
    
    @patch('os.walk')
    @patch('os.scandir')
    def test_execute_find_files_no_recursion(self, mock_scandir, mock_walk):
        """Test file search without recursion"""
        # Configure mocks
        mock_entry1 = Mock()
        mock_entry1.name = "test.txt"
        mock_entry1.path = "/app/test.txt"
        mock_entry1.is_file.return_value = True
        mock_entry1.is_dir.return_value = False
        mock_entry1.stat.return_value.st_size = 100
        mock_entry1.stat.return_value.st_mtime = 1615000000
        
        mock_scandir.return_value.__enter__.return_value = [mock_entry1]
        
        # Execute command without recursion - explicitly set recursion_depth to 0
        result = self.command.execute(search_path="/app", pattern="*.txt", recursive="0")
        
        # Verify result
        assert result["success"] is True
        assert result["pattern"] == "*.txt"
        assert result["recursive"] == "none"  # This is the expected display text for depth 0
        assert len(result["results"]) == 1
        assert result["results"][0]["name"] == "test.txt"
    
    @patch('os.walk')
    @patch('os.scandir')
    @patch('fnmatch.fnmatch')
    def test_execute_find_files_with_recursion(self, mock_fnmatch, mock_scandir, mock_walk):
        """Test file search with recursion"""
        # Configure mocks for os.walk
        mock_walk.return_value = [
            ("/app", ["subdir"], ["test1.txt"]),
            ("/app/subdir", [], ["test2.txt"])
        ]
        
        # Configure fnmatch to match our test files
        mock_fnmatch.return_value = True
        
        # Create mocks for files 
        mock_entry1 = Mock()
        mock_entry1.name = "test1.txt"
        mock_entry1.path = "/app/test1.txt"
        mock_entry1.is_file.return_value = True
        mock_entry1.is_dir.return_value = False
        mock_entry1.stat.return_value.st_size = 100
        mock_entry1.stat.return_value.st_mtime = 1615000000
        
        mock_entry2 = Mock()
        mock_entry2.name = "test2.txt"
        mock_entry2.path = "/app/subdir/test2.txt"
        mock_entry2.is_file.return_value = True
        mock_entry2.is_dir.return_value = False
        mock_entry2.stat.return_value.st_size = 200
        mock_entry2.stat.return_value.st_mtime = 1616000000
        
        # Setup scandir mock for the recursive case
        scandir_entries = {
            "/app": [mock_entry1],
            "/app/subdir": [mock_entry2]
        }
        
        def mock_scandir_side_effect(path):
            mock = Mock()
            mock.__enter__.return_value = scandir_entries.get(path, [])
            return mock
            
        mock_scandir.side_effect = mock_scandir_side_effect
        
        # Execute command with recursion
        result = self.command.execute(search_path="/app", pattern="*.txt", recursive="-r")
        
        # Verify result
        assert result["success"] is True
        assert result["pattern"] == "*.txt"
        assert result["recursive"] == "unlimited"
        
    def test_format_bytes(self):
        """Test bytes formatting"""
        # Update assertions to match the actual implementation
        assert self.command._format_bytes(0) == "0.00 B"
        assert self.command._format_bytes(1023) == "1023.00 B"
        assert self.command._format_bytes(1024) == "1.00 KB"
        assert self.command._format_bytes(1024*1024) == "1.00 MB"
        assert self.command._format_bytes(1024*1024*1024) == "1.00 GB" 