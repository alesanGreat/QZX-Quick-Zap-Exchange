"""Capture Python and child-process stdout without corrupting JSON output."""

from __future__ import annotations

import contextlib
import io
import os
import tempfile


@contextlib.contextmanager
def capture_process_stdout(original_stdout):
    """Yield text emitted through Python or the process stdout descriptor."""
    captured = io.StringIO()
    stdout_fd = _stream_fileno(original_stdout)
    if stdout_fd is None:
        with contextlib.redirect_stdout(captured):
            yield captured
        return
    saved_stdout_fd = _duplicate_stdout(original_stdout, stdout_fd)
    if saved_stdout_fd is None:
        with contextlib.redirect_stdout(captured):
            yield captured
        return
    try:
        with tempfile.TemporaryFile(mode="w+b") as temporary_stdout:
            with _redirect_descriptor(
                captured, original_stdout, stdout_fd, saved_stdout_fd, temporary_stdout
            ):
                yield captured
    finally:
        os.close(saved_stdout_fd)


def _stream_fileno(stream):
    try:
        return stream.fileno()
    except (AttributeError, io.UnsupportedOperation, OSError):
        return None


def _duplicate_stdout(stream, stdout_fd):
    try:
        stream.flush()
        return os.dup(stdout_fd)
    except OSError:
        return None


def _capture_encoding(stream):
    return getattr(stream, "encoding", None) or "utf-8"


def _capture_stream(stdout_fd, encoding):
    return io.TextIOWrapper(
        os.fdopen(os.dup(stdout_fd), "wb", closefd=True),
        encoding=encoding,
        errors="replace",
        write_through=True,
    )


@contextlib.contextmanager
def _redirect_descriptor(captured, original_stdout, stdout_fd, saved_fd, temporary):
    encoding = _capture_encoding(original_stdout)
    try:
        os.dup2(temporary.fileno(), stdout_fd)
        capture_stream = _capture_stream(stdout_fd, encoding)
    except (OSError, ValueError):
        os.dup2(saved_fd, stdout_fd)
        with contextlib.redirect_stdout(captured):
            yield
        return
    try:
        with contextlib.redirect_stdout(capture_stream):
            yield
    finally:
        _restore_and_collect(
            captured, capture_stream, stdout_fd, saved_fd, temporary, encoding
        )


def _restore_and_collect(captured, capture_stream, stdout_fd, saved_fd,
                         temporary, encoding):
    try:
        capture_stream.flush()
    finally:
        try:
            capture_stream.close()
        finally:
            os.dup2(saved_fd, stdout_fd)
            temporary.seek(0)
            captured.write(temporary.read().decode(encoding, errors="replace"))
