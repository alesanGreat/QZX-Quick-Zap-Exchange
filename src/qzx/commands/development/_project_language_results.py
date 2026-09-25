"""Aggregation and reporting for ``projectLanguages``."""


def percentage(value, total):
    return 0.0 if total <= 0 else round(value / total * 100, 2)


def quantity(value, singular, plural=None):
    label = singular if value == 1 else (plural or f"{singular}s")
    return f"{value} {label}"


def _totals(values, source_kinds):
    sources = [item for item in values if item["kind"] in source_kinds]
    return {
        "source_files": sum(item["file_count"] for item in sources),
        "source_bytes": sum(item["bytes"] for item in sources),
        "source_code_lines": sum(item["code_lines"] for item in sources),
        "recognized_files": sum(item["file_count"] for item in values),
        "recognized_bytes": sum(item["bytes"] for item in values),
        "recognized_total_lines": sum(item["total_lines"] for item in values),
        "recognized_code_lines": sum(item["code_lines"] for item in values),
        "recognized_comment_lines": sum(item["comment_lines"] for item in values),
        "recognized_blank_lines": sum(item["blank_lines"] for item in values),
    }


def _composition_basis(totals):
    if totals["source_code_lines"] > 0:
        return "source_code_lines", "code_lines", totals["source_code_lines"]
    if totals["source_bytes"] > 0:
        return "source_bytes", "bytes", totals["source_bytes"]
    return "source_file_count", "file_count", totals["source_files"]


def _ranked_counts(counter, name_key):
    return [
        {name_key: name, "file_count": count}
        for name, count in sorted(counter.items(), key=lambda item: (-item[1], item[0]))
    ]


def _language_entry(command, stats, totals, basis_key, basis_total):
    source = stats["kind"] in command.SOURCE_KINDS
    return {
        "language": stats["language"],
        "kind": stats["kind"],
        "aliases": stats["aliases"],
        "composition_percentage": command._percentage(stats[basis_key], basis_total) if source else None,
        "file_count": stats["file_count"],
        "file_percentage": command._percentage(stats["file_count"], totals["recognized_files"]),
        "bytes": stats["bytes"],
        "bytes_formatted": command._format_bytes(stats["bytes"]),
        "byte_percentage": command._percentage(stats["bytes"], totals["recognized_bytes"]),
        "total_lines": stats["total_lines"],
        "code_lines": stats["code_lines"],
        "code_percentage": command._percentage(stats["code_lines"], totals["recognized_code_lines"]),
        "comment_lines": stats["comment_lines"],
        "blank_lines": stats["blank_lines"],
        "extensions": _ranked_counts(stats["extensions"], "extension"),
        "detected_variants": _ranked_counts(stats["detected_variants"], "name"),
        "example_files": stats["example_files"],
    }


def finalize_languages(command, language_stats):
    values = list(language_stats.values())
    totals = _totals(values, command.SOURCE_KINDS)
    basis, basis_key, basis_total = _composition_basis(totals)
    entries = [
        _language_entry(command, stats, totals, basis_key, basis_total)
        for stats in values
    ]
    languages = sorted(
        (item for item in entries if item["kind"] in command.SOURCE_KINDS),
        key=lambda item: (-(item["composition_percentage"] or 0), -item["code_lines"], item["language"].casefold()),
    )
    supporting = sorted(
        (item for item in entries if item["kind"] not in command.SOURCE_KINDS),
        key=lambda item: (-item["code_lines"], -item["file_count"], item["language"].casefold()),
    )
    return languages, supporting, totals, basis


def _source_lines(command, languages):
    if not languages:
        return ["No source programming, markup, or stylesheet languages were detected."]
    lines = ["Source language composition:"]
    for item in languages:
        lines.append(
            f"  - {item['language']}: {item['composition_percentage']:.2f}% "
            f"({command._quantity(item['file_count'], 'file')}, "
            f"{command._quantity(item['code_lines'], 'code line')})"
        )
    return lines


