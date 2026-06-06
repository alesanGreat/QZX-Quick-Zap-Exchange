#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Tests for the GetProjectTree command
"""

import os
from qzx.commands.development.get_project_tree import GetProjectTreeCommand

class TestGetProjectTreeCommand:
    """
    Tests for the GetProjectTree command
    """
    
    def setup_method(self):
        """Setup for each test"""
        self.command = GetProjectTreeCommand()
        
    def test_nonexistent_directory(self):
        """Test with a directory that does not exist"""
        result = self.command.execute("non_existent_folder_xyz")
        assert result["success"] is False
        assert "does not exist" in result["error"]
        
    def test_file_instead_of_directory(self, tmp_path):
        """Test with a file path instead of a directory"""
        file_path = tmp_path / "test.txt"
        file_path.touch()
        
        result = self.command.execute(str(file_path))
        assert result["success"] is False
        assert "is not a directory" in result["error"]
        
    def test_generate_tree_structure(self, tmp_path):
        """Test tree generation with nested files and folders and filtering"""
        # Create structure:
        # root/
        #   file1.txt
        #   .git/ (should be excluded by default)
        #     config
        #   src/
        #     app.py
        #     utils/
        #       helper.py
        #   tests/
        #     test_app.py
        
        (tmp_path / "file1.txt").touch()
        
        git_dir = tmp_path / ".git"
        git_dir.mkdir()
        (git_dir / "config").touch()
        
        src_dir = tmp_path / "src"
        src_dir.mkdir()
        (src_dir / "app.py").touch()
        
        utils_dir = src_dir / "utils"
        utils_dir.mkdir()
        (utils_dir / "helper.py").touch()
        
        tests_dir = tmp_path / "tests"
        tests_dir.mkdir()
        (tests_dir / "test_app.py").touch()
        
        # 1. Test standard tree up to depth 2 (including files)
        result = self.command.execute(str(tmp_path), max_depth=2, include_files="true")
        assert result["success"] is True
        
        # Check ASCII lines
        tree_text = result["tree_text"]
        assert "file1.txt" in tree_text
        assert "src" in tree_text
        assert "app.py" in tree_text
        assert "tests" in tree_text
        assert "test_app.py" in tree_text
        
        # Excludes check: .git should be excluded
        assert ".git" not in tree_text
        assert "config" not in tree_text
        
        # Depth check: depth 2 means we see root and level 1 (src, tests, file1) and level 2 (app.py, test_app.py, utils)
        # Wait, level 3 (helper.py inside utils) is at depth 3, so it should NOT be in the tree text
        assert "helper.py" not in tree_text
        assert "utils" in tree_text  # Level 2 dir is visible
        
        # Verify JSON structure
        json_tree = result["tree_structure"]
        assert json_tree["type"] == "directory"
        
        children = {c["name"]: c for c in json_tree["children"]}
        assert "file1.txt" in children
        assert "src" in children
        assert "tests" in children
        assert ".git" not in children
        
        # Verify src children (depth 1 to depth 2)
        src_children = {c["name"]: c for c in children["src"]["children"]}
        assert "app.py" in src_children
        assert "utils" in src_children
        # utils children should be empty because utils is at depth 2 (max depth) and we don't go deeper
        assert len(src_children["utils"]["children"]) == 0
        
    def test_exclude_files_mode(self, tmp_path):
        """Test tree generation in folder-only mode (include_files=false)"""
        (tmp_path / "file1.txt").touch()
        src_dir = tmp_path / "src"
        src_dir.mkdir()
        (src_dir / "app.py").touch()
        
        result = self.command.execute(str(tmp_path), include_files="false")
        assert result["success"] is True
        
        tree_text = result["tree_text"]
        assert "src" in tree_text
        assert "file1.txt" not in tree_text
        assert "app.py" not in tree_text
        
        # Verify JSON
        json_tree = result["tree_structure"]
        assert len(json_tree["children"]) == 1
        assert json_tree["children"][0]["name"] == "src"
        assert len(json_tree["children"][0]["children"]) == 0
        
    def test_custom_exclude_dirs(self, tmp_path):
        """Test tree generation with custom directories excluded"""
        src_dir = tmp_path / "src"
        src_dir.mkdir()
        (src_dir / "app.py").touch()
        
        tests_dir = tmp_path / "tests"
        tests_dir.mkdir()
        (tests_dir / "test_app.py").touch()
        
        # Exclude 'src' and let others show
        result = self.command.execute(str(tmp_path), exclude_dirs="src")
        assert result["success"] is True
        
        tree_text = result["tree_text"]
        assert "tests" in tree_text
        assert "src" not in tree_text
