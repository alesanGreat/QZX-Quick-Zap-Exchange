#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Measure HTTP latency and bounded download throughput."""

from __future__ import annotations

import time
import urllib.error
import urllib.request

from qzx.commands.network._internet_speed_workflow import execute_internet_speed
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
        """Run the bounded HTTP speed-test workflow."""
        return execute_internet_speed(self, max_seconds)

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
