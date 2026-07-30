"""Tests for testInternetSpeed over real HTTP connections and streams."""

import socket

from qzx.commands.network.test_internet_speed import TestInternetSpeedCommand


def _unused_local_url():
    with socket.socket() as reserved_socket:
        reserved_socket.bind(("127.0.0.1", 0))
        host, port = reserved_socket.getsockname()
    return f"http://{host}:{port}"


class TestInternetSpeedCommandSuite:
    def setup_method(self):
        self.command = TestInternetSpeedCommand()

    def test_speed_measurement_reads_a_real_http_stream(self, local_http_server):
        self.command.LATENCY_URL = f"{local_http_server}/latency"
        self.command.TEST_URL = f"{local_http_server}/download"

        result = self.command.execute(max_seconds=5)

        assert result["success"] is True
        assert result["latency"]["average"] > 0
        assert result["latency"]["minimum"] > 0
        assert result["download"]["megabits_per_second"] > 0
        assert result["download"]["mebibytes_per_second"] > 0
        assert result["download"]["bytes_downloaded"] > 1_000_000
        assert result["download"]["duration_seconds"] > 0
        assert (
            f"({result['download']['mebibytes_per_second']:.2f} MiB/s)"
            in result["message"]
        )
        assert "Web speed test measured" in result["message"]

    def test_download_failure_comes_from_a_real_refused_connection(
        self,
        local_http_server,
    ):
        self.command.LATENCY_URL = f"{local_http_server}/latency"
        self.command.TEST_URL = _unused_local_url()

        result = self.command.execute(max_seconds=1)

        assert result["success"] is False
        assert result["error_code"] == "download_measurement_failed"
        assert result["error"]
        assert "could not measure" in result["message"].lower()

    def test_configured_public_endpoints_really_transfer_data(self):
        result = self.command.execute(max_seconds=0.05)

        assert result["success"] is True
        assert result["latency"]["average"] > 0
        assert result["download"]["bytes_downloaded"] > 0
        assert result["download"]["duration_seconds"] > 0

    def test_invalid_duration_fails_closed(self):
        result = self.command.execute(max_seconds=0)

        assert result["success"] is False
        assert result["error_code"] == "invalid_max_seconds"
