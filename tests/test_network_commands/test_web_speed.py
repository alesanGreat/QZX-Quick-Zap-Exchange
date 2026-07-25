#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Tests for the TestWebSpeed command
"""

from unittest.mock import patch, MagicMock
from qzx.commands.network.test_web_speed import TestWebSpeedCommand

class TestWebSpeedCommandSuite:
    """
    Tests for the TestWebSpeed command
    """
    
    def setup_method(self):
        """Setup for each test"""
        self.command = TestWebSpeedCommand()
        
    @patch("urllib.request.urlopen")
    def test_speed_test_success(self, mock_urlopen):
        """Test successful execution of speed and latency checks with mocked HTTP download streams"""
        # 1. Mock connection for latency check (returns mock responses 3 times)
        latency_conn = MagicMock()
        latency_conn.read.return_value = b"OK"
        
        # 2. Mock connection for download speed check
        # First read returns 1 MB (1024 * 1024 bytes)
        # Second read returns empty bytes (EOF)
        download_conn = MagicMock()
        download_conn.read.side_effect = [b"A" * 1048576, b""]
        
        # side_effect order: 3 latency checks, then 1 download check
        mock_urlopen.return_value.__enter__.side_effect = [
            latency_conn,
            latency_conn,
            latency_conn,
            download_conn
        ]
        
        with patch(
            "qzx.commands.network.test_web_speed.time.perf_counter",
            side_effect=[0.0, 0.01, 1.0, 1.02, 2.0, 2.03, 3.0, 3.5],
        ):
            result = self.command.execute(max_seconds=5)
        
        assert result["success"] is True
        assert result["latency_ms"]["average"] is not None
        assert result["download_speed_mbps"] > 0
        assert (
            f"({result['download_speed_mbs']:.2f} MB/s)"
            in result["message"]
        )
        assert result["test_details"]["bytes_downloaded"] == 1048576
        assert result["test_details"]["duration_seconds"] == 0.5
        assert "Internet Speed Test Results" in result["message"]
        
    @patch("urllib.request.urlopen")
    def test_speed_test_download_failed(self, mock_urlopen):
        """Test speed test behavior when the download endpoint fails"""
        # Latency succeeds but download throws Exception
        latency_conn = MagicMock()
        latency_conn.read.return_value = b"OK"
        
        mock_urlopen.return_value.__enter__.side_effect = [
            latency_conn,
            latency_conn,
            latency_conn,
            Exception("Download stream connection reset")
        ]
        
        result = self.command.execute(max_seconds=3)
        
        assert result["success"] is False
        assert "Download stream connection reset" in result["error"]
        assert "failed" in result["message"]
