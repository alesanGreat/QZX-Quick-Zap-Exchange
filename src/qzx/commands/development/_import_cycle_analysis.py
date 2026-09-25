"""Import-graph construction and cycle reporting for ``traceCircularImports``."""

import ast
import os

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


def _import_graph(command, paths, module_to_file):
    graph = {}
    for file_path in paths:
        resolved = {
            match
            for imported in command._parse_file_imports(file_path)
            if (match := _resolve_import(imported, module_to_file)) is not None
        }
        resolved.discard(file_path)
        graph[file_path] = list(resolved)
    return graph


def _format_message(paths, cycles, file_to_modules):
    message = (
        "Circular Import Dependency Diagnostics:\n"
        f"- Total Python files scanned: {len(paths)}\n"
        f"- Detected circular import loops: {len(cycles)}\n"
    )
    if not cycles:
        return message + "\n[OK] No circular import dependencies detected in the scanned files.\n"
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
    cycles = command._find_cycles(_import_graph(command, paths, module_to_file))
    serialized = [
        [os.path.relpath(path, absolute).replace(os.path.sep, "/") for path in cycle]
        for cycle in cycles
    ]
    return {
        "success": True,
        "scan_path": absolute,
        "cycles_count": len(cycles),
        "cycles": serialized,
        "message": _format_message(paths, cycles, file_to_modules),
    }


def parse_file_imports(_command, file_path):
    """Extract import targets from one Python file."""
    imports = []
    try:
        with open(file_path, "r", encoding="utf-8", errors="replace") as handle:
            tree = ast.parse(handle.read(), filename=file_path)
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.extend(name.name for name in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imports.append(node.module)
    except Exception:
        pass
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
