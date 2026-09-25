"""Date/time snapshot assembly for getCurrentDateTime."""

from __future__ import annotations

import calendar
from datetime import datetime


SUPPORTED_FORMATS = ("full", "simple", "iso")


def invalid_format(value):
    return {
        "success": False,
        "error_code": "invalid_output_format",
        "error": (
            f"Unsupported output format {value!r}; choose "
            f"{', '.join(SUPPORTED_FORMATS)}."
        ),
        "message": (
            "Could not report the current date and time because "
            "--output-format must be full, simple, or iso."
        ),
        "details": {"received": value, "supported": list(SUPPORTED_FORMATS)},
    }


def _offset(now):
    value = now.strftime("%z")
    return f"{value[:3]}:{value[3:]}" if len(value) == 5 else value


def _presentation(command, now, requested, timezone_name, utc_offset, timestamp):
    simple = now.strftime(
        f"%A, %B %d, %Y %I:%M:%S %p {timezone_name}"
    )
    iso = now.isoformat()
    if requested == "simple":
        return simple, iso, f"Current local date and time: {simple}."
    if requested == "iso":
        return iso, iso, f"Current local date and time (ISO 8601): {iso}."
    full = command._full_output(
        now,
        timezone_name,
        utc_offset,
        timestamp,
        now.isocalendar().week,
    )
    message = (
        "Current local date and time captured with timezone, "
        "calendar, ISO-week, and timestamp details."
    )
    return full, iso, message


def _date_row(now, iso_calendar):
    return {
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
    }


def _time_row(now, timezone_name, utc_offset):
    return {
        "hour_24": now.hour,
        "hour_12": int(now.strftime("%I")),
        "minute": now.minute,
        "second": now.second,
        "microsecond": now.microsecond,
        "am_pm": now.strftime("%p"),
        "timezone": timezone_name,
        "utc_offset": utc_offset,
    }


def execute_current_date_time(command, output_format="full"):
    """Capture one local clock observation and return a consistent result."""
    requested = str(output_format).strip().lower()
    if requested not in SUPPORTED_FORMATS:
        return invalid_format(output_format)
    try:
        now = datetime.now().astimezone()
        iso_calendar = now.isocalendar()
        timestamp = int(now.timestamp())
        timezone_name = now.tzname() or "local time"
        utc_offset = _offset(now)
        output, iso_output, message = _presentation(
            command, now, requested, timezone_name, utc_offset, timestamp
        )
        return {
            "success": True,
            "message": message,
            "output": output,
            "output_format": requested,
            "date": _date_row(now, iso_calendar),
            "time": _time_row(now, timezone_name, utc_offset),
            "timestamp": timestamp,
            "iso_format": iso_output,
        }
    except (OSError, OverflowError, ValueError) as exc:
        error = f"{type(exc).__name__}: {exc}"
        return {
            "success": False,
            "error_code": "current_date_time_unavailable",
            "error": error,
            "message": f"Could not read the current local date and time: {error}.",
        }
