"""Traversal and file classification for ``projectLanguages``."""

import os
from collections import Counter
from pathlib import Path

import chardet

try:
    import pathspec
    import pygments
    from pathspec import GitIgnoreSpec
    from pygments.lexers import get_lexer_for_filename, guess_lexer
    from pygments.token import Comment, Text
    from pygments.util import ClassNotFound

    LANGUAGE_DEPENDENCY_ERROR = None
except ImportError as dependency_error:  # pragma: no cover - import isolation
    pathspec = None
    pygments = None
    GitIgnoreSpec = None
    get_lexer_for_filename = None
    guess_lexer = None
    Comment = None
    Text = None
    ClassNotFound = Exception
    LANGUAGE_DEPENDENCY_ERROR = dependency_error


def initial_ignore_scopes(command, scan_root, ignore_sources, scan_errors):
    scopes = []
    repository_root = command._find_repository_root(scan_root)
    scope_root = repository_root or scan_root
    if repository_root is not None:
        metadata = repository_root / ".git"
        if metadata.is_dir():
            command._load_ignore_file(
                metadata / "info" / "exclude", repository_root, scan_root,
                scopes, ignore_sources, scan_errors,
            )
    current = scope_root
    while True:
        command._load_ignore_files(
            current, scan_root, scopes, ignore_sources, scan_errors
        )
        if current == scan_root:
            break
        try:
            parts = scan_root.relative_to(current).parts
        except ValueError:
            break
        if not parts:
            break
        current = current / parts[0]
    return scopes


def find_repository_root(path):
    current = path.resolve()
    for candidate in (current, *current.parents):
        if (candidate / ".git").exists():
            return candidate
    return None


def load_ignore_files(command, directory, scan_root, scopes, ignore_sources, scan_errors):
    for ignore_name in (".gitignore", ".ignore"):
        command._load_ignore_file(
            directory / ignore_name, directory, scan_root, scopes,
            ignore_sources, scan_errors,
        )


def load_ignore_file(command, ignore_path, scope_path, scan_root, scopes, ignore_sources, scan_errors):
    if not ignore_path.is_file():
        return
    try:
        lines = ignore_path.read_text(encoding="utf-8-sig").splitlines()
        scopes.append((scope_path.resolve(), GitIgnoreSpec.from_lines(lines)))
        ignore_sources.append(command._relative_display(ignore_path, scan_root))
    except (OSError, UnicodeError, ValueError) as error:
        command._record_error(scan_errors, scan_root, ignore_path, error)


def is_ignored(path, is_directory, scopes):
    ignored = False
    for scope_path, spec in scopes:
        try:
            relative_path = path.relative_to(scope_path).as_posix()
        except ValueError:
            continue
        candidate = f"{relative_path}/" if is_directory else relative_path
        check_result = spec.check_file(candidate)
        if check_result.include is not None:
            ignored = bool(check_result.include)
    return ignored


def looks_binary(content):
    if not content:
        return False
    sample = content[:8192]
    if b"\x00" in sample:
        return True
    allowed_controls = {7, 8, 9, 10, 12, 13, 27}
    suspicious = sum(
        1 for value in sample if value < 32 and value not in allowed_controls
    )
    return suspicious / len(sample) >= 0.10


def decode_text(content):
    if not content:
        return ""
    try:
        return content.decode("utf-8-sig")
    except UnicodeDecodeError:
        detection = chardet.detect(content)
        encoding = detection.get("encoding")
        if encoding:
            try:
                return content.decode(encoding)
            except (LookupError, UnicodeDecodeError):
                pass
        return content.decode("utf-8", errors="replace")


def is_generated(command, file_name, text):
    if any(pattern.fullmatch(file_name) for pattern in command.GENERATED_NAME_PATTERNS):
        return True
    header = "\n".join(text.splitlines()[:20])
    return bool(command.GENERATED_CONTENT_PATTERN.search(header))


def detect_lexer(file_name, text):
    try:
        return get_lexer_for_filename(file_name, text, stripnl=False, ensurenl=False)
    except ClassNotFound:
        if text.startswith("#!"):
            try:
                return guess_lexer(text, stripnl=False, ensurenl=False)
            except ClassNotFound:
                pass
        return None