def _supporting_lines(command, supporting):
    if not supporting:
        return []
    lines = ["", "Supporting project formats:"]
    for item in supporting:
        lines.append(
            f"  - {item['language']} ({item['kind']}): "
            f"{command._quantity(item['file_count'], 'file')}, "
            f"{command._quantity(item['code_lines'], 'content line')}"
        )
    return lines


def _exclusion_line(command, exclusions, unclassified):
    values = (
        command._quantity(exclusions["ignored_directories_encountered"], "ignored directory", "ignored directories"),
        command._quantity(exclusions["ignored_files_encountered"], "ignored file"),
        command._quantity(exclusions["generated_files"], "generated file"),
        command._quantity(exclusions["binary_files"], "binary file"),
        command._quantity(exclusions["oversized_files"], "oversized file"),
        command._quantity(unclassified["file_count"], "unknown text file"),
    )
    return "Excluded or unclassified: " + ", ".join(values[:-1]) + f", {values[-1]}."


def build_message(command, target, languages, supporting, summary, exclusions, unclassified, composition_basis, scan_complete, scan_error_count):
    labels = {
        "source_code_lines": "source code lines",
        "source_bytes": "source bytes because the detected files contained no code lines",
        "source_file_count": "source file count because the detected files were empty",
    }
    lines = [
        "QZX Project Languages Profile",
        f"- Scanned path: {target}",
        f"- Composition basis: {labels[composition_basis]}",
        f"- Analyzed: {summary['analyzed_files']} recognized files, {summary['recognized_code_lines']} code lines, {summary['recognized_bytes_formatted']}",
        "",
        *_source_lines(command, languages),
        *_supporting_lines(command, supporting),
        "",
        _exclusion_line(command, exclusions, unclassified),
        "Detection used Pygments for maintained language definitions and pathspec for gitignore-style exclusions.",
    ]
    if not scan_complete:
        lines.append(
            f"The scan completed with {scan_error_count} access or read errors; inspect scan_errors in JSON for details."
        )
    return "\n".join(lines)


def make_summary(command, counters, totals, language_count, supporting_count, errors):
    return {
        **counters,
        "analyzed_files": counters["recognized_files"],
        "source_language_count": language_count,
        "supporting_format_count": supporting_count,
        "total_language_count": language_count + supporting_count,
        "primary_language": None,
        "source_files": totals["source_files"],
        "source_bytes": totals["source_bytes"],
        "source_bytes_formatted": command._format_bytes(totals["source_bytes"]),
        "source_code_lines": totals["source_code_lines"],
        "recognized_bytes": totals["recognized_bytes"],
        "recognized_bytes_formatted": command._format_bytes(totals["recognized_bytes"]),
        "recognized_total_lines": totals["recognized_total_lines"],
        "recognized_code_lines": totals["recognized_code_lines"],
        "recognized_comment_lines": totals["recognized_comment_lines"],
        "recognized_blank_lines": totals["recognized_blank_lines"],
        "scan_error_count": errors,
    }


def make_exclusions(command, counters, examples, ignore_sources):
    return {
        "respected_ignore_files": sorted(set(ignore_sources)),
        "built_in_directory_names": sorted(command.DEFAULT_EXCLUDED_DIRECTORIES),
        "ignored_files_encountered": counters["ignored_files"],
        "ignored_directories_encountered": counters["ignored_directories"],
        "generated_files": counters["generated_files"],
        "generated_examples": examples["generated"],
        "binary_files": counters["binary_files"],
        "binary_examples": examples["binary"],
        "oversized_files": counters["oversized_files"],
        "oversized_examples": examples["oversized"],
        "max_file_size_bytes": command.MAX_FILE_SIZE_BYTES,
        "max_file_size_formatted": command._format_bytes(command.MAX_FILE_SIZE_BYTES),
        "symlinks_skipped": counters["symlinks_skipped"],
    }


def make_unclassified(counters, extensions, examples):
    return {
        "file_count": counters["unknown_files"],
        "extensions": _ranked_counts(extensions, "extension"),
        "example_files": examples,
    }
