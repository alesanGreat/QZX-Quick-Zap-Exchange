"""Bounded environment-variable reference analysis."""

import os
import re

from qzx.core.recursive_findfiles_utils import find_files, parse_recursive_parameter

ENV_NAMES = (".env", ".env.example", ".env.template", ".env.local", ".env.development")
SENSITIVE_PATTERN = re.compile(
    r"(?:secret|token|password|passwd|api[_-]?key|private[_-]?key)", re.I
)


def _is_sensitive(name):
    return bool(SENSITIVE_PATTERN.search(name))


def _validate(var_name, project_path, recursive):
    name = var_name.strip()
    if not name:
        message = "Environment variable name cannot be empty."
        return None, {"success": False, "error": message, "message": message}
    path = os.path.abspath(project_path)
    if not os.path.exists(path):
        message = f"Project path '{project_path}' does not exist."
        return None, {"success": False, "error": message, "message": message}
    recursion = parse_recursive_parameter(recursive) if isinstance(recursive, str) else recursive
    return (name, path, recursion), None


def _environment_files(command, path, name):
    return {
        filename: command._parse_env_file_for_var(candidate, name)
        for filename in ENV_NAMES
        if os.path.isfile(candidate := os.path.join(path, filename))
    }


def _reference(command, file_path, root, name, pattern, sensitive):
    references = []
    try:
        if os.path.getsize(file_path) > 1024 * 1024:
            return references
        with open(file_path, "r", encoding="utf-8", errors="replace") as handle:
            for line_number, line in enumerate(handle, 1):
                if not pattern.search(line):
                    continue
                fallback = command._detect_fallback_in_line(line, name)
                references.append({
                    "file": os.path.relpath(file_path, root).replace(os.path.sep, "/"),
                    "line_number": line_number,
                    "line_content": f"<reference to {name} redacted>" if sensitive else line.strip(),
                    "fallback_detected": "<redacted>" if sensitive and fallback is not None else fallback,
                })
    except Exception:
        pass
    return references


def _code_references(command, path, name, recursive):
    pattern = re.compile(r"\b" + re.escape(name) + r"\b")
    sensitive = _is_sensitive(name)
    if os.path.isfile(path):
        candidates = [path]
    else:
        candidates = find_files(path, recursive=recursive, file_type="f")
    references = []
    for file_path in candidates:
        extension = os.path.splitext(file_path)[1].lower()
        if extension in command.SUPPORTED_EXTENSIONS:
            references.extend(_reference(command, file_path, path, name, pattern, sensitive))
    return references


def _message(name, path, env_files, references):
    message = f"Environment Variable Trace completed for '{name}':\n- Project directory: {path}\n\nEnv File Status:\n"
    for filename, info in env_files.items():
        status = "DEFINED" if info["defined"] else "NOT DEFINED"
        value = f" (Value: {info['masked_value']})" if info["defined"] else ""
        message += f"  - {filename}: {status}{value}\n"
    message += f"\nCode Usages found: {len(references)}\n"
    for reference in references[:10]:
        fallback = reference["fallback_detected"]
        suffix = f" [Fallback: {fallback}]" if fallback else ""
        message += f"  - {reference['file']}:{reference['line_number']}: '{reference['line_content']}'{suffix}\n"
    if len(references) > 10:
        message += f"  ... and {len(references) - 10} more usage references.\n"
    return message


def execute_environment_trace(command, var_name, project_path=".", recursive=True):
    """Trace one variable without exposing sensitive values or unbounded files."""
    request, error = _validate(var_name, project_path, recursive)
    if error:
        return error
    name, path, recursion = request
    env_files = _environment_files(command, path, name)
    references = _code_references(command, path, name, recursion)
    return {
        "success": True,
        "var_name": name,
        "project_path": path,
        "env_files_diagnostics": env_files,
        "references_count": len(references),
        "references": references,
        "message": _message(name, path, env_files, references),
    }


def parse_env_file_for_var(_command, filepath, var_name):
    """Return masked definition state for one variable in one env file."""
    raw_value = None
    try:
        with open(filepath, "r", encoding="utf-8", errors="replace") as handle:
            for source_line in handle:
                line = source_line.strip()
                if not line or line.startswith("#"):
                    continue
                match = re.match(r"^(?:export\s+)?([A-Za-z0-9_]+)\s*=\s*(.*)$", line)
                if match and match.group(1) == var_name:
                    raw_value = match.group(2).strip()
                    if len(raw_value) >= 2 and raw_value[0] == raw_value[-1] and raw_value[0] in "\"'":
                        raw_value = raw_value[1:-1].strip()
                    break
    except Exception:
        pass
    if raw_value is None:
        masked = None
    elif not raw_value:
        masked = "<empty>"
    elif len(raw_value) <= 3:
        masked = "****"
    elif _is_sensitive(var_name):
        masked = "<redacted>"
    else:
        masked = f"{raw_value[:2]}...{raw_value[-2:]}"
    return {"defined": raw_value is not None, "value_found": raw_value is not None, "masked_value": masked}


def detect_fallback_in_line(_command, line, var_name):
    """Extract a same-line fallback for supported language idioms."""
    name = re.escape(var_name)
    patterns = (
        rf"(?:getenv|environ\.get)\(\s*['\"]{name}['\"]\s*,\s*([^\)]+)\)",
        rf"{name}\s*(?:\|\||\?\?)\s*([^\n;]+)",
        rf"(?:getenv\(\s*['\"]{name}['\"]\s*\)|(?:\$_ENV|\$_SERVER)\[\s*['\"]{name}['\"]\s*\])\s*(?:\?\?:|\?:|\?\?)\s*([^\n;]+)",
        rf"(?:env::var|option_env!)\(\s*['\"]{name}['\"]\s*\)\s*\.\s*(?:unwrap_or|unwrap_or_else)\(\s*([^()]+(?:\([^()]*\))?[^()]*)\)",
        rf"(?:std::)?getenv\(\s*['\"]{name}['\"]\s*\)\s*(?:\?\s*(?:std::)?getenv\(\s*['\"]{name}['\"]\s*\)\s*:\s*|\?\:\s*)([^\n;]+)",
    )
    for pattern in patterns:
        match = re.search(pattern, line)
        if match:
            return match.group(1).strip()
    return None
