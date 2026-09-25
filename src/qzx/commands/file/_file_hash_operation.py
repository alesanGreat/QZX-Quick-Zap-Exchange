"""Hash calculation workflow for calculateFileHash."""

from __future__ import annotations

import hashlib
import os


SUPPORTED_ALGORITHMS = {
    "sha256": hashlib.sha256,
    "sha1": hashlib.sha1,
    "md5": hashlib.md5,
}


def _validate(file_path, algorithm):
    if not os.path.exists(file_path):
        return None, {
            "success": False,
            "error": f"File '{file_path}' does not exist.",
        }
    if not os.path.isfile(file_path):
        return None, {
            "success": False,
            "error": f"'{file_path}' is not a file.",
        }
    normalized = algorithm.strip().lower()
    if normalized not in SUPPORTED_ALGORITHMS:
        return None, {
            "success": False,
            "error": (
                f"Unsupported hash algorithm '{normalized}'. Supported algorithms: "
                f"{', '.join(SUPPORTED_ALGORITHMS.keys())}"
            ),
        }
    return normalized, None


def _digest(file_path, algorithm):
    digest = SUPPORTED_ALGORITHMS[algorithm]()
    with open(file_path, "rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def execute_file_hash(command, file_path, algorithm="sha256"):
    """Calculate one supported digest and return file metadata."""
    try:
        algorithm, error = _validate(file_path, algorithm)
        if error:
            return error
        file_size = os.path.getsize(file_path)
        calculated = _digest(file_path, algorithm)
        return {
            "success": True,
            "file_path": os.path.abspath(file_path),
            "algorithm": algorithm,
            "hash": calculated,
            "file_size": file_size,
            "file_size_readable": command._format_bytes(file_size),
            "message": (
                f"{algorithm.upper()} hash for '{file_path}': {calculated}"
            ),
        }
    except Exception as exc:
        return {
            "success": False,
            "file_path": file_path,
            "error": str(exc),
            "message": f"Failed to calculate file hash: {str(exc)}",
        }
