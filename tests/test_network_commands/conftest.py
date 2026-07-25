"""Real local network services used by network command tests."""

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread

import pytest


class _TestHttpHandler(BaseHTTPRequestHandler):
    """Serve deterministic responses over a real TCP/HTTP connection."""

    protocol_version = "HTTP/1.1"
    download_body = b"QZX network test data\n" * 65536

    def do_GET(self):
        if self.path == "/not-found":
            body = b"not found"
            self.send_response(404)
            self.send_header("Content-Type", "text/plain")
        elif self.path == "/download":
            body = self.download_body
            self.send_response(200)
            self.send_header("Content-Type", "application/octet-stream")
        else:
            body = b"ok"
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")

        self.send_header("Content-Length", str(len(body)))
        self.send_header("Server", "QZX-real-test-server")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, _format, *_args):
        """Keep the test output focused on assertions."""


@pytest.fixture
def local_http_server():
    """Run a real HTTP server bound only to the test host."""

    server = ThreadingHTTPServer(("127.0.0.1", 0), _TestHttpHandler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        host, port = server.server_address
        yield f"http://{host}:{port}"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
