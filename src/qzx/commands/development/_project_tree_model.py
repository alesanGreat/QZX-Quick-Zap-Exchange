"""Validation and result model for ``getProjectTree``."""

import os
from dataclasses import dataclass, field
from pathlib import Path


DEFAULT_EXCLUDES = (
    ".git", ".idea", ".next", ".nuxt", ".venv", ".vscode", "__pycache__",
    "artifacts", "build", "dist", "env", "node_modules",
)
DEFAULT_EXCLUDES_TEXT = ",".join(DEFAULT_EXCLUDES)


@dataclass
class _TreeScanState:
    """Mutable counters and bounded evidence for one tree traversal."""

    root: Path
    max_entries: int
    entry_count: int = 0
    directory_count: int = 0
    file_count: int = 0
    symlink_count: int = 0
    other_count: int = 0
    unavailable_count: int = 0
    excluded_directory_count: int = 0
    skipped_file_count: int = 0
    scan_error_count: int = 0
    scan_error_samples: list[dict[str, str]] = field(default_factory=list)
    entry_limit_reached: bool = False

    @property
    def remaining_entries(self):
        return max(0, self.max_entries - self.entry_count)

    def record_error(self, path, error):
        self.scan_error_count += 1
        if len(self.scan_error_samples) < 20:
            self.scan_error_samples.append(
                {"path": str(path), "error_type": type(error).__name__, "error": str(error)}
            )

    def record_entry(self, entry_type):
        self.entry_count += 1
        if entry_type == "directory":
            self.directory_count += 1
        elif entry_type == "file":
            self.file_count += 1
        elif entry_type == "symlink":
            self.symlink_count += 1
        elif entry_type == "unavailable":
            self.unavailable_count += 1
        else:
            self.other_count += 1


def normalize_directory(dir_path):
    try:
        raw_path = os.fspath(dir_path)
    except TypeError:
        return None, _path_error("invalid_directory_path", "dir_path must be text or a filesystem path object.", "Provide a directory path for the project tree.")
    if not isinstance(raw_path, str):
        return None, _path_error("invalid_directory_path", "dir_path must resolve to text, not raw bytes.", "Provide a text directory path for the project tree.")
    if not raw_path or "\x00" in raw_path:
        return None, _path_error("invalid_directory_path", "dir_path must not be empty." if not raw_path else "dir_path must not contain NUL bytes.", "Provide a non-empty directory path for the project tree." if not raw_path else "Provide a valid directory path for the project tree.")
    try:
        normalized = Path(raw_path).expanduser().absolute()
        exists, is_directory = normalized.exists(), normalized.is_dir()
    except (OSError, RuntimeError, ValueError) as exc:
        return None, _path_error("invalid_directory_path", f"{type(exc).__name__}: {exc}", "QZX could not normalize the requested directory path.")
    if not exists:
        return None, _path_error("directory_not_found", f"Directory '{normalized}' does not exist.", f"The requested project directory '{normalized}' was not found.")
    if not is_directory:
        return None, _path_error("not_a_directory", f"'{normalized}' is not a directory.", "Project trees require a directory path.")
    return normalized, None


def _path_error(code, error, message):
    return {"success": False, "error_code": code, "error": error, "message": message}


def bounded_integer(value, *, field, minimum, maximum):
    try:
        parsed = None if isinstance(value, bool) else int(value)
    except (TypeError, ValueError, OverflowError):
        parsed = None
    if parsed is None or parsed < minimum or parsed > maximum:
        return None, {
            "success": False,
            "error_code": f"invalid_{field}",
            "error": f"{field} must be an integer from {minimum} through {maximum}; received {value!r}.",
            "message": f"Choose a bounded {field} value and retry.",
        }
    return parsed, None


def normalize_boolean(cls, value):
    return value if isinstance(value, bool) else cls._parse_bool(value)


def normalize_excludes(exclude_dirs):
    if exclude_dirs is None:
        names = DEFAULT_EXCLUDES
    elif isinstance(exclude_dirs, str):
        names = exclude_dirs.split(",")
    else:
        return None, {
            "success": False,
            "error_code": "invalid_exclude_dirs",
            "error": "exclude_dirs must be one comma-separated string.",
            "message": "Provide directory names separated by commas.",
        }
    return {name.strip().casefold() for name in names if name.strip()}, None
