"""Benchmark workflow for testDiskSpeed."""

from __future__ import annotations

import os
import tempfile
import time
from pathlib import Path


CHUNK_SIZE = 1024 * 1024


def execute_disk_speed(command, test_path=".", size_mib=50):
    """Run the disk benchmark and guarantee fixture cleanup."""
    directory, requested_size, failure = _validated_request(
        command,
        test_path,
        size_mib,
    )
    if failure is not None:
        return failure
    return _benchmark_directory(command, directory, requested_size)


def _validated_request(command, test_path, size_mib):
    directory = Path(test_path).expanduser().resolve()
    if not directory.exists():
        return None, None, command._failure(
            "test_path_missing",
            f"Directory '{directory}' does not exist.",
            directory,
            size_mib,
        )
    if not directory.is_dir():
        return None, None, command._failure(
            "test_path_not_directory",
            f"Path '{directory}' is not a directory.",
            directory,
            size_mib,
        )
    try:
        requested_size = int(size_mib)
    except (TypeError, ValueError):
        requested_size = 0
    if 1 <= requested_size <= 1024:
        return directory, requested_size, None
    return None, None, command._failure(
        "invalid_size_mib",
        "size_mib must be an integer from 1 through 1024.",
        directory,
        size_mib,
    )


def _benchmark_directory(command, directory, requested_size):
    fixture_path = None
    result = None
    try:
        fixture_path = _new_fixture(directory)
        result = _run_benchmark(
            command,
            directory,
            fixture_path,
            requested_size,
        )
    except OSError as exc:
        result = command._failure(
            "disk_benchmark_failed",
            (
                f"Filesystem benchmark in '{directory}' failed: "
                f"{type(exc).__name__}: {exc}."
            ),
            directory,
            requested_size,
        )
    finally:
        result = _cleanup_fixture(
            command,
            directory,
            requested_size,
            fixture_path,
            result,
        )
    return result


def _new_fixture(directory):
    descriptor, fixture_name = tempfile.mkstemp(
        prefix=".qzx-disk-speed-",
        suffix=".bin",
        dir=directory,
    )
    os.close(descriptor)
    return Path(fixture_name)


def _run_benchmark(
    command,
    directory,
    fixture_path,
    requested_size,
):
    chunk = os.urandom(CHUNK_SIZE)
    clock_floor = time.get_clock_info("perf_counter").resolution
    write_duration = _write_fixture(
        fixture_path,
        requested_size,
        chunk,
        clock_floor,
    )
    bytes_read, read_duration = _read_fixture(
        fixture_path,
        clock_floor,
    )
    expected_bytes = requested_size * CHUNK_SIZE
    if bytes_read != expected_bytes:
        return command._failure(
            "fixture_verification_failed",
            (
                f"Expected to read {expected_bytes} bytes but read {bytes_read}; "
                "benchmark results were discarded."
            ),
            directory,
            requested_size,
        )
    return _success_result(
        directory,
        requested_size,
        expected_bytes,
        bytes_read,
        write_duration,
        read_duration,
    )


def _write_fixture(
    fixture_path,
    requested_size,
    chunk,
    clock_floor,
):
    started = time.perf_counter()
    with fixture_path.open("wb") as handle:
        for _ in range(requested_size):
            handle.write(chunk)
        handle.flush()
        os.fsync(handle.fileno())
    return max(time.perf_counter() - started, clock_floor)


def _read_fixture(fixture_path, clock_floor):
    bytes_read = 0
    started = time.perf_counter()
    with fixture_path.open("rb") as handle:
        while read_chunk := handle.read(CHUNK_SIZE):
            bytes_read += len(read_chunk)
    duration = max(time.perf_counter() - started, clock_floor)
    return bytes_read, duration


def _success_result(
    directory,
    requested_size,
    expected_bytes,
    bytes_read,
    write_duration,
    read_duration,
):
    write_speed = requested_size / write_duration
    read_speed = requested_size / read_duration
    return {
        "success": True,
        "message": (
            f"Filesystem benchmark completed in '{directory}': "
            f"{write_speed:.2f} MiB/s durable write and "
            f"{read_speed:.2f} MiB/s buffered read using a "
            f"{requested_size} MiB temporary fixture."
        ),
        "test_directory": str(directory),
        "fixture_size": {
            "mebibytes": requested_size,
            "bytes": expected_bytes,
        },
        "write": {
            "mebibytes_per_second": round(write_speed, 2),
            "duration_seconds": write_duration,
            "durability": "flush + fsync after sequential write",
        },
        "read": {
            "mebibytes_per_second": round(read_speed, 2),
            "duration_seconds": read_duration,
            "bytes_verified": bytes_read,
        },
        "details": {
            "temporary_fixture": "unique and removed",
            "chunk_size_bytes": CHUNK_SIZE,
        },
    }


def _cleanup_fixture(
    command,
    directory,
    requested_size,
    fixture_path,
    result,
):
    if fixture_path is None or not fixture_path.exists():
        return result
    try:
        fixture_path.unlink()
        return result
    except OSError as exc:
        if result is None:
            return command._failure(
                "fixture_cleanup_failed",
                (
                    f"Temporary fixture '{fixture_path}' could not be removed: "
                    f"{type(exc).__name__}: {exc}."
                ),
                directory,
                requested_size,
            )
        result.setdefault("warnings", []).append(
            {
                "code": "fixture_cleanup_failed",
                "message": (
                    f"Remove temporary fixture '{fixture_path}' manually: "
                    f"{type(exc).__name__}: {exc}."
                ),
            }
        )
        result["details"]["temporary_fixture"] = str(fixture_path)
        return result
