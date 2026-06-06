#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Tests for the InspectPort command
"""

import sys
from unittest.mock import MagicMock, patch
from qzx.commands.system.inspect_port import InspectPortCommand

class TestInspectPortCommand:
    """
    Tests for the InspectPort command
    """
    
    def setup_method(self):
        """Setup for each test"""
        self.command = InspectPortCommand()
        
    def test_invalid_port_type(self):
        """Test handling of invalid port string"""
        result = self.command.execute("not_a_port")
        assert result["success"] is False
        assert "Port must be an integer" in result["error"]
        
    @patch("psutil.net_connections")
    def test_port_free(self, mock_net_conns):
        """Test with a port that is currently free"""
        # Return connections on other ports
        conn1 = MagicMock()
        conn1.laddr.port = 8080
        conn1.pid = 1111
        
        mock_net_conns.return_value = [conn1]
        
        result = self.command.execute(3000)
        assert result["success"] is True
        assert result["port"] == 3000
        assert result["in_use"] is False
        assert result["killed"] is False
        assert "free" in result["message"]
        
    @patch("psutil.Process")
    @patch("psutil.net_connections")
    def test_port_in_use_inspect_only(self, mock_net_conns, mock_process_class):
        """Test inspecting a port in use without killing the process"""
        # Connection on target port
        conn = MagicMock()
        conn.laddr.port = 3000
        conn.pid = 1234
        mock_net_conns.return_value = [conn]
        
        # Mock process info
        mock_proc = MagicMock()
        mock_proc.name.return_value = "node"
        mock_proc.status.return_value = "running"
        mock_proc.exe.return_value = "/usr/bin/node"
        mock_proc.cmdline.return_value = ["node", "server.js"]
        mock_proc.username.return_value = "testuser"
        
        mem_info = MagicMock()
        mem_info.rss = 1024 * 1024 * 20  # 20 MB
        mock_proc.memory_info.return_value = mem_info
        
        mock_process_class.return_value = mock_proc
        
        result = self.command.execute(3000, kill="false")
        
        assert result["success"] is True
        assert result["port"] == 3000
        assert result["in_use"] is True
        assert result["killed"] is False
        assert len(result["processes"]) == 1
        
        proc_info = result["processes"][0]
        assert proc_info["pid"] == 1234
        assert proc_info["name"] == "node"
        assert proc_info["status"] == "running"
        assert proc_info["exe"] == "/usr/bin/node"
        assert proc_info["cmdline"] == ["node", "server.js"]
        assert proc_info["username"] == "testuser"
        assert proc_info["memory_usage"]["rss"] == 1024 * 1024 * 20
        assert proc_info["memory_usage"]["rss_readable"] == "20.00 MB"
        
        # Ensure process was NOT killed
        mock_proc.kill.assert_not_called()
        
    @patch("psutil.Process")
    @patch("psutil.net_connections")
    def test_port_in_use_and_kill(self, mock_net_conns, mock_process_class):
        """Test inspecting a port in use and successfully terminating the process"""
        # Connection on target port
        conn = MagicMock()
        conn.laddr.port = 3000
        conn.pid = 1234
        mock_net_conns.return_value = [conn]
        
        mock_proc = MagicMock()
        mock_proc.name.return_value = "node"
        mock_proc.status.return_value = "running"
        mock_process_class.return_value = mock_proc
        
        result = self.command.execute(3000, kill="true")
        
        assert result["success"] is True
        assert result["port"] == 3000
        assert result["in_use"] is True
        assert result["killed"] is True
        assert 1234 in result["killed_pids"]
        
        # Verify process.kill() was called
        mock_proc.kill.assert_called_once()
        
    @patch("platform.system")
    @patch("subprocess.run")
    def test_fallback_windows_free(self, mock_run, mock_system):
        """Test fallback implementation when psutil is not available on Windows"""
        mock_system.return_value = "Windows"
        
        # Mock netstat -ano output with a different port
        netstat_output = (
            "  Proto  Local Address          Foreign Address        State           PID\n"
            "  TCP    0.0.0.0:8080           0.0.0.0:0              LISTENING       4444\n"
        )
        
        netstat_mock = MagicMock()
        netstat_mock.returncode = 0
        netstat_mock.stdout = netstat_output
        mock_run.return_value = netstat_mock
        
        # Run with psutil imports blocked
        with patch.dict(sys.modules, {'psutil': None}):
            result = self.command.execute(3000)
            
        assert result["success"] is True
        assert result["port"] == 3000
        assert result["in_use"] is False
        assert "free" in result["message"]
        
    @patch("platform.system")
    @patch("subprocess.run")
    def test_fallback_windows_in_use(self, mock_run, mock_system):
        """Test fallback implementation on Windows when port is in use"""
        mock_system.return_value = "Windows"
        
        # Mock netstat -ano output containing target port
        netstat_output = (
            "  Proto  Local Address          Foreign Address        State           PID\n"
            "  TCP    0.0.0.0:3000           0.0.0.0:0              LISTENING       1234\n"
        )
        netstat_mock = MagicMock(returncode=0, stdout=netstat_output)
        
        # Mock tasklist lookup
        tasklist_output = (
            "Image Name                     PID Session Name        Session#    Mem Usage\n"
            "========================= ======== ================ =========== ============\n"
            "node.exe                      1234 Console                    1     20,480 K\n"
        )
        tasklist_mock = MagicMock(returncode=0, stdout=tasklist_output)
        
        # Mock taskkill for termination
        taskkill_mock = MagicMock(returncode=0, stdout="SUCCESS: Sent termination signal to process with PID 1234.\n")
        
        mock_run.side_effect = [netstat_mock, tasklist_mock, taskkill_mock]
        
        with patch.dict(sys.modules, {'psutil': None}):
            result = self.command.execute(3000, kill="true")
            
        assert result["success"] is True
        assert result["port"] == 3000
        assert result["in_use"] is True
        assert result["killed"] is True
        assert 1234 in result["killed_pids"]
        assert result["processes"][0]["name"] == "node.exe"
