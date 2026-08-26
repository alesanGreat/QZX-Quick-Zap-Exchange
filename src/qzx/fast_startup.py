"""Minimal human welcome path used before importing the full QZX runtime."""

import os
import sys

from qzx._build_info import ATTRIBUTION, VERSION
from qzx._stdio import configure_utf8_stdio
from qzx.first_run import claim_first_run_attribution
from qzx.welcome_text import basic_welcome_message, welcome_summary


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


def main(environ=None, telemetry_scheduler=None):
    """Render the clean onboarding screen, then schedule optional telemetry."""
    configure_utf8_stdio()
    environ = os.environ if environ is None else environ
    sections = []
    if claim_first_run_attribution(environ):
        sections.append(ATTRIBUTION)
    sections.extend(
        (
            welcome_summary(VERSION),
            basic_welcome_message(VERSION).rstrip("\n"),
        )
    )
    print("\n\n".join(sections))
    sys.stdout.flush()
    _schedule_optional_telemetry(
        environ,
        telemetry_scheduler=telemetry_scheduler,
    )
    return 0
