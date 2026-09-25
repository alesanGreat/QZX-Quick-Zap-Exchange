"""Metric extraction for ``analyzeComplexity``."""

import ast
import math
import os
import re


FUNCTION_PATTERNS = {
    "python": r"def\s+\w+\s*\(",
    "javascript": r"function\s+\w+|const\s+\w+\s*=\s*function|\w+\s*:\s*function|\([^)]*\)\s*=>",
    "typescript": r"function\s+\w+|const\s+\w+\s*=\s*function|\w+\s*:\s*function|\([^)]*\)\s*=>",
    "java": r"(public|private|protected|static|\s) +[\w\<\>\[\]]+\s+(\w+) *\([^\)]*\)",
    "c": r"\w+\s+\w+\s*\([^;]*\)\s*\{",
    "cpp": r"[\w\<\>\[\]]+\s+\w+\s*\([^;]*\)\s*\{",
    "csharp": r"(public|private|protected|static|\s) +[\w\<\>\[\]]+\s+(\w+) *\([^\)]*\)",
    "php": r"function\s+\w+\s*\(",
    "ruby": r"def\s+\w+",
    "go": r"func\s+\w+",
    "rust": r"fn\s+\w+",
}
CLASS_PATTERNS = {
    "python": r"class\s+\w+",
    "javascript": r"class\s+\w+",
    "typescript": r"class\s+\w+|interface\s+\w+",
    "java": r"class\s+\w+|interface\s+\w+",
    "cpp": r"class\s+\w+",
    "csharp": r"class\s+\w+|interface\s+\w+",
    "php": r"class\s+\w+",
    "ruby": r"class\s+\w+",
    "rust": r"struct\s+\w+|enum\s+\w+|trait\s+\w+",
}
OPERATORS = {
    "python": ["+", "-", "*", "/", "%", "**", "//", "=", "+=", "-=", "*=", "/=", "%=", "**=", "//=", "==", "!=", ">", "<", ">=", "<=", "and", "or", "not", "in", "is", "lambda"],
    "javascript": ["+", "-", "*", "/", "%", "**", "=", "+=", "-=", "*=", "/=", "%=", "**=", "==", "===", "!=", "!==", ">", "<", ">=", "<=", "&&", "||", "!", "typeof", "instanceof"],
}
KEYWORDS = {
    "python": ["def", "class", "if", "else", "elif", "for", "while", "try", "except", "finally", "with", "as", "import", "from", "return", "yield", "break", "continue", "pass", "True", "False", "None"],
    "javascript": ["function", "class", "if", "else", "for", "while", "try", "catch", "finally", "with", "switch", "case", "default", "break", "continue", "return", "throw", "typeof", "instanceof", "new", "this", "super", "true", "false", "null", "undefined"],
}


def analyze_file(command, file_path):
    extension = os.path.splitext(file_path)[1].lower()
    if extension not in command.SUPPORTED_EXTENSIONS:
        return None
    language = command.SUPPORTED_EXTENSIONS[extension]
    try:
        with open(file_path, "r", encoding="utf-8", errors="replace") as source:
            content = source.read()
        metrics = {
            "file_path": file_path,
            "language": language,
            "size_bytes": os.path.getsize(file_path),
            "line_count": content.count("\n") + 1,
            "character_count": len(content),
        }
        metrics.update(command._get_language_metrics(content, language))
        metrics["complexity_score"] = command._calculate_complexity_score(metrics)
        return metrics
    except Exception as exc:
        return {"file_path": file_path, "language": language, "error": str(exc)}


def get_language_metrics(command, content, language):
    lines = [line for line in content.split("\n") if line.strip()]
    metrics = {
        "line_count": content.count("\n") + 1,
        "comment_count": 0,
        "function_count": 0,
        "class_count": 0,
        "condition_count": 0,
        "loop_count": 0,
        "avg_line_length": 0,
        "max_line_length": 0,
        "cyclomatic_complexity": 1,
        "halstead_metrics": {},
        "maintainability_index": 0,
        "non_empty_lines": len(lines),
    }
    if not lines:
        return metrics
    lengths = [len(line) for line in lines]
    metrics.update(avg_line_length=sum(lengths) / len(lengths), max_line_length=max(lengths))
    if language == "python":
        return command._analyze_python(content, metrics)
    if language in {"javascript", "typescript"}:
        return command._analyze_js_ts(content, metrics)
    return command._analyze_generic(content, metrics, language)


def _python_structure(tree, metrics):
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            metrics["function_count"] += 1
            for child in ast.walk(node):
                if isinstance(child, (ast.If, ast.IfExp)):
                    metrics["condition_count"] += 1
                    metrics["cyclomatic_complexity"] += 1
                elif isinstance(child, (ast.For, ast.AsyncFor, ast.While)):
                    metrics["loop_count"] += 1
                    metrics["cyclomatic_complexity"] += 1
                elif isinstance(child, ast.BoolOp):
                    metrics["cyclomatic_complexity"] += len(child.values) - 1
        elif isinstance(node, ast.ClassDef):
            metrics["class_count"] += 1


def _finish_metrics(command, content, metrics, language):
    metrics["halstead_metrics"] = command._calculate_halstead_metrics(content, language)
    metrics["maintainability_index"] = command._calculate_maintainability_index(
        metrics["cyclomatic_complexity"],
        metrics["halstead_metrics"].get("volume", 0),
        metrics["line_count"],
    )
    return metrics


