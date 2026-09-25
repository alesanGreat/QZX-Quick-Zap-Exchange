"""Atomic HTTP transfer and result assembly for downloadFile."""

from __future__ import annotations

import hashlib
import os
import sys
import tempfile
import time
import urllib.request


USER_AGENT = "QZX/0.2 (+https://qzx.yumbale.com/)"
CHUNK_SIZE = 64 * 1024


def download_prepared_file(command, request):
    """Transfer one prepared HTTP request into its destination atomically."""
    temporary_path = None
    try:
        temporary_path = _temporary_path(request)
        transfer = _stream_http_response(
            command,
            request,
            temporary_path,
        )
        os.replace(temporary_path, request["destination"])
        temporary_path = None
        if request["show_progress"]:
            print()
        return _success_result(command, request, transfer)
    except Exception as exc:
        return _download_failure(request, exc)
    finally:
        if temporary_path and os.path.exists(temporary_path):
            os.unlink(temporary_path)


def _temporary_path(request):
    descriptor, temporary_path = tempfile.mkstemp(
        prefix=".qzx-download-",
        suffix=".part",
        dir=request["destination_dir"] or None,
    )
    os.close(descriptor)
    return temporary_path


def _stream_http_response(command, request, temporary_path):
    http_request = urllib.request.Request(
        request["url"],
        headers={"User-Agent": USER_AGENT},
    )
    sha256 = hashlib.sha256()
    state = {
        "response_status": None,
        "final_url": request["url"],
        "content_type": None,
        "expected_size": None,
        "file_size": 0,
        "started_monotonic": time.monotonic(),
    }
    with open(temporary_path, "wb") as destination_file:
        _read_response(command, request, http_request, destination_file, sha256, state)
        destination_file.flush()
        os.fsync(destination_file.fileno())
    if (
        state["expected_size"] is not None
        and state["file_size"] != state["expected_size"]
    ):
        raise OSError(
            "response ended after {} bytes; expected {}".format(
                state["file_size"],
                state["expected_size"],
            )
        )
    state["sha256"] = sha256.hexdigest()
    return state


def _read_response(
    command,
    request,
    http_request,
    destination_file,
    sha256,
    state,
):
    with urllib.request.urlopen(  # nosec B310 - URL validated before this call.
        http_request,
        timeout=request["timeout"],
    ) as response:
        _response_metadata(command, response, state)
        while True:
            chunk = response.read(CHUNK_SIZE)
            if not chunk:
                break
            destination_file.write(chunk)
            sha256.update(chunk)
            state["file_size"] += len(chunk)
            if request["show_progress"]:
                _show_progress(command, state)


def _response_metadata(command, response, state):
    final_url = response.geturl()
    command._validated_http_url(final_url)
    state["final_url"] = final_url
    state["response_status"] = getattr(response, "status", None)
    state["content_type"] = response.headers.get_content_type()
    content_length = response.headers.get("Content-Length")
    if content_length:
        try:
            state["expected_size"] = int(content_length)
        except ValueError:
            state["expected_size"] = None


def _show_progress(command, state):
    elapsed = max(time.monotonic() - state["started_monotonic"], 0.001)
    speed = state["file_size"] / elapsed
    expected_size = state["expected_size"]
    if expected_size and expected_size > 0:
        percent = min(100.0, state["file_size"] * 100 / expected_size)
        progress = (
            f"{percent:.1f}% "
            f"({command._format_bytes(state['file_size'])} / "
            f"{command._format_bytes(expected_size)})"
        )
    else:
        progress = command._format_bytes(state["file_size"])
    sys.stdout.write(
        "\rDownloading: "
        f"{progress} at {command._format_bytes(speed)}/s"
    )
    sys.stdout.flush()


def _success_result(command, request, transfer):
    file_size = transfer["file_size"]
    file_size_readable = command._format_bytes(file_size)
    download_time = time.time() - request["start_time"]
    if download_time > 0:
        avg_speed = file_size / download_time
        avg_speed_readable = command._format_bytes(avg_speed) + "/s"
    else:
        avg_speed = None
        avg_speed_readable = "N/A"
    return {
        "url": request["url"],
        "destination": request["destination"],
        "show_progress": request["show_progress"],
        "timeout": request["timeout"],
        "overwrite": request["overwrite"],
        "start_time": request["start_time"],
        "success": True,
        "final_url": transfer["final_url"],
        "http_status": transfer["response_status"],
        "content_type": transfer["content_type"],
        "expected_size": transfer["expected_size"],
        "file_size": file_size,
        "file_size_readable": file_size_readable,
        "sha256": transfer["sha256"],
        "download_time": download_time,
        "download_time_readable": f"{download_time:.2f} seconds",
        "avg_speed": avg_speed,
        "avg_speed_readable": avg_speed_readable,
        "message": (
            f"Downloaded {transfer['final_url']} to {request['destination']} "
            f"({file_size_readable}, SHA-256 {transfer['sha256']})."
        ),
    }


def _download_failure(request, exc):
    return {
        "success": False,
        "error_code": "download_failed",
        "url": request["url"],
        "destination": request["destination"],
        "error": f"{type(exc).__name__}: {exc}",
        "message": (
            f"Download from '{request['url']}' failed before the destination "
            f"was replaced: {exc}"
        ),
        "details": {
            "timeout_seconds": request["timeout"],
            "partial_file_removed": True,
        },
    }
