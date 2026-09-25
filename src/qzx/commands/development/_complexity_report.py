"""Text reports for ``analyzeComplexity``."""


def _averages(results):
    maintainable = [item["maintainability_index"] for item in results if "maintainability_index" in item]
    return {
        "complexity": sum(item.get("complexity_score", 0) for item in results) / len(results),
        "cyclomatic": sum(item.get("cyclomatic_complexity", 0) for item in results) / len(results),
        "maintainability": sum(maintainable) / len(maintainable) if maintainable else 0,
    }


def _rating(score):
    if score < 2:
        return "Very Low"
    if score < 4:
        return "Low"
    if score < 6:
        return "Moderate"
    if score < 8:
        return "High"
    return "Very High"


def _basic_lines(result):
    return [
        "",
        "Basic Metrics:",
        f"- Lines of Code: {result['line_count']}",
        f"- Non-Empty Lines: {result.get('non_empty_lines', 'N/A')}",
        f"- File Size: {result['size_bytes']} bytes",
        f"- Average Line Length: {result['avg_line_length']:.2f} characters",
        f"- Maximum Line Length: {result['max_line_length']} characters",
        "",
        "Structural Metrics:",
        f"- Functions/Methods: {result['function_count']}",
        f"- Classes/Interfaces: {result['class_count']}",
        f"- Conditional Statements: {result['condition_count']}",
        f"- Loops: {result['loop_count']}",
        f"- Comments: {result['comment_count']}",
        "",
        "Complexity Metrics:",
        f"- Cyclomatic Complexity: {result['cyclomatic_complexity']}",
        f"- Maintainability Index: {result['maintainability_index']:.2f}/100",
    ]


def _halstead_lines(result):
    metrics = result["halstead_metrics"]
    return [
        "",
        "Halstead Metrics:",
        f"- Vocabulary: {metrics.get('vocabulary', 'N/A')}",
        f"- Length: {metrics.get('length', 'N/A')}",
        f"- Volume: {metrics.get('volume', 'N/A'):.2f}",
        f"- Difficulty: {metrics.get('difficulty', 'N/A'):.2f}",
        f"- Effort: {metrics.get('effort', 'N/A'):.2f}",
    ]


def _recommendations(result):
    lines = ["", "Recommendations:"]
    if result["complexity_score"] >= 7:
        lines.extend([
            "- Consider refactoring complex sections into smaller functions",
            "- Reduce nesting levels in conditional statements",
        ])
    if result["function_count"] > 0 and result["comment_count"] / result["function_count"] < 0.5:
        lines.append("- Add more comments to improve code documentation")
    if result["avg_line_length"] > 80:
        lines.append("- Reduce average line length for better readability")
    if result["max_line_length"] > 100:
        lines.append("- Break up long lines of code")
    if result["maintainability_index"] < 65:
        lines.append("- Improve maintainability by simplifying complex methods")
    return lines


def _detailed_file(index, result):
    if "error" in result:
        return [f"File {index}: {result['file_path']}", f"Error: {result['error']}", ""]
    lines = [
        f"File {index}: {result['file_path']}",
        f"Language: {result['language']}",
        f"Complexity Score: {result['complexity_score']:.2f}/10",
        f"Complexity Rating: {_rating(result['complexity_score'])}",
    ]
    return [*lines, *_basic_lines(result), *_halstead_lines(result), *_recommendations(result), "", "-" * 50, ""]


def format_detailed(_command, results, total_files, analyzed_files):
    output = [
        "Code Complexity Analysis Report (Detailed)",
        "=" * 50,
        f"Files Analyzed: {analyzed_files}/{total_files}",
        "",
    ]
    for index, result in enumerate(results, 1):
        output.extend(_detailed_file(index, result))
    output.extend(["", "Overall Summary:"])
    if results:
        averages = _averages(results)
        output.append(f"- Average Complexity Score: {averages['complexity']:.2f}/10")
        output.append(f"- Average Maintainability Index: {averages['maintainability']:.2f}/100")
        most_complex = max(results, key=lambda item: item.get("complexity_score", 0))
        output.append(f"- Most Complex File: {most_complex['file_path']} (Score: {most_complex['complexity_score']:.2f})")
    return "\n".join(output)


def _distribution_lines(results):
    low = len([item for item in results if item.get("complexity_score", 0) < 4])
    medium = len([item for item in results if 4 <= item.get("complexity_score", 0) < 7])
    high = len([item for item in results if item.get("complexity_score", 0) >= 7])
    count = len(results)
    return low, medium, high, [
        "Complexity Distribution:",
        f"- Low Complexity (0-3.99): {low} files ({low/count*100:.1f}%)",
        f"- Medium Complexity (4-6.99): {medium} files ({medium/count*100:.1f}%)",
        f"- High Complexity (7-10): {high} files ({high/count*100:.1f}%)",
        "",
    ]


def _top_files(results):
    lines = ["Top 5 Most Complex Files:"]
    for index, result in enumerate(results[:5], 1):
        score = result.get("complexity_score", 0)
        cyclomatic = result.get("cyclomatic_complexity", "N/A")
        maintainability = result.get("maintainability_index", "N/A")
        if isinstance(maintainability, (int, float)):
            maintainability = f"{maintainability:.2f}/100"
        lines.extend([
            f"{index}. {result['file_path']}",
            f"   Score: {score:.2f}/10, Cyclomatic: {cyclomatic}, Maintainability: {maintainability}",
        ])
        if score >= 7:
            lines.append("   Recommendation: Consider refactoring into smaller components")
        elif cyclomatic != "N/A" and cyclomatic > 10:
            lines.append("   Recommendation: Reduce complexity by simplifying conditional logic")
    return lines


def _general_recommendations(high, result_count, averages):
    lines = ["", "General Recommendations:"]
    if high > 0:
        lines.append("- Refactor highly complex files to improve maintainability")
    if averages["maintainability"] < 65:
        lines.append("- Improve documentation and code structure to increase maintainability")
    if averages["cyclomatic"] > 15:
        lines.append("- Reduce conditional logic complexity by extracting methods")
    if high / result_count > 0.3:
        lines.append("- Consider a code quality review process for complex components")
    return lines


def format_summary(_command, results, total_files, analyzed_files):
    output = [
        "Code Complexity Analysis Report (Summary)",
        "=" * 50,
        f"Files Analyzed: {analyzed_files}/{total_files}",
        "",
    ]
    if not results:
        return "\n".join(output)
    averages = _averages(results)
    output.extend([
        "Overall Metrics:",
        f"- Total Lines of Code: {sum(item.get('line_count', 0) for item in results)}",
        f"- Total Functions/Methods: {sum(item.get('function_count', 0) for item in results)}",
        f"- Total Classes/Interfaces: {sum(item.get('class_count', 0) for item in results)}",
        f"- Average Complexity Score: {averages['complexity']:.2f}/10",
        f"- Average Cyclomatic Complexity: {averages['cyclomatic']:.2f}",
        f"- Average Maintainability Index: {averages['maintainability']:.2f}/100",
        "",
    ])
    _low, _medium, high, distribution = _distribution_lines(results)
    output.extend(distribution)
    output.extend(_top_files(results))
    output.extend(_general_recommendations(high, len(results), averages))
    return "\n".join(output)


def format_results(command, results, total_files, analyzed_files, format_type):
    results.sort(key=lambda item: item.get("complexity_score", 0), reverse=True)
    if format_type.lower() == "summary":
        return command._format_summary(results, total_files, analyzed_files)
    return command._format_detailed(results, total_files, analyzed_files)
