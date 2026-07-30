#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Benchmark sequential filesystem throughput with a collision-safe fixture."""

from __future__ import annotations

import os
import tempfile
import time
from pathlib import Path

from qzx.core.command_base import CommandBase


class TestDiskSpeedCommand(CommandBase):
    """Measure sequential read and durable write throughput."""

    name = "testDiskSpeed"
    description = (
        "Measures sequential durable-write and buffered-read throughput in "
        "MiB/s using a uniquely named temporary file"
    )
    category = "system"

    parameters = [
        {
            "name": "test_path",
            "description": (
                "Existing directory whose filesystem will be benchmarked"
            ),
            "required": False,
            "default": ".",
            "type": "str",
        },
        {
            "name": "size_mib",
            "description": (
                "Temporary fixture size in MiB, from 1 through 1024"
            ),
            "required": False,
            "default": 50,
            "type": "int",
        },
    ]

    examples = [
        {
            "command": "qzx testDiskSpeed",
            "description": (
                "Benchmark the current filesystem with a 50 MiB fixture"
            ),
        },
        {
            "command": "qzx testDiskSpeed C:/temp --size-mib 100",
            "description": (
                "Benchmark C:/temp with a unique 100 MiB temporary fixture"
            ),
        },
    ]

    def execute(self, test_path=".", size_mib=50):
        """Run the benchmark and remove its unique fixture on every path."""
        directory = Path(test_path).expanduser().resolve()
        if not directory.exists():
            return self._failure(
                "test_path_missing",
                f"Directory '{directory}' does not exist.",
                directory,
                size_mib,
            )
        if not directory.is_dir():
            return self._failure(
                "test_path_not_directory",
                f"Path '{directory}' is not a directory.",
                directory,
                size_mib,
            )

        try:
            requested_size = int(size_mib)
        except (TypeError, ValueError):
            requested_size = 0
        if not 1 <= requested_size <= 1024:
            return self._failure(
                "invalid_size_mib",
                "size_mib must be an integer from 1 through 1024.",
                directory,
                size_mib,
            )

        fixture_path = None
        result = None
        try:
            descriptor, fixture_name = tempfile.mkstemp(
                prefix=".qzx-disk-speed-",
                suffix=".bin",
                dir=directory,
            )
            fixture_path = Path(fixture_name)
            os.close(descriptor)
            chunk_size = 1024 * 1024
            chunk = os.urandom(chunk_size)
            clock_floor = time.get_clock_info("perf_counter").resolution

            write_started = time.perf_counter()
            with fixture_path.open("wb") as handle:
                for _ in range(requested_size):
                    handle.write(chunk)
                handle.flush()
                os.fsync(handle.fileno())
            write_duration = max(
                time.perf_counter() - write_started,
                clock_floor,
            )

            bytes_read = 0
            read_started = time.perf_counter()
            with fixture_path.open("rb") as handle:
                while read_chunk := handle.read(chunk_size):
                    bytes_read += len(read_chunk)
            read_duration = max(
                time.perf_counter() - read_started,
                clock_floor,
            )
            expected_bytes = requested_size * chunk_size
            if bytes_read != expected_bytes:
                result = self._failure(
                    "fixture_verification_failed",
                    (
                        f"Expected to read {expected_bytes} bytes but read "
                        f"{bytes_read}; benchmark results were discarded."
                    ),
                    directory,
                    requested_size,
                )
            else:
                write_speed = requested_size / write_duration
                read_speed = requested_size / read_duration
                result = {
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
                        "chunk_size_bytes": chunk_size,
                    },
                }
        except OSError as exc:
            result = self._failure(
                "disk_benchmark_failed",
                (
                    f"Filesystem benchmark in '{directory}' failed: "
                    f"{type(exc).__name__}: {exc}."
                ),
                directory,
                requested_size,
            )
        finally:
            if fixture_path is not None and fixture_path.exists():
                try:
                    fixture_path.unlink()
                except OSError as exc:
                    if result is None:
                        result = self._failure(
                            "fixture_cleanup_failed",
                            (
                                f"Temporary fixture '{fixture_path}' could "
                                f"not be removed: {type(exc).__name__}: {exc}."
                            ),
                            directory,
                            requested_size,
                        )
                    else:
                        result.setdefault("warnings", []).append(
                            {
                                "code": "fixture_cleanup_failed",
                                "message": (
                                    f"Remove temporary fixture "
                                    f"'{fixture_path}' manually: "
                                    f"{type(exc).__name__}: {exc}."
                                ),
                            }
                        )
                        result["details"]["temporary_fixture"] = str(
                            fixture_path
                        )
        return result

    @staticmethod
    def _failure(error_code, message, directory, received_size):
        return {
            "success": False,
            "error_code": error_code,
            "error": message,
            "message": message,
            "details": {
                "test_directory": str(directory),
                "received_size_mib": received_size,
                "allowed_size_mib": {"minimum": 1, "maximum": 1024},
            },
        }
