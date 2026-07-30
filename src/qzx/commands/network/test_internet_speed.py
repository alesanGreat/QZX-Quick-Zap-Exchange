#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Measure HTTP latency and bounded download throughput."""

from __future__ import annotations

import time
import urllib.error
import urllib.request

from qzx.core.command_base import CommandBase


class TestInternetSpeedCommand(CommandBase):
    """Measure a real HTTP stream without printing progress into command output."""

    name = "testInternetSpeed"
    description = (
        "Measures HTTP latency in milliseconds and bounded download "
        "throughput in Mbps and MiB/s"
    )
    category = "network"

    parameters = [
        {
            "name": "max_seconds",
            "description": (
                "Maximum download measurement duration, greater than 0 and "
                "no more than 30 seconds"
            ),
            "required": False,
            "default": 3.0,
            "type": "float",
        }
    ]

    examples = [
        {
            "command": "qzx testInternetSpeed",
            "description": (
                "Measure HTTP latency and download throughput for up to "
                "3 seconds"
            ),
        },
        {
            "command": "qzx testInternetSpeed --max-seconds 5",
            "description": "Run the download measurement for up to 5 seconds",
        },
    ]

    TEST_URL = "https://speed.cloudflare.com/__down?bytes=25000000"
    LATENCY_URL = "https://speed.cloudflare.com/cdn-cgi/trace"

    def execute(self, max_seconds=3.0):
        """Run three latency samples and one bounded streaming download."""
        try:
            duration_limit = float(max_seconds)
        except (TypeError, ValueError):
            duration_limit = 0
        if not 0 < duration_limit <= 30:
            return {
                "success": False,
                "error_code": "invalid_max_seconds",
                "error": (
                    "max_seconds must be greater than 0 and no more than 30."
                ),
                "message": (
                    "Could not run the web speed test because --max-seconds "
                    "must be greater than 0 and no more than 30."
                ),
                "details": {
                    "received": max_seconds,
                    "minimum_exclusive": 0,
                    "maximum": 30,
                    "unit": "seconds",
                },
            }

        clock_floor = time.get_clock_info("perf_counter").resolution
        latencies, latency_failures = self._measure_latency(clock_floor)
        download = self._measure_download(duration_limit, clock_floor)
        if download["bytes"] == 0:
            error = download["error"] or "No bytes were received."
            return {
                "success": False,
                "error_code": "download_measurement_failed",
                "error": error,
                "message": (
                    "Web speed test could not measure download throughput: "
                    f"{error}"
                ),
                "details": {
                    "duration_limit_seconds": duration_limit,
                    "latency_samples_completed": len(latencies),
                    "latency_samples_failed": latency_failures,
                },
            }

        elapsed = download["duration"]
        speed_mbps = (download["bytes"] * 8) / elapsed / 1_000_000
        speed_mib = download["bytes"] / (1024 * 1024) / elapsed
        latency = {
            "average": (
                sum(latencies) / len(latencies) if latencies else None
            ),
            "minimum": min(latencies) if latencies else None,
            "maximum": max(latencies) if latencies else None,
            "samples_completed": len(latencies),
            "samples_failed": latency_failures,
            "unit": "milliseconds",
        }
        latency_summary = (
            f"average HTTP latency {latency['average']:.1f} ms and "
            if latency["average"] is not None
            else "HTTP latency unavailable; "
        )
        result = {
            "success": True,
            "message": (
                f"Web speed test measured {latency_summary}"
                f"{speed_mbps:.2f} Mbps ({speed_mib:.2f} MiB/s) across "
                f"{download['bytes']} bytes in {elapsed:.3f} seconds."
            ),
            "latency": latency,
            "download": {
                "megabits_per_second": round(speed_mbps, 2),
                "mebibytes_per_second": round(speed_mib, 2),
                "bytes_downloaded": download["bytes"],
                "duration_seconds": elapsed,
                "duration_limit_seconds": duration_limit,
                "stopped_at_duration_limit": (
                    elapsed >= duration_limit
                ),
            },
        }
        if latency_failures:
            result["warnings"] = [
                {
                    "code": "latency_samples_failed",
                    "message": (
                        f"{latency_failures} of 3 HTTP latency samples failed; "
                        "download throughput was still measured."
                    ),
                }
            ]
        return result

    def _measure_latency(self, clock_floor):
        latencies = []
        failures = 0
        for _ in range(3):
            started = time.perf_counter()
            request = urllib.request.Request(
                self.LATENCY_URL,
                headers={"User-Agent": "QZX Speed Client"},
            )
            try:
                with urllib.request.urlopen(request, timeout=2) as connection:
                    connection.read(10)
            except (OSError, TimeoutError, urllib.error.URLError):
                failures += 1
                continue
            latencies.append(
                max(time.perf_counter() - started, clock_floor) * 1000
            )
        return latencies, failures

    def _measure_download(self, duration_limit, clock_floor):
        request = urllib.request.Request(
            self.TEST_URL,
            headers={"User-Agent": "QZX Speed Client"},
        )
        bytes_downloaded = 0
        started = time.perf_counter()
        error = None
        try:
            with urllib.request.urlopen(request, timeout=5) as connection:
                while chunk := connection.read(65536):
                    bytes_downloaded += len(chunk)
                    if time.perf_counter() - started >= duration_limit:
                        break
        except (OSError, TimeoutError, urllib.error.URLError) as exc:
            error = f"{type(exc).__name__}: {exc}"
        elapsed = max(time.perf_counter() - started, clock_floor)
        return {
            "bytes": bytes_downloaded,
            "duration": elapsed,
            "error": error,
        }
