"""Readable storage triage with bounded paths, clear scope and no deletion promises."""

from __future__ import annotations

from qzx.commands.file._duplicate_presentation import (
    SPACE_ESTIMATE_NOTE, display_path, duplicate_group_lines,
)


HUMAN_LARGE_FILE_LIMIT = 20


def storage_report(target, assessment, scope, large_files, duplicates, coverage, format_bytes):
    lines = [
        f"Storage diagnosis: {display_path(target)}",
        "Filesystem capacity: {}% used; {} free of {}. Status: {}.".format(
            f"{assessment['percent_used']:g}", assessment["free_readable"],
            assessment["total_readable"], assessment["capacity_status"],
        ),
        "Large files: {} matched; {} returned for review.".format(
            assessment["large_files_matched"], assessment["large_files_returned"]
        ),
    ]
    lines.extend(_large_file_lines(large_files, format_bytes))
    status = coverage["probe_status"]["duplicates"]
    lines.extend(_duplicate_lines(assessment, duplicates, status, format_bytes))
    lines.extend([
        "", "Scope: directory depth 0 through {} (inclusive); large-file threshold {}; "
        "duplicate threshold {} KiB.".format(
            scope["max_depth"], scope["min_file_size"], scope["duplicate_min_size_kb"]
        ),
        "Thresholds and directory exclusions limit coverage; see scan_scope and the probe results in --json.",
    ])
    if coverage["partial"]:
        lines.append("Result completeness: partial; inspect the warnings before drawing conclusions.")
    else:
        lines.append("Result completeness: complete within the requested scope and enabled probes.")
    if status in {"ok", "partial"}:
        lines.extend(["", SPACE_ESTIMATE_NOTE])
    lines.append("Safety: read-only diagnosis; QZX did not delete or modify files.")
    return "\n".join(lines)


def _large_file_lines(large_files, format_bytes):
    results = large_files.get("results") or []
    if not results:
        return []
    lines = ["\nLargest files to review (size alone is not a deletion signal):"]
    for index, item in enumerate(results[:HUMAN_LARGE_FILE_LIMIT], 1):
        size = format_bytes(int(item.get("size_bytes") or 0))
        lines.append(f"  {index}. {size}  {display_path(item.get('path', ''))}")
    if len(results) > HUMAN_LARGE_FILE_LIMIT:
        hidden = len(results) - HUMAN_LARGE_FILE_LIMIT
        lines.append(f"  ... {hidden} more returned files in --json.")
    return lines


def _duplicate_lines(assessment, duplicates, status, format_bytes):
    if status == "skipped":
        return ["\nDuplicates: skipped by request; no absence-of-duplicates conclusion is possible."]
    if status == "failed":
        return ["\nDuplicates: scan failed; see warnings for the partial result."]
    lines = [
        "\nDuplicates: {} verified group(s), {} independent file copies, up to {} "
        "reclaimable content (logical bytes; physical disk savings not measured).".format(
            assessment["duplicate_groups"], assessment["duplicate_files"],
            assessment["confirmed_reclaimable_readable"],
        )
    ]
    if status == "partial":
        lines.append("Duplicate coverage is partial; the verified groups below remain useful.")
    groups = (duplicates or {}).get("duplicate_groups") or {}
    lines.extend(duplicate_group_lines(groups, format_bytes))
    aliases = len((duplicates or {}).get("hardlink_aliases") or [])
    if aliases:
        lines.append(f"Hardlink aliases excluded from independent-copy totals: {aliases}.")
    return lines


def storage_message(target, assessment, coverage):
    message = (
        f"Storage diagnosis completed for '{display_path(target)}': "
        f"{assessment['percent_used']:g}% used with {assessment['free_readable']} free; "
        f"{assessment['large_files_matched']} file(s) matched the large-file threshold. "
    )
    status = coverage["probe_status"]["duplicates"]
    if status in {"ok", "partial"}:
        message += (
            f"Confirmed {assessment['duplicate_groups']} duplicate group(s) with "
            f"{assessment['confirmed_reclaimable_readable']} of redundant logical content. "
        )
    elif status == "skipped":
        message += "Duplicate analysis was skipped. "
    else:
        message += "Duplicate analysis failed. "
    if coverage["partial"]:
        message += "The evidence is partial; see warnings. "
    return message + "QZX did not delete or modify any files."
