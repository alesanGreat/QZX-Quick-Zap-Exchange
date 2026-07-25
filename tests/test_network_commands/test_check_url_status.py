"""Tests for the checkUrlStatus command using real HTTP connections."""

import socket

from qzx.commands.network.check_url_status import CheckUrlStatusCommand


def _unused_local_url():
    with socket.socket() as reserved_socket:
        reserved_socket.bind(("127.0.0.1", 0))
        host, port = reserved_socket.getsockname()
    return f"http://{host}:{port}"


class TestCheckUrlStatusCommand:
    def setup_method(self):
        self.command = CheckUrlStatusCommand()

    def test_empty_url(self):
        result = self.command.execute("")

        assert result["success"] is False
        assert "cannot be empty" in result["error"]

    def test_missing_protocol_uses_real_https_endpoint(self):
        result = self.command.execute("example.com", timeout=10)

        assert result["success"] is True
        assert result["url"] == "https://example.com"
        assert result["is_online"] is True
        assert result["status_code"] == 200
        assert result["response_time_ms"] > 0

    def test_real_local_http_success(self, local_http_server):
        result = self.command.execute(f"{local_http_server}/ok", timeout=3.5)

        assert result["success"] is True
        assert result["is_online"] is True
        assert result["status_code"] == 200
        assert result["reason"] == "OK"
        assert result["headers"]["Content-Type"] == "text/plain"
        assert int(result["headers"]["Content-Length"]) == 2
        assert result["response_time_ms"] > 0
        assert "is ONLINE" in result["message"]

    def test_real_local_http_error(self, local_http_server):
        result = self.command.execute(f"{local_http_server}/not-found")

        assert result["success"] is True
        assert result["is_online"] is False
        assert result["status_code"] == 404
        assert result["reason"] == "Not Found"
        assert result["headers"]["Content-Type"] == "text/plain"
        assert "responded with client/server error" in result["message"]

    def test_real_connection_refusal(self):
        result = self.command.execute(_unused_local_url(), timeout=1)

        assert result["success"] is True
        assert result["is_online"] is False
        assert "status_code" not in result
        assert "Connection Failed" in result["error"]
        assert "is OFFLINE" in result["message"]

    def test_real_tls_handshake_failure(self, local_http_server):
        plain_http_target = local_http_server.removeprefix("http://")
        result = self.command.execute(
            f"https://{plain_http_target}/ok",
            timeout=2,
        )

        assert result["success"] is True
        assert result["is_online"] is False
        assert "error" in result
        assert "is OFFLINE" in result["message"]
