"""Command orchestration for ``addPythonDocstrings``."""

import ast
import os
import stat
import tempfile

from ._python_docstring_visitor import DocstringVisitor


def error_result(error_code, message, file_path):
    return {
        "success": False,
        "error_code": error_code,
        "error": message,
        "message": message,
        "details": {"file_path": file_path},
    }


def validate_file_path(cls, file_path, preview):
    absolute_path = os.path.abspath(os.fspath(file_path))
    checks = (
        (not os.path.lexists(absolute_path), "file_not_found", f"File '{absolute_path}' does not exist."),
        (os.path.islink(absolute_path), "symbolic_link_refused", f"File '{absolute_path}' is a symbolic link. QZX refuses to replace an ambiguous target."),
        (not os.path.isfile(absolute_path), "path_not_file", f"Path '{absolute_path}' is not a regular file."),
        (not absolute_path.lower().endswith(".py"), "not_python_file", f"File '{absolute_path}' does not have a .py extension."),
        (not preview and not os.access(absolute_path, os.W_OK), "file_not_writable", f"File '{absolute_path}' is not writable."),
    )
    for failed, code, message in checks:
        if failed:
            return cls._error_result(code, message, absolute_path)
    return None


def preserve_file_endings(original, generated):
    newline = "\r\n" if "\r\n" in original else "\n"
    if newline != "\n":
        generated = generated.replace("\n", newline)
    if original.endswith(("\n", "\r")) and not generated.endswith(newline):
        generated += newline
    return generated


def atomic_write_text(file_path, content):
    original_mode = stat.S_IMODE(os.stat(file_path).st_mode)
    directory = os.path.dirname(file_path) or os.curdir
    descriptor, temporary_path = tempfile.mkstemp(
        dir=directory,
        prefix=f".{os.path.basename(file_path)}.qzx-",
        suffix=".tmp",
    )
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="") as temporary:
            descriptor = None
            temporary.write(content)
            temporary.flush()
            os.fsync(temporary.fileno())
        os.chmod(temporary_path, original_mode)
        os.replace(temporary_path, file_path)
        temporary_path = None
    finally:
        if descriptor is not None:
            os.close(descriptor)
        if temporary_path is not None:
            try:
                os.unlink(temporary_path)
            except FileNotFoundError:
                pass


def _validated_options(command, path, style, overwrite, dry_run):
    failure = command._validate_file_path(path, preview=True)
    if failure:
        return failure, None
    normalized_style = str(style).strip().lower()
    if normalized_style not in {"google", "numpy", "sphinx"}:
        message = f"Invalid style '{normalized_style}'. Choose google, numpy, or sphinx."
        return command._error_result("invalid_style", message, path), None
    overwrite_value = command._parse_bool(overwrite)
    if overwrite_value is None:
        message = f"overwrite must be true or false, got {overwrite!r}."
        return command._error_result("invalid_overwrite", message, path), None
    dry_run_value = command._parse_bool(dry_run)
    if dry_run_value is None:
        message = f"dry_run must be true or false, got {dry_run!r}."
        return command._error_result("invalid_dry_run", message, path), None
    failure = command._validate_file_path(path, preview=dry_run_value)
    return failure, (normalized_style, overwrite_value, dry_run_value)


def _parse_source(command, path, content):
    try:
        return ast.parse(content), None
    except SyntaxError as exc:
        result = command._error_result(
            "invalid_python_syntax", f"Python syntax error: {exc}", path
        )
        result["details"].update({"line": exc.lineno, "offset": exc.offset})
        return None, result


def _success_result(path, style, overwrite, dry_run, visitor, content, generated):
    preview = visitor.get_changes_preview() if visitor.updates else []
    changed = content != generated
    return {
        "success": True,
        "status": "preview" if dry_run else "unchanged",
        "file_path": path,
        "style": style,
        "overwrite": overwrite,
        "dry_run": dry_run,
        "stats": dict(visitor.stats),
        "changes_detected": changed,
        "changes_applied": False,
        "changes_made": False,
        "changes_preview": preview,
    }


def _finish_result(command, result, generated):
    path = result["file_path"]
    if not result["dry_run"] and result["changes_detected"]:
        command._atomic_write_text(path, generated)
        result.update(status="updated", changes_applied=True, changes_made=True)
    count = len(result["changes_preview"])
    if result["dry_run"] and count:
        result["message"] = f"Previewed {count} docstring change(s) for '{path}'. Nothing was written."
    elif result["dry_run"]:
        result["message"] = f"No docstring templates are needed for '{path}'."
    elif result["changes_applied"]:
        result["message"] = f"Applied {count} docstring change(s) atomically to '{path}'."
    else:
        result["message"] = f"No docstring templates were needed for '{path}'; the file was not rewritten."
    return result


def execute_add_python_docstrings(command, file_path, style="google", overwrite=False, dry_run=True):
    path = os.path.abspath(os.fspath(file_path))
    try:
        failure, options = _validated_options(command, path, style, overwrite, dry_run)
        if failure:
            return failure
        style, overwrite, dry_run = options
        with open(path, "r", encoding="utf-8", newline="") as source:
            content = source.read()
        tree, failure = _parse_source(command, path, content)
        if failure:
            return failure
        visitor = DocstringVisitor(content, style, overwrite)
        visitor.visit(tree)
        generated = command._preserve_file_endings(
            content, visitor.get_modified_content()
        )
        result = _success_result(
            path, style, overwrite, dry_run, visitor, content, generated
        )
        return _finish_result(command, result, generated)
    except Exception as exc:
        return {
            "success": False,
            "error_code": "docstring_generation_failed",
            "file_path": path,
            "error": f"{type(exc).__name__}: {exc}",
            "message": f"Could not generate docstring templates for '{file_path}': {exc}",
        }
