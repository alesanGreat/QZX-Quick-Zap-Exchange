#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Focused public-contract tests for getRamInfo."""

from types import SimpleNamespace

from qzx.commands.system.get_ram_info import GetRamInfoCommand


def test_get_ram_info_reports_memory_and_swap_with_units():
    def virtual_memory():
        return SimpleNamespace(
            total=8_589_934_592,
            available=4_294_967_296,
            used=4_294_967_296,
            free=2_147_483_648,
            percent=50.0,
            cached=1_073_741_824,
            buffers=536_870_912,
        )

    def swap_memory():
        return SimpleNamespace(
            total=2_147_483_648,
            used=536_870_912,
            free=1_610_612_736,
            percent=25.0,
            sin=0,
            sout=0,
        )

    result = GetRamInfoCommand(
        virtual_memory_provider=virtual_memory,
        swap_memory_provider=swap_memory,
    ).invoke([])

    assert result["success"] is True
    assert result["ram_info"]["virtual_memory"]["total"] == 8_589_934_592
    assert result["ram_info"]["virtual_memory"]["total_readable"] == "8.00 GB"
    assert result["ram_info"]["swap"]["total_readable"] == "2.00 GB"
    assert result["ram_info"]["memory_stats"]["cached"]["readable"] == "1.00 GB"
    assert "50.0%" in result["message"]
    assert "25.0%" in result["message"]
    assert result["meta"]["command"] == "getRamInfo"


def test_get_ram_info_system_failure_is_explicit():
    def fail():
        raise OSError("memory probe unavailable")

    def unexpected_swap_probe():
        raise AssertionError("Swap must not be probed after RAM failure.")

    result = GetRamInfoCommand(
        virtual_memory_provider=fail,
        swap_memory_provider=unexpected_swap_probe,
    ).invoke([])

    assert result["success"] is False
    assert "memory probe unavailable" in result["error"]
    assert "memory probe unavailable" in result["message"]
    assert result["meta"]["schema_version"] == 1
