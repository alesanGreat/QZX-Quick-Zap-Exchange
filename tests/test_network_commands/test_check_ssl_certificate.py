#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Tests for the CheckSslCertificate command
"""

import socket
import ssl
from unittest.mock import patch, MagicMock
from datetime import datetime, timezone, timedelta
from qzx.commands.network.check_ssl_certificate import CheckSslCertificateCommand

class TestCheckSslCertificateCommand:
    """
    Tests for the CheckSslCertificate command
    """
    
    def setup_method(self):
        """Setup for each test"""
        self.command = CheckSslCertificateCommand()
        
    def test_empty_host(self):
        """Test with empty host name"""
        result = self.command.execute("")
        assert result["success"] is False
        assert "must not be empty" in result["error"]
        
    def test_invalid_port_type(self):
        """Test with invalid port argument"""
        result = self.command.execute("google.com", "not_a_port")
        assert result["success"] is False
        assert "Port must be an integer" in result["error"]
        
    @patch("socket.create_connection")
    @patch("ssl.create_default_context")
    def test_successful_ssl_inspect(self, mock_ssl_context, mock_socket_conn):
        """Test inspecting a valid SSL certificate with mock socket peer cert details"""
        # Configure peer certificate mock data
        expiry_date = datetime.now(timezone.utc) + timedelta(days=90)
        start_date = datetime.now(timezone.utc) - timedelta(days=10)
        
        # SSL dates format: 'Feb 15 12:00:00 2027 GMT'
        expiry_str = expiry_date.strftime("%b %d %H:%M:%S %Y GMT")
        start_str = start_date.strftime("%b %d %H:%M:%S %Y GMT")
        
        mock_cert = {
            "subject": ((("commonName", "google.com"),),),
            "issuer": ((("commonName", "Google Trust Services"),),),
            "notBefore": start_str,
            "notAfter": expiry_str,
            "subjectAltName": (("DNS", "google.com"), ("DNS", "*.google.com"))
        }
        
        # Configure context and wrapped socket mock
        mock_wrapped_sock = MagicMock()
        mock_wrapped_sock.getpeercert.return_value = mock_cert
        mock_wrapped_sock.cipher.return_value = ("AES256-GCM-SHA384", "TLSv1.3", 256)
        mock_wrapped_sock.version.return_value = "TLSv1.3"
        
        mock_context = MagicMock()
        mock_context.wrap_socket.return_value.__enter__.return_value = mock_wrapped_sock
        mock_ssl_context.return_value = mock_context
        
        result = self.command.execute("google.com", 443)
        
        assert result["success"] is True
        assert result["host"] == "google.com"
        assert result["port"] == 443
        assert result["is_valid"] is True
        assert result["is_expired"] is False
        assert result["hostname_match"] is True
        assert result["days_remaining"] == 89 or result["days_remaining"] == 90
        assert result["subject"]["commonName"] == "google.com"
        assert result["issuer"]["commonName"] == "Google Trust Services"
        assert "TLSv1.3" in result["ssl_version"]
        assert result["cipher_suite"] == "AES256-GCM-SHA384"
        assert "VALID" in result["message"]
        
    @patch("socket.create_connection")
    @patch("ssl.create_default_context")
    def test_expired_ssl_inspect(self, mock_ssl_context, mock_socket_conn):
        """Test behavior when a certificate has expired"""
        expiry_date = datetime.now(timezone.utc) - timedelta(days=5)
        start_date = datetime.now(timezone.utc) - timedelta(days=100)
        
        mock_cert = {
            "subject": ((("commonName", "expired.com"),),),
            "issuer": ((("commonName", "Mock Issuer"),),),
            "notBefore": start_date.strftime("%b %d %H:%M:%S %Y GMT"),
            "notAfter": expiry_date.strftime("%b %d %H:%M:%S %Y GMT"),
            "subjectAltName": (("DNS", "expired.com"),)
        }
        
        mock_wrapped_sock = MagicMock()
        mock_wrapped_sock.getpeercert.return_value = mock_cert
        mock_wrapped_sock.cipher.return_value = ("AES128-GCM-SHA256", "TLSv1.2", 128)
        mock_wrapped_sock.version.return_value = "TLSv1.2"
        
        mock_context = MagicMock()
        mock_context.wrap_socket.return_value.__enter__.return_value = mock_wrapped_sock
        mock_ssl_context.return_value = mock_context
        
        result = self.command.execute("expired.com")
        
        assert result["success"] is True
        assert result["is_valid"] is False
        assert result["is_expired"] is True
        assert result["days_remaining"] < 0
        assert "EXPIRED" in result["message"]
