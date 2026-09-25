"""Single-file matching and rendering for findText."""

from __future__ import annotations

import sys

import colorama


colorama.init(autoreset=True)


def safe_string(text):
    """Return text representable by the active stdout encoding."""
    if text is None:
        return ""
    try:
        encoding = getattr(sys.stdout, "encoding", None)
        if encoding:
            return text.encode(encoding, errors="replace").decode(encoding)
        return text.encode("ascii", errors="replace").decode("ascii")
    except Exception:
        return "".join(character if ord(character) < 128 else "?" for character in text)


def _read_lines(file_path):
    with open(file_path, "r", encoding="utf-8", errors="replace") as handle:
        return handle.readlines()


def _matches_line(line, pattern, regex, case_sensitive):
    if regex:
        return bool(pattern.search(line))
    if case_sensitive:
        return pattern in line
    return pattern.lower() in line.lower()


def _matching_lines(lines, pattern, regex, case_sensitive, invert_match):
    matches = []
    for index, line in enumerate(lines):
        matched = _matches_line(line, pattern, regex, case_sensitive)
        if matched != invert_match:
            matches.append((index, line))
    return matches


def _highlight_colors(colored):
    if not colored:
        return "", ""
    try:
        return colorama.Fore.RED + colorama.Style.BRIGHT, colorama.Style.RESET_ALL
    except Exception:
        return "", ""


def _highlight_literal(line_text, pattern, case_sensitive, highlight, reset):
    haystack = line_text if case_sensitive else line_text.lower()
    needle = pattern if case_sensitive else pattern.lower()
    index = haystack.find(needle)
    if index < 0:
        return line_text.rstrip()
    before = line_text[:index]
    matched = line_text[index:index + len(pattern)]
    after = line_text[index + len(pattern):]
    return f"{before}{highlight}{matched}{reset}{after}".rstrip()


def _highlight_match(line_text, pattern, regex, case_sensitive, colored,
                     invert_match, highlight, reset):
    if not colored or invert_match:
        return line_text.rstrip()
    if regex:
        return pattern.sub(
            lambda match: f"{highlight}{match.group(0)}{reset}",
            line_text.rstrip(),
        )
    return _highlight_literal(
        line_text, pattern, case_sensitive, highlight, reset
    )


def _context_rows(lines, start, end):
    return [
        {
            "line_num": index + 1,
            "content": safe_string(lines[index].rstrip()),
            "is_match": False,
        }
        for index in range(start, end)
    ]


def _match_row(line_num, line_text, pattern, regex, case_sensitive, colored,
               invert_match, highlight, reset):
    try:
        content = _highlight_match(
            line_text,
            pattern,
            regex,
            case_sensitive,
            colored,
            invert_match,
            highlight,
            reset,
        )
        return {
            "line_num": line_num + 1,
            "content": safe_string(content),
            "is_match": True,
        }
    except Exception as exc:
        return {
            "line_num": line_num + 1,
            "content": safe_string(line_text.rstrip()),
            "is_match": True,
            "highlight_error": str(exc),
        }


def _render_matches(lines, matches, pattern, regex, case_sensitive,
                    context_lines, invert_match, colored):
    rendered = []
    highlight, reset = _highlight_colors(colored)
    for line_num, line_text in matches:
        start = max(0, line_num - context_lines)
        rendered.extend(_context_rows(lines, start, line_num))
        rendered.append(
            _match_row(
                line_num,
                line_text,
                pattern,
                regex,
                case_sensitive,
                colored,
                invert_match,
                highlight,
                reset,
            )
        )
        end = min(len(lines), line_num + context_lines + 1)
        rendered.extend(_context_rows(lines, line_num + 1, end))
    return rendered


def search_text_file(file_path, pattern, regex, case_sensitive, context_lines,
                     invert_match, count_only, colored):
    """Search one file and preserve the historical findText result contract."""
    try:
        lines = _read_lines(file_path)
    except Exception as exc:
        return {
            "file": file_path,
            "error": f"Could not read file: {str(exc)}",
            "matches": 0,
        }

    try:
        matches = _matching_lines(
            lines, pattern, regex, case_sensitive, invert_match
        )
        if not matches:
            return None
        if count_only:
            return {
                "file": file_path,
                "matches": len(matches),
                "count_only": True,
            }
        return {
            "file": file_path,
            "matches": len(matches),
            "lines": _render_matches(
                lines,
                matches,
                pattern,
                regex,
                case_sensitive,
                context_lines,
                invert_match,
                colored,
            ),
        }
    except Exception as exc:
        return {"file": file_path, "error": str(exc), "matches": 0}
