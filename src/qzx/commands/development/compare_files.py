#!/usr/bin/env python

"""Compare the contents of two files."""

import difflib
import hashlib
import operator
import os
from typing import ClassVar

import chardet

from qzx.core.command_base import CommandBase


class CompareFilesCommand(CommandBase):
    """Compare two files and report their differences."""

    name = "compareFiles"
    description = (
        "Compares text files line by line and binary files by exact bytes and SHA-256"
    )
    category = "development"
    DEFAULT_MAX_BYTES = 1_048_576

    parameters: ClassVar[list[dict[str, object]]] = [
        {"name": "file1", "description": "Path to the first file", "required": True},
        {"name": "file2", "description": "Path to the second file", "required": True},
        {
            "name": "mode",
            "description": 'Comparison mode: "full", "summary", or "percent"',
            "required": False,
            "default": "full",
        },
        {
            "name": "max_bytes",
            "description": (
                "Maximum allowed size of each file in bytes (defaults to 1 MiB)"
            ),
            "required": False,
            "default": DEFAULT_MAX_BYTES,
        },
    ]

    examples: ClassVar[list[dict[str, str]]] = [
        {
            "command": 'qzx compareFiles "file1.py" "file2.py"',
            "description": "Compare two Python files and show every difference",
        },
        {
            "command": 'qzx compareFiles "file1.txt" "file2.txt" "summary"',
            "description": "Show a summary of differences between two text files",
        },
        {
            "command": 'qzx compareFiles "version1.js" "version2.js" "percent"',
            "description": "Show the similarity percentage between two JavaScript files",
        },
        {
            "command": 'qzx compareFiles "image-a.png" "image-b.png"',
            "description": (
                "Check whether two binary files are exactly equal by bytes and SHA-256"
            ),
        },
    ]

    result_schema: ClassVar[dict[str, object]] = {
        "type": "object",
        "properties": {
            "success": {"type": "boolean"},
            "message": {"type": "string"},
            "error": {"type": "string"},
            "error_code": {"type": "string"},
            "remediation": {"type": "string"},
            "file1": {"type": "string"},
            "file2": {"type": "string"},
            "mode": {
                "type": "string",
                "enum": ["full", "summary", "percent"],
            },
            "identical": {"type": "boolean"},
            "added_lines": {"type": "integer"},
            "removed_lines": {"type": "integer"},
            "total_changes": {"type": "integer"},
            "diff": {"type": "string"},
            "similarity": {"type": "number"},
            "lines_file1": {"type": "integer"},
            "lines_file2": {"type": "integer"},
            "identical_lines": {"type": "integer"},
            "changes": {"type": "integer"},
            "summary": {"type": "string"},
            "content_type": {
                "type": "string",
                "enum": ["text", "binary"],
            },
            "comparison_basis": {"type": "string"},
            "byte_identical": {"type": "boolean"},
            "bytes_file1": {"type": "integer"},
            "bytes_file2": {"type": "integer"},
            "max_bytes": {"type": "integer"},
            "encoding_file1": {"type": ["string", "null"]},
            "encoding_file2": {"type": ["string", "null"]},
            "encoding_confidence_file1": {"type": ["number", "null"]},
            "encoding_confidence_file2": {"type": ["number", "null"]},
            "sha256_file1": {"type": "string"},
            "sha256_file2": {"type": "string"},
            "similarity_available": {"type": "boolean"},
        },
        "additionalProperties": True,
    }

    @staticmethod
    def _error(message, error_code="comparison_failed", remediation=None, **details):
        """Return the complete public failure contract."""
        result = {
            "success": False,
            "message": message,
            "error": message,
            "error_code": error_code,
        }
        if remediation:
            result["remediation"] = remediation
        result.update(details)
        return result

    @staticmethod
    def _normalize_max_bytes(value):
        """Return a positive byte limit or None when the input is invalid."""
        if isinstance(value, bool):
            return None
        try:
            normalized = (
                int(value.strip(), 10)
                if isinstance(value, str)
                else operator.index(value)
            )
        except (TypeError, ValueError):
            return None
        return normalized if normalized > 0 else None

    @staticmethod
    def _looks_binary(data):
        """Detect control-byte patterns that should not be rendered as text."""
        if not data:
            return False
        sample = data[:65_536]
        if b"\x00" in sample:
            return True
        accepted_controls = {8, 9, 10, 12, 13, 27}
        control_count = sum(
            byte < 32 and byte not in accepted_controls for byte in sample
        )
        return control_count / len(sample) > 0.10

    @classmethod
    def _decode_text(cls, data, detect_encoding=chardet.detect):
        """Decode without replacement; return text, encoding, and confidence."""
        if not data:
            return "", "utf-8", 1.0

        bom_encodings = (
            (b"\x00\x00\xfe\xff", "utf-32"),
            (b"\xff\xfe\x00\x00", "utf-32"),
            (b"\xef\xbb\xbf", "utf-8-sig"),
            (b"\xfe\xff", "utf-16"),
            (b"\xff\xfe", "utf-16"),
        )
        for prefix, encoding in bom_encodings:
            if data.startswith(prefix):
                try:
                    return data.decode(encoding), encoding, 1.0
                except UnicodeDecodeError:
                    return None, None, None

        if cls._looks_binary(data):
            return None, None, None

        try:
            return data.decode("utf-8"), "utf-8", 1.0
        except UnicodeDecodeError:
            detection = detect_encoding(data[:65_536])
            encoding = detection.get("encoding")
            if not isinstance(encoding, str):
                return None, None, None
            try:
                confidence = float(detection.get("confidence"))
            except (TypeError, ValueError):
                return None, None, None
            if not 0 <= confidence <= 1:
                return None, None, None
            try:
                return (
                    data.decode(encoding),
                    encoding.lower(),
                    round(confidence, 4),
                )
            except (LookupError, UnicodeDecodeError):
                return None, None, None

    @staticmethod
    def _sha256(data):
        return hashlib.sha256(data).hexdigest()

    def _file_too_large(self, file1, file2, size1, size2, max_bytes):
        return self._error(
            (
                "Comparison stopped before reading the files: "
                f"the limit is {max_bytes} bytes per file, while "
                f"'{file1}' is {size1} bytes and '{file2}' is {size2} bytes."
            ),
            error_code="file_too_large",
            remediation=(
                "Pass a larger positive max_bytes value only when the expected "
                "memory use and result size are acceptable."
            ),
            file1=file1,
            file2=file2,
            bytes_file1=size1,
            bytes_file2=size2,
            max_bytes=max_bytes,
        )

    def _compare_binary(self, file1, file2, data1, data2):
        """Perform an exact, lossless binary comparison."""
        identical = data1 == data2
        sha256_file1 = self._sha256(data1)
        sha256_file2 = self._sha256(data2)
        if identical:
            message = (
                f"Binary files '{file1}' and '{file2}' are byte-for-byte "
                f"identical (SHA-256: {sha256_file1})."
            )
        else:
            message = (
                f"Binary files '{file1}' and '{file2}' differ. QZX compared "
                "their exact bytes and SHA-256 hashes; a text diff and partial "
                "similarity percentage do not apply."
            )
        result = {
            "success": True,
            "file1": file1,
            "file2": file2,
            "content_type": "binary",
            "comparison_basis": "exact_bytes_and_sha256",
            "identical": identical,
            "byte_identical": identical,
            "bytes_file1": len(data1),
            "bytes_file2": len(data2),
            "encoding_file1": None,
            "encoding_file2": None,
            "encoding_confidence_file1": None,
            "encoding_confidence_file2": None,
            "sha256_file1": sha256_file1,
            "sha256_file2": sha256_file2,
            "similarity_available": identical,
            "message": message,
        }
        if identical:
            result["similarity"] = 100.0
        return result

    def execute(self, file1, file2, mode="full", max_bytes=DEFAULT_MAX_BYTES):
        """
        Compare two files and report their differences.

        Args:
            file1: Path to the first file.
            file2: Path to the second file.
            mode: Comparison mode (full, summary, percent).
            max_bytes: Maximum allowed size of each file in bytes.

        Returns:
            The comparison result in the requested format.
        """
        try:
            file1 = os.fspath(file1)
            file2 = os.fspath(file2)
        except TypeError as error:
            return self._error(
                f"Both file paths must be strings or path-like: {error}",
                error_code="invalid_path",
                remediation="Pass two filesystem paths.",
            )

        normalized_mode = str(mode).strip().lower()
        if normalized_mode not in {"full", "summary", "percent"}:
            return self._error(
                f"Invalid comparison mode '{mode}'. "
                "Use 'full', 'summary', or 'percent'.",
                error_code="invalid_mode",
                remediation="Use 'full', 'summary', or 'percent'.",
            )

        normalized_max_bytes = self._normalize_max_bytes(max_bytes)
        if normalized_max_bytes is None:
            return self._error(
                f"max_bytes must be a positive integer, got '{max_bytes}'.",
                error_code="invalid_max_bytes",
                remediation="Pass a positive byte count, such as 1048576.",
            )

        # Verify that both paths exist.
        if not os.path.exists(file1):
            return self._error(
                f"File '{file1}' does not exist.",
                error_code="file_not_found",
                remediation="Check the first path and try again.",
                file1=file1,
                file2=file2,
            )
        if not os.path.exists(file2):
            return self._error(
                f"File '{file2}' does not exist.",
                error_code="file_not_found",
                remediation="Check the second path and try again.",
                file1=file1,
                file2=file2,
            )

        # Verify that both paths are files rather than directories.
        if not os.path.isfile(file1):
            return self._error(
                f"Path '{file1}' is not a file.",
                error_code="not_a_file",
                remediation="Pass a file path instead of a directory.",
                file1=file1,
                file2=file2,
            )
        if not os.path.isfile(file2):
            return self._error(
                f"Path '{file2}' is not a file.",
                error_code="not_a_file",
                remediation="Pass a file path instead of a directory.",
                file1=file1,
                file2=file2,
            )

        try:
            size1 = os.path.getsize(file1)
            size2 = os.path.getsize(file2)
            if size1 > normalized_max_bytes or size2 > normalized_max_bytes:
                return self._file_too_large(
                    file1,
                    file2,
                    size1,
                    size2,
                    normalized_max_bytes,
                )

            with open(file1, "rb") as handle:
                data1 = handle.read(normalized_max_bytes + 1)
            with open(file2, "rb") as handle:
                data2 = handle.read(normalized_max_bytes + 1)
            if len(data1) > normalized_max_bytes or len(data2) > normalized_max_bytes:
                return self._file_too_large(
                    file1,
                    file2,
                    len(data1),
                    len(data2),
                    normalized_max_bytes,
                )

            text1, encoding1, confidence1 = self._decode_text(data1)
            text2, encoding2, confidence2 = self._decode_text(data2)
            if text1 is None or text2 is None:
                result = self._compare_binary(file1, file2, data1, data2)
            else:
                content1 = text1.splitlines(keepends=True)
                content2 = text2.splitlines(keepends=True)
                if normalized_mode == "full":
                    result = self._compare_full(file1, file2, content1, content2)
                elif normalized_mode == "summary":
                    result = self._compare_summary(
                        file1,
                        file2,
                        content1,
                        content2,
                    )
                else:
                    result = self._compare_percent(
                        file1,
                        file2,
                        content1,
                        content2,
                    )
                byte_identical = data1 == data2
                result.update(
                    {
                        "content_type": "text",
                        "comparison_basis": "decoded_text_lines",
                        "byte_identical": byte_identical,
                        "bytes_file1": len(data1),
                        "bytes_file2": len(data2),
                        "encoding_file1": encoding1,
                        "encoding_file2": encoding2,
                        "encoding_confidence_file1": confidence1,
                        "encoding_confidence_file2": confidence2,
                        "sha256_file1": self._sha256(data1),
                        "sha256_file2": self._sha256(data2),
                        "similarity_available": True,
                    }
                )
                if result["identical"] and not byte_identical:
                    result["message"] = (
                        f"Files '{file1}' and '{file2}' decode to identical "
                        "text, but their byte encodings differ."
                    )

            result["mode"] = normalized_mode
            result["max_bytes"] = normalized_max_bytes
            return result

        except OSError as error:
            return self._error(
                f"Could not compare the files: {error}",
                error_code="file_read_failed",
                remediation="Check file permissions and whether the files changed.",
                file1=file1,
                file2=file2,
            )

    def _compare_full(self, file1, file2, content1, content2):
        """Perform a complete line-by-line comparison."""
        diff = difflib.unified_diff(
            content1,
            content2,
            fromfile=file1,
            tofile=file2,
            lineterm="",
        )

        diff_text = [line.rstrip("\r\n") for line in diff]

        if not diff_text:
            return {
                "success": True,
                "file1": file1,
                "file2": file2,
                "identical": True,
                "added_lines": 0,
                "removed_lines": 0,
                "total_changes": 0,
                "diff": "",
                "message": f"Files '{file1}' and '{file2}' are identical.",
            }

        result = [f"Differences between '{file1}' and '{file2}':"]
        result.extend(diff_text)

        # Statistics
        result.append("\nStatistics:")
        added, removed = 0, 0
        for line in diff_text:
            if line.startswith("+") and not line.startswith("+++"):
                added += 1
            elif line.startswith("-") and not line.startswith("---"):
                removed += 1

        result.append(f"- Added lines: {added}")
        result.append(f"- Removed lines: {removed}")
        result.append(f"- Total changes: {added + removed}")

        return {
            "success": True,
            "file1": file1,
            "file2": file2,
            "identical": False,
            "added_lines": added,
            "removed_lines": removed,
            "total_changes": added + removed,
            "diff": "\n".join(result),
            "message": (
                f"Compared '{file1}' with '{file2}': "
                f"{added} added and {removed} removed lines."
            ),
        }

    def _compare_summary(self, file1, file2, content1, content2):
        """Summarize the number of differences."""
        matcher = difflib.SequenceMatcher(None, content1, content2)

        # Get matching blocks.
        blocks = matcher.get_matching_blocks()

        # Calculate statistics.
        similarity = matcher.ratio() * 100
        total_lines1 = len(content1)
        total_lines2 = len(content2)

        # Count identical lines.
        identical_lines = sum(block.size for block in blocks if block.size > 0)

        # Count changes.
        changes = max(total_lines1, total_lines2) - identical_lines

        summary = [
            f"Difference summary for '{file1}' and '{file2}':",
            f"- Similarity: {similarity:.2f}%",
            f"- Lines in file 1: {total_lines1}",
            f"- Lines in file 2: {total_lines2}",
            f"- Identical lines: {identical_lines}",
            f"- Changes detected: {changes}",
        ]

        return {
            "success": True,
            "file1": file1,
            "file2": file2,
            "identical": changes == 0,
            "similarity": similarity,
            "lines_file1": total_lines1,
            "lines_file2": total_lines2,
            "identical_lines": identical_lines,
            "changes": changes,
            "summary": "\n".join(summary),
            "message": (
                f"Compared '{file1}' with '{file2}': "
                f"{similarity:.2f}% similarity and {changes} detected changes."
            ),
        }

    def _compare_percent(self, file1, file2, content1, content2):
        """Return only the similarity percentage."""
        # Calculate similarity using SequenceMatcher.
        matcher = difflib.SequenceMatcher(None, content1, content2)
        similarity = matcher.ratio() * 100

        # Similarity is approximate; identity remains an exact text comparison.
        identical = content1 == content2

        return {
            "success": True,
            "file1": file1,
            "file2": file2,
            "identical": identical,
            "similarity": similarity,
            "message": (
                f"Similarity between '{file1}' and '{file2}': {similarity:.2f}%"
            ),
        }
