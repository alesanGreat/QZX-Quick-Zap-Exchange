"""Actionable, bounded terminal views of verified duplicate-file evidence."""

from __future__ import annotations


SPACE_ESTIMATE_NOTE = (
    "Redundant logical content is not a measurement of recoverable physical disk "
    "space. Hardlink aliases are not independent copies; compression, sparse "
    "files, shared extents and snapshots can change the space actually freed."
)
_CONTROL_ESCAPES = {value: f"\\x{value:02x}" for value in range(32)}
_CONTROL_ESCAPES[127] = "\\x7f"


def display_path(path) -> str:
    """Keep Unicode names readable without letting a filename emit terminal controls."""
    return str(path).translate(_CONTROL_ESCAPES)


def duplicate_totals(groups) -> tuple[int, int]:
    copies = sum(len(group["files"]) for group in groups.values())
    redundant = sum(
        group["size_bytes"] * (len(group["files"]) - 1)
        for group in groups.values()
    )
    return copies, redundant


def duplicate_result(inventory, groups, format_bytes, *, depth, minimum, excluded):
    """Build the structured duplicate-file result from verified evidence."""
    copies, redundant = duplicate_totals(groups)
    return {
        "success": True,
        "message": duplicate_message(inventory, groups, format_bytes),
        "scan_path": inventory.root,
        "total_groups": len(groups),
        "total_duplicate_files": copies,
        "reclaimable_bytes": redundant,
        "reclaimable_space_readable": format_bytes(redundant),
        "reclaimable_space_basis": "logical_content_bytes",
        "physical_reclaimable_bytes": None,
        "space_estimate_note": SPACE_ESTIMATE_NOTE,
        "duplicate_groups": groups,
        "hardlink_aliases": inventory.hardlink_aliases,
        "read_only": True,
        "partial": inventory.partial,
        "scan_complete": not inventory.partial,
        "scan_scope": {
            "max_depth": depth,
            "depth_inclusive": True,
            "min_size_bytes": minimum,
            "excluded_directories": sorted(excluded),
            "follow_directory_links": False,
            "hydrate_offline_files": False,
        },
        "scan_statistics": inventory.statistics,
        "warnings": inventory.warnings,
        "warning_count": inventory.warning_count,
        "warning_counts": dict(inventory.warning_counts),
        "warning_sample_truncated": inventory.warning_count > len(inventory.warnings),
    }


def duplicate_group_lines(groups, format_bytes, *, max_groups=5, max_paths=8):
    """Prioritize redundant content, not just the size of an individual file."""
    ranked = sorted(groups.values(), key=_group_rank)
    lines = []
    for index, group in enumerate(ranked[:max_groups], 1):
        size = int(group.get("size_bytes") or 0)
        paths = sorted(group.get("files") or [])
        redundant = size * max(0, len(paths) - 1)
        lines.append(
            f"  {index}. {format_bytes(redundant)} redundant logical content; "
            f"{len(paths)} independent copies of {format_bytes(size)} each."
        )
        lines.extend(f"     {display_path(path)}" for path in paths[:max_paths])
        if len(paths) > max_paths:
            lines.append(f"     ... {len(paths) - max_paths} more paths in --json.")
    if len(ranked) > max_groups:
        lines.append(f"  ... {len(ranked) - max_groups} more groups in --json.")
    return lines


def _group_rank(group):
    paths = group.get("files") or []
    redundant = int(group.get("size_bytes") or 0) * max(0, len(paths) - 1)
    return -redundant, tuple(sorted(paths))


def duplicate_message(inventory, groups, format_bytes):
    copies, redundant = duplicate_totals(groups)
    lines = [
        f"Duplicate files scan completed for '{display_path(inventory.root)}':",
        f"- Verified duplicate groups: {len(groups)}; independent file copies: {copies}.",
        f"- Redundant logical content: {format_bytes(redundant)} if one copy per group is kept.",
        f"- Scope: directory depth 0 through {inventory.max_depth}, inclusive; "
        f"minimum file size {format_bytes(inventory.min_bytes)}.",
        f"- Hardlink aliases excluded from copy counts: {len(inventory.hardlink_aliases)}.",
    ]
    if groups:
        lines.append("\nTop duplicate groups to review (byte-for-byte verified):")
        lines.extend(duplicate_group_lines(groups, format_bytes))
    lines.extend(_coverage_lines(inventory))
    lines.extend([
        "", SPACE_ESTIMATE_NOTE,
        "Review each group and keep an intentional copy before making any changes.",
        "QZX did not delete or modify any files.",
    ])
    return "\n".join(lines)


def _coverage_lines(inventory):
    stats = inventory.statistics
    lines = [
        "\nCoverage: {} directories, {} files examined; {} independent files hashed.".format(
            stats["directories_scanned"], stats["files_seen"], stats["files_hashed"]
        ),
        "Excluded from traversal: {} dependency directories, {} directory links; "
        "{} directories beyond the requested depth.".format(
            stats["excluded_directories"], stats["directory_links_skipped"],
            stats["depth_limited_directories"],
        ),
    ]
    if inventory.partial:
        lines.append(
            f"Result completeness: partial ({inventory.warning_count} issue(s)); "
            "unreadable or changed files are not evidence of an absence of duplicates."
        )
        for warning in inventory.warnings[:3]:
            lines.append(
                f"  [{warning['code']}] {display_path(warning['path'])}: "
                f"{display_path(warning['message'])}"
            )
        lines.append("See --json for issue counts and the bounded warning sample.")
    else:
        lines.append("Result completeness: complete within the stated scope.")
    return lines
