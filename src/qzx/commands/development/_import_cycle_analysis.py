"""Import-graph construction and cycle reporting for ``traceCircularImports``."""

import ast
import os
import tokenize

from qzx.core.recursive_findfiles_utils import (
    SOURCE_ANALYSIS_EXCLUDED_DIRECTORIES,
    find_files,
)


def _python_files(scan_path):
    if os.path.isfile(scan_path):
        return [scan_path] if scan_path.lower().endswith(".py") else []
    if not os.path.isdir(scan_path):
        return []
    return [
        path
        for path in find_files(
            scan_path,
            recursive=True,
            exclude_dirs=SOURCE_ANALYSIS_EXCLUDED_DIRECTORIES,
            file_type="f",
        )
        if path.lower().endswith(".py")
    ]


def _module_index(paths, scan_path):
    module_to_file = {}
    file_to_modules = {}
    for file_path in paths:
        parts = os.path.relpath(file_path, scan_path).removesuffix(".py").split(os.path.sep)
        module_name = ".".join(parts)
        module_to_file[module_name] = file_path
        potential = {module_name}
        if len(parts) > 1 and parts[0] in ("src", "lib", "app"):
            source_name = ".".join(parts[1:])
            module_to_file[source_name] = file_path
            potential.add(source_name)
        file_to_modules[file_path] = potential
    return module_to_file, file_to_modules


def _resolve_import(import_name, module_to_file):
    if import_name in module_to_file:
        return module_to_file[import_name]
    initializer = import_name + ".__init__"
    if initializer in module_to_file:
        return module_to_file[initializer]
    for candidate, path in module_to_file.items():
        if import_name.startswith(candidate + "."):
            return path
    return None


def _source_parse_error(file_path, scan_path, exc):
    error = {
        "file": os.path.relpath(file_path, scan_path).replace(os.path.sep, "/"),
        "error_type": type(exc).__name__,
        "message": str(exc),
    }
    if isinstance(exc, SyntaxError):
        error["line_number"] = exc.lineno
        error["column"] = exc.offset
    return error


def _import_graph(command, paths, module_to_file, scan_path):
    graph = {}
    parse_errors = []
    for file_path in paths:
        try:
            imports = command._parse_file_imports(file_path)
        except (OSError, SyntaxError, UnicodeError, ValueError) as exc:
            graph[file_path] = []
            parse_errors.append(_source_parse_error(file_path, scan_path, exc))
            continue
        resolved = {
            match
            for imported in imports
            if (match := _resolve_import(imported, module_to_file)) is not None
        }
        resolved.discard(file_path)
        graph[file_path] = list(resolved)
    return graph, parse_errors


def _format_message(paths, cycles, file_to_modules, parse_errors):
    message = (
        "Circular Import Dependency Diagnostics:\n"
        f"- Total Python files scanned: {len(paths)}\n"
        f"- Python files not parsed: {len(parse_errors)}\n"
        f"- Detected circular import loops: {len(cycles)}\n"
    )
    if not cycles and not parse_errors:
        return message + "\n[OK] No circular import dependencies detected in the scanned files.\n"
    if parse_errors:
        message += (
            "\n[INCOMPLETE] Some Python files could not be parsed; "
            "the no-cycle conclusion is unavailable.\n"
        )
        for error in parse_errors[:10]:
            message += (
                f"  - {error['file']}: {error['error_type']}: "
                f"{error['message']}\n"
            )
    if cycles:
        message += "\n[WARNING] Circular import loops identified:\n"
        for index, cycle in enumerate(cycles, 1):
            modules = [
                next(iter(file_to_modules.get(path, {os.path.basename(path)})))
                for path in cycle
            ]
            message += f"  Loop #{index}:\n    " + " -> ".join(modules) + "\n"
    return message


def execute_import_cycle_trace(command, scan_path="."):
    """Analyze a Python tree and return its serializable import cycles."""
    absolute = os.path.abspath(scan_path)
    if not os.path.exists(absolute):
        message = f"Path '{scan_path}' does not exist."
        return {"success": False, "error": message, "message": message}
    paths = _python_files(absolute)
    if not paths:
        return {"success": True, "cycles_count": 0, "cycles": [], "message": "No Python files found to analyze."}
    module_to_file, file_to_modules = _module_index(paths, absolute)
    graph, parse_errors = _import_graph(command, paths, module_to_file, absolute)
    cycles = command._find_cycles(graph)
    serialized = [
        [os.path.relpath(path, absolute).replace(os.path.sep, "/") for path in cycle]
        for cycle in cycles
    ]
    result = {
        "success": not parse_errors,
        "scan_path": absolute,
        "analysis_complete": not parse_errors,
        "files_scanned": len(paths),
        "files_parsed": len(paths) - len(parse_errors),
        "cycles_count": len(cycles),
        "cycles": serialized,
        "message": _format_message(paths, cycles, file_to_modules, parse_errors),
    }
    if parse_errors:
        result.update(
            {
                "error": "Circular import analysis was incomplete.",
                "error_code": "source_parse_failed",
                "parse_errors": parse_errors,
            }
        )
    return result


def parse_file_imports(_command, file_path):
    """Extract import targets from one Python file or expose parse failures."""
    imports = []
    with tokenize.open(file_path) as handle:
        tree = ast.parse(handle.read(), filename=file_path)
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.extend(name.name for name in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.append(node.module)
    return imports


def find_cycles(_command, graph):
    """Find unique simple cycles in a directed graph using DFS."""
    cycles, visited, path, seen = [], {}, [], set()

    def visit(node):
        visited[node] = 1
        path.append(node)
        for neighbor in graph.get(node, []):
            if visited.get(neighbor, 0) == 1:
                cycle = path[path.index(neighbor):]
                signature = tuple(sorted(cycle))
                if signature not in seen:
                    seen.add(signature)
                    cycles.append(cycle + [neighbor])
            elif visited.get(neighbor, 0) == 0:
                visit(neighbor)
        path.pop()
        visited[node] = 2

    for node in graph:
        if visited.get(node, 0) == 0:
            visit(node)
    return cycles
