"""Tests for testWebSpeed over real HTTP connections and streams."""

import socket

from qzx.commands.network.test_web_speed import TestWebSpeedCommand


def _unused_local_url():
    with socket.socket() as reserved_socket:
        reserved_socket.bind(("127.0.0.1", 0))
        host, port = reserved_socket.getsockname()
    return f"http://{host}:{port}"


class TestWebSpeedCommandSuite:
    def setup_method(self):
        self.command = TestWebSpeedCommand()

    def test_speed_measurement_reads_a_real_http_stream(self, local_http_server):
        self.command.LATENCY_URL = f"{local_http_server}/latency"
        self.command.TEST_URL = f"{local_http_server}/download"

        result = self.command.execute(max_seconds=5)

        assert result["success"] is True
        assert result["latency_ms"]["average"] > 0
        assert result["latency_ms"]["min"] > 0
        assert result["download_speed_mbps"] > 0
        assert result["download_speed_mbs"] > 0
        assert result["test_details"]["bytes_downloaded"] > 1_000_000
        assert result["test_details"]["duration_seconds"] > 0
        assert (
            f"({result['download_speed_mbs']:.2f} MB/s)"
            in result["message"]
        )
        assert "Internet Speed Test Results" in result["message"]

    def test_download_failure_comes_from_a_real_refused_connection(
        self,
        local_http_server,
    ):
        self.command.LATENCY_URL = f"{local_http_server}/latency"
        self.command.TEST_URL = _unused_local_url()

        result = self.command.execute(max_seconds=1)

        assert result["success"] is False
        assert result["error"]
        assert "failed" in result["message"].lower()

    def test_configured_public_endpoints_really_transfer_data(self):
        result = self.command.execute(max_seconds=0.05)

        assert result["success"] is True
        assert result["latency_ms"]["average"] > 0
        assert result["test_details"]["bytes_downloaded"] > 0
        assert result["test_details"]["duration_seconds"] > 0