def analyze_python(command, content, metrics):
    try:
        _python_structure(ast.parse(content), metrics)
    except SyntaxError:
        return command._analyze_generic(content, metrics, "python")
    metrics["comment_count"] = len(re.findall(r"^\s*#.*$", content, re.MULTILINE))
    return _finish_metrics(command, content, metrics, "python")


def analyze_js_ts(command, content, metrics):
    patterns = [r"function\s+\w+\s*\(", r"const\s+\w+\s*=\s*function", r"const\s+\w+\s*=\s*\([^)]*\)\s*=>", r"\w+\s*:\s*function"]
    metrics["function_count"] = sum(len(re.findall(pattern, content)) for pattern in patterns)
    metrics["class_count"] = len(re.findall(r"class\s+\w+", content))
    for pattern in [r"\bif\s*\(", r"\bswitch\s*\(", r"\?"]:
        count = len(re.findall(pattern, content))
        metrics["condition_count"] += count
        metrics["cyclomatic_complexity"] += count
    for pattern in [r"\bfor\s*\(", r"\bwhile\s*\(", r"\bdo\s*\{"]:
        count = len(re.findall(pattern, content))
        metrics["loop_count"] += count
        metrics["cyclomatic_complexity"] += count
    metrics["cyclomatic_complexity"] += len(re.findall(r"&&|\|\|", content))
    metrics["comment_count"] = sum(len(re.findall(pattern, content, re.MULTILINE)) for pattern in [r"//.*$", r"/\*[\s\S]*?\*/"])
    return _finish_metrics(command, content, metrics, "javascript")


def analyze_generic(command, content, metrics, language):
    function_pattern = FUNCTION_PATTERNS.get(language, r"\b\w+\s+\w+\s*\(")
    class_pattern = CLASS_PATTERNS.get(language, r"class\s+\w+")
    metrics["function_count"] = len(re.findall(function_pattern, content, re.MULTILINE))
    metrics["class_count"] = len(re.findall(class_pattern, content, re.MULTILINE))
    conditions = len(re.findall(r"\bif\s*\(|\bswitch\s*\(|\?|else\s+if", content))
    loops = len(re.findall(r"\bfor\s*\(|\bwhile\s*\(|\bdo\s*\{|\bforeach", content))
    metrics.update(condition_count=conditions, loop_count=loops)
    metrics["cyclomatic_complexity"] += conditions + loops
    comment_pattern = r"#.*$" if language in {"python", "ruby"} else r"//.*$|/\*[\s\S]*?\*/"
    metrics["comment_count"] = len(re.findall(comment_pattern, content, re.MULTILINE))
    return _finish_metrics(command, content, metrics, language)


def _operand_counts(content, language):
    identifier_pattern = r"\b[a-zA-Z_]\w*\b"
    string_pattern = r'"[^"]*"|\'[^\']*\''
    number_pattern = r"\b\d+(\.\d+)?\b"
    identifiers = set(re.findall(identifier_pattern, content)) - set(KEYWORDS.get(language, KEYWORDS["javascript"]))
    strings = set(re.findall(string_pattern, content))
    numbers = set(re.findall(number_pattern, content))
    unique = len(identifiers) + len(strings) + len(numbers) or 1
    total = sum(len(re.findall(pattern, content)) for pattern in [identifier_pattern, string_pattern, number_pattern])
    return unique, total


def calculate_halstead_metrics(_command, content, language):
    operators = OPERATORS.get(language, OPERATORS["javascript"])
    pattern = "|".join(re.escape(operator) for operator in operators)
    unique_operators = len(set(re.findall(pattern, content))) or 1
    total_operators = len(re.findall(pattern, content))
    unique_operands, total_operands = _operand_counts(content, language)
    vocabulary = unique_operators + unique_operands
    length = total_operators + total_operands
    volume = length * math.log2(vocabulary) if vocabulary > 0 else 0
    difficulty = (unique_operators / 2) * (total_operands / unique_operands)
    return {
        "unique_operators": unique_operators,
        "unique_operands": unique_operands,
        "total_operators": total_operators,
        "total_operands": total_operands,
        "vocabulary": vocabulary,
        "length": length,
        "volume": volume,
        "difficulty": difficulty,
        "effort": difficulty * volume,
    }


def calculate_maintainability_index(_command, cyclomatic_complexity, halstead_volume, line_count):
    if halstead_volume <= 0 or line_count <= 0:
        return 100
    index = 171 - 5.2 * math.log(halstead_volume) - 0.23 * cyclomatic_complexity - 16.2 * math.log(line_count)
    return max(0, min(100, index * 100 / 171))


def calculate_complexity_score(_command, metrics):
    normalized = {
        "cyclomatic_complexity": min(10, metrics["cyclomatic_complexity"] / 5),
        "halstead_effort": min(10, metrics["halstead_metrics"].get("effort", 0) / 10000),
        "line_count": min(10, metrics["line_count"] / 300),
        "function_count": min(10, metrics["function_count"] / 20),
        "class_count": min(10, metrics["class_count"] / 10),
        "maintainability": 10 - metrics["maintainability_index"] / 10,
    }
    weights = {"cyclomatic_complexity": 0.3, "halstead_effort": 0.2, "line_count": 0.1, "function_count": 0.1, "class_count": 0.1, "maintainability": 0.2}
    return sum(normalized[key] * weight for key, weight in weights.items())
