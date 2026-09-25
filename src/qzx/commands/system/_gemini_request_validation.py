"""Request validation for explainFileWithGemini."""

from __future__ import annotations

from pathlib import Path

MAX_SAMPLE_CHARACTERS = 100_000
MAX_PROMPT_CHARACTERS = 20_000
MEBIBYTE = 1024 * 1024


def validate_gemini_request(
    command,
    file_path,
    sample_size,
    model,
    custom_prompt,
    max_file_size_mb,
    dry_run,
    apply,
):
    """Validate local file, limits, and explicit external-sharing flags."""
    limits, failure = _validated_limits(command, sample_size, max_file_size_mb)
    if failure is not None:
        return failure

    custom_prompt = str(custom_prompt or "")
    failure = _custom_prompt_failure(command, custom_prompt)
    if failure is not None:
        return failure

    target_info, failure = _validated_file_limit(
        command,
        file_path,
        limits["max_file_size_mb"],
    )
    if failure is not None:
        return failure

    flags, failure = _validated_application_flags(command, dry_run, apply)
    if failure is not None:
        return failure

    requested_model = _normalized_model_name(model)
    return _valid_request_result(
        target_info["target"],
        target_info["resolved"],
        target_info["file_stat"],
        limits["sample_size"],
        target_info["max_file_size_bytes"],
        requested_model,
        custom_prompt,
        flags,
    )


def _custom_prompt_failure(command, custom_prompt):
    if len(custom_prompt) <= MAX_PROMPT_CHARACTERS:
        return None
    return command._failure(
        "custom_prompt_too_large",
        "custom_prompt exceeds 20000 characters.",
        "Shorten the instruction before sending it to an external API.",
    )


def _validated_file_limit(command, file_path, max_file_size_mb):
    target, resolved, file_stat, failure = _validated_target(
        command,
        file_path,
    )
    if failure is not None:
        return None, failure
    max_file_size_bytes = max_file_size_mb * MEBIBYTE
    if file_stat.st_size > max_file_size_bytes:
        return None, command._failure(
            "file_too_large",
            (
                "The selected file is larger than the configured local "
                "read limit."
            ),
            (
                "Choose a smaller file or deliberately raise "
                "max_file_size_mb up to 100."
            ),
            details={
                "path": str(resolved),
                "file_size_bytes": file_stat.st_size,
                "max_file_size_bytes": max_file_size_bytes,
            },
        )
    return {
        "target": target,
        "resolved": resolved,
        "file_stat": file_stat,
        "max_file_size_bytes": max_file_size_bytes,
    }, None


def _normalized_model_name(model):
    requested_model = str(model or "").strip()
    if requested_model.startswith("models/"):
        return requested_model.split("/", 1)[1]
    return requested_model


def _validated_limits(command, sample_size, max_file_size_mb):
    try:
        sample_size = int(sample_size)
        max_file_size_mb = int(max_file_size_mb)
    except (TypeError, ValueError):
        return None, command._failure(
            "invalid_limits",
            "Sample and file-size limits must be integers.",
            "Use sample_size 10-100000 and max_file_size_mb 1-100.",
        )
    if not 10 <= sample_size <= MAX_SAMPLE_CHARACTERS:
        return None, command._failure(
            "invalid_sample_size",
            "sample_size must be between 10 and 100000 characters.",
            "Choose a bounded positive sample size within that range.",
        )
    if not 1 <= max_file_size_mb <= 100:
        return None, command._failure(
            "invalid_file_size_limit",
            "max_file_size_mb must be between 1 and 100.",
            "Choose a local read limit within that range.",
        )
    return {
        "sample_size": sample_size,
        "max_file_size_mb": max_file_size_mb,
    }, None


def _validated_target(command, file_path):
    target = Path(file_path).expanduser()
    try:
        resolved = target.resolve(strict=True)
        file_stat = resolved.stat()
    except (OSError, RuntimeError) as exc:
        return None, None, None, command._failure(
            "file_not_found",
            "The selected file could not be resolved.",
            "Provide a readable regular text file.",
            details={
                "path": str(target),
                "cause": type(exc).__name__,
            },
        )
    if not resolved.is_file():
        return None, None, None, command._failure(
            "not_a_regular_file",
            "The selected path is not a regular file.",
            "Choose one local text file rather than a directory or device.",
            details={"path": str(resolved)},
        )
    return target, resolved, file_stat, None


def _validated_application_flags(command, dry_run, apply):
    is_dry_run = command._as_bool(dry_run)
    is_apply = command._as_bool(apply)
    if is_dry_run is None or is_apply is None:
        return None, command._failure(
            "invalid_boolean",
            "dry_run and apply must be explicit boolean values.",
            "Use true or false for both options.",
        )
    if is_dry_run and is_apply:
        return None, command._failure(
            "conflicting_application_flags",
            "apply=true conflicts with dry_run=true.",
            "Use preview defaults, or combine --dry-run false --apply.",
        )
    if not is_dry_run and not is_apply:
        return None, command._failure(
            "explicit_application_required",
            "Sending file content requires apply=true.",
            "Review the preview, then use --dry-run false --apply.",
        )
    return {"dry_run": is_dry_run, "apply": is_apply}, None


def _valid_request_result(
    target,
    resolved,
    file_stat,
    sample_size,
    max_file_size_bytes,
    requested_model,
    custom_prompt,
    flags,
):
    external_service = {
        "provider": "Google Gemini",
        "endpoint_host": "generativelanguage.googleapis.com",
        "content_shared": False,
        "planned_source_characters_maximum": sample_size * 3,
    }
    return {
        "success": True,
        "message": "Gemini request inputs are valid.",
        "details": {
            "display_path": str(target),
            "resolved_path": str(resolved),
            "file_size_bytes": file_stat.st_size,
            "last_modified_ns": file_stat.st_mtime_ns,
            "sample_size_characters": sample_size,
            "planned_source_characters_maximum": sample_size * 3,
            "sample_strategy": (
                "whole decoded file when it fits; otherwise beginning, "
                "middle, and end"
            ),
            "max_file_size_bytes": max_file_size_bytes,
            "requested_model": requested_model,
            "model_selection": (
                "explicit" if requested_model else "automatic after apply"
            ),
            "prompt_source": (
                "custom" if custom_prompt.strip() else "QZX default"
            ),
            "custom_prompt_characters": len(custom_prompt),
            "dry_run": flags["dry_run"],
            "apply": flags["apply"],
            "content_shared": False,
            "network_request_made": False,
            "external_service": external_service,
        },
    }
