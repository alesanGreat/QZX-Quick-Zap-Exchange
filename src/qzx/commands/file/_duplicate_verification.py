"""SHA-256 candidates are verified by bytes and rechecked for observable changes."""

from __future__ import annotations

from ._duplicate_inventory import file_signature, file_snapshot


def verified_duplicate_groups(
    inventory,
    hash_file,
    compare_files,
    format_bytes,
    *,
    snapshot_reader=file_snapshot,
):
    """Return only independent, unchanged files whose content compared equal."""
    verified = []
    for size, candidates in sorted(inventory.files_by_size.items()):
        if len(candidates) < 2:
            continue
        by_digest = _hash_candidates(
            inventory, candidates, hash_file, snapshot_reader
        )
        for digest, matching in sorted(by_digest.items()):
            if len(matching) < 2:
                continue
            for group in _partition_by_bytes(
                inventory, matching, compare_files, snapshot_reader
            ):
                if len(group) > 1:
                    verified.append((digest, size, group))
    return _finalize_groups(
        inventory, verified, format_bytes, snapshot_reader
    )


def _finalize_groups(inventory, verified, format_bytes, snapshot_reader):
    duplicates = {}
    for digest, size, group in verified:
        stable = [
            item
            for item in group
            if _unchanged(inventory, item, snapshot_reader)
        ]
        if len(stable) < 2:
            continue
        key = _group_key(duplicates, digest)
        duplicates[key] = {
            "sha256": digest,
            "verification": "byte_for_byte",
            "size_bytes": size,
            "size_readable": format_bytes(size),
            "files": sorted(item.path for item in stable),
            "independent_file_count": len(stable),
            "reclaimable_bytes": size * (len(stable) - 1),
        }
    return duplicates


def _hash_candidates(inventory, candidates, hash_file, snapshot_reader):
    hashes = {}
    for candidate in candidates:
        if not _unchanged(inventory, candidate, snapshot_reader):
            continue
        try:
            inventory.statistics["hash_attempts"] += 1
            digest = hash_file(candidate.path)
        except OSError as exc:
            inventory.problem("hash_failed", str(exc), candidate.path)
            continue
        if not isinstance(digest, str) or not digest:
            inventory.problem(
                "hash_failed", "No content digest was returned.", candidate.path
            )
            continue
        inventory.statistics["files_hashed"] += 1
        if _unchanged(inventory, candidate, snapshot_reader):
            hashes.setdefault(digest, []).append(candidate)
    return hashes


def _partition_by_bytes(
    inventory, candidates, compare_files, snapshot_reader
):
    groups = []
    for candidate in candidates:
        match = _matching_group(
            inventory, candidate, groups, compare_files, snapshot_reader
        )
        if match is False:
            continue
        if match is None:
            groups.append([candidate])
        else:
            match.append(candidate)
    return groups


def _matching_group(
    inventory, candidate, groups, compare_files, snapshot_reader
):
    if not _unchanged(inventory, candidate, snapshot_reader):
        return False
    for group in groups:
        representative = group[0]
        if not _unchanged(inventory, representative, snapshot_reader):
            continue
        try:
            inventory.statistics["byte_comparisons"] += 1
            identical = compare_files(candidate.path, representative.path)
        except OSError as exc:
            inventory.problem("comparison_failed", str(exc), candidate.path)
            return False
        if not _unchanged(inventory, candidate, snapshot_reader):
            return False
        if not _unchanged(inventory, representative, snapshot_reader):
            return False
        if identical:
            return group
    return None


def _unchanged(inventory, candidate, snapshot_reader) -> bool:
    try:
        current = snapshot_reader(candidate.path)
    except OSError as exc:
        inventory.problem("file_unreadable", str(exc), candidate.path)
        return False
    if file_signature(current) != candidate.signature:
        inventory.problem(
            "file_changed",
            "File changed during analysis; its evidence was excluded.",
            candidate.path,
        )
        return False
    return True


def _group_key(groups, digest):
    """A forced collision, including across sizes, must not overwrite another group."""
    key = digest
    number = 1
    while key in groups:
        number += 1
        key = f"{digest}:{number}"
    return key
