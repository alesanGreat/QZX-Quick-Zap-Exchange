#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Tests for the CheckUrlStatus command
"""

import urllib.request
import urllib.error
from unittest.mock import patch, MagicMock
from qzx.commands.network.check_url_status import CheckUrlStatusCommand

class TestCheckUrlStatusCommand:
    """
    Tests for the CheckUrlStatus command
    """
    
    def setup_method(self):
        """Setup for each test"""
        self.command = CheckUrlStatusCommand()
        
    def test_empty_url(self):
        """Test with an empty URL"""
        result = self.command.execute("")
        assert result["success"] is False
        assert "cannot be empty" in result["error"]
        
    @patch("urllib.request.urlopen")
    def test_missing_protocol(self, mock_urlopen):
        """Test that URL gets prepended with https:// if it has no protocol"""
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.msg = "OK"
        mock_response.headers = {}
        mock_urlopen.return_value.__enter__.return_value = mock_response
        
        result = self.command.execute("api.github.com")
        assert result["success"] is True
        assert result["url"] == "https://api.github.com"
        
    @patch("urllib.request.urlopen")
    def test_url_online_success(self, mock_urlopen):
        """Test check on an online URL returning 200 OK"""
        # Configure response mock
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.msg = "OK"
        mock_response.headers = {
            'Content-Type': 'application/json',
            'Content-Length': '150',
            'Server': 'GitHub.com'
        }
        mock_urlopen.return_value.__enter__.return_value = mock_response
        
        result = self.command.execute("https://api.github.com", timeout="3.5")
        
        assert result["success"] is True
        assert result["is_online"] is True
        assert result["status_code"] == 200
        assert result["reason"] == "OK"
        assert result["headers"]["Content-Type"] == "application/json"
        assert result["headers"]["Content-Length"] == "150"
        assert "is ONLINE" in result["message"]
        
    @patch("urllib.request.urlopen")
    def test_url_http_error(self, mock_urlopen):
        """Test check on a URL that returns an HTTP error status (e.g. 404)"""
        # Configure urlopen mock to raise HTTPError
        mock_headers = MagicMock()
        mock_headers.items.return_value = [('Content-Type', 'text/html')]
        
        http_error = urllib.error.HTTPError(
            url="https://api.github.com/invalid",
            code=404,
            msg="Not Found",
            hdrs=mock_headers,
            fp=None
        )
        mock_urlopen.side_effect = http_error
        
        result = self.command.execute("https://api.github.com/invalid")
        
        assert result["success"] is True
        assert result["is_online"] is False
        assert result["status_code"] == 404
        assert result["reason"] == "Not Found"
        assert result["headers"]["Content-Type"] == "text/html"
        assert "responded with client/server error" in result["message"]
        
    @patch("urllib.request.urlopen")
    def test_url_connection_failed(self, mock_urlopen):
        """Test check on a URL that has connection/DNS failure"""
        # Configure urlopen mock to raise URLError
        url_error = urllib.error.URLError(reason="Name or service not known")
        mock_urlopen.side_effect = url_error
        
        result = self.command.execute("https://nonexistent-server-xyz.com")
        
        assert result["success"] is True
        assert result["is_online"] is False
        assert "status_code" not in result
        assert "Connection Failed" in result["error"]
        assert "is OFFLINE" in result["message"]
        
    @patch("urllib.request.urlopen")
    def test_execute_exception_handling(self, mock_urlopen):
        """Test how the command handles generic unexpected errors"""
        mock_urlopen.side_effect = Exception("SSL verification failed")
        
        result = self.command.execute("https://expired-ssl.com")
        
        assert result["success"] is True
        assert result["is_online"] is False
        assert "Request Failed" in result["error"]
        assert "SSL verification failed" in result["error"]
        assert "is OFFLINE" in result["message"]
