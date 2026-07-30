"""Real-loopback regression tests for downloadFile."""

import contextlib
import hashlib
import http.server
import threading
import zipfile

from qzx.commands.file.download_file import DownloadFileCommand


class _DownloadHandler(http.server.BaseHTTPRequestHandler):
    payload = b"QZX download regression payload\n"

    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(self.payload)))
        self.end_headers()
        self.wfile.write(self.payload)

    def log_message(self, format, *args):
        return


@contextlib.contextmanager
def _download_server():
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), _DownloadHandler)
    server.daemon_threads = True
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}/payload.txt"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def test_download_uses_real_http_and_reports_integrity(tmp_path):
    destination = tmp_path / "nested" / "payload.txt"
    with _download_server() as url:
        result = DownloadFileCommand().invoke(
            [url, str(destination), "--no-show-progress"]
        )

    assert result["success"] is True
    assert destination.read_bytes() == _DownloadHandler.payload
    assert result["http_status"] == 200
    assert result["file_size"] == len(_DownloadHandler.payload)
    assert result["sha256"] == hashlib.sha256(
        _DownloadHandler.payload
    ).hexdigest()


def test_download_rejects_non_http_urls_without_creating_destination(tmp_path):
    destination = tmp_path / "copied.txt"
    source = tmp_path / "private.txt"
    source.write_text("private", encoding="utf-8")

    result = DownloadFileCommand().invoke(
        [source.as_uri(), str(destination), "--no-show-progress"]
    )

    assert result["success"] is False
    assert result["error_code"] == "invalid_url"
    assert result["details"]["allowed_schemes"] == ["http", "https"]
    assert not destination.exists()


def test_existing_destination_is_preserved_without_overwrite(tmp_path):
    destination = tmp_path / "payload.txt"
    destination.write_text("original", encoding="utf-8")
    with _download_server() as url:
        result = DownloadFileCommand().invoke(
            [url, str(destination), "--no-show-progress"]
        )

    assert result["success"] is False
    assert result["error_code"] == "destination_exists"
    assert destination.read_text(encoding="utf-8") == "original"


def test_overwrite_creates_backup_before_replacing_file(
    monkeypatch,
    tmp_path,
):
    destination = tmp_path / "payload.txt"
    destination.write_text("original", encoding="utf-8")
    backup_directory = tmp_path / "backups"
    monkeypatch.setenv("QZX_BACKUPS_PATH", str(backup_directory))

    with _download_server() as url:
        result = DownloadFileCommand().invoke(
            [
                url,
                str(destination),
                "--no-show-progress",
                "--overwrite",
            ]
        )

    assert result["success"] is True
    assert destination.read_bytes() == _DownloadHandler.payload
    backup = result["meta"]["safety_backup"]
    assert backup["status"] == "created"
    assert backup["source_exists"] is True
    with zipfile.ZipFile(backup["path"]) as archive:
        stored_files = [
            name
            for name in archive.namelist()
            if name != "__qzx_backup_manifest__.json"
        ]
        assert len(stored_files) == 1
        assert archive.read(stored_files[0]) == b"original"
