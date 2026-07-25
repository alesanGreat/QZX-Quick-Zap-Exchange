#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Tests for the SystemDoctor command
"""

from qzx.commands.system.system_doctor import SystemDoctorCommand


class TestSystemDoctorCommand:
    """
    Tests for the SystemDoctor command
    """

    def setup_method(self):
        """Setup for each test"""
        self.command = SystemDoctorCommand()

    def test_system_doctor_execute(self):
        """Test basic execution of systemDoctor"""
        result = self.command.execute(quick=True)
        assert result["success"] is True
        assert "details" in result
        details = result["details"]
        assert "cpu" in details
        assert "ram" in details
        assert "disk" in details
        assert "network" in details
        assert "path" in details
        assert "health_score" in details
        assert isinstance(details["health_score"], int)
        assert 0 <= details["health_score"] <= 100
        assert "recommendations" in details
        assert isinstance(details["recommendations"], list)

    def test_system_doctor_quick_parameter_parsing(self):
        """Test parsing of string quick parameters"""
        result_str = self.command.execute(quick="true")
        assert result_str["success"] is True

        result_str_false = self.command.execute(quick="false")
        assert result_str_false["success"] is True

    def test_health_score_maps_normalized_smart_results(self):
        """Test deterministic scoring from normalized QZX check results."""
        smart_results = {
            "status": "available",
            "drives": [
                {"disk": "disk-warning", "health_status": "WARNING"},
                {"disk": "disk-failed", "health_status": "FAILED"},
                {"disk": "disk-passed", "health_status": "PASSED"},
            ],
        }

        issues = self.command._smart_issues(smart_results)
        score, recommendations = self.command._score_issues(issues)

        assert [item[0] for item in issues] == [
            "Disk SMART Warning",
            "Disk SMART Failure",
        ]
        assert score == 70
        assert [item["title"] for item in recommendations] == [
            "Disk SMART Warning",
            "Disk SMART Failure",
        ]
        assert [item["severity"] for item in recommendations] == [
            "medium",
            "high",
        ]
