#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Privacy-conscious telemetry for QZX version activations.

QZX sends at most one event per installed QZX version and local installation
identifier. The identifier is a random UUID; it is not derived from hardware,
the operating-system account, or any file owned by the user.

Telemetry must never change the result or standard output of a QZX command.
Network work therefore runs in a daemon thread, its exit wait is bounded, and
all failures are contained inside this module. A one-time disclosure is written
to standard error for transparency.
"""

from __future__ import print_function

import atexit
import json
import os
import platform
import sys
import tempfile
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path

TELEMETRY_ENDPOINT = "https://qzx.yumbale.com/api/v1/telemetry"
TELEMETRY_POLICY_URL = (
    "https://github.com/alesanGreat/QZX-Quick-Zap-Exchange/"
    "blob/main/docs/telemetry.md"
)
TELEMETRY_NOTICE = (
    "QZX telemetry: one version-activation event sends a random installation "
    "ID, IP observed by the server, and QZX/Python/OS details; never commands, "
    "paths, usernames, hostnames, or file content. Disable with "
    "QZX_TELEMETRY=0. Details: {policy_url}"
).format(policy_url=TELEMETRY_POLICY_URL)

_SCHEMA_VERSION = 1
_FALSE_VALUES = {"0", "false", "no", "off", "disabled"}
_TRUE_VALUES = {"1", "true", "yes", "on", "enabled"}
_STATE_FILENAME = "telemetry.json"
_THREAD_JOIN_SECONDS = 0.35
_REQUEST_TIMEOUT_SECONDS = 1.5


def _utc_now():
    """Return a compact UTC timestamp without depending on newer Python APIs."""
    return (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def _normalise_bool(value):
    if value is None:
        return None
    normalised = str(value).strip().lower()
    if normalised in _TRUE_VALUES:
        return True
    if normalised in _FALSE_VALUES:
        return False
    return None


def telemetry_enabled(environ=None):
    """Return whether telemetry is enabled for the current process."""
    environ = os.environ if environ is None else environ
    explicit_setting = _normalise_bool(environ.get("QZX_TELEMETRY"))
    if explicit_setting is not None:
        return explicit_setting
    return _normalise_bool(environ.get("DO_NOT_TRACK")) is not True


def _state_directory(environ=None):
    environ = os.environ if environ is None else environ
    override = environ.get("QZX_TELEMETRY_STATE_DIR")
    if override:
        return Path(override).expanduser()

    if os.name == "nt":
        base = environ.get("LOCALAPPDATA")
        if base:
            return Path(base) / "qzx"
    elif sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "qzx"

    xdg_state_home = environ.get("XDG_STATE_HOME")
    if xdg_state_home:
        return Path(xdg_state_home) / "qzx"
    return Path.home() / ".local" / "state" / "qzx"


def telemetry_state_path(environ=None, state_directory=None):
    """Return the local state file used only for deduplication and opt-out UI."""
    directory = (
        Path(state_directory)
        if state_directory is not None
        else _state_directory(environ)
    )
    return directory / _STATE_FILENAME


def _new_state():
    return {
        "schema_version": _SCHEMA_VERSION,
        "installation_id": str(uuid.uuid4()),
        "notice_shown": False,
        "pending_versions": {},
        "sent_versions": {},
    }


def _load_state(path):
    try:
        with path.open("r", encoding="utf-8") as handle:
            state = json.load(handle)
        uuid.UUID(str(state.get("installation_id", "")))
        if not isinstance(state.get("pending_versions"), dict):
            state["pending_versions"] = {}
        if not isinstance(state.get("sent_versions"), dict):
            state["sent_versions"] = {}
        state["notice_shown"] = bool(state.get("notice_shown", False))
        state["schema_version"] = _SCHEMA_VERSION
        return state
    except (OSError, ValueError, TypeError, AttributeError):
        return _new_state()


def _write_state(path, state):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_name = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=str(path.parent),
            prefix="telemetry-",
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


def _normalise_os_name(system_name):
    lookup = {
        "windows": "windows",
        "linux": "linux",
        "darwin": "macos",
        "freebsd": "freebsd",
    }
    return lookup.get(str(system_name).strip().lower(), "other")


def _linux_pretty_release():
    try:
        freedesktop_release = getattr(platform, "freedesktop_os_release", None)
        if freedesktop_release:
            values = freedesktop_release()
        else:
            values = {}
            with Path("/etc/os-release").open("r", encoding="utf-8") as handle:
                for raw_line in handle:
                    key, separator, value = raw_line.strip().partition("=")
                    if separator:
                        values[key] = value.strip().strip('"').strip("'")
        pretty_name = values.get("PRETTY_NAME")
        if pretty_name:
            return pretty_name
        return " ".join(
            value
            for value in (values.get("NAME"), values.get("VERSION_ID"))
            if value
        )
    except (OSError, ValueError, TypeError):
        return ""


def _os_details():
    system_name = platform.system()
    os_name = _normalise_os_name(system_name)
    kernel = platform.release() or "unknown"

    if os_name == "windows":
        human_release = platform.release() or "Windows"
        kernel = platform.version() or kernel
    elif os_name == "macos":
        human_release = platform.mac_ver()[0] or kernel
    elif os_name == "linux":
        human_release = _linux_pretty_release() or kernel
    else:
        human_release = platform.release() or system_name or "unknown"

    return os_name, str(human_release)[:128], str(kernel)[:128]


def _is_virtual_environment():
    base_prefix = getattr(sys, "base_prefix", sys.prefix)
    real_prefix = getattr(sys, "real_prefix", None)
    return bool(real_prefix or sys.prefix != base_prefix)


def _is_ci(environ=None):
    environ = os.environ if environ is None else environ
    known_markers = (
        "CI",
        "GITHUB_ACTIONS",
        "GITLAB_CI",
        "JENKINS_URL",
        "CIRCLECI",
        "TF_BUILD",
        "BUILDKITE",
    )
    return any(_normalise_bool(environ.get(name)) is True for name in known_markers)


def build_event(qzx_version, installation_id, event_id, environ=None):
    """Build the complete allow-listed payload sent to the QZX endpoint."""
    os_name, os_release, os_kernel = _os_details()
    return {
        "schema_version": _SCHEMA_VERSION,
        "event": "version_first_run",
        "event_id": str(event_id),
        "installation_id": str(installation_id),
        "qzx_version": str(qzx_version)[:32],
        "python_version": platform.python_version()[:32],
        "python_implementation": platform.python_implementation()[:32],
        "os_name": os_name,
        "os_release": os_release,
        "os_kernel": os_kernel,
        "architecture": platform.machine()[:32] or "unknown",
        "virtual_environment": _is_virtual_environment(),
        "ci": _is_ci(environ),
    }


def _debug(message, environ=None):
    environ = os.environ if environ is None else environ
    if _normalise_bool(environ.get("QZX_TELEMETRY_DEBUG")) is True:
        print("QZX telemetry debug: {0}".format(message), file=sys.stderr)


def _mark_sent(state_path, qzx_version, event_id):
    state = _load_state(state_path)
    pending_event_id = state["pending_versions"].get(qzx_version)
    if pending_event_id != event_id:
        return
    state["pending_versions"].pop(qzx_version, None)
    state["sent_versions"][qzx_version] = {
        "event_id": event_id,
        "sent_at": _utc_now(),
    }
    _write_state(state_path, state)


def send_event(event, state_path, endpoint=TELEMETRY_ENDPOINT, opener=None,
               timeout=_REQUEST_TIMEOUT_SECONDS, environ=None):
    """Send one event synchronously; intended for the worker and unit tests."""
    # Importing urllib.request recursively imports the HTTP and email stacks.
    # On synced Windows workspaces that can take several seconds, so keep it
    # inside the already-backgrounded network path instead of charging every
    # QZX invocation for a transport it will usually never need.
    from urllib import request as urllib_request

    opener = urllib_request.urlopen if opener is None else opener
    payload = json.dumps(event, separators=(",", ":"), sort_keys=True).encode(
        "utf-8"
    )
    outgoing = urllib_request.Request(
        endpoint,
        data=payload,
        headers={
            "Content-Type": "application/json",
            "User-Agent": "qzx-telemetry/1",
        },
        method="POST",
    )

    try:
        response = opener(outgoing, timeout=timeout)
        try:
            status = response.getcode()
        finally:
            close = getattr(response, "close", None)
            if close:
                close()
        if 200 <= status < 300:
            _mark_sent(
                state_path,
                event["qzx_version"],
                event["event_id"],
            )
            return {
                "success": True,
                "message": "Telemetry version activation accepted.",
                "details": {"http_status": status},
            }
        _debug("server returned HTTP {0}".format(status), environ)
    except Exception as exc:  # Telemetry must never break a QZX command.
        _debug(str(exc), environ)

    return {
        "success": False,
        "message": "Telemetry was not sent; QZX execution is unaffected.",
        "details": {"retry_on_next_run": True},
    }


def schedule_version_telemetry(qzx_version, environ=None, state_directory=None,
                               endpoint=TELEMETRY_ENDPOINT, opener=None):
    """Schedule a non-blocking activation event once for each QZX version."""
    environ = os.environ if environ is None else environ
    if not telemetry_enabled(environ):
        return {
            "success": True,
            "message": "QZX telemetry is disabled.",
            "details": {"scheduled": False, "reason": "disabled"},
        }

    try:
        state_path = telemetry_state_path(environ, state_directory)
        state = _load_state(state_path)
        version = str(qzx_version)[:32]
        if version in state["sent_versions"]:
            return {
                "success": True,
                "message": "This QZX version activation was already reported.",
                "details": {"scheduled": False, "reason": "already_sent"},
            }

        event_id = state["pending_versions"].get(version)
        if not event_id:
            event_id = str(uuid.uuid4())
            state["pending_versions"][version] = event_id

        show_notice = not state["notice_shown"]
        state["notice_shown"] = True
        _write_state(state_path, state)
        event = build_event(
            version,
            state["installation_id"],
            event_id,
            environ,
        )

        worker = threading.Thread(
            target=send_event,
            kwargs={
                "event": event,
                "state_path": state_path,
                "endpoint": endpoint,
                "opener": opener,
                "environ": environ,
            },
            name="qzx-telemetry",
        )
        worker.daemon = True
        worker.start()
        atexit.register(worker.join, _THREAD_JOIN_SECONDS)
        return {
            "success": True,
            "message": "QZX version activation telemetry was scheduled.",
            "details": {
                "scheduled": True,
                "notice": show_notice,
                "policy_url": TELEMETRY_POLICY_URL,
            },
        }
    except Exception as exc:  # State problems must not affect QZX either.
        _debug(str(exc), environ)
        return {
            "success": False,
            "message": "Telemetry could not be scheduled; QZX is unaffected.",
            "details": {"scheduled": False, "reason": "local_state_error"},
        }
