"""Filesystem inventory and cleanup-candidate classification for QZX."""

from __future__ import annotations

from collections import defaultdict
import os
from pathlib import Path, PurePosixPath

from qzx.core.workspace_contract import MAX_DUPLICATE_BYTES, WorkspaceAuditError
IGNORED_DIRECTORY_NAMES = {
    ".git",
    ".hg",
    ".svn",
    ".dropbox",
    ".dropbox.cache",
    "node_modules",
}
DIRECT_BUILD_DIRECTORIES = {
    "__pycache__",
    ".pytest_cache",
    ".sass-cache",
    ".next",
    ".nuxt",
    ".turbo",
}
CONDITIONAL_BUILD_DIRECTORIES = {
    "dist": {"package.json", "pyproject.toml", "setup.py"},
    "build": {"package.json", "pyproject.toml", "setup.py", "CMakeLists.txt"},
    "target": {"Cargo.toml"},
    "out": {"package.json", "tsconfig.json"},
}
BUILD_FILE_EXTENSIONS = {".pyc", ".pyo", ".class"}
TEMP_DELETE_EXTENSIONS = {".tmp", ".swp", ".temp"}
TEMP_REVIEW_EXTENSIONS = {".log", ".bak"}
ARTIFACT_EXTENSIONS = {
    ".a",
    ".dll",
    ".dylib",
    ".exe",
    ".lib",
    ".o",
    ".obj",
    ".pyd",
    ".so",
}
DUPLICATE_NAME_PATTERNS = (" (1)", " - copy", "_backup", "_copy")
class WorkspaceInventoryScanner:
    """Collect a deterministic, bounded, non-traversing workspace inventory."""

    def __init__(self, root, max_files, *, entry_type):
        self.root = root
        self.max_files = max_files
        self.entry_type = entry_type
        self.inventory = {}
        self.errors = []
        self.ignored = []
        self.file_count = 0
        self.limit_reached = False
    def scan(self):
        stack = [self.root]
        while stack and not self.limit_reached:
            directory = stack.pop()
            entries = self._read_directory(directory)
            if entries is None:
                continue
            child_directories = []
            for entry in entries:
                child = self._record_entry(entry)
                if child is not None:
                    child_directories.append(child)
                if self.limit_reached:
                    break
            stack.extend(reversed(child_directories))
        return self.inventory, self.errors, self.ignored, self.limit_reached
    def _read_directory(self, directory):
        relative = self._relative(directory)
        try:
            with os.scandir(directory) as scanner:
                return sorted(scanner, key=lambda item: (item.name.casefold(), item.name))
        except OSError as exc:
            self._record_error(relative, exc)
            return None

    def _record_entry(self, entry):
        entry_path = Path(entry.path)
        relative = entry_path.relative_to(self.root).as_posix()
        try:
            item_type = self.entry_type(entry)
        except OSError as exc:
            self._record_error(relative, exc)
            return None
        if item_type == "directory":
            return self._record_directory(entry, entry_path, relative)
        if not self._accept_file(relative):
            return None
        self._record_non_directory(entry, entry_path, relative, item_type)
        return None

    def _record_directory(self, entry, entry_path, relative):
        if entry.name in IGNORED_DIRECTORY_NAMES or entry.name.startswith(
            ".qzx-repair-stage-"
        ):
            self.ignored.append(relative)
            return None
        self.inventory[relative] = {
            "path": entry_path,
            "type": "directory",
            "name": entry.name,
        }
        return entry_path

    def _accept_file(self, relative):
        self.file_count += 1
        if self.file_count <= self.max_files:
            return True
        self.limit_reached = True
        self.errors.append(
            {
                "path": relative,
                "error_type": "ScanLimitExceeded",
                "error": (
                    "The scan exceeded max_files={}; no resulting plan may be applied."
                ).format(self.max_files),
            }
        )
        return False

    def _record_non_directory(self, entry, entry_path, relative, item_type):
        item = {"path": entry_path, "type": item_type, "name": entry.name}
        if item_type == "file":
            try:
                item["size_bytes"] = entry.stat(follow_symlinks=False).st_size
            except OSError as exc:
                self._record_error(relative, exc)
                return
        self.inventory[relative] = item

    def _record_error(self, relative, error):
        self.errors.append(
            {
                "path": relative,
                "error_type": type(error).__name__,
                "error": str(error),
            }
        )

    def _relative(self, directory):
        if directory == self.root:
            return "."
        return directory.relative_to(self.root).as_posix()


