#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Detect file type with bounded built-in signatures and optional libmagic."""

from __future__ import annotations

from qzx.core.command_base import CommandBase
from qzx.core.file_content_analysis import (
    FileChangedDuringReadError,
    DEFAULT_TYPE_SAMPLE_SIZE,
    MAX_SAMPLE_SIZE,
    MIN_SAMPLE_SIZE,
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

try:
    import magic
except ImportError:  # The built-in detector remains fully usable.
    magic = None


_DEFAULT_MAGIC_PROVIDER = object()


class DetectFileTypeCommand(CommandBase):
    """Identify one regular file without trusting its extension alone."""

    name = "detectFileType"
    description = (
        "Identifies a regular file from bounded content signatures with an "
        "optional libmagic refinement and an explicit extension comparison"
    )
    category = "file"
    _byte_units = ("B", "KB", "MB", "GB", "TB", "PB")

    parameters = [
        {
            "name": "file_path",
            "description": "Path to the regular file to identify",
            "required": True,
            "type": "str",
        },
        {
            "name": "detailed_info",
            "description": "Include categories, sample evidence, and detector details",
            "required": False,
            "default": False,
            "type": "bool",
        },
        {
            "name": "sample_size",
            "description": (
                f"Total content sample budget in bytes ({MIN_SAMPLE_SIZE} through "
                f"{MAX_SAMPLE_SIZE})"
            ),
            "required": False,
            "default": DEFAULT_TYPE_SAMPLE_SIZE,
            "type": "int",
        },
        {
            "name": "follow_symlinks",
            "description": (
                "Follow reviewed symbolic-link or junction components to their "
                "resolved regular-file target"
            ),
            "required": False,
            "default": False,
            "type": "bool",
        },
    ]

    examples = [
        {
            "command": "qzx detectFileType image.jpg",
            "description": "Identify a file from its contents rather than its name",
        },
        {
            "command": "qzx detectFileType unknown.bin true",
            "description": "Include detailed detector and sampling evidence",
        },
        {
            "command": "qzx detectFileType reviewed-link false 65536 true",
            "description": "Identify the resolved target of an explicitly reviewed link",
        },
    ]

    def __init__(
        self,
        *,
        magic_provider=_DEFAULT_MAGIC_PROVIDER,
        open_file=None,
        detect_encoding=None,
    ):
        super().__init__()
        self._magic_provider = (
            magic if magic_provider is _DEFAULT_MAGIC_PROVIDER else magic_provider
        )
        self._open_file = open_file
        self._detect_encoding = detect_encoding

    def execute(
        self,
        file_path,
        detailed_info=False,
        sample_size=DEFAULT_TYPE_SAMPLE_SIZE,
        follow_symlinks=False,
    ):
        detailed, error = normalize_boolean(
            detailed_info,
            field="detailed_info",
            command_base=self,
        )
        if error is not None:
            return error
        sample_budget, error = normalize_sample_size(
            sample_size,
            default=DEFAULT_TYPE_SAMPLE_SIZE,
        )
        if error is not None:
            return error
        follow_links, error = normalize_boolean(
            follow_symlinks,
            field="follow_symlinks",
            command_base=self,
        )
        if error is not None:
            return error

        target, error = validate_regular_file(
            file_path,
            follow_symlinks=follow_links,
        )
        if error is not None:
            return error
        try:
            sample = read_distributed_sample(
                target,
                sample_budget,
                **(
                    {"open_file": self._open_file}
                    if self._open_file is not None
                    else {}
                ),
            )
        except FileChangedDuringReadError as exc:
            return {
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
            return {
                "success": False,
                "error_code": "file_read_failed",
                "error": f"{type(exc).__name__}: {exc}",
                "message": "QZX could not read the requested file sample.",
                "details": target.evidence(),
            }

        binary_analysis = analyze_binary_content(
            sample,
            threshold=10.0,
            path=target.analyzed_path,
            detect_encoding=self._detect_encoding,
        )
        builtin_type = detect_builtin_type(
            target.analyzed_path,
            sample,
            binary_analysis,
        )
        selected_type = builtin_type
        warnings = []
        libmagic_type, libmagic_description, libmagic_error = (
            self._detect_with_libmagic(target, sample)
        )
        normalized_magic = normalize_mime_type(libmagic_type)
        strong_builtin = builtin_type.source == "content_signature"
        if normalized_magic is not None:
            if strong_builtin:
                if normalized_magic != builtin_type.mime_type:
                    warnings.append(
                        "libmagic disagreed with a strong built-in content "
                        f"signature ({normalized_magic} versus "
                        f"{builtin_type.mime_type}); QZX retained the signature."
                    )
            elif (
                normalized_magic != "application/octet-stream"
                or builtin_type.mime_type == "application/octet-stream"
            ):
                selected_type = DetectedType(
                    normalized_magic,
                    libmagic_description or normalized_magic,
                    "libmagic",
                    95.0,
                )
        elif libmagic_type is not None:
            warnings.append(
                "libmagic returned a malformed MIME type; the bounded built-in "
                "detector was used instead."
            )
        elif libmagic_error is not None:
            warnings.append(
                "libmagic refinement failed; the bounded built-in detector was "
                f"used instead ({libmagic_error})."
            )

        if (
            selected_type.source == "zip_container_plus_extension_hint"
            and libmagic_type is None
        ):
            warnings.append(
                "The Office Open XML subtype is inferred from the extension only; "
                "the ZIP container was detected, but its internal package layout "
                "was not opened or verified."
            )

        extension = target.absolute_path.suffix.casefold().lstrip(".") or None
        common_extensions = common_extensions_for_mime(selected_type.mime_type)
        extension_matches = (
            extension in common_extensions if common_extensions else None
        )
        details = {
            "detection": selected_type.evidence(),
            "builtin_detection": builtin_type.evidence(),
            "libmagic_available": self._magic_provider is not None,
            "libmagic_mime_type": normalized_magic,
            "libmagic_agrees_with_builtin": (
                None
                if normalized_magic is None
                else normalized_magic == builtin_type.mime_type
            ),
            "container_mime_type": (
                "application/zip"
                if builtin_type.source == "zip_container_plus_extension_hint"
                else None
            ),
            "extension_match_status": (
                "unknown"
                if extension_matches is None
                else "matches"
                if extension_matches
                else "mismatch"
            ),
            "target": target.evidence(),
        }
        if detailed:
            details.update(
                {
                    "categories": categorize_mime_type(selected_type.mime_type),
                    "common_extensions": common_extensions,
                    "sampling": sample.evidence(),
                    "binary_analysis": binary_analysis,
                    "libmagic_description": libmagic_description,
                }
            )

        result = {
            "success": True,
            "message": (
                f"File '{target.absolute_path}' was identified as "
                f"{selected_type.mime_type} by {selected_type.source}."
            ),
            "file_path": str(target.absolute_path),
            "analyzed_path": str(target.analyzed_path),
            "file_size": target.file_size,
            "file_size_readable": self._format_bytes(float(target.file_size)),
            "mime_type": selected_type.mime_type,
            "description": selected_type.description,
            "is_binary": binary_analysis["is_binary"],
            "extension": f".{extension}" if extension else None,
            "extension_matches_content": extension_matches,
            "details": details,
        }
        if extension_matches is False and common_extensions:
            result["suggested_extension"] = f".{common_extensions[0]}"
            result["message"] += (
                f" The current extension does not match; "
                f"'.{common_extensions[0]}' is the canonical suggestion."
            )
        if warnings:
            result["warnings"] = warnings
        return result

    def _detect_with_libmagic(self, target, sample):
        provider = self._magic_provider
        if provider is None:
            return None, None, None
        try:
            from_buffer = getattr(provider, "from_buffer", None)
            if callable(from_buffer):
                mime_type = from_buffer(sample.head, mime=True)
                description = from_buffer(sample.head, mime=False)
            else:
                from_file = getattr(provider, "from_file")
                mime_type = from_file(str(target.analyzed_path), mime=True)
                description = from_file(str(target.analyzed_path), mime=False)
            return mime_type, description, None
        except Exception as exc:
            return None, None, f"{type(exc).__name__}: {exc}"
