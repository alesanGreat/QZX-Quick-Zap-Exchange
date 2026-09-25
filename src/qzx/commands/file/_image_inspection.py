"""File validation and result assembly for inspectImage."""

from __future__ import annotations

import os


def _invalid_path(image_path):
    if not image_path:
        return {
            "success": False,
            "error": "The image_path parameter is required.",
            "message": "Image path is required.",
        }
    absolute = os.path.abspath(image_path)
    if not os.path.exists(absolute):
        return {
            "success": False,
            "error": f"Image file '{image_path}' does not exist.",
            "message": f"Image file '{image_path}' does not exist.",
        }
    if not os.path.isfile(absolute):
        return {
            "success": False,
            "error": f"'{image_path}' is not a file.",
            "message": f"'{image_path}' is not a file.",
        }
    return None


def _message(path, meta, readable_size, file_size):
    message = f"Image Diagnostics for '{path}':\n"
    message += f"- Format: {meta['format']}\n"
    message += f"- Dimensions: {meta['width']} x {meta['height']} px\n"
    message += f"- File Size: {readable_size} ({file_size} bytes)\n"
    if "depth" in meta:
        message += f"- Color Depth: {meta['depth']} bits"
    return message


def execute_inspect_image(command, image_path):
    """Inspect one image using only native binary headers."""
    image_path = image_path.strip()
    error = _invalid_path(image_path)
    if error:
        return error
    absolute = os.path.abspath(image_path)
    try:
        file_size = os.path.getsize(absolute)
        meta = command._parse_image(absolute)
        if not meta:
            return {
                "success": False,
                "error": "Unsupported image format or corrupt header.",
                "message": (
                    "Could not identify image format or extract dimensions "
                    "from header."
                ),
            }
        readable_size = command._format_bytes(file_size)
        return {
            "success": True,
            "file_path": absolute,
            "format": meta["format"],
            "width": meta["width"],
            "height": meta["height"],
            "color_depth": meta.get("depth"),
            "file_bytes": file_size,
            "file_size_readable": readable_size,
            "message": _message(absolute, meta, readable_size, file_size),
        }
    except Exception as exc:
        return {
            "success": False,
            "error": str(exc),
            "message": f"Failed to inspect image header: {str(exc)}",
        }
