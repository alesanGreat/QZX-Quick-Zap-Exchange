#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Report the current local date and time from one consistent observation."""

from __future__ import annotations

import calendar
from datetime import date, datetime

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
        requested_format = str(output_format).strip().lower()
        supported_formats = ("full", "simple", "iso")
        if requested_format not in supported_formats:
            return {
                "success": False,
                "error_code": "invalid_output_format",
                "error": (
                    f"Unsupported output format {output_format!r}; choose "
                    f"{', '.join(supported_formats)}."
                ),
                "message": (
                    "Could not report the current date and time because "
                    "--output-format must be full, simple, or iso."
                ),
                "details": {
                    "received": output_format,
                    "supported": list(supported_formats),
                },
            }

        try:
            now = datetime.now().astimezone()
            iso_calendar = now.isocalendar()
            timestamp = int(now.timestamp())
            timezone_name = now.tzname() or "local time"
            utc_offset = now.strftime("%z")
            if len(utc_offset) == 5:
                utc_offset = f"{utc_offset[:3]}:{utc_offset[3:]}"

            simple_output = now.strftime(
                f"%A, %B %d, %Y %I:%M:%S %p {timezone_name}"
            )
            iso_output = now.isoformat()
            if requested_format == "simple":
                output = simple_output
                message = f"Current local date and time: {output}."
            elif requested_format == "iso":
                output = iso_output
                message = f"Current local date and time (ISO 8601): {output}."
            else:
                output = self._full_output(
                    now,
                    timezone_name,
                    utc_offset,
                    timestamp,
                    iso_calendar.week,
                )
                message = (
                    "Current local date and time captured with timezone, "
                    "calendar, ISO-week, and timestamp details."
                )

            return {
                "success": True,
                "message": message,
                "output": output,
                "output_format": requested_format,
                "date": {
                    "year": now.year,
                    "month": now.month,
                    "month_name": now.strftime("%B"),
                    "day": now.day,
                    "day_of_week": now.strftime("%A"),
                    "day_of_year": now.timetuple().tm_yday,
                    "iso_week": iso_calendar.week,
                    "iso_week_year": iso_calendar.year,
                    "quarter": ((now.month - 1) // 3) + 1,
                    "is_leap_year": calendar.isleap(now.year),
                },
                "time": {
                    "hour_24": now.hour,
                    "hour_12": int(now.strftime("%I")),
                    "minute": now.minute,
                    "second": now.second,
                    "microsecond": now.microsecond,
                    "am_pm": now.strftime("%p"),
                    "timezone": timezone_name,
                    "utc_offset": utc_offset,
                },
                "timestamp": timestamp,
                "iso_format": iso_output,
            }
        except (OSError, OverflowError, ValueError) as exc:
            error = f"{type(exc).__name__}: {exc}"
            return {
                "success": False,
                "error_code": "current_date_time_unavailable",
                "error": error,
                "message": (
                    "Could not read the current local date and time: "
                    f"{error}."
                ),
            }

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
