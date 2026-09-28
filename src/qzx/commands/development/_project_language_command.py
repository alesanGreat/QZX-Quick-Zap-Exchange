"""Command orchestration for ``projectLanguages``."""

import os
from collections import Counter
from pathlib import Path

from ._project_language_native import native_available, scan_native


def missing_dependency_result(error):
    return {
        "success": False,
        "error_code": "missing_dependency",
        "error": str(error),
        "missing_dependencies": ["Pygments", "pathspec"],
        "remediation": 'Install QZX normally or run: python -m pip install "Pygments>=2.20,<3" "pathspec>=1.1,<2"',
        "message": "Project language analysis needs the maintained Pygments and pathspec dependencies, but they are not available.",
    }


def _target(scan_path):
    target = Path(scan_path).expanduser().resolve()
    if not target.exists():
        return None, {
            "success": False,
            "error_code": "path_not_found",
            "error": f"Path '{scan_path}' does not exist.",
            "scan_path": str(target),
            "remediation": "Provide an existing project directory or source file.",
            "message": f"Cannot profile project languages because '{scan_path}' does not exist.",
        }
    if not target.is_dir() and not target.is_file():
        return None, {
            "success": False,
            "error_code": "unsupported_path_type",
            "error": f"Path '{scan_path}' is neither a regular file nor a directory.",
            "scan_path": str(target),
            "remediation": "Provide a regular source file or project directory.",
            "message": f"Cannot profile languages at unsupported path '{scan_path}'.",
        }
    return target, None


def _state():
    return {
        "counters": {
            "visited_files": 0, "recognized_files": 0, "ignored_files": 0,
            "ignored_directories": 0, "generated_files": 0, "binary_files": 0,
            "unknown_files": 0, "oversized_files": 0, "symlinks_skipped": 0,
        },
        "examples": {"generated": [], "binary": [], "oversized": []},
        "extensions": Counter(),
        "unknown_examples": [],
        "errors": {"total": 0, "items": []},
        "languages": {},
        "ignore_sources": [],
    }


def _filter_directories(command, root, names, scopes, counters):
    retained = []
    for name in names:
        path = root / name
        if path.is_symlink():
            counters["symlinks_skipped"] += 1
        elif name.casefold() in command.DEFAULT_EXCLUDED_DIRECTORIES:
            counters["ignored_directories"] += 1
        elif command._is_ignored(path, True, scopes):
            counters["ignored_directories"] += 1
        else:
            retained.append(name)
    return retained


def _analyze_files(command, root, names, scan_root, scopes, state):
    counters = state["counters"]
    for name in names:
        path = root / name
        counters["visited_files"] += 1
        if path.is_symlink():
            counters["symlinks_skipped"] += 1
        elif command._is_ignored(path, False, scopes):
            counters["ignored_files"] += 1
        else:
            command._analyze_path(
                path, scan_root, counters, state["examples"], state["extensions"],
                state["unknown_examples"], state["errors"], state["languages"],
            )


def _walk_directory(command, scan_root, state):
    scopes = command._initial_ignore_scopes(
        scan_root, state["ignore_sources"], state["errors"]
    )

    def record_walk_error(error):
        path = Path(getattr(error, "filename", scan_root))
        command._record_error(state["errors"], scan_root, path, error)

    for root_text, directory_names, file_names in os.walk(
        scan_root, topdown=True, followlinks=False, onerror=record_walk_error
    ):
        root = Path(root_text)
        if root != scan_root:
            command._load_ignore_files(
                root, scan_root, scopes, state["ignore_sources"], state["errors"]
            )
        directory_names[:] = _filter_directories(
            command, root, directory_names, scopes, state["counters"]
        )
        _analyze_files(command, root, file_names, scan_root, scopes, state)


def _scan(command, target, state):
    scan_root = target if target.is_dir() else target.parent
    if target.is_file():
        state["counters"]["visited_files"] = 1
        command._analyze_path(
            target, scan_root, state["counters"], state["examples"],
            state["extensions"], state["unknown_examples"], state["errors"],
            state["languages"],
        )
    else:
        _walk_directory(command, scan_root, state)


