"""Deterministic detail probes for TerminalWelcome."""

from __future__ import annotations

from types import SimpleNamespace

from qzx.commands.system._terminal_welcome_details import format_gpu_result
from qzx.commands.system.terminal_welcome import TerminalWelcome


class _FakePsutil:
    def virtual_memory(self):
        return SimpleNamespace(
            total=8 * 1024,
            available=3 * 1024,
            used=5 * 1024,
            percent=62.5,
        )

    def disk_partitions(self, all=False):
        assert all is False
        return [
            SimpleNamespace(
                device="fixture-disk",
                mountpoint="/fixture",
                fstype="fixturefs",
            )
        ]

    def disk_usage(self, mountpoint):
        assert mountpoint == "/fixture"
        return SimpleNamespace(
            total=16 * 1024,
            used=6 * 1024,
            free=10 * 1024,
            percent=37.5,
        )

    def cpu_count(self, logical=True):
        return 8 if logical else 4


def test_terminal_welcome_collects_optional_system_details_once():
    loads = []

    def load_psutil():
        loads.append("loaded")
        return _FakePsutil()

    welcome = TerminalWelcome(
        qzx_version="test",
        psutil_loader=load_psutil,
    )

    first = welcome.system_info
    second = welcome.system_info

    assert first is second
    assert loads == ["loaded"]
    assert first["ram_total"] == 8 * 1024
    assert first["ram_available"] == 3 * 1024
    assert first["ram_used"] == 5 * 1024
    assert first["ram_percent"] == 62.5
    assert first["cpu_count_physical"] == 4
    assert first["cpu_count_logical"] == 8
    assert first["disk_info"] == [
        {
            "device": "fixture-disk",
            "mountpoint": "/fixture",
            "fstype": "fixturefs",
            "total": 16 * 1024,
            "used": 6 * 1024,
            "free": 10 * 1024,
            "percent": 37.5,
        }
    ]


def test_terminal_welcome_formats_gpu_snapshot_stably():
    result = format_gpu_result(
        {
            "success": True,
            "gpus": [
                {
                    "name": "Fixture GPU",
                    "vendor": "FixtureVendor",
                    "memory": {"total_mib": 8192, "used_mib": 2048},
                    "temperature_celsius": 55,
                    "utilization_percent": 25,
                }
            ],
        }
    )

    assert result == (
        "1. Fixture GPU [FixtureVendor] | Memory: 2048/8192 MiB "
        "| Temp: 55 °C | Usage: 25%"
    )
