"""Formatter discovery, execution, and result composition."""

import os
import subprocess

from qzx.core.recursive_findfiles_utils import find_files


def _failure(error, message=None):
    return {"success": False, "error": error, "message": message or error}


def _normalize_request(command, path, language, dry_run):
    dry = dry_run.lower() in ("true", "yes", "y", "1", "t") if isinstance(dry_run, str) else dry_run
    absolute = os.path.abspath(path)
    if not os.path.exists(absolute):
        return None, _failure(f"Path '{path}' does not exist.")
    selected = language.lower().strip() if isinstance(language, str) else ""
    if selected and selected not in command.FORMATTERS:
        supported = ", ".join(sorted(command.FORMATTERS))
        return None, _failure(f"Unsupported language: {selected}", f"Unsupported language '{selected}'. Supported: {supported}")
    return (absolute, selected, dry), None


def _collect_files(command, path, language):
    if os.path.isfile(path):
        extension = os.path.splitext(path)[1].lower()
        detected = command.EXTENSION_TO_LANGUAGE.get(extension)
        if not detected:
            return None, _failure(f"Unsupported file type: {extension}", f"File extension '{extension}' is not supported by formatCode.")
        if language and language != detected:
            return None, _failure(
                f"Language mismatch: requested '{language}' but file is '{detected}'",
                f"The provided language '{language}' does not match the auto-detected language '{detected}'.",
            )
        return [(path, detected)], None
    target_languages = {language} if language else set(command.FORMATTERS)
    files = []
    for file_path in find_files(path, recursive=True, file_type="f"):
        detected = command.EXTENSION_TO_LANGUAGE.get(os.path.splitext(file_path)[1].lower())
        if detected in target_languages:
            files.append((file_path, detected))
    return files, None


def _process_groups(command, files, dry_run):
    grouped = {}
    for file_path, language in files:
        grouped.setdefault(language, []).append(file_path)
    formatted, failed, skipped, unavailable = [], [], [], []
    for language, paths in grouped.items():
        configuration = command.FORMATTERS[language]
        tool = configuration["tool"]
        if not command._is_tool_available(tool):
            unavailable.append(tool)
            failed.extend({"file": path, "language": language, "reason": f"Formatter '{tool}' is not installed or not on PATH."} for path in paths)
            continue
        arguments = configuration["check_args"] if dry_run else configuration["args"]
        for path in paths:
            result = command._run_formatter(arguments, path, dry_run)
            item = {"file": path, "language": language}
            if result["ok"] and dry_run and not result.get("would_change", True):
                skipped.append({**item, "note": "Already formatted"})
            elif result["ok"]:
                formatted.append({**item, "dry_run": dry_run})
            else:
                failed.append({**item, "reason": result.get("error", "Unknown error")})
    return formatted, failed, skipped, sorted(set(unavailable))


def _message(dry_run, files, formatted, failed, skipped, unavailable):
    action = "checked" if dry_run else "formatted"
    message = (
        f"FormatCode Report ({action} mode):\n- Total files scanned: {len(files)}\n"
        f"- Successfully {action}: {len(formatted)}\n"
    )
    if dry_run:
        message += f"- Already formatted (no changes needed): {len(skipped)}\n"
    message += f"- Failed: {len(failed)}\n"
    if unavailable:
        message += f"\n⚠️  Missing formatters (not on PATH): {', '.join(unavailable)}\n"
    if failed:
        message += "\n❌ Failures:\n" + "".join(
            f"  - {item['file']} ({item['language']}): {item['reason']}\n" for item in failed[:10]
        )
        if len(failed) > 10:
            message += f"  ... and {len(failed) - 10} more failures.\n"
    if formatted:
        message += f"\n✅ Successfully {action} files:\n" + "".join(
            f"  - {item['file']} ({item['language']})\n" for item in formatted[:10]
        )
        if len(formatted) > 10:
            message += f"  ... and {len(formatted) - 10} more.\n"
    if not formatted and not failed and not skipped:
        message += "\nℹ️ No action was taken."
    return message


def execute_format_code(command, path, language="", dry_run=False):
    """Format or check every selected source file."""
    request, error = _normalize_request(command, path, language, dry_run)
    if error:
        return error
    absolute, selected, dry = request
    files, error = _collect_files(command, absolute, selected)
    if error:
        return error
    if not files:
        return {
            "success": True, "path": absolute, "dry_run": dry, "total_files": 0,
            "formatted_count": 0, "failed_count": 0, "skipped_count": 0,
            "formatted": [], "skipped": [], "failed": [], "unavailable_tools": [],
            "message": "No supported source files found to format.",
        }
    formatted, failed, skipped, unavailable = _process_groups(command, files, dry)
    return {
        "success": True, "all_succeeded": not failed, "path": absolute,
        "dry_run": dry, "total_files": len(files), "formatted_count": len(formatted),
        "skipped_count": len(skipped), "failed_count": len(failed),
        "formatted": formatted, "skipped": skipped, "failed": failed,
        "unavailable_tools": unavailable,
        "message": _message(dry, files, formatted, failed, skipped, unavailable),
    }


def is_tool_available(_command, tool):
    """Return whether a formatter executable can be started."""
    try:
        subprocess.run([tool, "--version"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
        return True
    except FileNotFoundError:
        return False


def run_formatter(_command, args, file_path, dry_run):
    """Run one formatter without a shell and normalize its outcome."""
    try:
        command = args + [file_path]
        result = subprocess.run(
            command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
            text=True, encoding="utf-8", errors="replace",
        )
        if dry_run:
            if "gofmt" in command[0]:
                changed = file_path in result.stdout.strip()
            else:
                changed = result.returncode != 0
            return {"ok": True, "would_change": changed, "stdout": result.stdout, "stderr": result.stderr}
        if result.returncode == 0:
            return {"ok": True}
        return {"ok": False, "error": result.stderr.strip() or f"Exit code {result.returncode}"}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}
