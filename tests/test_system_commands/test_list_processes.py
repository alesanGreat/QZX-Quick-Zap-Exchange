"""Deterministic contract tests for listProcesses."""

from __future__ import annotations

import contextlib
import os
from types import SimpleNamespace

from qzx.commands.system import _process_inventory
from qzx.commands.system._windows_process_snapshot import windows_process_snapshot
from qzx.commands.system.list_processes import ListProcessesCommand


class FakeAccessDenied(Exception):
    pass


class FakeZombieProcess(Exception):
    pass


class FakeNoSuchProcess(Exception):
    pass


class FakeProcess:
    detail_reads = 0

    def __init__(self, pid, name, cpu, memory, rss, *, denied=False):
        self.info = {
            "pid": pid,
            "name": name,
            "username": "tester",
            "memory_info": SimpleNamespace(rss=rss),
            "memory_percent": memory,
            "create_time": 1234.5,
            "exe": f"C:/apps/{name}.exe" if name else None,
        }
        self._cpu = cpu
        self._cpu_calls = 0
        self._denied = denied

    def cpu_percent(self, _interval=None):
        # Like psutil, the first call primes the counter and returns 0.0.
        self._cpu_calls += 1
        if self._denied:
            raise FakeAccessDenied()
        return 0.0 if self._cpu_calls == 1 else self._cpu

    @contextlib.contextmanager
    def oneshot(self):
        yield

    def status(self):
        FakeProcess.detail_reads += 1
        return "running"

    def num_threads(self):
        return 3


def _fixture_processes():
    return [
        FakeProcess(0, "System Idle Process", 95.0, 0.0, 8),
        FakeProcess(1, "alpha", 5.0, 20.0, 2048),
        FakeProcess(2, "beta", 10.0, 5.0, 1024),
        FakeProcess(3, None, 50.0, 50.0, 4096),
        FakeProcess(4, "protected", 0.0, 1.0, 512, denied=True),
    ]


class FakePsutil:
    AccessDenied = FakeAccessDenied
    ZombieProcess = FakeZombieProcess
    NoSuchProcess = FakeNoSuchProcess
    requested_attributes = None
    processes = staticmethod(_fixture_processes)

    @classmethod
    def process_iter(cls, attributes):
        cls.requested_attributes = list(attributes)
        return cls.processes()


class ManyProcessesPsutil(FakePsutil):
    processes = staticmethod(
        lambda: [FakeProcess(pid, f"worker{pid}", 1.0, 1.0, 100) for pid in range(1, 41)]
    )


class FakeListProcessesCommand(ListProcessesCommand):
    @staticmethod
    def _load_psutil():
        return FakePsutil

    @staticmethod
    def _platform_system():
        return "Windows"

    @staticmethod
    def _process_snapshot():
        # Exercise the portable psutil path.
        return None

    @staticmethod
    def _wait_for_cpu_sample(_seconds):
        return None


class ManyProcessesCommand(FakeListProcessesCommand):
    @staticmethod
    def _load_psutil():
        return ManyProcessesPsutil


def test_filter_sort_and_limit_preserve_process_contract():
    result = FakeListProcessesCommand().execute(sort_by="memory", limit=1)

    assert result["success"] is True
    assert result["total_processes"] == 3
    assert result["displayed_processes"] == 1
    assert result["processes"][0]["name"] == "alpha"
    assert result["processes"][0]["memory_rss"] == 2048
    assert result["processes"][0]["exe"].endswith("alpha.exe")
    assert result["processes"][0]["status"] == "running"
    assert result["processes"][0]["num_threads"] == 3
    assert result["stats"]["top_memory_process"]["name"] == "alpha"
    assert result["os_type"] == "windows"
    assert "pass limit 0" in result["message"]


def test_cpu_is_sampled_over_a_window_instead_of_psutil_first_zero():
    result = FakeListProcessesCommand().execute()

    names = [row["name"] for row in result["processes"]]
    assert names[:2] == ["beta", "alpha"]
    assert result["processes"][0]["cpu_percent"] == 10.0
    assert result["stats"]["top_cpu_process"]["name"] == "beta"
    assert result["cpu_sample_seconds"] == _process_inventory.CPU_SAMPLE_SECONDS
    # Windows' idle pseudo-process must never top a CPU ranking.
    assert "System Idle Process" not in names
    # A process whose CPU counters are denied stays listed with an unknown CPU.
    protected = next(row for row in result["processes"] if row["name"] == "protected")
    assert protected["cpu_percent"] is None


