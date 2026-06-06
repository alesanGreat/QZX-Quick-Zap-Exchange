#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Tests for the CheckDns command
"""

import subprocess
from unittest.mock import patch, MagicMock
from qzx.commands.network.check_dns import CheckDnsCommand

class TestCheckDnsCommand:
    """
    Tests for the CheckDns command
    """
    
    def setup_method(self):
        """Setup for each test"""
        self.command = CheckDnsCommand()
        
    def test_empty_domain(self):
        """Test with empty domain"""
        result = self.command.execute("")
        assert result["success"] is False
        assert "must not be empty" in result["error"]
        
    @patch("socket.getaddrinfo")
    @patch("subprocess.run")
    def test_successful_dns_queries(self, mock_run, mock_getaddrinfo):
        """Test resolving all standard DNS records with mock outputs"""
        # Mock socket.getaddrinfo for basic A/AAAA
        mock_getaddrinfo.return_value = [
            (None, None, None, None, ("142.250.190.46", 0)),
            (None, None, None, None, ("2607:f8b0:4005:805::200e", 0))
        ]
        
        # Configure subprocess mocks for each record type query
        # MX mock
        mx_mock = MagicMock(returncode=0, stdout="google.com mail exchanger = 10 smtp.google.com\n")
        # TXT mock
        txt_mock = MagicMock(returncode=0, stdout='google.com text = "v=spf1 include:_spf.google.com ~all"\n')
        # NS mock
        ns_mock = MagicMock(returncode=0, stdout="google.com nameserver = ns1.google.com\n")
        # CNAME mock
        cname_mock = MagicMock(returncode=0, stdout="")
        # A mock
        a_mock = MagicMock(returncode=0, stdout="Name: google.com\nAddress: 142.250.190.46\n")
        # AAAA mock
        aaaa_mock = MagicMock(returncode=0, stdout="Name: google.com\nAddress: 2607:f8b0:4005:805::200e\n")
        
        mock_run.side_effect = [
            mx_mock,
            txt_mock,
            ns_mock,
            cname_mock,
            a_mock,
            aaaa_mock
        ]
        
        result = self.command.execute("google.com")
        
        assert result["success"] is True
        assert result["domain"] == "google.com"
        
        records = result["records"]
        assert "142.250.190.46" in records["A"]
        assert "2607:f8b0:4005:805::200e" in records["AAAA"]
        assert "10 smtp.google.com" in records["MX"]
        assert "v=spf1 include:_spf.google.com ~all" in records["TXT"]
        assert "ns1.google.com" in records["NS"]
        assert len(records["CNAME"]) == 0
        
        assert result["summary"]["MX"] == 1
        assert "TXT" in result["message"]
