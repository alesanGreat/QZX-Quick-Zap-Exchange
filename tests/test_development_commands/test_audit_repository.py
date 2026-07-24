#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Tests for the AuditRepository command
"""

import os
from qzx.commands.development.audit_repository import AuditRepositoryCommand

class TestAuditRepositoryCommand:
    """
    Tests for the AuditRepository command
    """
    
    def setup_method(self):
        """Setup for each test"""
        self.command = AuditRepositoryCommand()
        
    def test_audit_repository_nonexistent_path(self):
        """Test auditing a path that doesn't exist"""
        result = self.command.execute(path="nonexistent_folder_xyz")
        assert result["success"] is False
        assert "does not exist" in result["error"]
        
    def test_audit_repository_license_and_gitignore(self, tmp_path):
        """Test detection of missing LICENSE and .gitignore"""
        result = self.command.execute(path=str(tmp_path))
        assert result["success"] is True
        details = result["details"]
        assert details["license"] == "missing"
        
        # Check gitignore issues
        git_issues = [gi["issue"] for gi in details["gitignore_issues"]]
        assert "no_gitignore" in git_issues
        
        # Verify findings list has license and gitignore findings
        cats = [f["category"] for f in details["summary"]["findings"]]
        assert "license" in cats
        assert "gitignore" in cats
        
    def test_audit_repository_secrets_detection(self, tmp_path):
        """Test detection of hardcoded secrets in files"""
        # Create a mock code file with a secret
        code_file = tmp_path / "app.py"
        synthetic_google_key = "".join(
            ("AI", "za", "Sy", "FakeGoogleApiKey", "12345678901234567")
        )
        code_file.write_text(
            f"API_KEY = '{synthetic_google_key}'\n",
            encoding="utf-8",
        )
        
        # Create a LICENSE file
        license_file = tmp_path / "LICENSE"
        license_file.write_text("MIT License")
        
        # Create a .gitignore file
        gitignore = tmp_path / ".gitignore"
        gitignore.write_text("node_modules\n.env\n__pycache__\ndist\nbuild\n")
        
        result = self.command.execute(path=str(tmp_path))
        assert result["success"] is True
        details = result["details"]
        
        # Secret should be found
        assert len(details["secrets"]) >= 1
        assert any(s["file"] == "app.py" and "Google API Key" in s["type"] for s in details["secrets"])
        assert all("FakeGoogleApiKey" not in s["context"] for s in details["secrets"])
        
        # License should be found
        assert details["license"] == "LICENSE"
        
        # Gitignore should have no issues
        assert len(details["gitignore_issues"]) == 0
        
        # Risk level should be critical due to secret
        assert details["summary"]["risk_level"] == "critical"
