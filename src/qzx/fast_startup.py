"""Minimal human welcome path used before importing the full QZX runtime."""

import os
import sys

from qzx._build_info import ATTRIBUTION, VERSION, WELCOME_MATURITY
from qzx.first_run import claim_first_run_attribution
from qzx.welcome_text import basic_welcome_message


_FALSE_VALUES = {"0", "false", "no", "off", "disabled"}
_TRUE_VALUES = {"1", "true", "yes", "on", "enabled"}


def _normalized_bool(value):
    if value is None:
        return None
    normalized = str(value).strip().lower()
    if normalized in _TRUE_VALUES:
        return True
    if normalized in _FALSE_VALUES:
        return False
    return None


def _telemetry_definitely_disabled(environ):
    explicit = _normalized_bool(environ.get("QZX_TELEMETRY"))
    if explicit is not None:
        return not explicit
    return _normalized_bool(environ.get("DO_NOT_TRACK")) is True


def _schedule_optional_telemetry(environ, telemetry_scheduler=None):
    if _telemetry_definitely_disabled(environ):
        return
    try:
        telemetry_notice = None
        if telemetry_scheduler is None:
            from qzx.telemetry import (
                TELEMETRY_NOTICE,
                schedule_version_telemetry,
            )

            telemetry_scheduler = schedule_version_telemetry
            telemetry_notice = TELEMETRY_NOTICE

        status = telemetry_scheduler(VERSION, environ=environ)
        if status.get("details", {}).get("notice") and telemetry_notice:
            print(telemetry_notice, file=sys.stderr)
    except Exception as exc:
        if _normalized_bool(environ.get("QZX_TELEMETRY_DEBUG")) is True:
            print(
                "QZX telemetry scheduling failed: {}.".format(
                    type(exc).__name__
                ),
                file=sys.stderr,
            )


def _human_label(name):
    return " ".join(
        word[:1].upper() + word[1:]
        for word in str(name).replace("-", "_").split("_")
        if word
    )


def _human_scalar(value):
    if value is None:
        return "Not available"
    if isinstance(value, bool):
        return "Yes" if value else "No"
    return str(value)


def _append_human_value(lines, label, value, indent):
    prefix = " " * indent
    if isinstance(value, dict):
        lines.append("{}{}:".format(prefix, label))
        for key, item in value.items():
            _append_human_value(
                lines,
                _human_label(key),
                item,
                indent + 2,
            )
        return
    if isinstance(value, (list, tuple)):
        lines.append("{}{}:".format(prefix, label))
        for item in value:
            lines.append("{}  - {}".format(prefix, _human_scalar(item)))
        return
    lines.append("{}{}: {}".format(prefix, label, _human_scalar(value)))


def main(environ=None, telemetry_scheduler=None):
    """Print the basic welcome first, then perform optional background work."""
    environ = os.environ if environ is None else environ
    if claim_first_run_attribution(environ):
        print(ATTRIBUTION)

    welcome = basic_welcome_message(VERSION).strip()
    lines = [
        "QZX welcome screen (basic view) displayed. Version {}.".format(
            VERSION
        ),
        "",
        "Output:",
        welcome,
        "",
        "Details:",
        "  Meta:",
    ]
    _append_human_value(
        lines,
        "Command Maturity",
        WELCOME_MATURITY,
        4,
    )
    print("\n".join(lines))
    sys.stdout.flush()
    _schedule_optional_telemetry(
        environ,
        telemetry_scheduler=telemetry_scheduler,
    )
    return 0
