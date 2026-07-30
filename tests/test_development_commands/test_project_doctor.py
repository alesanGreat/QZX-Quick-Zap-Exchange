#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Tests for the ProjectDoctor command
"""

from qzx.commands.development.project_doctor import ProjectDoctorCommand

class TestProjectDoctorCommand:
    """
    Tests for the ProjectDoctor command
    """
    
    def setup_method(self):
        """Setup for each test"""
        self.command = ProjectDoctorCommand()
        
    def test_project_doctor_nonexistent_path(self):
        """Test with nonexistent path"""
        result = self.command.execute(path="nonexistent_folder_xyz")
        assert result["success"] is False
        assert "does not exist" in result["error"]
        
    def test_project_doctor_python_stack(self, tmp_path):
        """Test project doctor diagnosis on a mock Python project"""
        # Create pyproject.toml
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text("[project]\nname = 'test'\n")
        
        # Create requirements.txt
        reqs = tmp_path / "requirements.txt"
        reqs.write_text("pytest>=7.0\n")
        
        # Create .env.example and .env
        env_ex = tmp_path / ".env.example"
        env_ex.write_text("PORT=8000\n")
        
        # Run command
        result = self.command.execute(path=str(tmp_path))
        assert result["success"] is True
        details = result["details"]
        
        # Stack should contain Python
        assert "Python" in details["stack"]
        
        # Manifests found
        assert "pyproject.toml" in details["dependencies"]["manifests_found"]
        assert "requirements.txt" in details["dependencies"]["manifests_found"]
        
        # Environment status
        assert details["environment"]["env_file_present"] is False
        assert details["environment"]["env_example_present"] is True
        
        # Missing .env should be flagged in issues
        issue_titles = [issue["title"] for issue in details["summary"]["issues"]]
        assert "Missing .env file" in issue_titles
