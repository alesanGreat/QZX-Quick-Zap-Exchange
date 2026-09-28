"""Native Tokei adapter for projectLanguages.

Performance contract: the default/``auto`` route must prefer a compatible native
backend without running both backends just to decide which is faster. Python is
the portability/recovery path when native code is unavailable, explicitly
disabled, or rejects/fails a scan. Never choose a stale native binary merely to
avoid Python; source-checkout cache entries must match the Rust source fingerprint.

Remaining general optimizations are recorded next to the expensive boundaries
below. They must preserve ignore rules, exclusions, symlink/error accounting,
unclassified files, fresh filesystem state, and backend-specific result parity.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
from collections import Counter
from pathlib import Path

from qzx.core.file_search_entries import walk_directory_entries
from qzx.core.path_identity import canonical_path_key


def _load_extension(path):
    path = Path(path).expanduser().resolve()
    if not path.is_file():
        return None, f"native module does not exist: {path}"
    try:
        spec = importlib.util.spec_from_file_location(
            "qzx._project_languages_native",
            path,
        )
        if spec is None or spec.loader is None:
            return None, f"cannot load native module from {path}"
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module, None
    except (ImportError, OSError) as error:
        return None, f"{type(error).__name__}: {error}"


def _source_native_fingerprint():
    project_root = Path(__file__).resolve().parents[4]
    native_root = project_root / "native" / "project_languages"
    files = (
        native_root / "Cargo.toml",
        native_root / "Cargo.lock",
        native_root / "src" / "lib.rs",
    )
    if not all(path.is_file() for path in files):
        return None
    digest = hashlib.sha256()
    for path in files:
        digest.update(path.name.encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()[:24]


def _native_cache_directory():
    """Return the shared native cache root used by discovery and provisioning."""
    explicit_cache = os.environ.get("QZX_NATIVE_CACHE")
    if explicit_cache:
        cache_root = Path(explicit_cache).expanduser()
    elif os.name == "nt" and os.environ.get("LOCALAPPDATA"):
        cache_root = Path(os.environ["LOCALAPPDATA"]) / "QZX" / "native"
    else:
        cache_root = Path(
            os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache")
        ) / "qzx" / "native"

    return cache_root / "project_languages"


def _native_cache_candidates():
    project_cache = _native_cache_directory()
    fingerprint = _source_native_fingerprint()
    if fingerprint:
        project_cache = project_cache / fingerprint
    if not project_cache.is_dir():
        return []
    candidates = []
    for pattern in (
        "_project_languages_native*.pyd",
        "_project_languages_native*.so",
        "_project_languages_native*.dylib",
    ):
        candidates.extend(project_cache.glob(pattern))
    return sorted(candidates, key=lambda path: path.name)


def _load_native_module():
    """Load the fastest compatible backend known without per-run benchmarking.

    Order is deliberate: an installed/bundled native extension is cheapest to
    discover; source checkouts may then use an explicit native path or a
    source-fingerprint-matched cache. If none loads, callers retain Python.
    A future build-time embedded fingerprint could reduce source-checkout hashing,
    but must not be replaced by an mtime/size-only cache that can accept stale code.
    """
    if os.environ.get("QZX_PROJECT_LANGUAGES_BACKEND", "auto").casefold() == "python":
        return None, "disabled by QZX_PROJECT_LANGUAGES_BACKEND=python"
    try:
        from qzx import _project_languages_native

        return _project_languages_native, None
    except ImportError as import_error:
        errors = [str(import_error)]

    override = os.environ.get("QZX_PROJECT_LANGUAGES_NATIVE")
    candidates = [Path(override)] if override else []
    candidates.extend(_native_cache_candidates())
    for candidate in candidates:
        module, error = _load_extension(candidate)
        if module is not None:
            return module, None
        if error:
            errors.append(error)
    return None, "; ".join(error for error in errors if error)


_NATIVE, NATIVE_IMPORT_ERROR = _load_native_module()


def native_available():
    return _NATIVE is not None


def _path_key(path):
    return canonical_path_key(path)


def _new_language(command, language):
    return {
        "language": language,
        "kind": command._language_kind(language, []),
        "aliases": [],
        "file_count": 0,
        "bytes": 0,
        "total_lines": 0,
        "code_lines": 0,
        "comment_lines": 0,
        "blank_lines": 0,
        "extensions": Counter(),
        "detected_variants": Counter(),
        "example_files": [],
    }


def _record_native(command, record, scan_root, language_stats):
    language = str(record["language"])
    stats = language_stats.get(language)
    if stats is None:
        stats = language_stats[language] = _new_language(command, language)
    stats["file_count"] += 1
    stats["bytes"] += int(record["bytes"])
    stats["total_lines"] += int(record["total_lines"])
    stats["code_lines"] += int(record["code_lines"])
    stats["comment_lines"] += int(record["comment_lines"])
    stats["blank_lines"] += int(record["blank_lines"])
    path = Path(record["path"])
    stats["extensions"][path.suffix.casefold() or "(no extension)"] += 1
    stats["detected_variants"][language] += 1
    # Resolve display paths only for examples that will actually be retained.
    if len(stats["example_files"]) < command.MAX_EXAMPLES_PER_GROUP:
        command._append_example(
            stats["example_files"],
            command._relative_display(path, scan_root),
        )


def _append_exclusion(command, state, reason, path, scan_root):
    relative = command._relative_display(path, scan_root)
    if reason == "oversized":
        state["counters"]["oversized_files"] += 1
        command._append_example(state["examples"]["oversized"], relative)
    elif reason == "binary":
        state["counters"]["binary_files"] += 1
        command._append_example(state["examples"]["binary"], relative)
    elif reason == "generated":
        state["counters"]["generated_files"] += 1
        command._append_example(state["examples"]["generated"], relative)


def _classify_unreported(command, path, scan_root, state):
    relative = command._relative_display(path, scan_root)
    try:
        size = path.stat().st_size
        if size > command.MAX_FILE_SIZE_BYTES:
            _append_exclusion(command, state, "oversized", path, scan_root)
            return
        with path.open("rb") as file_handle:
            raw = file_handle.read(min(command.MAX_FILE_SIZE_BYTES, 128 * 1024))
        if command._looks_binary(raw):
            _append_exclusion(command, state, "binary", path, scan_root)
            return
        text = command._decode_text(raw)
        if command._is_generated(path.name, text):
            _append_exclusion(command, state, "generated", path, scan_root)
            return
        state["counters"]["unknown_files"] += 1
        state["extensions"][path.suffix.casefold() or "(no extension)"] += 1
        command._append_example(state["unknown_examples"], relative)
    except (OSError, UnicodeError, ValueError) as error:
        command._record_error(state["errors"], scan_root, path, error)


def _handle_metadata_file(
    command,
    path,
    scopes,
    scan_root,
    state,
    native_status,
    included,
    entry=None,
):
    state["counters"]["visited_files"] += 1
    if entry.is_symlink() if entry is not None else path.is_symlink():
        state["counters"]["symlinks_skipped"] += 1
        return
    if scopes and command._is_ignored(path, False, scopes):
        state["counters"]["ignored_files"] += 1
        return
    key = _path_key(path)
    status = native_status.get(key)
    if status == "recognized":
        included.add(key)
    elif status in {"generated", "binary", "oversized"}:
        _append_exclusion(command, state, status, path, scan_root)
    else:
        _classify_unreported(command, path, scan_root, state)


def _retained_directories(command, root, directory_names, scopes, state):
    retained = []
    for item in directory_names:
        entry = item if isinstance(item, os.DirEntry) else None
        name = entry.name if entry is not None else item
        path = root / name
        if entry.is_symlink() if entry is not None else path.is_symlink():
            state["counters"]["symlinks_skipped"] += 1
        elif name.casefold() in command.DEFAULT_EXCLUDED_DIRECTORIES:
            state["counters"]["ignored_directories"] += 1
        elif command._is_ignored(path, True, scopes):
            state["counters"]["ignored_directories"] += 1
        else:
            retained.append(item)
    return retained


# PERFORMANCE ROADMAP: Tokei already traversed these targets. This second pass
# is intentional because QZX still owns ignore/reinclude semantics, symlink
# counts, unknown files, exclusions and read-error accounting. The largest
# remaining native-path win is moving that complete metadata contract into Rust;
# remove this traversal only after exact parity tests.
def _metadata_scan(command, target, state, native_status):
    scan_root = target if target.is_dir() else target.parent
    included = set()
    if target.is_file():
        _handle_metadata_file(
            command, target, [], scan_root, state, native_status, included
        )
        return scan_root, included

    scopes = command._initial_ignore_scopes(
        scan_root,
        state["ignore_sources"],
        state["errors"],
    )

    def record_walk_error(error):
        path = Path(getattr(error, "filename", scan_root))
        command._record_error(state["errors"], scan_root, path, error)

    for root_text, directory_names, file_entries in walk_directory_entries(
        scan_root, on_error=record_walk_error,
    ):
        root = Path(root_text)
        if root != scan_root:
            command._load_ignore_files(
                root,
                scan_root,
                scopes,
                state["ignore_sources"],
                state["errors"],
            )
        directory_names[:] = _retained_directories(
            command, root, directory_names, scopes, state
        )
        for entry in file_entries:
            _handle_metadata_file(
                command,
                root / entry.name,
                scopes,
                scan_root,
                state,
                native_status,
                included,
                entry=entry,
            )
    return scan_root, included


def _native_payload(command, targets, *, native_module=None):
    """Prefer zero-copy PyO3 objects while retaining the legacy JSON ABI."""
    backend = _NATIVE if native_module is None else native_module
    if backend is None:
        raise RuntimeError(NATIVE_IMPORT_ERROR or "native backend unavailable")
    paths = [str(Path(target).resolve()) for target in targets]
    excluded = sorted(command.DEFAULT_EXCLUDED_DIRECTORIES)
    max_bytes = int(command.MAX_FILE_SIZE_BYTES)

    if len(paths) == 1:
        scanner = getattr(backend, "scan_project", None)
        if scanner is not None:
            payload = scanner(paths[0], excluded, max_bytes)
        else:
            payload = json.loads(
                backend.scan_project_json(paths[0], excluded, max_bytes)
            )
    else:
        scanner = getattr(backend, "scan_projects", None)
        if scanner is not None:
            payload = scanner(paths, excluded, max_bytes)
        else:
            json_scanner = getattr(backend, "scan_projects_json", None)
            if json_scanner is None:
                raise RuntimeError(
                    "native backend does not support batch scanning"
                )
            payload = json.loads(json_scanner(paths, excluded, max_bytes))

    if not isinstance(payload, dict):
        raise RuntimeError(
            "native projectLanguages backend returned a non-object payload"
        )
    return payload


def scan_native_records(command, targets):
    return _native_payload(command, targets)


def _native_maps(payload):
    if payload.get("inaccurate_languages"):
        raise RuntimeError(
            "Native parser reported incomplete language statistics; retry with the portable backend"
        )
    native_status = {}
    records_by_key = {}
    for record in payload.get("files", []):
        key = _path_key(record["path"])
        reason = record.get("excluded_reason")
        native_status[key] = reason or "recognized"
        records_by_key[key] = record
    return native_status, records_by_key


def _native_engine(payload):
    return {
        "language_detection": payload.get("engine", "Tokei"),
        "language_detection_version": payload.get("engine_version", "unknown"),
        "ignore_matching": "Tokei + QZX pathspec compatibility accounting",
        "ignore_matching_version": None,
        "inaccurate_languages": payload.get("inaccurate_languages", []),
        "percentage_precision": 2,
        "native": True,
    }


def _populate_native_state(command, targets, state, native_status, records_by_key):
    included_roots = {}

    for target in targets:
        scan_root, included = _metadata_scan(
            command,
            Path(target),
            state,
            native_status,
        )
        for key in included:
            included_roots.setdefault(key, scan_root)

    for key, scan_root in included_roots.items():
        record = records_by_key.get(key)
        if record is None:
            continue
        _record_native(command, record, scan_root, state["languages"])
        state["counters"]["recognized_files"] += 1



def scan_native_many(command, targets, state):
    payload = _native_payload(command, targets)
    native_status, records_by_key = _native_maps(payload)
    _populate_native_state(command, targets, state, native_status, records_by_key)
    return _native_engine(payload)


def scan_native_groups(command, groups, *, payload_loader=None):
    """Parse once for multiple projects, retaining full accounting per group."""
    from ._project_language_command import _state, _target

    resolved = []
    for group in groups:
        targets = []
        for path in group:
            target, failure = _target(path)
            if failure:
                raise ValueError(failure["message"])
            targets.append(target)
        if not targets:
            raise ValueError("Every project group must contain at least one target")
        resolved.append(targets)
    if not resolved:
        return []
    loader = _native_payload if payload_loader is None else payload_loader
    payload = loader(command, [path for group in resolved for path in group])
    native_status, records_by_key = _native_maps(payload)
    engine = _native_engine(payload)
    results = []
    for group in resolved:
        state = _state()
        _populate_native_state(command, group, state, native_status, records_by_key)
        results.append(_build_batch_result(command, group, state, engine))
    return results


def scan_native(command, target, state):
    return scan_native_many(command, [target], state)


def scan_native_batch_result(command, targets):
    from ._project_language_command import _state

    resolved_targets = [Path(target).resolve() for target in targets]
    state = _state()
    engine = scan_native_many(command, resolved_targets, state)
    return _build_batch_result(command, resolved_targets, state, engine)


def _build_batch_result(command, resolved_targets, state, engine):
    languages, supporting, totals, basis = command._finalize_languages(state["languages"])
    error_count = state["errors"]["total"]
    summary = command._make_summary(
        state["counters"],
        totals,
        len(languages),
        len(supporting),
        error_count,
    )
    summary["primary_language"] = languages[0]["language"] if languages else None
    exclusions = command._make_exclusions(
        state["counters"],
        state["examples"],
        state["ignore_sources"],
    )
    unclassified = command._make_unclassified(
        state["counters"],
        state["extensions"],
        state["unknown_examples"],
    )
    found = {entry["language"]: entry["file_count"] for entry in languages + supporting}
    return {
        "success": True,
        "scan_paths": [str(target) for target in resolved_targets],
        "scan_kind": "batch",
        "scan_complete": error_count == 0,
        "composition_basis": basis,
        "summary": summary,
        "languages": languages,
        "supporting_formats": supporting,
        "exclusions": exclusions,
        "unclassified": unclassified,
        "scan_errors": state["errors"]["items"],
        "scan_errors_truncated": error_count > len(state["errors"]["items"]),
        "analysis_engine": engine,
        "total_files": state["counters"]["recognized_files"],
        "languages_found": found,
        "message": (
            f"QZX native project language batch analyzed "
            f"{len(resolved_targets)} targets."
        ),
    }
