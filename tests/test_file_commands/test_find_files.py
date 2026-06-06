#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Test for the FindFiles command
"""

from qzx.commands.file.find_files import FindFilesCommand

class TestFindFilesCommand:
    """
    Tests for the FindFiles command
    """
    
    def setup_method(self):
        """Setup for each test"""
        self.command = FindFilesCommand()
        
    def test_parse_recursive_parameter(self):
        """Test interpretation of the recursive parameter"""
        assert self.command._parse_recursive_parameter(None) == 0
        
        # Unlimited recursion
        assert self.command._parse_recursive_parameter("-r") is None
        assert self.command._parse_recursive_parameter("--recursive") is None
        
        # Specific depth recursion
        assert self.command._parse_recursive_parameter("-r3") == 3
        assert self.command._parse_recursive_parameter("--recursive2") == 2
        
        # Unrecognized format
        assert self.command._parse_recursive_parameter("invalid") == 0
    
    def test_execute_find_files_no_recursion(self, tmp_path):
        """Test file search without recursion"""
        root_file = tmp_path / "test.txt"
        root_file.write_text("root", encoding="utf-8")
        nested = tmp_path / "nested"
        nested.mkdir()
        (nested / "nested.txt").write_text("nested", encoding="utf-8")

        result = self.command.execute(
            search_path=str(tmp_path),
            pattern="*.txt",
            recursive=0,
            type="f",
            format="json",
        )

        assert result["success"] is True
        assert result["pattern"] == "*.txt"
        assert result["recursive"] == "none"
        assert len(result["results"]) == 1
        assert result["results"][0]["name"] == "test.txt"

    def test_execute_find_files_with_recursion(self, tmp_path):
        """Test file search with recursion"""
        root_file = tmp_path / "test1.txt"
        root_file.write_text("root", encoding="utf-8")
        nested = tmp_path / "nested"
        nested.mkdir()
        nested_file = nested / "test2.txt"
        nested_file.write_text("nested", encoding="utf-8")

        result = self.command.execute(
            search_path=str(tmp_path),
            pattern="*.txt",
            recursive="-r",
            type="f",
            format="json",
        )

        assert result["success"] is True
        assert result["pattern"] == "*.txt"
        assert result["recursive"] == "unlimited"
        assert {entry["name"] for entry in result["results"]} == {
            "test1.txt",
            "test2.txt",
        }

    def test_format_bytes(self):
        """Test bytes formatting"""
        # Update assertions to match the actual implementation
        assert self.command._format_bytes(0) == "0.00 B"
        assert self.command._format_bytes(1023) == "1023.00 B"
        assert self.command._format_bytes(1024) == "1.00 KB"
        assert self.command._format_bytes(1024*1024) == "1.00 MB"
        assert self.command._format_bytes(1024*1024*1024) == "1.00 GB"
