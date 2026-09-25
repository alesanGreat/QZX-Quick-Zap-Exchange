"""Bounded byte/text comparison helpers for ``compareFiles``."""

import difflib
import hashlib
import operator
import os

import chardet

COMPARE_RESULT_SCHEMA = {
    "type": "object",
    "properties": {
        "success": {"type": "boolean"}, "message": {"type": "string"},
        "error": {"type": "string"}, "error_code": {"type": "string"},
        "remediation": {"type": "string"}, "file1": {"type": "string"},
        "file2": {"type": "string"},
        "mode": {"type": "string", "enum": ["full", "summary", "percent"]},
        "identical": {"type": "boolean"}, "added_lines": {"type": "integer"},
        "removed_lines": {"type": "integer"}, "total_changes": {"type": "integer"},
        "diff": {"type": "string"}, "similarity": {"type": "number"},
        "lines_file1": {"type": "integer"}, "lines_file2": {"type": "integer"},
        "identical_lines": {"type": "integer"}, "changes": {"type": "integer"},
        "summary": {"type": "string"},
        "content_type": {"type": "string", "enum": ["text", "binary"]},
        "comparison_basis": {"type": "string"}, "byte_identical": {"type": "boolean"},
        "bytes_file1": {"type": "integer"}, "bytes_file2": {"type": "integer"},
        "max_bytes": {"type": "integer"}, "encoding_file1": {"type": ["string", "null"]},
        "encoding_file2": {"type": ["string", "null"]},
        "encoding_confidence_file1": {"type": ["number", "null"]},
        "encoding_confidence_file2": {"type": ["number", "null"]},
        "sha256_file1": {"type": "string"}, "sha256_file2": {"type": "string"},
        "similarity_available": {"type": "boolean"},
    },
    "additionalProperties": True,
}


def comparison_error(message, error_code="comparison_failed", remediation=None, **details):
    result = {"success": False, "message": message, "error": message, "error_code": error_code}
    if remediation:
        result["remediation"] = remediation
    result.update(details)
    return result


def normalize_max_bytes(value):
    if isinstance(value, bool):
        return None
    try:
        normalized = int(value.strip(), 10) if isinstance(value, str) else operator.index(value)
    except (TypeError, ValueError):
        return None
    return normalized if normalized > 0 else None


def looks_binary(data):
    if not data:
        return False
    sample = data[:65_536]
    if b"\x00" in sample:
        return True
    controls = sum(byte < 32 and byte not in {8, 9, 10, 12, 13, 27} for byte in sample)
    return controls / len(sample) > 0.10


def decode_text(command_class, data, detect_encoding=chardet.detect):
    if not data:
        return "", "utf-8", 1.0
    for prefix, encoding in ((b"\x00\x00\xfe\xff", "utf-32"), (b"\xff\xfe\x00\x00", "utf-32"), (b"\xef\xbb\xbf", "utf-8-sig"), (b"\xfe\xff", "utf-16"), (b"\xff\xfe", "utf-16")):
        if data.startswith(prefix):
            try:
                return data.decode(encoding), encoding, 1.0
            except UnicodeDecodeError:
                return None, None, None
    if command_class._looks_binary(data):
        return None, None, None
    try:
        return data.decode("utf-8"), "utf-8", 1.0
    except UnicodeDecodeError:
        detection = detect_encoding(data[:65_536])
        encoding = detection.get("encoding")
        try:
            confidence = float(detection.get("confidence"))
            if not isinstance(encoding, str) or not 0 <= confidence <= 1:
                return None, None, None
            return data.decode(encoding), encoding.lower(), round(confidence, 4)
        except (TypeError, ValueError, LookupError, UnicodeDecodeError):
            return None, None, None


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def file_too_large(command, file1, file2, size1, size2, max_bytes):
    return command._error(
        f"Comparison stopped before reading the files: the limit is {max_bytes} bytes per file, while '{file1}' is {size1} bytes and '{file2}' is {size2} bytes.",
        error_code="file_too_large",
        remediation="Pass a larger positive max_bytes value only when the expected memory use and result size are acceptable.",
        file1=file1, file2=file2, bytes_file1=size1, bytes_file2=size2, max_bytes=max_bytes,
    )


def compare_binary(command, file1, file2, data1, data2):
    identical = data1 == data2
    digest1, digest2 = command._sha256(data1), command._sha256(data2)
    message = (
        f"Binary files '{file1}' and '{file2}' are byte-for-byte identical (SHA-256: {digest1})."
        if identical else
        f"Binary files '{file1}' and '{file2}' differ. QZX compared their exact bytes and SHA-256 hashes; a text diff and partial similarity percentage do not apply."
    )
    result = {
        "success": True, "file1": file1, "file2": file2, "content_type": "binary",
        "comparison_basis": "exact_bytes_and_sha256", "identical": identical,
        "byte_identical": identical, "bytes_file1": len(data1), "bytes_file2": len(data2),
        "encoding_file1": None, "encoding_file2": None,
        "encoding_confidence_file1": None, "encoding_confidence_file2": None,
        "sha256_file1": digest1, "sha256_file2": digest2,
        "similarity_available": identical, "message": message,
    }
    if identical:
        result["similarity"] = 100.0
    return result


