"""Request validation and preparation for downloadFile."""

from __future__ import annotations

import os
import time


def prepare_download_request(
    command,
    url,
    destination_path,
    show_progress,
    timeout,
    overwrite,
):
    """Validate public inputs and return normalized download state."""
    show_progress, failure = _boolean_value(
        command,
        show_progress,
        "show_progress",
    )
    if failure is not None:
        return None, failure
    overwrite, failure = _boolean_value(command, overwrite, "overwrite")
    if failure is not None:
        return None, failure
    timeout, failure = _timeout_value(timeout)
    if failure is not None:
        return None, failure

    try:
        command._validated_http_url(url)
    except ValueError as exc:
        return None, _invalid_url(url, exc)

    normalized_destination = os.path.normpath(destination_path)
    absolute_destination = os.path.abspath(normalized_destination)
    failure = _destination_failure(absolute_destination, overwrite)
    if failure is not None:
        return None, failure

    destination_dir = os.path.dirname(absolute_destination)
    if destination_dir and not os.path.exists(destination_dir):
        os.makedirs(destination_dir)

    return {
        "url": str(url),
        "destination": absolute_destination,
        "destination_dir": destination_dir,
        "show_progress": show_progress,
        "timeout": timeout,
        "overwrite": bool(overwrite),
        "start_time": time.time(),
    }, None


def _boolean_value(command, value, field):
    if not isinstance(value, str):
        return value, None
    parsed = command._parse_bool(value)
    if parsed is not None:
        return parsed, None
    return None, {
        "success": False,
        "error_code": f"invalid_{field}",
        "error": f"Invalid {field} value: {value}",
        "message": (
            f"{field} must be true or false; received '{value}'."
        ),
    }


def _timeout_value(timeout):
    try:
        timeout = int(timeout)
    except (TypeError, ValueError):
        return None, {
            "success": False,
            "error_code": "invalid_timeout",
            "error": f"Invalid timeout: {timeout}",
            "message": (
                f"timeout must be a positive integer; received '{timeout}'."
            ),
        }
    if timeout > 0:
        return timeout, None
    return None, {
        "success": False,
        "error_code": "invalid_timeout",
        "error": f"Invalid timeout: {timeout}",
        "message": f"timeout must be greater than zero; received {timeout}.",
    }


def _invalid_url(url, exc):
    return {
        "success": False,
        "error_code": "invalid_url",
        "error": str(exc),
        "message": f"Download was not started: {exc}.",
        "details": {
            "url": str(url),
            "allowed_schemes": ["http", "https"],
        },
    }


def _destination_failure(destination, overwrite):
    if os.path.isdir(destination) and not os.path.islink(destination):
        return {
            "success": False,
            "error_code": "destination_is_directory",
            "error": f"Destination is a directory: {destination}",
            "message": (
                f"Destination '{destination}' is a directory. Choose a file path."
            ),
            "details": {"destination": destination},
        }
    if os.path.lexists(destination) and not overwrite:
        return {
            "success": False,
            "error_code": "destination_exists",
            "error": f"Destination already exists: {destination}",
            "message": (
                f"Destination '{destination}' already exists. Use --overwrite "
                "to replace it after a safety backup."
            ),
            "details": {
                "destination": destination,
                "overwrite": False,
            },
        }
    return None
