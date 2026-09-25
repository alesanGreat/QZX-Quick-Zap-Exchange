"""Discovery and removal workflow for generated development directories."""

import fnmatch
import os
import shutil


def _normalize_boolean(value):
    if not isinstance(value, str):
        return bool(value)
    token = value.strip().lower()
    if token in {"true", "yes", "y", "1", "t", "on"}:
        return True
    if token in {"false", "no", "n", "0", "f", "off"}:
        return False
    return None


def _normalize_request(command, scan_path, dry_run, max_depth):
    absolute = os.path.abspath(scan_path)
    if not os.path.exists(absolute):
        return None, command._path_error("path_not_found", f"Path '{scan_path}' does not exist.", absolute)
    if not os.path.isdir(absolute):
        return None, command._path_error("path_not_directory", f"Path '{scan_path}' is not a directory.", absolute)
    preview = _normalize_boolean(dry_run)
    if preview is None:
        return None, command._argument_error("invalid_dry_run", f"Invalid dry_run value: {dry_run!r}.", absolute, dry_run=dry_run, max_depth=max_depth)
    try:
        depth = int(max_depth)
    except (TypeError, ValueError):
        depth = 0
    if depth < 1:
        return None, command._argument_error("invalid_max_depth", f"max_depth must be at least 1, got {max_depth!r}.", absolute, dry_run=preview, max_depth=max_depth)
    return (absolute, preview, depth), None


def _conditional_reason(command, name, files):
    for trigger in command.CONDITIONAL_TARGETS.get(name, ()):
        if "*" in trigger and any(fnmatch.fnmatch(filename, trigger) for filename in files):
            return f"Conditional target '{name}' matched by file pattern '{trigger}'"
        if "*" not in trigger and trigger in files:
            return f"Conditional target '{name}' matched by parent file '{trigger}'"
    return None


def _matched_directories(command, root, directories, files):
    matches = []
    for name in list(directories):
        if name in command.CACHE_TARGETS:
            reason = f"Direct cache target name '{name}'"
        else:
            reason = _conditional_reason(command, name, files)
        if reason:
            directories.remove(name)
            matches.append((os.path.join(root, name), name, reason))
    return matches


def _scan(command, absolute, depth_limit):
    found, identified_bytes = [], 0
    base_depth = absolute.count(os.sep)
    for root, directories, files in os.walk(absolute, topdown=True):
        if root.count(os.sep) - base_depth >= depth_limit:
            directories.clear()
            continue
        directories[:] = [name for name in directories if name not in {".git", ".svn", ".hg"}]
        for path, name, reason in _matched_directories(command, root, directories, files):
            size = command._get_dir_size(path)
            found.append({
                "path": path, "relative_path": os.path.relpath(path, absolute),
                "name": name, "reason": reason, "size_bytes": size,
                "size_readable": command._format_bytes(size),
            })
            identified_bytes += size
    return found, identified_bytes


def _delete(command, found, preview):
    deleted, failures, errors, deleted_bytes = [], [], [], 0
    if preview:
        return deleted, failures, errors, deleted_bytes
    for item in found:
        try:
            command._remove_directory(item["path"])
            deleted.append(item["path"])
            deleted_bytes += item["size_bytes"]
        except Exception as exc:
            errors.append(f"Failed to delete '{item['path']}': {type(exc).__name__}: {exc}")
            failures.append({"path": item["path"], "error_type": type(exc).__name__, "error": str(exc)})
    return deleted, failures, errors, deleted_bytes


def _message(command, absolute, preview, found, deleted, failures, identified, deleted_bytes):
    if preview:
        return (
            f"Previewed '{absolute}' and found {len(found)} generated development "
            f"director(ies), totaling {command._format_bytes(identified)}. Nothing was deleted."
        )
    if failures:
        return (
            f"Cleaned {len(deleted)} of {len(found)} matched directorie(s) below "
            f"'{absolute}', recovering {command._format_bytes(deleted_bytes)}. "
            f"{len(failures)} deletion(s) failed; review deletion_failures and restore "
            "from the reported safety backup if needed."
        )
    return f"Removed {len(deleted)} generated development directorie(s) below '{absolute}', recovering {command._format_bytes(deleted_bytes)}."


def execute_cleanup(command, scan_path=".", dry_run=True, max_depth=4):
    """Discover generated directories and optionally delete selected matches."""
    request, error = _normalize_request(command, scan_path, dry_run, max_depth)
    if error:
        return error
    absolute, preview, depth = request
    try:
        found, identified = _scan(command, absolute, depth)
        deleted, failures, errors, deleted_bytes = _delete(command, found, preview)
        success = not failures
        return {
            "success": success, "status": "preview" if preview else ("success" if success else "partial_failure"),
            "scan_path": absolute, "dry_run": preview, "max_depth": depth,
            "total_folders_found": len(found), "total_bytes_identified": identified,
            "total_space_identified_readable": command._format_bytes(identified),
            "total_bytes_saved": deleted_bytes,
            "total_space_saved_readable": command._format_bytes(deleted_bytes),
            "found_folders": found, "deleted_folders": deleted,
            "deletion_failures": failures, "errors": errors,
            "message": _message(command, absolute, preview, found, deleted, failures, identified, deleted_bytes),
        }
    except Exception as exc:
        return {
            "success": False, "error_code": "scan_failed",
            "error": f"{type(exc).__name__}: {exc}",
            "message": f"Could not inspect generated development directories below '{absolute}': {exc}",
            "details": {"scan_path": absolute, "dry_run": preview, "max_depth": depth},
        }


def get_dir_size(_command, path):
    """Return the size of regular non-link descendants."""
    total = 0
    try:
        for root, _, files in os.walk(path):
            for filename in files:
                candidate = os.path.join(root, filename)
                try:
                    if not os.path.islink(candidate):
                        total += os.path.getsize(candidate)
                except OSError:
                    pass
    except Exception:
        pass
    return total


def remove_directory(_command, path):
    """Remove one selected directory through an overrideable boundary."""
    shutil.rmtree(path)
