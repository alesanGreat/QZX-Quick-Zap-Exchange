"""One-call Windows process snapshot for listProcesses.

psutil reads most per-process fields with OpenProcess(). For protected or
other-user processes that call is denied and psutil falls back to a complete
NtQuerySystemInformation(SystemProcessInformation) snapshot *per field and per
process*, which makes a full listing quadratic (tens of seconds for ~600
processes). This module takes that same system snapshot once and parses every
process from it, so a CPU-sampled listing needs exactly two kernel calls.

Only documented, layout-stable fields are read. Any failure returns ``None`` and
the caller falls back to psutil.
"""

from __future__ import annotations

import ctypes
import os

_SYSTEM_PROCESS_INFORMATION_CLASS = 5
_STATUS_INFO_LENGTH_MISMATCH = 0xC0000004
_INITIAL_BUFFER_BYTES = 512 * 1024
_MAX_BUFFER_BYTES = 64 * 1024 * 1024
_FILETIME_EPOCH_OFFSET_SECONDS = 11644473600
_HUNDRED_NS_PER_SECOND = 10_000_000
_THREAD_STATE_WAITING = 5
_WAIT_REASON_SUSPENDED = 5


class _UnicodeString(ctypes.Structure):
    _fields_ = [
        ("Length", ctypes.c_ushort),
        ("MaximumLength", ctypes.c_ushort),
        ("Buffer", ctypes.c_void_p),
    ]


class _SystemProcessInformation(ctypes.Structure):
    _fields_ = [
        ("NextEntryOffset", ctypes.c_ulong),
        ("NumberOfThreads", ctypes.c_ulong),
        ("WorkingSetPrivateSize", ctypes.c_longlong),
        ("HardFaultCount", ctypes.c_ulong),
        ("NumberOfThreadsHighWatermark", ctypes.c_ulong),
        ("CycleTime", ctypes.c_ulonglong),
        ("CreateTime", ctypes.c_longlong),
        ("UserTime", ctypes.c_longlong),
        ("KernelTime", ctypes.c_longlong),
        ("ImageName", _UnicodeString),
        ("BasePriority", ctypes.c_long),
        ("UniqueProcessId", ctypes.c_void_p),
        ("InheritedFromUniqueProcessId", ctypes.c_void_p),
        ("HandleCount", ctypes.c_ulong),
        ("SessionId", ctypes.c_ulong),
        ("UniqueProcessKey", ctypes.c_void_p),
        ("PeakVirtualSize", ctypes.c_size_t),
        ("VirtualSize", ctypes.c_size_t),
        ("PageFaultCount", ctypes.c_ulong),
        ("PeakWorkingSetSize", ctypes.c_size_t),
        ("WorkingSetSize", ctypes.c_size_t),
        ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
        ("QuotaPagedPoolUsage", ctypes.c_size_t),
        ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
        ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
        ("PagefileUsage", ctypes.c_size_t),
        ("PeakPagefileUsage", ctypes.c_size_t),
        ("PrivatePageCount", ctypes.c_size_t),
        ("ReadOperationCount", ctypes.c_longlong),
        ("WriteOperationCount", ctypes.c_longlong),
        ("OtherOperationCount", ctypes.c_longlong),
        ("ReadTransferCount", ctypes.c_longlong),
        ("WriteTransferCount", ctypes.c_longlong),
        ("OtherTransferCount", ctypes.c_longlong),
    ]


class _SystemThreadInformation(ctypes.Structure):
    _fields_ = [
        ("KernelTime", ctypes.c_longlong),
        ("UserTime", ctypes.c_longlong),
        ("CreateTime", ctypes.c_longlong),
        ("WaitTime", ctypes.c_ulong),
        ("StartAddress", ctypes.c_void_p),
        ("UniqueProcess", ctypes.c_void_p),
        ("UniqueThread", ctypes.c_void_p),
        ("Priority", ctypes.c_long),
        ("BasePriority", ctypes.c_long),
        ("ContextSwitches", ctypes.c_ulong),
        ("ThreadState", ctypes.c_ulong),
        ("WaitReason", ctypes.c_ulong),
    ]


def _query_buffer(nt_query):
    size = _INITIAL_BUFFER_BYTES
    while size <= _MAX_BUFFER_BYTES:
        buffer = ctypes.create_string_buffer(size)
        needed = ctypes.c_ulong(0)
        status = nt_query(
            _SYSTEM_PROCESS_INFORMATION_CLASS, buffer, size, ctypes.byref(needed)
        ) & 0xFFFFFFFF
        if status == 0:
            return buffer
        if status != _STATUS_INFO_LENGTH_MISMATCH:
            return None
        size = max(size * 2, needed.value + 64 * 1024)
    return None


def _image_name(entry, pid):
    name = entry.ImageName
    if name.Buffer and name.Length:
        return ctypes.wstring_at(name.Buffer, name.Length // 2)
    return "System Idle Process" if pid == 0 else "System"


def _is_suspended(buffer, offset, thread_count):
    if thread_count == 0:
        return False
    base = offset + ctypes.sizeof(_SystemProcessInformation)
    size = ctypes.sizeof(_SystemThreadInformation)
    for index in range(thread_count):
        thread = _SystemThreadInformation.from_buffer(buffer, base + index * size)
        if not (
            thread.ThreadState == _THREAD_STATE_WAITING
            and thread.WaitReason == _WAIT_REASON_SUSPENDED
        ):
            return False
    return True


def _record(buffer, offset, entry):
    pid = int(entry.UniqueProcessId or 0)
    create_time = None
    if entry.CreateTime > 0:
        create_time = (
            entry.CreateTime / _HUNDRED_NS_PER_SECOND - _FILETIME_EPOCH_OFFSET_SECONDS
        )
    return pid, {
        "name": _image_name(entry, pid),
        "num_threads": int(entry.NumberOfThreads),
        "create_time": create_time,
        "cpu_time_100ns": int(entry.UserTime + entry.KernelTime),
        "memory_rss": int(entry.WorkingSetSize),
        "status": (
            "stopped"
            if _is_suspended(buffer, offset, int(entry.NumberOfThreads))
            else "running"
        ),
    }


def _parse(buffer):
    processes = {}
    offset = 0
    limit = len(buffer)
    while offset + ctypes.sizeof(_SystemProcessInformation) <= limit:
        entry = _SystemProcessInformation.from_buffer(buffer, offset)
        pid, record = _record(buffer, offset, entry)
        processes[pid] = record
        if entry.NextEntryOffset == 0:
            break
        offset += entry.NextEntryOffset
    return processes


def windows_process_snapshot():
    """Return ``{pid: record}`` for every process, or ``None`` when unavailable."""
    if os.name != "nt":
        return None
    try:
        nt_query = ctypes.WinDLL("ntdll").NtQuerySystemInformation
        nt_query.restype = ctypes.c_long
        buffer = _query_buffer(nt_query)
        return None if buffer is None else _parse(buffer)
    except (AttributeError, OSError, ValueError):
        return None
