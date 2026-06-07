#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Tests for the SystemDoctor command
"""

import os
from unittest.mock import patch
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

    def test_system_doctor_smart_integration(self):
        """Test SMART health check integration with health_score and issues"""
        # Mock all system checks so the health score is deterministic (base = 100)
        static_ok = {"status": "ok"}
        with (
            patch.object(SystemDoctorCommand, '_check_cpu', return_value=static_ok),
            patch.object(SystemDoctorCommand, '_check_ram', return_value=static_ok),
            patch.object(SystemDoctorCommand, '_check_disk', return_value=static_ok),
            patch.object(SystemDoctorCommand, '_check_network', return_value=static_ok),
            patch.object(SystemDoctorCommand, '_check_path', return_value=static_ok),
            patch.object(SystemDoctorCommand, '_check_services', return_value=static_ok),
            patch.object(SystemDoctorCommand, '_check_ports', return_value=static_ok),
            patch.object(SystemDoctorCommand, '_check_startup', return_value=static_ok),
            patch.object(SystemDoctorCommand, '_check_errors', return_value=static_ok),
        ):
            # Scenario 0: SMART clean/passed to get base score
            mock_smart_clean = {
                "status": "available",
                "drives": [
                    {
                        "disk": "PhysicalDrive0",
                        "device_path": "\\\\.\\PhysicalDrive0",
                        "health_status": "PASSED",
                        "output": "PASSED"
                    }
                ]
            }
            with patch.object(SystemDoctorCommand, '_check_smart', return_value=mock_smart_clean):
                base_result = self.command.execute(quick=False)
                assert base_result["success"] is True
                base_score = base_result["details"]["health_score"]

            # Scenario 1: SMART reporting WARNING
            mock_smart_warning = {
                "status": "available",
                "drives": [
                    {
                        "disk": "PhysicalDrive0",
                        "device_path": "\\\\.\\PhysicalDrive0",
                        "health_status": "WARNING",
                        "output": "SMART overall-health self-assessment test result: WARNING"
                    }
                ]
            }

            with patch.object(SystemDoctorCommand, '_check_smart', return_value=mock_smart_warning):
                result = self.command.execute(quick=False)
                assert result["success"] is True
                details = result["details"]
                assert details["smart"] == mock_smart_warning
                # A WARNING should subtract 10 points from the clean base score
                assert details["health_score"] == max(0, base_score - 10)
                recommendation_titles = [r["title"] for r in details["recommendations"]]
                assert "Disk SMART Warning" in recommendation_titles

            # Scenario 2: SMART reporting FAILED
            mock_smart_failed = {
                "status": "available",
                "drives": [
                    {
                        "disk": "PhysicalDrive0",
                        "device_path": "\\\\.\\PhysicalDrive0",
                        "health_status": "FAILED",
                        "output": "SMART overall-health self-assessment test result: FAILED"
                    }
                ]
            }

            with patch.object(SystemDoctorCommand, '_check_smart', return_value=mock_smart_failed):
                result = self.command.execute(quick=False)
                assert result["success"] is True
                details = result["details"]
                assert details["smart"] == mock_smart_failed
                # A FAILED status should subtract 20 points from the clean base score
                assert details["health_score"] == max(0, base_score - 20)
                recommendation_titles = [r["title"] for r in details["recommendations"]]
                assert "Disk SMART Failure" in recommendation_titles
