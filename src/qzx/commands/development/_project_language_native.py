"""Native Tokei adapter for projectLanguages."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
from collections import Counter
from pathlib import Path


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


def _native_cache_candidates():
    explicit_cache = os.environ.get("QZX_NATIVE_CACHE")
    if explicit_cache:
        cache_root = Path(explicit_cache).expanduser()
    elif os.name == "nt" and os.environ.get("LOCALAPPDATA"):
        cache_root = Path(os.environ["LOCALAPPDATA"]) / "QZX" / "native"
    else:
        cache_root = Path(
            os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache")
        ) / "qzx" / "native"

    project_cache = cache_root / "project_languages"
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
    return os.path.normcase(str(Path(path).resolve()))


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
    stats = language_stats.setdefault(language, _new_language(command, language))
    stats["file_count"] += 1
    stats["bytes"] += int(record["bytes"])
    stats["total_lines"] += int(record["total_lines"])
    stats["code_lines"] += int(record["code_lines"])
    stats["comment_lines"] += int(record["comment_lines"])
    stats["blank_lines"] += int(record["blank_lines"])
    path = Path(record["path"])
    stats["extensions"][path.suffix.casefold() or "(no extension)"] += 1
    stats["detected_variants"][language] += 1
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
):
    state["counters"]["visited_files"] += 1
    if path.is_symlink():
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
    for name in directory_names:
        path = root / name
        if path.is_symlink():
            state["counters"]["symlinks_skipped"] += 1
        elif name.casefold() in command.DEFAULT_EXCLUDED_DIRECTORIES:
            state["counters"]["ignored_directories"] += 1
        elif command._is_ignored(path, True, scopes):
            state["counters"]["ignored_directories"] += 1
        else:
            retained.append(name)
    return retained


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

    for root_text, directory_names, file_names in os.walk(
        scan_root,
        topdown=True,
        followlinks=False,
        onerror=record_walk_error,
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
        for name in file_names:
            _handle_metadata_file(
                command,
                root / name,
                scopes,
                scan_root,
                state,
                native_status,
                included,
            )
    return scan_root, included


def _native_payload(command, targets):
    if _NATIVE is None:
        raise RuntimeError(NATIVE_IMPORT_ERROR or "native backend unavailable")
    paths = [str(Path(target).resolve()) for target in targets]
    if len(paths) == 1:
        raw = _NATIVE.scan_project_json(
            paths[0],
            sorted(command.DEFAULT_EXCLUDED_DIRECTORIES),
            int(command.MAX_FILE_SIZE_BYTES),
        )
    else:
        scanner = getattr(_NATIVE, "scan_projects_json", None)
        if scanner is None:
            raise RuntimeError("native backend does not support batch scanning")
        raw = scanner(
            paths,
            sorted(command.DEFAULT_EXCLUDED_DIRECTORIES),
            int(command.MAX_FILE_SIZE_BYTES),
        )
    return json.loads(raw)


def scan_native_records(command, targets):
    return _native_payload(command, targets)


def _native_maps(payload):
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


def scan_native_many(command, targets, state):
    payload = _native_payload(command, targets)
    native_status, records_by_key = _native_maps(payload)
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

    return _native_engine(payload)


def scan_native(command, target, state):
    return scan_native_many(command, [target], state)


def scan_native_batch_result(command, targets):
    from ._project_language_command import _state

    resolved_targets = [Path(target).resolve() for target in targets]
    state = _state()
    engine = scan_native_many(command, resolved_targets, state)
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