class WorkspaceInventoryClassifier:
    """Turn one workspace inventory into explicit delete or review actions."""

    def __init__(
        self,
        root,
        inventory,
        categories,
        file_hasher,
        *,
        fingerprint,
        files_equal,
        is_link_like,
    ):
        self.root = root
        self.inventory = inventory
        self.categories = categories
        self.file_hasher = file_hasher
        self.fingerprint = fingerprint
        self.files_equal = files_equal
        self.is_link_like = is_link_like
        self.actions = []
        self.executable_directories = set()
        self.duplicate_candidates = defaultdict(list)

    def classify(self):
        if "build" in self.categories:
            self._classify_build_directories()
        self._classify_entries()
        if "duplicates" in self.categories:
            self._classify_duplicates()
        return deduplicate_actions(self.actions)

    def _classify_build_directories(self):
        for relative, item in self.inventory.items():
            if item["type"] != "directory":
                continue
            if nested_under_any(relative, self.executable_directories):
                continue
            reason = build_directory_reason(
                self.root,
                relative,
                item["name"],
                is_link_like=self.is_link_like,
            )
            if reason is not None:
                self._record_build_directory(relative, item, reason)

    def _record_build_directory(self, relative, item, reason):
        try:
            fingerprint = self.fingerprint(item["path"])
        except (OSError, WorkspaceAuditError) as exc:
            self.actions.append(
                review_action(
                    "build",
                    relative,
                    "review_directory",
                    "Build candidate requires review because it could not be "
                    "fingerprinted safely: {}: {}.".format(type(exc).__name__, exc),
                )
            )
            return
        self.executable_directories.add(relative)
        self.actions.append(
            {
                "category": "build",
                "kind": "delete_directory",
                "path": relative,
                "reason": reason,
                "executable": True,
                "size_bytes": fingerprint["size_bytes"],
                "fingerprint": fingerprint,
            }
        )

    def _classify_entries(self):
        for relative, item in self.inventory.items():
            if nested_under_any(relative, self.executable_directories):
                continue
            if item["type"] == "file":
                self._classify_file(relative, item)
            elif "reorganizations" in self.categories and item["type"] in {
                "symlink",
                "special",
            }:
                self.actions.append(
                    review_action(
                        "reorganizations",
                        relative,
                        "review_special_entry",
                        "{} entries are never altered automatically.".format(
                            item["type"].capitalize()
                        ),
                    )
                )

    def _classify_file(self, relative, item):
        path = item["path"]
        size = item["size_bytes"]
        suffix = path.suffix.lower()
        primary = self._primary_file_action(relative, item, suffix)
        if primary is not None:
            self.actions.append(primary)
        scheduled = bool(primary and primary["executable"])
        if "artifacts" in self.categories and suffix in ARTIFACT_EXTENSIONS:
            self.actions.append(
                review_action(
                    "artifacts",
                    relative,
                    "review_file",
                    "Compiled artifacts may be intentional deliverables.",
                    size,
                )
            )
        if "reorganizations" in self.categories:
            self._classify_reorganization(relative, item)
        if "duplicates" in self.categories and not scheduled and size <= MAX_DUPLICATE_BYTES:
            self._record_duplicate_candidate(relative, item)

    def _primary_file_action(self, relative, item, suffix):
        if "build" in self.categories and suffix in BUILD_FILE_EXTENSIONS:
            return file_delete_action(
                "build",
                relative,
                item["path"],
                "Known generated build or interpreter-cache extension.",
                fingerprint=self.fingerprint,
            )
        if "temp" in self.categories and (
            suffix in TEMP_DELETE_EXTENSIONS or item["name"].endswith("~")
        ):
            return file_delete_action(
                "temp",
                relative,
                item["path"],
                "Temporary editor or tool output selected for explicit cleanup.",
                fingerprint=self.fingerprint,
            )
        if "temp" in self.categories and suffix in TEMP_REVIEW_EXTENSIONS:
            return review_action(
                "temp",
                relative,
                "review_file",
                "Logs and backup files can contain valuable recovery evidence.",
                item["size_bytes"],
            )
        return None

    def _classify_reorganization(self, relative, item):
        path = item["path"]
        candidate_name, reasons = proposed_name(item["name"])
        if item["name"] == ".env" and path.parent != self.root:
            self.actions.append(
                review_action(
                    "reorganizations",
                    relative,
                    "review_move",
                    "Nested .env files can be scope-specific and are never moved automatically.",
                    item["size_bytes"],
                    proposed_path=".env",
                )
            )
        elif candidate_name != item["name"]:
            proposed_relative = (PurePosixPath(relative).parent / candidate_name).as_posix()
            self.actions.append(
                review_action(
                    "reorganizations",
                    relative,
                    "review_rename",
                    "Filename normalization suggestion: {}.".format(", ".join(reasons)),
                    item["size_bytes"],
                    proposed_path=proposed_relative,
                )
            )

    def _record_duplicate_candidate(self, relative, item):
        try:
            digest = self.file_hasher(item["path"])
        except OSError:
            return
        key = (item["size_bytes"], digest)
        self.duplicate_candidates[key].append((relative, item["path"]))
        lowered_name = item["name"].lower()
        if any(pattern in lowered_name for pattern in DUPLICATE_NAME_PATTERNS):
            self.actions.append(
                review_action(
                    "duplicates",
                    relative,
                    "review_filename_pattern",
                    "The filename resembles a copy, but name alone never authorizes deletion.",
                    item["size_bytes"],
                )
            )

    def _classify_duplicates(self):
        for candidates in self._ordered_duplicate_groups():
            originals = []
            for relative, path in candidates:
                matching = self._matching_original(path, originals)
                if matching is None:
                    originals.append((relative, path))
                    continue
                self._record_duplicate(relative, path, matching)

    def _ordered_duplicate_groups(self):
        for _key, candidates in sorted(self.duplicate_candidates.items()):
            candidates.sort(key=lambda item: (item[0].casefold(), item[0]))
            yield candidates

    def _matching_original(self, path, originals):
        return next(
            (original for original in originals if self.files_equal(path, original[1])),
            None,
        )

    def _record_duplicate(self, relative, path, matching):
        target_fingerprint = self.fingerprint(path)
        original_fingerprint = self.fingerprint(matching[1])
        self.actions.append(
            {
                "category": "duplicates",
                "kind": "delete_duplicate",
                "path": relative,
                "duplicate_of": matching[0],
                "reason": "SHA-256 and exact byte match.",
                "executable": True,
                "size_bytes": target_fingerprint["size_bytes"],
                "fingerprint": target_fingerprint,
                "original_fingerprint": original_fingerprint,
            }
        )


