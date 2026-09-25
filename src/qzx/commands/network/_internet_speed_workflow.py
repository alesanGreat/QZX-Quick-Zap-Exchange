"""Result assembly for testInternetSpeed."""

from __future__ import annotations

import time


def _duration_limit(value):
    try:
        duration = float(value)
    except (TypeError, ValueError):
        duration = 0
    if 0 < duration <= 30:
        return duration, None
    return None, {
        "success": False,
        "error_code": "invalid_max_seconds",
        "error": "max_seconds must be greater than 0 and no more than 30.",
        "message": (
            "Could not run the web speed test because --max-seconds must be "
            "greater than 0 and no more than 30."
        ),
        "details": {
            "received": value,
            "minimum_exclusive": 0,
            "maximum": 30,
            "unit": "seconds",
        },
    }


def _download_failure(duration, latencies, failures, download):
    error = download["error"] or "No bytes were received."
    return {
        "success": False,
        "error_code": "download_measurement_failed",
        "error": error,
        "message": (
            "Web speed test could not measure download throughput: "
            f"{error}"
        ),
        "details": {
            "duration_limit_seconds": duration,
            "latency_samples_completed": len(latencies),
            "latency_samples_failed": failures,
        },
    }


def _latency_row(latencies, failures):
    return {
        "average": sum(latencies) / len(latencies) if latencies else None,
        "minimum": min(latencies) if latencies else None,
        "maximum": max(latencies) if latencies else None,
        "samples_completed": len(latencies),
        "samples_failed": failures,
        "unit": "milliseconds",
    }


def _success_result(duration, latency, failures, download):
    elapsed = download["duration"]
    speed_mbps = (download["bytes"] * 8) / elapsed / 1_000_000
    speed_mib = download["bytes"] / (1024 * 1024) / elapsed
    latency_summary = (
        f"average HTTP latency {latency['average']:.1f} ms and "
        if latency["average"] is not None
        else "HTTP latency unavailable; "
    )
    result = {
        "success": True,
        "message": (
            f"Web speed test measured {latency_summary}"
            f"{speed_mbps:.2f} Mbps ({speed_mib:.2f} MiB/s) across "
            f"{download['bytes']} bytes in {elapsed:.3f} seconds."
        ),
        "latency": latency,
        "download": {
            "megabits_per_second": round(speed_mbps, 2),
            "mebibytes_per_second": round(speed_mib, 2),
            "bytes_downloaded": download["bytes"],
            "duration_seconds": elapsed,
            "duration_limit_seconds": duration,
            "stopped_at_duration_limit": elapsed >= duration,
        },
    }
    if failures:
        result["warnings"] = [
            {
                "code": "latency_samples_failed",
                "message": (
                    f"{failures} of 3 HTTP latency samples failed; download "
                    "throughput was still measured."
                ),
            }
        ]
    return result


def execute_internet_speed(command, max_seconds=3.0):
    """Run three latency samples and one bounded streaming download."""
    duration, error = _duration_limit(max_seconds)
    if error:
        return error
    clock_floor = time.get_clock_info("perf_counter").resolution
    latencies, failures = command._measure_latency(clock_floor)
    download = command._measure_download(duration, clock_floor)
    if download["bytes"] == 0:
        return _download_failure(duration, latencies, failures, download)
    latency = _latency_row(latencies, failures)
    return _success_result(duration, latency, failures, download)
