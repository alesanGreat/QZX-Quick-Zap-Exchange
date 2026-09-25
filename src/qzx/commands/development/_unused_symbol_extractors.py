"""Language-specific static symbol extraction for ``findUnusedCode``."""

import ast
import os
import re


def _append(symbols, name, kind, file_path, relative, line):
    symbols.append({"name": name, "type": kind, "file_abs": file_path, "file_rel": relative, "line_number": line})


def extract_python_symbols(_command, content, file_path, relative, symbols):
    try:
        tree = ast.parse(content, filename=file_path)
        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if not node.name.startswith(("_", "test_")):
                    _append(symbols, node.name, "function", file_path, relative, node.lineno)
            elif isinstance(node, ast.ClassDef) and not node.name.startswith("_"):
                bases = {base.id if isinstance(base, ast.Name) else base.attr if isinstance(base, ast.Attribute) else "" for base in node.bases}
                is_test = node.name.startswith("Test") and (relative.startswith("tests/") or os.path.basename(relative).startswith("test_"))
                if "CommandBase" not in bases and not is_test:
                    _append(symbols, node.name, "class", file_path, relative, node.lineno)
    except Exception:
        pass


def extract_js_ts_symbols(_command, content, file_path, relative, symbols):
    patterns = (
        re.compile(r"^\s*export\s+(?:default\s+)?(?:const|let|var|function|class|interface|type|async\s+function)\s+([A-Za-z0-9_]+)"),
        re.compile(r"^\s*export\s+default\s+(?:class|function)\s+([A-Za-z0-9_]+)"),
    )
    for line_number, line in enumerate(content.splitlines(), 1):
        match = next((pattern.search(line) for pattern in patterns if pattern.search(line)), None)
        if not match or match.group(1).startswith("_"):
            continue
        kind = "class" if "class" in line else "function" if "function" in line else "interface" if "interface" in line or "type" in line else "export"
        _append(symbols, match.group(1), kind, file_path, relative, line_number)


def extract_php_symbols(_command, content, file_path, relative, symbols):
    type_pattern = re.compile(r"^\s*(?:abstract\s+|final\s+)?(?:class|interface|trait)\s+([A-Za-z0-9_]+)", re.I)
    function_pattern = re.compile(r"^\s*(?:public\s+|protected\s+|private\s+|static\s+|final\s+)*function\s+([A-Za-z0-9_]+)", re.I)
    for line_number, line in enumerate(content.splitlines(), 1):
        match = type_pattern.search(line)
        if match and not match.group(1).startswith("_"):
            kind = "interface" if "interface" in line.lower() else "trait" if "trait" in line.lower() else "class"
            _append(symbols, match.group(1), kind, file_path, relative, line_number)
            continue
        match = function_pattern.search(line)
        if match and not match.group(1).startswith("__") and not match.group(1).lower().startswith("test"):
            _append(symbols, match.group(1), "function", file_path, relative, line_number)


def extract_rust_symbols(_command, content, file_path, relative, symbols):
    pattern = re.compile(r"^\s*(?:pub(?:\([^)]*\))?\s+)?(fn|struct|enum|trait|type|union)\s+([A-Za-z0-9_]+)")
    kinds = {"fn": "function", "struct": "struct", "enum": "enum", "trait": "trait", "type": "type", "union": "union"}
    for line_number, line in enumerate(content.splitlines(), 1):
        match = pattern.search(line)
        if match and not match.group(2).startswith(("_", "test_")):
            _append(symbols, match.group(2), kinds[match.group(1)], file_path, relative, line_number)


def extract_go_symbols(_command, content, file_path, relative, symbols):
    function = re.compile(r"^\s*func\s+(?:\([^)]*\)\s*)?([A-Za-z_][A-Za-z0-9_]*)\s*\(")
    type_pattern = re.compile(r"^\s*type\s+([A-Za-z_][A-Za-z0-9_]*)\s+(struct|interface|func)")
    for line_number, line in enumerate(content.splitlines(), 1):
        match = function.search(line)
        if match and match.group(1) not in {"main", "init"} and not match.group(1).startswith("_"):
            _append(symbols, match.group(1), "function", file_path, relative, line_number)
            continue
        match = type_pattern.search(line)
        if match and not match.group(1).startswith("_"):
            kind = "interface" if match.group(2) == "interface" else "type" if match.group(2) == "func" else "struct"
            _append(symbols, match.group(1), kind, file_path, relative, line_number)


