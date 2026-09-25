"""Bounded native-process execution for runDiagnosticCommand."""

from __future__ import annotations

import locale
import os
import subprocess
import threading
import time


def _subprocess_output_encoding():
    """Return the encoding used by redirected native console output."""
    if os.name == "nt":
        try:
            import ctypes

            code_page = ctypes.windll.kernel32.GetOEMCP()
            if code_page:
                return "cp{}".format(code_page)
        except (AttributeError, OSError):
            pass
    return locale.getpreferredencoding(False) or "utf-8"


class _BoundedStreamCapture:
    """Drain one pipe continuously while retaining only a byte budget."""

    def __init__(self, limit):
        self.limit = limit
        self.chunks = []
        self.retained_bytes = 0
        self.observed_bytes = 0
        self.read_error = None

    def consume(self, stream):
        try:
            while True:
                chunk = stream.read(8192)
                if not chunk:
                    break
                self.observed_bytes += len(chunk)
                remaining = self.limit - self.retained_bytes
                if remaining > 0:
                    retained = chunk[:remaining]
                    self.chunks.append(retained)
                    self.retained_bytes += len(retained)
        except (OSError, ValueError) as exc:
            self.read_error = "{}: {}".format(type(exc).__name__, exc)

    @property
    def truncated(self):
        return self.observed_bytes > self.retained_bytes

    def text(self):
        payload = b"".join(self.chunks)
        text = payload.decode(
            _subprocess_output_encoding(),
            errors="replace",
        )
        if self.truncated:
            text += "\n… output truncated by QZX …"
        return text


def _run_bounded_process(
    argv,
    *,
    timeout_seconds,
    stdout_limit,
    stderr_limit,
    cwd=None,
    env=None,
):
    """Execute a trusted argv while bounding memory during pipe drainage."""
    started = time.perf_counter()
    process = _start_process(argv, cwd=cwd, env=env)
    stdout_capture, stderr_capture, readers = _start_readers(
        process,
        stdout_limit,
        stderr_limit,
    )
    return_code, timed_out = _wait_for_process(process, timeout_seconds)
    _finish_readers(
        process,
        readers,
        stdout_capture,
        stderr_capture,
    )
    return _execution_snapshot(
        started,
        return_code,
        timed_out,
        stdout_capture,
        stderr_capture,
    )


def _start_process(argv, *, cwd, env):
    creation_flags = 0
    if os.name == "nt":
        creation_flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    return subprocess.Popen(
        argv,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        shell=False,
        creationflags=creation_flags,
        start_new_session=(os.name != "nt"),
        cwd=cwd,
        env=env,
    )


def _start_readers(process, stdout_limit, stderr_limit):
    stdout_capture = _BoundedStreamCapture(stdout_limit)
    stderr_capture = _BoundedStreamCapture(stderr_limit)
    readers = [
        threading.Thread(
            target=stdout_capture.consume,
            args=(process.stdout,),
            name="qzx-diagnostic-stdout",
            daemon=True,
        ),
        threading.Thread(
            target=stderr_capture.consume,
            args=(process.stderr,),
            name="qzx-diagnostic-stderr",
            daemon=True,
        ),
    ]
    for reader in readers:
        reader.start()
    return stdout_capture, stderr_capture, readers


def _wait_for_process(process, timeout_seconds):
    try:
        return process.wait(timeout=timeout_seconds), False
    except subprocess.TimeoutExpired:
        process.kill()
        try:
            return process.wait(timeout=5), True
        except subprocess.TimeoutExpired:
            return None, True


def _finish_readers(
    process,
    readers,
    stdout_capture,
    stderr_capture,
):
    for reader in readers:
        reader.join(timeout=5)
    for stream in (process.stdout, process.stderr):
        if stream is not None:
            try:
                stream.close()
            except OSError:
                pass
    for reader in readers:
        reader.join(timeout=1)
    _mark_stuck_readers(
        readers,
        (stdout_capture, stderr_capture),
    )


def _mark_stuck_readers(readers, captures):
    for reader, capture in zip(readers, captures):
        if reader.is_alive() and capture.read_error is None:
            capture.read_error = (
                "{} did not terminate after its pipe was closed.".format(
                    reader.name
                )
            )


def _execution_snapshot(
    started,
    return_code,
    timed_out,
    stdout_capture,
    stderr_capture,
):
    return {
        "return_code": return_code,
        "timed_out": timed_out,
        "duration_seconds": round(time.perf_counter() - started, 6),
        "stdout": stdout_capture.text(),
        "stderr": stderr_capture.text(),
        "stdout_observed_bytes": stdout_capture.observed_bytes,
        "stderr_observed_bytes": stderr_capture.observed_bytes,
        "stdout_retained_bytes": stdout_capture.retained_bytes,
        "stderr_retained_bytes": stderr_capture.retained_bytes,
        "stdout_truncated": stdout_capture.truncated,
        "stderr_truncated": stderr_capture.truncated,
        "reader_errors": [
            error
            for error in (
                stdout_capture.read_error,
                stderr_capture.read_error,
            )
            if error
        ],
    }
