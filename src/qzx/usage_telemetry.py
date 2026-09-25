#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Privacy-bounded 10-day QZX usage and interaction telemetry.

Individual invocations never leave the machine. QZX stores per-day aggregates
locally and emits one closed, globally aligned 10-day window at a time. The
payload contains canonical command names with counts/timing aggregates and
coarse interaction evidence only; it never contains command arguments, paths,
terminal input, output, file contents, key presses, pointer coordinates, or
process names.
"""

from __future__ import print_function

import atexit
import json
import time
from contextlib import contextmanager
import math
import os
import tempfile
import threading
import uuid
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from qzx import telemetry
from qzx._usage_interaction import interaction_snapshot as interaction_snapshot

_USAGE_STATE_FILENAME = "usage-telemetry.json"
_USAGE_SCHEMA_VERSION = 1
_WINDOW_DAYS = 10
_WINDOW_ANCHOR = date(2026, 1, 1)
_MAX_COMMANDS = 128
_MAX_STATE_DAYS = 120
_THREAD_JOIN_SECONDS = 0.35
_REQUEST_TIMEOUT_SECONDS = 1.5
_LOCK_WAIT_SECONDS = 0.20
_LOCK_RETRY_SECONDS = 0.01


def _utc_day(now=None):
    current = datetime.now(timezone.utc) if now is None else now
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    return current.astimezone(timezone.utc).date()


def _usage_state_path(environ=None, state_directory=None):
    directory = (
        Path(state_directory)
        if state_directory is not None
        else telemetry.telemetry_state_path(environ=environ).parent
    )
    return directory / _USAGE_STATE_FILENAME


def _acquire_state_lock(handle):
    if os.name == "nt":
        import msvcrt

        handle.seek(0, os.SEEK_END)
        if handle.tell() == 0:
            handle.write(b"\0")
            handle.flush()
        handle.seek(0)
        msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
        return ("windows", msvcrt)

    import fcntl

    fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    return ("posix", fcntl)


def _release_state_lock(handle, backend):
    kind, module = backend
    if kind == "windows":
        handle.seek(0)
        module.locking(handle.fileno(), module.LK_UNLCK, 1)
    else:
        module.flock(handle.fileno(), module.LOCK_UN)


@contextmanager
def _state_lock(path):
    """Bound concurrent aggregate updates without delaying a QZX command."""
    path.parent.mkdir(parents=True, exist_ok=True)
    lock_path = path.with_name(path.name + ".lock")
    handle = lock_path.open("a+b")
    backend = None
    deadline = time.monotonic() + _LOCK_WAIT_SECONDS
    try:
        while True:
            try:
                backend = _acquire_state_lock(handle)
                break
            except OSError:
                if time.monotonic() >= deadline:
                    raise TimeoutError("QZX usage telemetry state is busy.")
                time.sleep(_LOCK_RETRY_SECONDS)
        yield
    finally:
        if backend is not None:
            try:
                _release_state_lock(handle, backend)
            except OSError:
                pass
        handle.close()


def _new_usage_state(installation_id):
    return {
        "schema_version": _USAGE_SCHEMA_VERSION,
        "installation_id": str(installation_id),
        "days": {},
        "sent_periods": [],
        "pending_report": None,
    }


def _load_usage_state(path, installation_id):
    try:
        with path.open("r", encoding="utf-8") as handle:
            state = json.load(handle)
        if str(state.get("installation_id")) != str(installation_id):
            return _new_usage_state(installation_id)
        if not isinstance(state.get("days"), dict):
            state["days"] = {}
        if not isinstance(state.get("sent_periods"), list):
            state["sent_periods"] = []
        if state.get("pending_report") is not None and not isinstance(
            state.get("pending_report"), dict
        ):
            state["pending_report"] = None
        state["schema_version"] = _USAGE_SCHEMA_VERSION
        return state
    except (OSError, ValueError, TypeError, AttributeError):
        return _new_usage_state(installation_id)


def _write_usage_state(path, state):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_name = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=str(path.parent),
            prefix="usage-telemetry-",
            suffix=".tmp",
            delete=False,
        ) as handle:
            temporary_name = handle.name
            json.dump(state, handle, indent=2, sort_keys=True)
            handle.write("\n")
        try:
            os.chmod(temporary_name, 0o600)
        except OSError:
            pass
        os.replace(temporary_name, str(path))
    finally:
        if temporary_name and os.path.exists(temporary_name):
            try:
                os.unlink(temporary_name)
            except OSError:
                pass


def _period_for_day(day):
    index = (day - _WINDOW_ANCHOR).days // _WINDOW_DAYS
    start = _WINDOW_ANCHOR + timedelta(days=index * _WINDOW_DAYS)
    end = start + timedelta(days=_WINDOW_DAYS - 1)
    return start, end


def _empty_day_bucket():
    return {
        "commands": {},
        "invocations": 0,
        "interactive_invocations": 0,
        "foreground_invocations": 0,
        "foreground_supported_invocations": 0,
        "recent_input_invocations": 0,
        "recent_input_supported_invocations": 0,
    }


def _record_day(state, day, command, duration_ms, interaction):
    key = day.isoformat()
    bucket = state["days"].setdefault(key, _empty_day_bucket())
    commands = bucket.setdefault("commands", {})
    command_row = commands.setdefault(
        command, {"count": 0, "total_duration_ms": 0.0, "max_duration_ms": 0.0}
    )
    command_row["count"] = int(command_row.get("count", 0)) + 1
    command_row["total_duration_ms"] = round(
        float(command_row.get("total_duration_ms", 0.0)) + duration_ms, 3
    )
    command_row["max_duration_ms"] = round(
        max(float(command_row.get("max_duration_ms", 0.0)), duration_ms), 3
    )
    bucket["invocations"] = int(bucket.get("invocations", 0)) + 1
    if interaction["interactive"]:
        bucket["interactive_invocations"] = (
            int(bucket.get("interactive_invocations", 0)) + 1
        )
    if interaction["foreground"] is not None:
        bucket["foreground_supported_invocations"] = (
            int(bucket.get("foreground_supported_invocations", 0)) + 1
        )
        if interaction["foreground"]:
            bucket["foreground_invocations"] = (
                int(bucket.get("foreground_invocations", 0)) + 1
            )
    if interaction["recent_input"] is not None:
        bucket["recent_input_supported_invocations"] = (
            int(bucket.get("recent_input_supported_invocations", 0)) + 1
        )
        if interaction["recent_input"]:
            bucket["recent_input_invocations"] = (
                int(bucket.get("recent_input_invocations", 0)) + 1
            )


def _period_days(state, start, end):
    rows = []
    for key, bucket in state.get("days", {}).items():
        try:
            day = date.fromisoformat(key)
        except (TypeError, ValueError):
            continue
        if start <= day <= end:
            rows.append((day, bucket))
    rows.sort(key=lambda item: item[0])
    return rows


def _aggregate_period(state, start, end):
    rows = _period_days(state, start, end)
    if not rows:
        return None
    commands = {}
    evidence = {
        "total_invocations": 0,
        "active_days": len(rows),
        "interactive_invocations": 0,
        "interactive_days": 0,
        "foreground_invocations": 0,
        "foreground_days": 0,
        "foreground_supported_invocations": 0,
        "foreground_supported_days": 0,
        "recent_input_invocations": 0,
        "recent_input_days": 0,
        "recent_input_supported_invocations": 0,
        "recent_input_supported_days": 0,
    }
    for _day, bucket in rows:
        evidence["total_invocations"] += int(bucket.get("invocations", 0))
        for prefix in ("interactive", "foreground", "recent_input"):
            count = int(bucket.get(prefix + "_invocations", 0))
            evidence[prefix + "_invocations"] += count
            if count > 0:
                evidence[prefix + "_days"] += 1
        for prefix in ("foreground", "recent_input"):
            count = int(bucket.get(prefix + "_supported_invocations", 0))
            evidence[prefix + "_supported_invocations"] += count
            if count > 0:
                evidence[prefix + "_supported_days"] += 1
        for command, values in bucket.get("commands", {}).items():
            target = commands.setdefault(
                command,
                {"command": command, "count": 0, "total_duration_ms": 0.0, "max_duration_ms": 0.0},
            )
            target["count"] += int(values.get("count", 0))
            target["total_duration_ms"] = round(
                target["total_duration_ms"]
                + float(values.get("total_duration_ms", 0.0)),
                3,
            )
            target["max_duration_ms"] = round(
                max(target["max_duration_ms"], float(values.get("max_duration_ms", 0.0))),
                3,
            )
    command_usage = sorted(commands.values(), key=lambda row: row["command"].casefold())
    return {"command_usage": command_usage, "evidence": evidence}


def _oldest_closed_period(state, today):
    sent = set(str(value) for value in state.get("sent_periods", []))
    candidates = []
    for key in state.get("days", {}):
        try:
            day = date.fromisoformat(key)
        except (TypeError, ValueError):
            continue
        start, end = _period_for_day(day)
        if end >= today or start.isoformat() in sent:
            continue
        candidates.append((start, end))
    return min(candidates) if candidates else None


def _activation_installation_id(environ=None, state_directory=None):
    activation_path = telemetry.telemetry_state_path(
        environ=environ, state_directory=state_directory
    )
    state = telemetry._load_state(activation_path)
    return str(state["installation_id"])


def _valid_command_result(result):
    if not isinstance(result, dict):
        return None
    meta = result.get("meta")
    if not isinstance(meta, dict):
        return None
    command = meta.get("command")
    duration = meta.get("duration_ms")
    if (
        not isinstance(command, str)
        or not command
        or len(command) > 64
        or not command[0].isalpha()
        or not all(character.isalnum() for character in command)
    ):
        return None
    if not isinstance(duration, (int, float)) or not math.isfinite(duration) or duration < 0:
        return None
    return command, min(float(duration), 86_400_000.0)


def _prune_state(state, today):
    threshold = today - timedelta(days=_MAX_STATE_DAYS)
    state["days"] = {
        key: value
        for key, value in state.get("days", {}).items()
        if _safe_day(key) is not None and _safe_day(key) >= threshold
    }
    state["sent_periods"] = list(state.get("sent_periods", []))[-24:]


def _safe_day(value):
    try:
        return date.fromisoformat(str(value))
    except ValueError:
        return None


def _build_report(state, qzx_version, environ, today):
    pending = state.get("pending_report")
    if isinstance(pending, dict):
        return pending
    period = _oldest_closed_period(state, today)
    if period is None:
        return None
    start, end = period
    aggregated = _aggregate_period(state, start, end)
    if aggregated is None:
        return None
    event = {
        "schema_version": _USAGE_SCHEMA_VERSION,
        "event": "usage_window",
        "event_id": str(uuid.uuid4()),
        "installation_id": str(state["installation_id"]),
        "qzx_version": str(qzx_version)[:32],
        "window_start": start.isoformat(),
        "window_end": end.isoformat(),
        "ci": telemetry._is_ci(environ),
        "command_usage": aggregated["command_usage"][:_MAX_COMMANDS],
        "interaction_evidence": aggregated["evidence"],
    }
    state["pending_report"] = event
    return event


def _mark_report_sent(state_path, event):
    try:
        with _state_lock(state_path):
            state = _load_usage_state(state_path, event["installation_id"])
            pending = state.get("pending_report")
            if not isinstance(pending, dict) or pending.get("event_id") != event["event_id"]:
                return
            period_key = str(event["window_start"])
            if period_key not in state["sent_periods"]:
                state["sent_periods"].append(period_key)
            start = date.fromisoformat(event["window_start"])
            end = date.fromisoformat(event["window_end"])
            state["days"] = {
                key: value
                for key, value in state.get("days", {}).items()
                if _safe_day(key) is None or not (start <= _safe_day(key) <= end)
            }
            state["pending_report"] = None
            _write_usage_state(state_path, state)
    except TimeoutError:
        # The server already deduplicates event/window retries. If another QZX
        # process owns the short local lock, leave the exact pending report for
        # a later invocation rather than blocking or losing concurrent counts.
        return


def send_usage_report(
    event,
    state_path,
    endpoint=telemetry.TELEMETRY_ENDPOINT,
    opener=None,
    timeout=_REQUEST_TIMEOUT_SECONDS,
    environ=None,
):
    try:
        outgoing, default_opener = telemetry._outgoing_request(event, endpoint)
        transport = default_opener if opener is None else opener
        status = telemetry._response_status(transport(outgoing, timeout=timeout))
        if 200 <= status < 300:
            _mark_report_sent(state_path, event)
            return True
        telemetry._debug("usage window server returned HTTP {0}".format(status), environ)
    except Exception as exc:
        telemetry._debug(str(exc), environ)
    return False


def _start_worker(event, state_path, endpoint, opener, environ):
    worker = threading.Thread(
        target=send_usage_report,
        kwargs={
            "event": event,
            "state_path": state_path,
            "endpoint": endpoint,
            "opener": opener,
            "environ": environ,
        },
        name="qzx-telemetry-usage",
    )
    worker.daemon = True
    worker.start()
    atexit.register(worker.join, _THREAD_JOIN_SECONDS)


def record_command_usage_and_schedule(
    qzx_version,
    result,
    environ=None,
    state_directory=None,
    endpoint=telemetry.TELEMETRY_ENDPOINT,
    opener=None,
    now=None,
    interaction_provider=None,
):
    """Record one known-command aggregate and schedule one closed 10-day report."""
    environ = os.environ if environ is None else environ
    if not telemetry.telemetry_enabled(environ):
        return {"scheduled": False, "reason": "disabled"}
    command_result = _valid_command_result(result)
    if command_result is None:
        return {"scheduled": False, "reason": "unmeasured_command"}

    installation_id = _activation_installation_id(environ, state_directory)
    state_path = _usage_state_path(environ, state_directory)
    current_day = _utc_day(now)
    command, duration_ms = command_result
    interaction_provider = interaction_snapshot if interaction_provider is None else interaction_provider
    interaction = interaction_provider()
    try:
        with _state_lock(state_path):
            state = _load_usage_state(state_path, installation_id)
            _record_day(state, current_day, command, duration_ms, interaction)
            _prune_state(state, current_day)
            event = _build_report(state, qzx_version, environ, current_day)
            _write_usage_state(state_path, state)
    except TimeoutError:
        return {"scheduled": False, "reason": "state_busy"}
    if event is None:
        return {"scheduled": False, "reason": "window_open"}
    _start_worker(event, state_path, endpoint, opener, environ)
    return {
        "scheduled": True,
        "window_start": event["window_start"],
        "window_end": event["window_end"],
    }
