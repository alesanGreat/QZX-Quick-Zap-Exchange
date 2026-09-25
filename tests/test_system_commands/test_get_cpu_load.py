"""Deterministic tests for getCpuLoad."""

from __future__ import annotations

from types import SimpleNamespace

from qzx.commands.system.get_cpu_load import GetCpuLoadCommand


class FakePsutil:
    @staticmethod
    def cpu_percent(interval=0.0, percpu=False):
        if percpu:
            assert interval == 0.0
            return [10.0, 20.0]
        assert interval == 0.5
        return 15.0

    @staticmethod
    def cpu_freq(percpu=False):
        if percpu:
            return [
                SimpleNamespace(current=3000.0),
                SimpleNamespace(current=3100.0),
            ]
        return SimpleNamespace(current=3050.0, min=800.0, max=4200.0)

    @staticmethod
    def getloadavg():
        return (1.0, 2.0, 3.0)

    @staticmethod
    def cpu_times_percent():
        return SimpleNamespace(user=20.0, system=10.0, idle=70.0)


def test_cpu_load_uses_one_interval_and_structures_optional_metrics():
    result = GetCpuLoadCommand(psutil_module=FakePsutil).execute(0.5)

    assert result["success"] is True
    assert result["overall_percent"] == 15.0
    assert result["per_core"] == [
        {"core": 1, "percent": 10.0},
        {"core": 2, "percent": 20.0},
    ]
    assert result["frequency"]["current_mhz"] == 3050.0
    assert result["per_core_frequency"][1]["current_mhz"] == 3100.0
    assert result["load_average"]["5min"] == 2.0
    assert result["times_percent"]["idle"] == 70.0
    assert "0.5 seconds" in result["message"]


def test_invalid_interval_fails_without_probing_cpu():
    result = GetCpuLoadCommand(psutil_module=FakePsutil).execute("many")

    assert result["success"] is False
    assert "interval must be a number" in result["error"]