def _validated_request(command, file1, file2, mode, max_bytes):
    try:
        first, second = os.fspath(file1), os.fspath(file2)
    except TypeError as exc:
        return None, command._error(f"Both file paths must be strings or path-like: {exc}", error_code="invalid_path", remediation="Pass two filesystem paths.")
    normalized_mode = str(mode).strip().lower()
    if normalized_mode not in {"full", "summary", "percent"}:
        return None, command._error(f"Invalid comparison mode '{mode}'. Use 'full', 'summary', or 'percent'.", error_code="invalid_mode", remediation="Use 'full', 'summary', or 'percent'.")
    limit = command._normalize_max_bytes(max_bytes)
    if limit is None:
        return None, command._error(f"max_bytes must be a positive integer, got '{max_bytes}'.", error_code="invalid_max_bytes", remediation="Pass a positive byte count, such as 1048576.")
    for candidate, label in ((first, "first"), (second, "second")):
        if not os.path.exists(candidate):
            return None, command._error(f"File '{candidate}' does not exist.", error_code="file_not_found", remediation=f"Check the {label} path and try again.", file1=first, file2=second)
        if not os.path.isfile(candidate):
            return None, command._error(f"Path '{candidate}' is not a file.", error_code="not_a_file", remediation="Pass a file path instead of a directory.", file1=first, file2=second)
    return (first, second, normalized_mode, limit), None


def _read_pair(command, first, second, limit):
    size1, size2 = os.path.getsize(first), os.path.getsize(second)
    if size1 > limit or size2 > limit:
        return None, command._file_too_large(first, second, size1, size2, limit)
    with open(first, "rb") as handle:
        data1 = handle.read(limit + 1)
    with open(second, "rb") as handle:
        data2 = handle.read(limit + 1)
    if len(data1) > limit or len(data2) > limit:
        return None, command._file_too_large(first, second, len(data1), len(data2), limit)
    return (data1, data2), None


def _text_result(command, first, second, mode, data1, data2):
    text1, encoding1, confidence1 = command._decode_text(data1)
    text2, encoding2, confidence2 = command._decode_text(data2)
    if text1 is None or text2 is None:
        return command._compare_binary(first, second, data1, data2)
    lines1, lines2 = text1.splitlines(keepends=True), text2.splitlines(keepends=True)
    comparator = {"full": command._compare_full, "summary": command._compare_summary, "percent": command._compare_percent}[mode]
    result = comparator(first, second, lines1, lines2)
    byte_identical = data1 == data2
    result.update({
        "content_type": "text", "comparison_basis": "decoded_text_lines",
        "byte_identical": byte_identical, "bytes_file1": len(data1), "bytes_file2": len(data2),
        "encoding_file1": encoding1, "encoding_file2": encoding2,
        "encoding_confidence_file1": confidence1, "encoding_confidence_file2": confidence2,
        "sha256_file1": command._sha256(data1), "sha256_file2": command._sha256(data2),
        "similarity_available": True,
    })
    if result["identical"] and not byte_identical:
        result["message"] = f"Files '{first}' and '{second}' decode to identical text, but their byte encodings differ."
    return result


def execute_file_comparison(command, file1, file2, mode="full", max_bytes=1_048_576):
    request, error = _validated_request(command, file1, file2, mode, max_bytes)
    if error:
        return error
    first, second, normalized_mode, limit = request
    try:
        pair, error = _read_pair(command, first, second, limit)
        if error:
            return error
        result = _text_result(command, first, second, normalized_mode, *pair)
        result.update(mode=normalized_mode, max_bytes=limit)
        return result
    except OSError as exc:
        return command._error(
            f"Could not compare the files: {exc}", error_code="file_read_failed",
            remediation="Check file permissions and whether the files changed.",
            file1=first, file2=second,
        )


def compare_full(_command, file1, file2, content1, content2):
    diff_lines = [line.rstrip("\r\n") for line in difflib.unified_diff(content1, content2, fromfile=file1, tofile=file2, lineterm="")]
    if not diff_lines:
        return {"success": True, "file1": file1, "file2": file2, "identical": True, "added_lines": 0, "removed_lines": 0, "total_changes": 0, "diff": "", "message": f"Files '{file1}' and '{file2}' are identical."}
    added = sum(line.startswith("+") and not line.startswith("+++") for line in diff_lines)
    removed = sum(line.startswith("-") and not line.startswith("---") for line in diff_lines)
    report = [f"Differences between '{file1}' and '{file2}':", *diff_lines, "\nStatistics:", f"- Added lines: {added}", f"- Removed lines: {removed}", f"- Total changes: {added + removed}"]
    return {"success": True, "file1": file1, "file2": file2, "identical": False, "added_lines": added, "removed_lines": removed, "total_changes": added + removed, "diff": "\n".join(report), "message": f"Compared '{file1}' with '{file2}': {added} added and {removed} removed lines."}


def compare_summary(_command, file1, file2, content1, content2):
    matcher = difflib.SequenceMatcher(None, content1, content2)
    similarity = matcher.ratio() * 100
    identical_lines = sum(block.size for block in matcher.get_matching_blocks() if block.size > 0)
    changes = max(len(content1), len(content2)) - identical_lines
    lines = [f"Difference summary for '{file1}' and '{file2}':", f"- Similarity: {similarity:.2f}%", f"- Lines in file 1: {len(content1)}", f"- Lines in file 2: {len(content2)}", f"- Identical lines: {identical_lines}", f"- Changes detected: {changes}"]
    return {"success": True, "file1": file1, "file2": file2, "identical": changes == 0, "similarity": similarity, "lines_file1": len(content1), "lines_file2": len(content2), "identical_lines": identical_lines, "changes": changes, "summary": "\n".join(lines), "message": f"Compared '{file1}' with '{file2}': {similarity:.2f}% similarity and {changes} detected changes."}


def compare_percent(_command, file1, file2, content1, content2):
    similarity = difflib.SequenceMatcher(None, content1, content2).ratio() * 100
    return {"success": True, "file1": file1, "file2": file2, "identical": content1 == content2, "similarity": similarity, "message": f"Similarity between '{file1}' and '{file2}': {similarity:.2f}%"}
