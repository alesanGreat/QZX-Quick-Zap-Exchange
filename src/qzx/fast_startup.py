"""Minimal human welcome path used before importing the full QZX runtime."""

import os
import sys
import time

from qzx._build_info import ATTRIBUTION, VERSION
from qzx._stdio import configure_utf8_stdio
from qzx.first_run import claim_first_run_attribution
from qzx.telemetry_runtime import schedule_optional_telemetry
from qzx.welcome_text import basic_welcome_message, welcome_summary



def main(environ=None, telemetry_scheduler=None, usage_recorder=None):
    """Render the clean onboarding screen, then schedule optional telemetry."""
    configure_utf8_stdio()
    started = time.perf_counter()
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
    schedule_optional_telemetry(
        environ,
        telemetry_scheduler=telemetry_scheduler,
        usage_recorder=usage_recorder,
        usage_result={
            "meta": {
                "command": "welcome",
                "duration_ms": round((time.perf_counter() - started) * 1000, 3),
            }
        },
    )
    return 0
