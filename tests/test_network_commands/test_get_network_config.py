#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Tests for the GetNetworkConfig command
"""

import subprocess
import urllib.request
import json
from unittest.mock import patch, MagicMock
from qzx.commands.network.get_network_config import GetNetworkConfigCommand

class TestGetNetworkConfigCommand:
    """
    Tests for the GetNetworkConfig command
    """
    
    def setup_method(self):
        """Setup for each test"""
        self.command = GetNetworkConfigCommand()
        
    @patch("socket.gethostname")
    @patch("socket.gethostbyname_ex")
    @patch("urllib.request.urlopen")
    @patch("subprocess.run")
    @patch("platform.system")
    def test_windows_network_config_full(self, mock_system, mock_run, mock_urlopen, mock_gethostbyname_ex, mock_gethostname):
        """Test retrieving network configuration on Windows with mock command outputs and public API responses"""
        mock_system.return_value = "Windows"
        mock_gethostname.return_value = "my-laptop"
        mock_gethostbyname_ex.return_value = ("my-laptop", [], ["192.168.1.15"])
        
        # Mock public IP response from ipinfo.io
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({
            "ip": "203.0.113.50",
            "country": "US",
            "region": "California",
            "city": "San Francisco",
            "org": "AS15133 MCI Communications Services, Inc."
        }).encode("utf-8")
        mock_urlopen.return_value.__enter__.return_value = mock_response
        
        # Mock ipconfig /all output containing active Ethernet and active VPN (TAP)
        ipconfig_output = (
            "Windows IP Configuration\n"
            "   Host Name . . . . . . . . . . . . : my-laptop\n"
            "   Primary Dns Suffix  . . . . . . . :\n"
            "\n"
            "Ethernet adapter Ethernet:\n"
            "   Connection-specific DNS Suffix  . : lan\n"
            "   Description . . . . . . . . . . . : Realtek PCIe GBE Family Controller\n"
            "   Physical Address. . . . . . . . . : AA-BB-CC-DD-EE-FF\n"
            "   DHCP Enabled. . . . . . . . . . . : Yes\n"
            "   IPv4 Address. . . . . . . . . . . : 192.168.1.15(Preferred)\n"
            "   IPv6 Address. . . . . . . . . . . : fe80::1234:5678:9abc:def0%4(Preferred)\n"
            "   Default Gateway . . . . . . . . . : 192.168.1.1\n"
            "   DNS Servers . . . . . . . . . . . : 1.1.1.1\n"
            "                                       8.8.8.8\n"
            "\n"
            "Ethernet adapter tun0:\n"
            "   Description . . . . . . . . . . . : TAP-Windows Adapter V9\n"
            "   Physical Address. . . . . . . . . : 00-FF-AA-BB-CC-DD\n"
            "   IPv4 Address. . . . . . . . . . . : 10.8.0.6(Preferred)\n"
        )
        
        ipconfig_mock = MagicMock(returncode=0, stdout=ipconfig_output)
        mock_run.return_value = ipconfig_mock
        
        result = self.command.execute(check_public="true")
        
        assert result["success"] is True
        assert result["hostname"] == "my-laptop"
        assert "192.168.1.15" in result["local_ips"]
        assert "1.1.1.1" in result["dns_servers"]
        assert "8.8.8.8" in result["dns_servers"]
        
        # Verify interfaces parsed
        interfaces = result["interfaces"]
        assert "Ethernet" in interfaces
        assert interfaces["Ethernet"]["mac"] == "AA-BB-CC-DD-EE-FF"
        assert interfaces["Ethernet"]["description"] == "Realtek PCIe GBE Family Controller"
        assert "192.168.1.15" in interfaces["Ethernet"]["ipv4"]
        
        # Verify VPN detected
        assert result["vpn"]["active"] is True
        assert "tun0" in result["vpn"]["detected_interfaces"]
        
        # Verify public details
        assert result["public"]["ip"] == "203.0.113.50"
        assert result["public"]["city"] == "San Francisco"
        assert result["public"]["country"] == "US"
        assert "MCI Communications" in result["public"]["isp"]
        
        assert "VPN Detected: YES" in result["message"]
        
    @patch("socket.gethostname")
    @patch("socket.gethostbyname_ex")
    @patch("subprocess.run")
    @patch("platform.system")
    def test_local_only_and_not_vpn(self, mock_system, mock_run, mock_gethostbyname_ex, mock_gethostname):
        """Test retrieving network configuration locally only, verifying vpn is false when no active VPN adapter has IPs"""
        mock_system.return_value = "Windows"
        mock_gethostname.return_value = "workstation"
        mock_gethostbyname_ex.return_value = ("workstation", [], ["10.0.0.50"])
        
        # Mock ipconfig /all output without active VPN IP addresses
        ipconfig_output = (
            "Windows IP Configuration\n"
            "Ethernet adapter Wi-Fi:\n"
            "   IPv4 Address. . . . . . . . . . . : 10.0.0.50(Preferred)\n"
            "   DNS Servers . . . . . . . . . . . : 192.168.1.1\n"
        )
        
        ipconfig_mock = MagicMock(returncode=0, stdout=ipconfig_output)
        mock_run.return_value = ipconfig_mock
        
        result = self.command.execute(check_public="false")
        
        assert result["success"] is True
        assert result["vpn"]["active"] is False
        assert result["public"] is None
        assert "VPN Detected: NO" in result["message"]