def count_lines(text, lexer):
    physical_lines = text.splitlines()
    if not physical_lines:
        return {"total_lines": 0, "code_lines": 0, "comment_lines": 0, "blank_lines": 0}
    states = [{"code": False, "comment": False} for _ in physical_lines]
    line_index = 0
    for token_type, token_value in lexer.get_tokens(text):
        for piece in token_value.splitlines(keepends=True):
            if line_index >= len(states):
                break
            content_piece = piece.rstrip("\r\n")
            if content_piece.strip():
                if token_type in Comment:
                    states[line_index]["comment"] = True
                elif not (token_type in Text and not content_piece.strip()):
                    states[line_index]["code"] = True
            if piece.endswith(("\n", "\r")):
                line_index += 1
    code = sum(1 for state in states if state["code"])
    comments = sum(1 for state in states if state["comment"] and not state["code"])
    return {
        "total_lines": len(physical_lines),
        "code_lines": code,
        "comment_lines": comments,
        "blank_lines": len(physical_lines) - code - comments,
    }


def language_kind(command, language_name, aliases):
    normalized_name = language_name.casefold()
    alias_set = set(aliases)
    groups = (
        (command.PROSE_ALIASES, "prose"),
        (command.DATA_ALIASES, "data"),
        (command.STYLESHEET_ALIASES, "stylesheet"),
        (command.MARKUP_ALIASES, "markup"),
    )
    for names, kind in groups:
        if normalized_name in names or alias_set & names:
            return kind
    return "programming"


def _record_language(command, file_path, relative_path, size, text, lexer, counters, language_stats):
    counts = command._count_lines(text, lexer)
    variant = lexer.name
    language = variant if variant.endswith("++") else variant.split("+", 1)[0]
    aliases = sorted({alias.casefold() for alias in getattr(lexer, "aliases", [])})
    stats = language_stats.setdefault(language, _new_language(language, command._language_kind(language, aliases), aliases))
    stats["file_count"] += 1
    stats["bytes"] += size
    for key in ("total_lines", "code_lines", "comment_lines", "blank_lines"):
        stats[key] += counts[key]
    stats["extensions"][file_path.suffix.casefold() or "(no extension)"] += 1
    stats["detected_variants"][variant] += 1
    command._append_example(stats["example_files"], relative_path)
    counters["recognized_files"] += 1


def _new_language(language, kind, aliases):
    return {
        "language": language, "kind": kind, "aliases": aliases,
        "file_count": 0, "bytes": 0, "total_lines": 0, "code_lines": 0,
        "comment_lines": 0, "blank_lines": 0, "extensions": Counter(),
        "detected_variants": Counter(), "example_files": [],
    }


def analyze_path(command, file_path, scan_root, counters, excluded_examples, unknown_extensions, unknown_examples, scan_errors, language_stats):
    relative = command._relative_display(file_path, scan_root)
    try:
        size = file_path.stat().st_size
        if size > command.MAX_FILE_SIZE_BYTES:
            counters["oversized_files"] += 1
            command._append_example(excluded_examples["oversized"], relative)
            return
        raw = file_path.read_bytes()
        if command._looks_binary(raw):
            counters["binary_files"] += 1
            command._append_example(excluded_examples["binary"], relative)
            return
        text = command._decode_text(raw)
        if command._is_generated(file_path.name, text):
            counters["generated_files"] += 1
            command._append_example(excluded_examples["generated"], relative)
            return
        lexer = command._detect_lexer(file_path.name, text)
        if lexer is None:
            counters["unknown_files"] += 1
            unknown_extensions[file_path.suffix.casefold() or "(no extension)"] += 1
            command._append_example(unknown_examples, relative)
            return
        _record_language(command, file_path, relative, size, text, lexer, counters, language_stats)
    except (OSError, UnicodeError, ValueError) as error:
        command._record_error(scan_errors, scan_root, file_path, error)


def append_example(command, examples, value):
    if len(examples) < command.MAX_EXAMPLES_PER_GROUP:
        examples.append(value)


def record_error(command, errors, scan_root, path, error):
    errors["total"] += 1
    if len(errors["items"]) < command.MAX_REPORTED_ERRORS:
        errors["items"].append({
            "path": command._relative_display(path, scan_root),
            "error_type": type(error).__name__,
            "error": str(error),
        })


def relative_display(path, scan_root):
    try:
        relative = Path(path).resolve().relative_to(scan_root.resolve())
        return relative.as_posix() or "."
    except (OSError, ValueError):
        return os.path.relpath(path, scan_root).replace("\\", "/")