def _result(command, target, state, pygments_module, pathspec_module, engine=None):
    languages, supporting, totals, basis = command._finalize_languages(state["languages"])
    error_count = state["errors"]["total"]
    summary = command._make_summary(
        state["counters"], totals, len(languages), len(supporting), error_count
    )
    summary["primary_language"] = languages[0]["language"] if languages else None
    exclusions = command._make_exclusions(
        state["counters"], state["examples"], state["ignore_sources"]
    )
    unclassified = command._make_unclassified(
        state["counters"], state["extensions"], state["unknown_examples"]
    )
    complete = error_count == 0
    message = command._build_message(
        target, languages, supporting, summary, exclusions, unclassified,
        basis, complete, error_count,
    )
    found = {entry["language"]: entry["file_count"] for entry in languages + supporting}
    return _assemble_result(
        target, complete, basis, summary, languages, supporting, exclusions,
        unclassified, state, found, message, pygments_module, pathspec_module, engine,
    )


def _assemble_result(target, complete, basis, summary, languages, supporting, exclusions, unclassified, state, found, message, pygments_module, pathspec_module, engine=None):
    error_count = state["errors"]["total"]
    return {
        "success": True,
        "scan_path": str(target),
        "scan_kind": "directory" if target.is_dir() else "file",
        "scan_complete": complete,
        "composition_basis": basis,
        "summary": summary,
        "languages": languages,
        "supporting_formats": supporting,
        "exclusions": exclusions,
        "unclassified": unclassified,
        "scan_errors": state["errors"]["items"],
        "scan_errors_truncated": error_count > len(state["errors"]["items"]),
        "analysis_engine": engine or {
            "language_detection": "Pygments",
            "language_detection_version": pygments_module.__version__,
            "ignore_matching": "pathspec",
            "ignore_matching_version": pathspec_module.__version__,
            "percentage_precision": 2,
            "native": False,
        },
        "total_files": state["counters"]["recognized_files"],
        "languages_found": found,
        "message": message,
    }


def _prepare_portable_dependencies(
    pygments_module,
    pathspec_module,
    portable_dependency_loader,
):
    if portable_dependency_loader is not None:
        pygments_module, pathspec_module, error = portable_dependency_loader()
        if error is not None:
            return pygments_module, pathspec_module, missing_dependency_result(error)
    if pygments_module is None or pathspec_module is None:
        error = ImportError("Portable projectLanguages dependencies are unavailable")
        return pygments_module, pathspec_module, missing_dependency_result(error)
    return pygments_module, pathspec_module, None


def _try_native_backend(
    command,
    target,
    state,
    native_available_func,
    scan_native_func,
):
    is_available = native_available if native_available_func is None else native_available_func
    native_scan = scan_native if scan_native_func is None else scan_native_func
    if not is_available():
        return state, None, False

    # Backend-selection invariant: never race native and portable scans. Native is
    # the fast path; a failed native attempt discards partial accounting before the
    # portable fallback so the two engines can never contaminate one another.
    try:
        return state, native_scan(command, target, state), True
    except Exception:
        return _state(), None, False


def execute_project_languages(
    command, scan_path, dependency_error, pygments_module, pathspec_module, *,
    native_available_func=None, scan_native_func=None, portable_dependency_loader=None,
):
    if dependency_error is not None:
        return missing_dependency_result(dependency_error)
    target, failure = _target(scan_path)
    if failure:
        return failure
    state, engine, used_native = _try_native_backend(
        command,
        target,
        _state(),
        native_available_func,
        scan_native_func,
    )
    if not used_native:
        pygments_module, pathspec_module, dependency_failure = (
            _prepare_portable_dependencies(
                pygments_module,
                pathspec_module,
                portable_dependency_loader,
            )
        )
        if dependency_failure is not None:
            return dependency_failure
        _scan(command, target, state)
    return _result(
        command,
        target,
        state,
        pygments_module,
        pathspec_module,
        engine=engine,
    )
