"""Bounded content-first workflow for detectFileType."""

from __future__ import annotations

from qzx.core.file_content_analysis import (
    FileChangedDuringReadError,
    DEFAULT_TYPE_SAMPLE_SIZE,
    DetectedType,
    analyze_binary_content,
    categorize_mime_type,
    common_extensions_for_mime,
    detect_builtin_type,
    normalize_boolean,
    normalize_mime_type,
    normalize_sample_size,
    read_distributed_sample,
    validate_regular_file,
)


def _normalize(command, detailed_info, sample_size, follow_symlinks):
    detailed, error = normalize_boolean(
        detailed_info, field="detailed_info", command_base=command
    )
    if error is not None:
        return None, None, None, error
    budget, error = normalize_sample_size(
        sample_size, default=DEFAULT_TYPE_SAMPLE_SIZE
    )
    if error is not None:
        return None, None, None, error
    follow_links, error = normalize_boolean(
        follow_symlinks, field="follow_symlinks", command_base=command
    )
    return detailed, budget, follow_links, error


def _read_sample(command, target, budget):
    kwargs = {"open_file": command._open_file} if command._open_file else {}
    try:
        return read_distributed_sample(target, budget, **kwargs), None
    except FileChangedDuringReadError as exc:
        return None, {
            "success": False,
            "error_code": "file_changed_during_read",
            "error": f"{type(exc).__name__}: {exc}",
            "message": (
                "The file changed while QZX was reading its bounded sample, "
                "so no classification was published."
            ),
            "details": target.evidence(),
        }
    except OSError as exc:
        return None, {
            "success": False,
            "error_code": "file_read_failed",
            "error": f"{type(exc).__name__}: {exc}",
            "message": "QZX could not read the requested file sample.",
            "details": target.evidence(),
        }


def _selected_type(builtin, normalized_magic, description):
    if normalized_magic is None or builtin.source == "content_signature":
        return builtin
    if (
        normalized_magic == "application/octet-stream"
        and builtin.mime_type != "application/octet-stream"
    ):
        return builtin
    return DetectedType(
        normalized_magic,
        description or normalized_magic,
        "libmagic",
        95.0,
    )


def _magic_warnings(builtin, raw_magic, normalized_magic, magic_error):
    warnings = []
    if normalized_magic is not None and builtin.source == "content_signature":
        if normalized_magic != builtin.mime_type:
            warnings.append(
                "libmagic disagreed with a strong built-in content signature "
                f"({normalized_magic} versus {builtin.mime_type}); "
                "QZX retained the signature."
            )
    elif raw_magic is not None and normalized_magic is None:
        warnings.append(
            "libmagic returned a malformed MIME type; the bounded built-in "
            "detector was used instead."
        )
    elif magic_error is not None:
        warnings.append(
            "libmagic refinement failed; the bounded built-in detector was "
            f"used instead ({magic_error})."
        )
    return warnings


def _selection(command, target, sample, binary_analysis):
    builtin = detect_builtin_type(target.analyzed_path, sample, binary_analysis)
    raw_magic, description, magic_error = command._detect_with_libmagic(
        target, sample
    )
    normalized_magic = normalize_mime_type(raw_magic)
    selected = _selected_type(builtin, normalized_magic, description)
    warnings = _magic_warnings(
        builtin, raw_magic, normalized_magic, magic_error
    )
    if (
        selected.source == "zip_container_plus_extension_hint"
        and raw_magic is None
    ):
        warnings.append(
            "The Office Open XML subtype is inferred from the extension only; "
            "the ZIP container was detected, but its internal package layout "
            "was not opened or verified."
        )
    return selected, builtin, raw_magic, description, normalized_magic, warnings


def _extension_context(target, selected):
    extension = target.absolute_path.suffix.casefold().lstrip(".") or None
    common = common_extensions_for_mime(selected.mime_type)
    matches = extension in common if common else None
    return extension, common, matches


def _details(command, target, sample, binary_analysis, selection, detailed):
    selected, builtin, _raw, description, normalized_magic, _warnings = selection
    extension, common, matches = _extension_context(target, selected)
    details = {
        "detection": selected.evidence(),
        "builtin_detection": builtin.evidence(),
        "libmagic_available": command._magic_provider is not None,
        "libmagic_mime_type": normalized_magic,
        "libmagic_agrees_with_builtin": (
            None if normalized_magic is None
            else normalized_magic == builtin.mime_type
        ),
        "container_mime_type": (
            "application/zip"
            if builtin.source == "zip_container_plus_extension_hint"
            else None
        ),
        "extension_match_status": (
            "unknown" if matches is None else "matches" if matches else "mismatch"
        ),
        "target": target.evidence(),
    }
    if detailed:
        details.update({
            "categories": categorize_mime_type(selected.mime_type),
            "common_extensions": common,
            "sampling": sample.evidence(),
            "binary_analysis": binary_analysis,
            "libmagic_description": description,
        })
    return details, extension, common, matches


def _result(command, target, binary_analysis, selection, context):
    selected = selection[0]
    warnings = selection[-1]
    details, extension, common, matches = context
    result = {
        "success": True,
        "message": (
            f"File '{target.absolute_path}' was identified as "
            f"{selected.mime_type} by {selected.source}."
        ),
        "file_path": str(target.absolute_path),
        "analyzed_path": str(target.analyzed_path),
        "file_size": target.file_size,
        "file_size_readable": command._format_bytes(float(target.file_size)),
        "mime_type": selected.mime_type,
        "description": selected.description,
        "is_binary": binary_analysis["is_binary"],
        "extension": f".{extension}" if extension else None,
        "extension_matches_content": matches,
        "details": details,
    }
    if matches is False and common:
        result["suggested_extension"] = f".{common[0]}"
        result["message"] += (
            f" The current extension does not match; "
            f"'.{common[0]}' is the canonical suggestion."
        )
    if warnings:
        result["warnings"] = warnings
    return result


def execute_file_type(
    command,
    file_path,
    detailed_info=False,
    sample_size=DEFAULT_TYPE_SAMPLE_SIZE,
    follow_symlinks=False,
):
    """Identify one regular file without trusting its extension alone."""
    detailed, budget, follow_links, error = _normalize(
        command, detailed_info, sample_size, follow_symlinks
    )
    if error is not None:
        return error
    target, error = validate_regular_file(
        file_path, follow_symlinks=follow_links
    )
    if error is not None:
        return error
    sample, error = _read_sample(command, target, budget)
    if error is not None:
        return error
    binary_analysis = analyze_binary_content(
        sample,
        threshold=10.0,
        path=target.analyzed_path,
        detect_encoding=command._detect_encoding,
    )
    selection = _selection(command, target, sample, binary_analysis)
    context = _details(
        command, target, sample, binary_analysis, selection, detailed
    )
    return _result(command, target, binary_analysis, selection, context)
