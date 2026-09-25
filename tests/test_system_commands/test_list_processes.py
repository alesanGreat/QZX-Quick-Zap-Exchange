"""Deterministic contract tests for listProcesses."""

from __future__ import annotations

from types import SimpleNamespace

from qzx.commands.system.list_processes import ListProcessesCommand


class FakeAccessDenied(Exception):
    pass


class FakeZombieProcess(Exception):
    pass


class FakeNoSuchProcess(Exception):
    pass


class FakeProcess:
    def __init__(self, pid, name, cpu, memory, rss):
        self.info = {
            "pid": pid,
            "name": name,
            "cpu_percent": cpu,
            "memory_percent": memory,
            "username": "tester",
            "status": "running",
        }
        self._rss = rss

    def num_threads(self):
        return 3

    def create_time(self):
        return 1234.5

    def memory_info(self):
        return SimpleNamespace(rss=self._rss)

    def exe(self):
        return f"C:/apps/{self.info['name']}.exe"


class FakePsutil:
    AccessDenied = FakeAccessDenied
    ZombieProcess = FakeZombieProcess
    NoSuchProcess = FakeNoSuchProcess

    @staticmethod
    def process_iter(_attributes):
        return [
            FakeProcess(1, "alpha", 5.0, 20.0, 2048),
            FakeProcess(2, "beta", 10.0, 5.0, 1024),
            FakeProcess(3, None, 50.0, 50.0, 4096),
        ]


class FakeListProcessesCommand(ListProcessesCommand):
    @staticmethod
    def _load_psutil():
        return FakePsutil


def test_filter_sort_and_limit_preserve_process_contract():
    result = FakeListProcessesCommand().execute(sort_by="memory", limit=1)

    assert result["success"] is True
    assert result["total_processes"] == 2
    assert result["displayed_processes"] == 1
    assert result["processes"][0]["name"] == "alpha"
    assert result["processes"][0]["memory_rss"] == 2048
    assert result["processes"][0]["exe"].endswith("alpha.exe")
    assert result["stats"]["top_memory_process"]["name"] == "alpha"


def test_filter_and_null_values_are_normalized_without_losing_results():
    filtered = FakeListProcessesCommand().execute(filter_str="BETA", sort_by="cpu")
    unbounded = FakeListProcessesCommand().execute(
        filter_str="null",
        sort_by="pid",
        limit="null",
    )

    assert filtered["success"] is True
    assert [row["name"] for row in filtered["processes"]] == ["beta"]
    assert unbounded["filter"] is None
    assert unbounded["limit"] is None
    assert [row["pid"] for row in unbounded["processes"]] == [1, 2]


def test_invalid_sort_and_limit_fail_closed():
    bad_sort = FakeListProcessesCommand().execute(sort_by="bogus")
    bad_limit = FakeListProcessesCommand().execute(limit="many")

    assert bad_sort["success"] is False
    assert "sort_by" in bad_sort["error"]
    assert bad_limit["success"] is False
    assert "limit" in bad_limit["error"]
