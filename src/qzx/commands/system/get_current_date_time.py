#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Report the current local date and time from one consistent observation."""

from __future__ import annotations

import calendar
from datetime import date

from qzx.commands.system._date_time_snapshot import execute_current_date_time
from qzx.core.command_base import CommandBase


class GetCurrentDateTimeCommand(CommandBase):
    """Return rich, timezone-aware local date and time information."""

    name = "getCurrentDateTime"
    description = (
        "Reports the current local date and time with timezone, calendar, "
        "ISO-week, and timestamp details"
    )
    category = "system"

    parameters = [
        {
            "name": "output_format",
            "description": "Presentation format: full, simple, or iso",
            "required": False,
            "default": "full",
            "type": "str",
        }
    ]

    examples = [
        {
            "command": "qzx getCurrentDateTime",
            "description": "Show detailed local date, time, and calendar context",
        },
        {
            "command": "qzx getCurrentDateTime --output-format simple",
            "description": "Show a compact local date and time",
        },
        {
            "command": "qzx getCurrentDateTime --output-format iso",
            "description": "Show a timezone-aware ISO 8601 value",
        },
    ]

    def execute(self, output_format="full"):
        """Capture the local clock once and return a consistent result."""
        return execute_current_date_time(self, output_format)

    @staticmethod
    def _full_output(now, timezone_name, utc_offset, timestamp, iso_week):
        """Build the warm terminal view without changing structured data."""
        border = "=" * 60
        weeks_in_year = date(now.year, 12, 28).isocalendar().week
        return (
            f"{border}\n"
            "DATE & TIME\n"
            f"{border}\n"
            f"Date: {now:%A, %B %d, %Y}\n"
            f"Time: {now:%I:%M:%S %p} ({now:%H:%M:%S} 24h)\n"
            f"Timezone: {timezone_name} (UTC{utc_offset})\n\n"
            f"Day of year: {now.timetuple().tm_yday} of "
            f"{366 if calendar.isleap(now.year) else 365}\n"
            f"ISO week: {iso_week} of {weeks_in_year}\n"
            f"Quarter: {((now.month - 1) // 3) + 1} of 4\n"
            f"Unix timestamp: {timestamp}\n\n"
            f"{calendar.month(now.year, now.month)}"
            f"{border}"
        )
