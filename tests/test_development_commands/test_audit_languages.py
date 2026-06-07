#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Tests for the auditLanguages command
"""

import os
from qzx.commands.development.audit_languages import AuditLanguagesCommand

class TestAuditLanguagesCommand:
    """
    Tests for the AuditLanguagesCommand class
    """
    
    def setup_method(self):
        """Setup for each test"""
        self.command = AuditLanguagesCommand()
        
    def test_nonexistent_directory(self):
        """Test with a directory that does not exist"""
        result = self.command.execute("non_existent_dir_abc_123")
        assert result["success"] is False
        assert "does not exist" in result["error"]
        
    def test_empty_directory(self, tmp_path):
        """Test with an empty directory"""
        result = self.command.execute(str(tmp_path))
        assert result["success"] is True
        assert result["total_files"] == 0
        assert result["alerts_count"] == 0
        
    def test_fully_represented_python(self, tmp_path):
        """Test with Python files which are fully supported in QZX"""
        # Create 4 python files (exceeding threshold of 3)
        for i in range(4):
            (tmp_path / f"file_{i}.py").touch()
            
        result = self.command.execute(str(tmp_path), threshold=3)
        assert result["success"] is True
        assert result["total_files"] == 4
        assert "python" in result["languages_found"]
        assert result["alerts_count"] == 0 # Python is fully supported
        assert len(result["fully_represented"]) == 1
        assert result["fully_represented"][0]["language"] == "python"
        
    def test_partially_represented_go(self, tmp_path):
        """Test with Go files which now have scaffolding and dead code support in QZX"""
        # Create 5 Go files
        for i in range(5):
            (tmp_path / f"file_{i}.go").touch()

        # Create 1 Python file to have a mixed total
        (tmp_path / "app.py").touch()

        result = self.command.execute(str(tmp_path), threshold=3)
        assert result["success"] is True
        assert result["total_files"] == 6
        assert "go" in result["languages_found"]

        # Go should be partially represented (scaffolding and dead_code present, env_fallbacks missing)
        go_entry = next((p for p in result["partially_represented"] if p["language"] == "go"), None)
        assert go_entry is not None
        assert "env_fallbacks" in go_entry["missing_capabilities"]
        assert "scaffolding" not in go_entry["missing_capabilities"]
        assert "dead_code" not in go_entry["missing_capabilities"]
