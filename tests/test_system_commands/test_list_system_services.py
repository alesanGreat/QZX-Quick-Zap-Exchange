#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Tests for the ListSystemServices command
"""

import platform
import json
import subprocess
from unittest.mock import patch, MagicMock
from qzx.commands.system.list_system_services import ListSystemServicesCommand

class TestListSystemServicesCommand:
    """
    Tests for the ListSystemServices command
    """
    
    def setup_method(self):
        """Setup for each test"""
        self.command = ListSystemServicesCommand()
        
    @patch("platform.system")
    @patch("subprocess.run")
    def test_windows_services_powershell(self, mock_run, mock_system):
        """Test listing services on Windows using mock PowerShell JSON response"""
        mock_system.return_value = "Windows"
        
        # Mock JSON stdout
        ps_output = json.dumps([
            {"Name": "wuauserv", "DisplayName": "Windows Update", "Status": "Running"},
            {"Name": "Spooler", "DisplayName": "Print Spooler", "Status": "Stopped"}
        ])
        
        mock_res = MagicMock(returncode=0, stdout=ps_output)
        mock_run.return_value = mock_res
        
        # Test default 'all' filter
        result = self.command.execute()
        assert result["success"] is True
        assert result["total_services"] == 2
        
        # Verify ordering (alphabetical: Spooler comes before wuauserv)
        services = result["services"]
        assert services[0]["name"] == "Spooler"
        assert services[0]["status"] == "stopped"
        assert services[1]["name"] == "wuauserv"
        assert services[1]["status"] == "running"
        
        # Test 'running' filter
        result_running = self.command.execute(status="running")
        assert result_running["success"] is True
        assert result_running["total_services"] == 1
        assert result_running["services"][0]["name"] == "wuauserv"
        
    @patch("platform.system")
    @patch("subprocess.run")
    def test_windows_services_sc_fallback(self, mock_run, mock_system):
        """Test listing Windows services using sc query fallback parser when PowerShell fails"""
        mock_system.return_value = "Windows"
        
        # First call to PowerShell fails, second call to sc succeeds
        ps_fail = MagicMock(returncode=1, stdout="")
        
        sc_output = (
            "SERVICE_NAME: nginx\n"
            "DISPLAY_NAME: nginx\n"
            "TYPE               : 10  WIN32_OWN_PROCESS\n"
            "STATE              : 4  RUNNING\n"
            "                         (STOPPABLE, NOT_PAUSABLE, ACCEPTS_SHUTDOWN)\n"
            "\n"
            "SERVICE_NAME: wuauserv\n"
            "STATE              : 1  STOPPED\n"
        )
        sc_success = MagicMock(returncode=0, stdout=sc_output)
        
        mock_run.side_effect = [ps_fail, sc_success]
        
        result = self.command.execute()
        
        assert result["success"] is True
        assert len(result["errors"]) == 1  # PS error captured
        assert result["total_services"] == 2
        assert result["services"][0]["name"] == "nginx"
        assert result["services"][0]["status"] == "running"
        assert result["services"][1]["name"] == "wuauserv"
        assert result["services"][1]["status"] == "stopped"
        
    @patch("platform.system")
    @patch("subprocess.run")
    def test_linux_services_systemctl(self, mock_run, mock_system):
        """Test listing services on Linux using mock systemctl response"""
        mock_system.return_value = "Linux"
        
        systemctl_output = (
            "nginx.service                           loaded active running nginx web server\n"
            "cron.service                            loaded active running regular background program processing daemon\n"
            "ssh.service                             loaded active running OpenBSD Secure Shell server\n"
            "ufw.service                             loaded inactive dead   ufw firewall\n"
        )
        mock_res = MagicMock(returncode=0, stdout=systemctl_output)
        mock_run.return_value = mock_res
        
        result = self.command.execute()
        
        assert result["success"] is True
        assert result["total_services"] == 4
        
        # Check ufw state (inactive -> stopped)
        ufw = [s for s in result["services"] if s["name"] == "ufw.service"][0]
        assert ufw["status"] == "stopped"
        
        # Test 'running' filter
        result_running = self.command.execute(status="running")
        assert result_running["success"] is True
        assert result_running["total_services"] == 3
