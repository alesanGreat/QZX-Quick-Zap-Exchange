#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Benchmark sequential filesystem throughput with a collision-safe fixture."""

from __future__ import annotations

from qzx.commands.system._disk_speed_workflow import execute_disk_speed
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
        return execute_disk_speed(self, test_path, size_mib)

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
