#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
TraceCircularImports Command - Analyzes Python source files in a workspace,
constructs an import dependency graph, and detects circular import loops.
"""

import os
import ast
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from qzx.core.command_base import CommandBase
from qzx.core.recursive_findfiles_utils import find_files

class TraceCircularImportsCommand(CommandBase):
    """
    Command to detect circular import dependencies in Python projects.
    """
    
    name = "traceCircularImports"
    description = "Traces module imports recursively and identifies circular import dependencies (loops)"
    category = "dev"
    
    parameters = [
        {
            'name': 'scan_path',
            'description': 'Path to scan for Python files (defaults to current directory)',
            'required': False,
            'default': '.'
        }
    ]
    
    examples = [
        {
            'command': 'qzx traceCircularImports',
            'description': 'Search for circular imports in the current directory'
        },
        {
            'command': 'qzx traceCircularImports "src/qzx"',
            'description': 'Search for circular imports specifically inside src/qzx'
        }
    ]
    
    def execute(self, scan_path='.'):
        """
        Executes circular imports detection
        
        Args:
            scan_path (str): Path to scan
            
        Returns:
            Dictionary with circular import analysis details
        """
        abs_scan_path = os.path.abspath(scan_path)
        if not os.path.exists(abs_scan_path):
            return {
                "success": False,
                "error": f"Path '{scan_path}' does not exist.",
                "message": f"Path '{scan_path}' does not exist."
            }
            
        # 1. Discover all Python files
        py_files = []
        def file_callback(file_path):
            py_files.append(file_path)
            return True
            
        def file_filter(file_path):
            return file_path.lower().endswith('.py')
            
        if os.path.isdir(abs_scan_path):
            for file_path in find_files(abs_scan_path, recursive=True, file_type='f'):
                if file_filter(file_path):
                    file_callback(file_path)
        elif os.path.isfile(abs_scan_path) and file_filter(abs_scan_path):
            py_files.append(abs_scan_path)
            
        if not py_files:
            return {
                "success": True,
                "cycles_count": 0,
                "cycles": [],
                "message": "No Python files found to analyze."
            }
            
        # 2. Build mapping from module names to file paths
        module_to_file = {}
        file_to_modules = {} # Track multiple potential module names for each file
        
        for file_path in py_files:
            rel = os.path.relpath(file_path, abs_scan_path)
            # Standardize module paths
            parts = rel.replace('.py', '').split(os.path.sep)
            
            # Module name directly relative to scan path
            mod_name = ".".join(parts)
            module_to_file[mod_name] = file_path
            
            potential_mods = {mod_name}
            
            # Handle standard source layouts (e.g. src/qzx/core/command_base.py -> qzx.core.command_base)
            if len(parts) > 1 and parts[0] in ('src', 'lib', 'app'):
                sub_mod = ".".join(parts[1:])
                module_to_file[sub_mod] = file_path
                potential_mods.add(sub_mod)
                
            file_to_modules[file_path] = potential_mods
            
        # 3. Parse imports for each file
        graph = {}
        for file_path in py_files:
            imports = self._parse_file_imports(file_path)
            
            # Resolve imports to our project files
            resolved = set()
            for imp in imports:
                # Direct match
                if imp in module_to_file:
                    resolved.add(module_to_file[imp])
                    continue
                # Submodule match (e.g. importing 'qzx.core' matches file 'qzx/core/__init__.py')
                init_mod = imp + ".__init__"
                if init_mod in module_to_file:
                    resolved.add(module_to_file[init_mod])
                    continue
                # Check prefix match (e.g. import 'qzx.core.command_base.CommandBase' -> matches 'qzx.core.command_base')
                for mod_candidate, path in module_to_file.items():
                    if imp.startswith(mod_candidate + "."):
                        resolved.add(path)
                        break
                        
            # Exclude self-imports
            resolved.discard(file_path)
            graph[file_path] = list(resolved)
            
        # 4. Find cycles using DFS
        cycles = self._find_cycles(graph)
        
        # 5. Format results
        msg = "Circular Import Dependency Diagnostics:\n"
        msg += f"- Total Python files scanned: {len(py_files)}\n"
        msg += f"- Detected circular import loops: {len(cycles)}\n"
        
        if cycles:
            msg += "\n[WARNING] Circular import loops identified:\n"
            for index, cycle in enumerate(cycles, 1):
                msg += f"  Loop #{index}:\n"
                cycle_str_list = []
                for file_path in cycle:
                    # Show one canonical module name for brevity
                    mod_rep = list(file_to_modules.get(file_path, {os.path.basename(file_path)}))[0]
                    cycle_str_list.append(mod_rep)
                msg += "    " + " -> ".join(cycle_str_list) + "\n"
        else:
            msg += "\n[OK] No circular import dependencies detected in the scanned files.\n"
            
        # Convert file paths in cycles to relative module paths for serialization
        serializable_cycles = []
        for cycle in cycles:
            serializable_cycle = []
            for file_path in cycle:
                rel_path = os.path.relpath(file_path, abs_scan_path).replace(os.path.sep, '/')
                serializable_cycle.append(rel_path)
            serializable_cycles.append(serializable_cycle)
            
        return {
            "success": True,
            "scan_path": abs_scan_path,
            "cycles_count": len(cycles),
            "cycles": serializable_cycles,
            "message": msg
        }
        
    def _parse_file_imports(self, file_path):
        """Extracts import statement targets from a Python file using AST"""
        imports = []
        try:
            with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
                tree = ast.parse(f.read(), filename=file_path)
                for node in ast.walk(tree):
                    if isinstance(node, ast.Import):
                        for name in node.names:
                            imports.append(name.name)
                    elif isinstance(node, ast.ImportFrom):
                        # Handle relative imports conversion if module exists
                        if node.module:
                            imports.append(node.module)
        except Exception:
            pass
        return imports
        
    def _find_cycles(self, graph):
        """Finds all unique simple cycles in a directed graph using DFS"""
        cycles = []
        visited = {} # 0: unvisited, 1: visiting, 2: visited
        path = []
        
        # Keep track of cycle signatures to avoid duplicates
        seen_cycles = set()
        
        def dfs(node):
            visited[node] = 1
            path.append(node)
            
            for neighbor in graph.get(node, []):
                if visited.get(neighbor, 0) == 1:
                    # Cycle found! Extract the loop path
                    start_idx = path.index(neighbor)
                    cycle = path[start_idx:]
                    
                    # Normalize cycle presentation (always start with the smallest string to identify duplicates)
                    cycle_rep = tuple(sorted(cycle))
                    if cycle_rep not in seen_cycles:
                        seen_cycles.add(cycle_rep)
                        # Append neighbor to close the loop in display representation
                        cycles.append(cycle + [neighbor])
                elif visited.get(neighbor, 0) == 0:
                    dfs(neighbor)
                    
            path.pop()
            visited[node] = 2
            
        for node in graph:
            if visited.get(node, 0) == 0:
                dfs(node)
                
        return cycles