def test_expensive_details_are_read_only_for_displayed_rows():
    FakeProcess.detail_reads = 0
    FakeListProcessesCommand().execute(sort_by="pid", limit=2)

    assert FakeProcess.detail_reads == 2
    assert "status" not in FakePsutil.requested_attributes
    assert "num_threads" not in FakePsutil.requested_attributes


def test_default_limit_keeps_agent_output_bounded():
    result = ManyProcessesCommand().execute()
    everything = ManyProcessesCommand().execute(limit=0)

    assert result["limit"] == _process_inventory.DEFAULT_LIMIT
    assert result["displayed_processes"] == _process_inventory.DEFAULT_LIMIT
    assert result["total_processes"] == 40
    assert everything["displayed_processes"] == 40


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
    assert [row["pid"] for row in unbounded["processes"]] == [1, 2, 4]


def test_invalid_sort_and_limit_fail_closed():
    bad_sort = FakeListProcessesCommand().execute(sort_by="bogus")
    bad_limit = FakeListProcessesCommand().execute(limit="many")
    negative = FakeListProcessesCommand().execute(limit="-3")

    assert bad_sort["success"] is False
    assert "sort_by" in bad_sort["error"]
    assert bad_limit["success"] is False
    assert "limit" in bad_limit["error"]
    assert negative["success"] is False


def _snapshot(cpu_by_pid):
    base = {
        "num_threads": 2,
        "create_time": 1000.0,
        "memory_rss": 1024,
        "status": "running",
    }
    names = {0: "System Idle Process", 10: "editor.exe", 11: "build.exe", 12: "sleepy.exe"}
    return {
        pid: dict(base, name=names[pid], cpu_time_100ns=cpu)
        for pid, cpu in cpu_by_pid.items()
    }


class SnapshotPsutil(FakePsutil):
    identities = {10: ("DESKTOP\\ale", "C:/apps/editor.exe")}

    @staticmethod
    def virtual_memory():
        return SimpleNamespace(total=1024 * 100)

    @classmethod
    def Process(cls, pid):  # noqa: N802 - mirrors psutil.Process
        identity = cls.identities.get(pid)

        def denied():
            raise FakeAccessDenied()

        return SimpleNamespace(
            username=(lambda: identity[0]) if identity else denied,
            exe=(lambda: identity[1]) if identity else denied,
        )


class SnapshotCommand(FakeListProcessesCommand):
    snapshots = None

    @staticmethod
    def _load_psutil():
        return SnapshotPsutil

    @classmethod
    def _process_snapshot(cls):
        return cls.snapshots.pop(0)


def test_windows_path_uses_two_native_snapshots_for_real_cpu():
    # 0.5 s window = 5,000,000 units of 100 ns for one fully busy CPU.
    SnapshotCommand.snapshots = [
        _snapshot({0: 0, 10: 1_000_000, 11: 0, 12: 0}),
        _snapshot({0: 4_000_000, 10: 2_000_000, 11: 5_000_000, 12: 0}),
    ]
    result = SnapshotCommand().execute()

    rows = {row["name"]: row for row in result["processes"]}
    assert result["collection_method"] == "windows_system_snapshot"
    assert [row["name"] for row in result["processes"]][:2] == ["build.exe", "editor.exe"]
    assert rows["build.exe"]["cpu_percent"] == 100.0
    assert rows["editor.exe"]["cpu_percent"] == 20.0
    assert rows["editor.exe"]["memory_percent"] == 1.0
    assert rows["editor.exe"]["username"] == "DESKTOP\\ale"
    assert rows["editor.exe"]["exe"] == "C:/apps/editor.exe"
    assert rows["build.exe"]["username"] is None
    assert rows["build.exe"]["num_threads"] == 2
    assert "System Idle Process" not in rows


def test_windows_path_reports_unknown_cpu_for_reused_pids():
    first = _snapshot({10: 0, 11: 0})
    second = _snapshot({10: 2_500_000, 11: 2_500_000})
    second[11]["create_time"] = 2000.0  # PID reused by a new process.
    SnapshotCommand.snapshots = [first, second]
    result = SnapshotCommand().execute(sort_by="pid")

    rows = {row["pid"]: row for row in result["processes"]}
    assert rows[10]["cpu_percent"] == 50.0
    assert rows[11]["cpu_percent"] is None


def test_native_snapshot_matches_the_current_process_on_its_real_boundary():
    snapshot = windows_process_snapshot()

    if os.name != "nt":
        assert snapshot is None
        return
    current = snapshot[os.getpid()]
    assert current["name"].lower().startswith("python")
    assert current["num_threads"] >= 1
    assert current["memory_rss"] > 0
    assert current["create_time"] > 0
    assert current["status"] == "running"
    assert snapshot[0]["name"] == "System Idle Process"