def _extract_jvm_like(content, file_path, relative, symbols, type_pattern, method_pattern, excluded):
    for line_number, line in enumerate(content.splitlines(), 1):
        match = type_pattern.search(line)
        if match and not match.group(1).startswith("_"):
            lowered = line.lower()
            kind = next((name for name in ("interface", "enum", "record", "struct", "object") if name in lowered), "class")
            _append(symbols, match.group(1), kind, file_path, relative, line_number)
            continue
        match = method_pattern.search(line)
        if match:
            name = match.group(1)
            if name not in excluded and not name.startswith("_") and not name.lower().startswith("test"):
                _append(symbols, name, "method", file_path, relative, line_number)


def extract_java_symbols(_command, content, file_path, relative, symbols):
    types = re.compile(r"^\s*(?:public\s+|private\s+|protected\s+|abstract\s+|final\s+)?(?:class|interface|enum|record)\s+([A-Za-z_][A-Za-z0-9_]*)")
    methods = re.compile(r"^\s*(?:public\s+|private\s+|protected\s+|static\s+|final\s+|abstract\s+)*(?:[A-Za-z_][A-Za-z0-9_<>\[\],\s]*\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*\(")
    _extract_jvm_like(content, file_path, relative, symbols, types, methods, {"if", "while", "for", "switch", "catch", "synchronized", "try", "main"})


def extract_kotlin_symbols(_command, content, file_path, relative, symbols):
    types = re.compile(r"^\s*(?:abstract\s+|sealed\s+|data\s+|open\s+|inner\s+)?(?:class|interface|object|enum\s+class|data\s+class)\s+([A-Za-z_][A-Za-z0-9_]*)")
    functions = re.compile(r"^\s*(?:private\s+|protected\s+|internal\s+|public\s+)?(?:inline\s+|tailrec\s+|suspend\s+)?fun\s+(?:<[^>]+>\s*)?([A-Za-z_][A-Za-z0-9_]*)\s*\(")
    for line_number, line in enumerate(content.splitlines(), 1):
        match = types.search(line)
        if match and not match.group(1).startswith("_"):
            kind = "interface" if "interface" in line else "object" if "object" in line else "enum" if "enum" in line else "class"
            _append(symbols, match.group(1), kind, file_path, relative, line_number)
            continue
        match = functions.search(line)
        if match and not match.group(1).startswith("_") and not match.group(1).lower().startswith("test"):
            _append(symbols, match.group(1), "function", file_path, relative, line_number)


def extract_csharp_symbols(_command, content, file_path, relative, symbols):
    types = re.compile(r"^\s*(?:public\s+|private\s+|protected\s+|internal\s+|abstract\s+|sealed\s+|static\s+|partial\s+)*(?:class|interface|enum|struct|record)\s+([A-Za-z_][A-Za-z0-9_]*)")
    methods = re.compile(r"^\s*(?:public\s+|private\s+|protected\s+|internal\s+|static\s+|abstract\s+|sealed\s+|override\s+|virtual\s+|async\s+)*(?:[A-Za-z_][A-Za-z0-9_<>\[\],\s]*\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*\(")
    excluded = {"if", "while", "for", "foreach", "switch", "catch", "using", "lock", "Main"}
    _extract_jvm_like(content, file_path, relative, symbols, types, methods, excluded)


def extract_cpp_symbols(_command, content, file_path, relative, symbols):
    types = re.compile(r"^\s*(class|struct|union)\s+([A-Za-z0-9_]+)\b")
    functions = re.compile(r"^\s*(?:inline\s+|static\s+|virtual\s+)?(?:[A-Za-z0-9_:<>]+(?:\s*\*|\s*&)?\s+)+([A-Za-z0-9_]+)\s*\([^)]*\)\s*(?:const)?\s*[{;]")
    for line_number, line in enumerate(content.splitlines(), 1):
        match = types.search(line)
        if match and not match.group(2).startswith("_"):
            _append(symbols, match.group(2), match.group(1) if match.group(1) != "union" else "union", file_path, relative, line_number)
            continue
        match = functions.search(line)
        if match and match.group(1) not in {"if", "while", "for", "switch", "catch", "main", "return"} and not match.group(1).startswith("_"):
            _append(symbols, match.group(1), "function", file_path, relative, line_number)
