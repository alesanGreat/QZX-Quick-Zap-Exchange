"""Scope, capacity and coverage semantics for the composed storage diagnosis."""

from __future__ import annotations

import math

from qzx.core.storage_validation import bounded_integer


def storage_options(min_file_size, max_files, duplicate_min_size_kb, max_depth,
                    include_duplicates, parse_bool):
    include = parse_bool(include_duplicates)
    if include is None:
        raise ValueError("include_duplicates must be true or false.")
    return {
        "min_file_size": min_file_size,
        "max_files": bounded_integer(max_files, "max_files", 1, 1000),
        "duplicate_min_size_kb": bounded_integer(
            duplicate_min_size_kb, "duplicate_min_size_kb", 0, 2**31 - 1
        ),
        "max_depth": bounded_integer(max_depth, "max_depth", 0, 64),
        "include_duplicates": include,
    }


def capacity_assessment(capacity, format_bytes):
    """Missing or invalid capacity cannot be presented as a comfortable disk."""
    info = capacity.get("disk_info")
    if not isinstance(info, dict):
        raise ValueError("Capacity probe did not return disk_info.")
    total, free, percent = _capacity_values(info)
    return {
        "capacity_status": _capacity_status(percent),
        "percent_used": percent,
        "total_bytes": total,
        "total_readable": _readable_bytes(info.get("total"), total, format_bytes),
        "free_bytes": free,
        "free_readable": _readable_bytes(info.get("free"), free, format_bytes),
    }


def _capacity_values(info):
    total, free = info.get("total_bytes"), info.get("free_bytes")
    for name, value in (("total_bytes", total), ("free_bytes", free)):
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise ValueError(f"Capacity {name} must be a non-negative integer.")
    if total <= 0 or free > total:
        raise ValueError("Capacity must have a positive total and free bytes within that total.")
    raw_percent = info.get("percent")
    if isinstance(raw_percent, bool):
        raise ValueError("Capacity percent must be a finite number from 0 to 100.")
    try:
        percent = float(raw_percent)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError("Capacity percent must be a finite number from 0 to 100.") from exc
    if not math.isfinite(percent) or not 0 <= percent <= 100:
        raise ValueError("Capacity percent must be a finite number from 0 to 100.")
    return total, free, percent


def _capacity_status(percent):
    if percent > 90:
        return "critical"
    return "attention" if percent > 80 else "comfortable"


def _readable_bytes(value, count, format_bytes):
    return value if isinstance(value, str) and value else format_bytes(count)


def storage_findings(large_files, duplicates, format_bytes):
    duplicate_data = duplicates if duplicates and duplicates.get("success") else {}
    redundant = int(duplicate_data.get("reclaimable_bytes") or 0)
    return {
        "large_files_matched": int(large_files.get("matched_count") or 0),
        "large_files_returned": int(large_files.get("count") or 0),
        "duplicate_groups": int(duplicate_data.get("total_groups") or 0),
        "duplicate_files": int(duplicate_data.get("total_duplicate_files") or 0),
        "confirmed_reclaimable_bytes": redundant,
        "confirmed_reclaimable_readable": format_bytes(redundant),
        "reclaimable_space_basis": "logical_content_bytes",
        "physical_reclaimable_bytes": None,
    }


def storage_coverage(capacity, large_files, duplicates):
    statuses, warnings = {}, []
    for name, result in (
        ("capacity", capacity), ("large_files", large_files), ("duplicates", duplicates)
    ):
        status = _coverage_status(result)
        statuses[name] = status
        warnings.extend(_probe_warnings(name, result, status))
    return {
        "partial": any(value in {"failed", "partial"} for value in statuses.values()),
        "probe_status": statuses,
        "warnings": warnings,
    }


def _coverage_status(result):
    if result is None:
        return "skipped"
    if result.get("success") is not True:
        return "failed"
    incomplete = (
        result.get("partial") is True or result.get("scan_complete") is False
        or bool(result.get("warnings")) or bool(result.get("skipped_unreadable"))
    )
    return "partial" if incomplete else "ok"


def _probe_warnings(name, result, status):
    if result is None:
        return []
    warnings = [dict(item, probe=name) for item in (result.get("warnings") or [])]
    if status == "failed":
        code = "duplicate_scan_failed" if name == "duplicates" else f"{name}_probe_failed"
        warnings.append({
            "code": code, "probe": name,
            "message": result.get("message") or result.get("error") or "Probe failed.",
        })
    elif status == "partial" and not warnings:
        warnings.append({
            "code": f"{name}_scan_partial", "probe": name,
            "message": "The probe reported incomplete coverage; its evidence is partial.",
        })
    return warnings
