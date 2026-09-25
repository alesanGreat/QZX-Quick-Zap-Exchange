"""CPU load snapshot assembly for getCpuLoad."""

from __future__ import annotations


def _interval_value(value):
    try:
        return float(value), None
    except (TypeError, ValueError):
        return None, {
            "success": False,
            "error": f"Error: interval must be a number, got '{value}'",
            "message": (
                f"Failed to get CPU information: interval must be a number, "
                f"got '{value}'"
            ),
        }


def _frequency_row(freq):
    row = {}
    for source, target in (
        ("current", "current_mhz"),
        ("min", "min_mhz"),
        ("max", "max_mhz"),
    ):
        value = getattr(freq, source, None)
        if value:
            row[target] = value
    return row


def _add_frequency(psutil_module, result):
    try:
        frequency = psutil_module.cpu_freq(percpu=False)
        if frequency:
            row = _frequency_row(frequency)
            if row:
                result["frequency"] = row
        try:
            per_core = psutil_module.cpu_freq(percpu=True)
        except Exception:
            return
        rows = []
        for index, frequency in enumerate(per_core or []):
            current = getattr(frequency, "current", None)
            if current:
                rows.append({"core": index + 1, "current_mhz": current})
        if rows:
            result["per_core_frequency"] = rows
    except Exception:
        pass


def _add_load_average(psutil_module, result):
    try:
        values = psutil_module.getloadavg()
    except Exception:
        return
    result["load_average"] = {
        "1min": values[0],
        "5min": values[1],
        "15min": values[2],
    }


def _add_times(psutil_module, result):
    try:
        times = psutil_module.cpu_times_percent()
    except Exception:
        return
    values = {}
    for name in ("user", "system", "idle", "nice", "iowait"):
        value = getattr(times, name, None)
        if value is not None:
            values[name] = value
    if values:
        result["times_percent"] = values


def _message(result, interval):
    cores_text = f"{result['cores_count']} cores"
    frequency = result.get("frequency", {}).get("current_mhz")
    freq_text = f" running at {frequency:.0f} MHz" if frequency else ""
    message = (
        f"CPU usage: {result['overall_percent']:.1f}% overall across "
        f"{cores_text}{freq_text}. Measured over {interval} second"
        f"{'' if interval == 1 else 's'}."
    )
    if "load_average" in result:
        load = result["load_average"]
        message += (
            f" Load averages: {load['1min']:.2f} (1m), "
            f"{load['5min']:.2f} (5m), {load['15min']:.2f} (15m)."
        )
    return message


def execute_cpu_load(command, interval=1):
    """Return one normalized CPU load snapshot."""
    interval, error = _interval_value(interval)
    if error:
        return error
    try:
        psutil_module = command._psutil
        overall = psutil_module.cpu_percent(interval=interval)
        per_core = psutil_module.cpu_percent(interval=0.0, percpu=True)
        result = {
            "success": True,
            "overall_percent": overall,
            "per_core": [
                {"core": index + 1, "percent": percent}
                for index, percent in enumerate(per_core)
            ],
            "cores_count": len(per_core),
        }
        _add_frequency(psutil_module, result)
        _add_load_average(psutil_module, result)
        _add_times(psutil_module, result)
        result["message"] = _message(result, interval)
        return result
    except Exception as exc:
        return {
            "success": False,
            "error": f"Error getting CPU load information: {str(exc)}",
            "message": f"Failed to retrieve CPU information: {str(exc)}",
        }