def scan_inventory(root, max_files, *, entry_type):
    return WorkspaceInventoryScanner(root, max_files, entry_type=entry_type).scan()


def classify_inventory(
    root,
    inventory,
    categories,
    file_hasher,
    *,
    fingerprint,
    files_equal,
    is_link_like,
):
    return WorkspaceInventoryClassifier(
        root,
        inventory,
        categories,
        file_hasher,
        fingerprint=fingerprint,
        files_equal=files_equal,
        is_link_like=is_link_like,
    ).classify()


def build_directory_reason(root, relative, name, *, is_link_like):
    if name in DIRECT_BUILD_DIRECTORIES:
        return "Known generated cache or build directory name."
    triggers = CONDITIONAL_BUILD_DIRECTORIES.get(name)
    if triggers is None:
        return None
    parent = (root / PurePosixPath(relative)).parent
    matched = sorted(
        trigger
        for trigger in triggers
        if (parent / trigger).is_file() and not is_link_like(parent / trigger)
    )
    if not matched:
        return None
    return "Generated directory matched parent marker(s): {}.".format(", ".join(matched))


def file_delete_action(category, relative, path, reason, *, fingerprint):
    path_fingerprint = fingerprint(path)
    return {
        "category": category,
        "kind": "delete_file",
        "path": relative,
        "reason": reason,
        "executable": True,
        "size_bytes": path_fingerprint["size_bytes"],
        "fingerprint": path_fingerprint,
    }


def review_action(
    category,
    relative,
    kind,
    reason,
    size_bytes=0,
    proposed_path=None,
):
    action = {
        "category": category,
        "kind": kind,
        "path": relative,
        "reason": reason,
        "executable": False,
        "size_bytes": size_bytes,
    }
    if proposed_path is not None:
        action["proposed_path"] = proposed_path
    return action


def proposed_name(name):
    stem, suffix = os.path.splitext(name)
    reasons = []
    proposed_stem = stem
    proposed_suffix = suffix
    if " " in name:
        proposed_stem = stem.replace(" ", "_")
        reasons.append("spaces in name")
    if suffix and suffix != suffix.lower():
        proposed_suffix = suffix.lower()
        reasons.append("uppercase extension")
    return proposed_stem + proposed_suffix, reasons


def deduplicate_actions(actions):
    seen = set()
    unique = []
    for action in actions:
        key = (
            action["category"],
            action["kind"],
            action["path"],
            action.get("proposed_path"),
        )
        if key not in seen:
            seen.add(key)
            unique.append(action)
    return unique


def nested_under_any(relative, parents):
    candidate = PurePosixPath(relative)
    return any(
        parent == relative or PurePosixPath(parent) in candidate.parents
        for parent in parents
    )
