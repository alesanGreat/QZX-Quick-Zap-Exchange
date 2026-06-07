#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
FindDeadCode Command - Scans the workspace files for exported or defined functions/classes,
builds a token map of references, and flags symbols that have no external references.
"""

import os
import re
import ast
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from qzx.core.command_base import CommandBase
from qzx.core.recursive_findfiles_utils import find_files

class FindDeadCodeCommand(CommandBase):
    """
    Command to identify dead code (unused classes, functions, or exports) in a codebase.
    """
    
    name = "findDeadCode"
    description = "Scans files for declared functions and classes, and identifies those with zero references in other files"
    category = "dev"
    
    parameters = [
        {
            'name': 'scan_path',
            'description': 'Path to scan for files (defaults to current directory)',
            'required': False,
            'default': '.'
        }
    ]
    
    examples = [
        {
            'command': 'qzx findDeadCode',
            'description': 'Scan the current directory for dead code'
        },
        {
            'command': 'qzx findDeadCode "src/"',
            'description': 'Scan the src/ directory'
        }
    ]
    
    SUPPORTED_EXTENSIONS = {'.py', '.js', '.jsx', '.ts', '.tsx'}
    
    def execute(self, scan_path='.'):
        """
        Executes dead code detection
        
        Args:
            scan_path (str): Path to scan
            
        Returns:
            Dictionary with dead code analysis details
        """
        abs_scan_path = os.path.abspath(scan_path)
        if not os.path.exists(abs_scan_path):
            return {
                "success": False,
                "error": f"Path '{scan_path}' does not exist.",
                "message": f"Path '{scan_path}' does not exist."
            }
            
        # 1. Discover all source files
        files = []
        def file_callback(file_path):
            files.append(file_path)
            return True
            
        def file_filter(file_path):
            _, ext = os.path.splitext(file_path)
            return ext.lower() in self.SUPPORTED_EXTENSIONS
            
        if os.path.isdir(abs_scan_path):
            for file_path in find_files(abs_scan_path, recursive=True, file_type='f'):
                if file_filter(file_path):
                    file_callback(file_path)
        elif os.path.isfile(abs_scan_path) and file_filter(abs_scan_path):
            files.append(abs_scan_path)
            
        if not files:
            return {
                "success": True,
                "dead_symbols_count": 0,
                "dead_symbols": [],
                "message": "No supported source files found to analyze."
            }
            
        # 2. Build token sets for each file (set of all alphanumeric words)
        token_sets = {}
        file_contents = {}
        
        word_pattern = re.compile(r'\b[A-Za-z0-9_]+\b')
        
        for file_path in files:
            try:
                # Skip massive files
                if os.path.getsize(file_path) > 1 * 1024 * 1024:
                    continue
                with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
                    content = f.read()
                    file_contents[file_path] = content
                    # Tokenize
                    token_sets[file_path] = set(word_pattern.findall(content))
            except Exception:
                pass
                
        # 3. Extract defined symbols (Function/Class names) from each file
        symbols = []
        for file_path in files:
            if file_path not in file_contents:
                continue
                
            _, ext = os.path.splitext(file_path)
            content = file_contents[file_path]
            rel_path = os.path.relpath(file_path, abs_scan_path).replace(os.path.sep, '/')
            
            if ext.lower() == '.py':
                self._extract_python_symbols(content, file_path, rel_path, symbols)
            elif ext.lower() in ('.js', '.jsx', '.ts', '.tsx'):
                self._extract_js_ts_symbols(content, file_path, rel_path, symbols)
                
        # 4. Check references for each symbol
        dead_symbols = []
        for sym in symbols:
            name = sym["name"]
            def_file = sym["file_abs"]
            
            referenced = False
            # Check if this symbol's name appears in any other file's token set
            for file_path, token_set in token_sets.items():
                if file_path == def_file:
                    continue
                if name in token_set:
                    referenced = True
                    break
                    
            if not referenced:
                dead_symbols.append({
                    "name": name,
                    "type": sym["type"],
                    "file": sym["file_rel"],
                    "line_number": sym["line_number"]
                })
                
        # 5. Format message (Verbose is Gold)
        msg = "Dead Code Diagnostic Report:\n"
        msg += f"- Total files scanned: {len(files)}\n"
        msg += f"- Total symbols analyzed: {len(symbols)}\n"
        msg += f"- Total dead/unused symbols identified: {len(dead_symbols)}\n"
        
        if dead_symbols:
            msg += "\n⚠️  Unused definitions identified (Zero references outside definition file):\n"
            for index, sym in enumerate(dead_symbols[:15], 1):
                msg += f"  {index}. [{sym['type'].upper()}] '{sym['name']}' at {sym['file']}:{sym['line_number']}\n"
            if len(dead_symbols) > 15:
                msg += f"  ... and {len(dead_symbols) - 15} more unused symbols.\n"
        else:
            msg += "\n✅ No dead code or unused exported symbols detected.\n"
            
        return {
            "success": True,
            "scan_path": abs_scan_path,
            "analyzed_symbols_count": len(symbols),
            "dead_symbols_count": len(dead_symbols),
            "dead_symbols": dead_symbols,
            "message": msg
        }
        
    def _extract_python_symbols(self, content, file_path, rel_path, symbols):
        """Extracts module-level function and class definitions from Python AST"""
        try:
            tree = ast.parse(content, filename=file_path)
            for node in tree.body:
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    name = node.name
                    # Skip private/internal methods and tests
                    if name.startswith('_') or name.startswith('test_'):
                        continue
                    symbols.append({
                        "name": name,
                        "type": "function",
                        "file_abs": file_path,
                        "file_rel": rel_path,
                        "line_number": node.lineno
                    })
                elif isinstance(node, ast.ClassDef):
                    name = node.name
                    if name.startswith('_'):
                        continue
                    symbols.append({
                        "name": name,
                        "type": "class",
                        "file_abs": file_path,
                        "file_rel": rel_path,
                        "line_number": node.lineno
                    })
        except Exception:
            pass
            
    def _extract_js_ts_symbols(self, content, file_path, rel_path, symbols):
        """Extracts exported functions, classes, interfaces, or variables from JS/TS using regex"""
        # Match 'export function name', 'export class name', etc.
        pattern = re.compile(
            r'^\s*export\s+(?:default\s+)?(?:const|let|var|function|class|interface|type|async\s+function)\s+([A-Za-z0-9_]+)',
            re.MULTILINE
        )
        
        # Match 'export default class name', 'export default function name'
        default_pattern = re.compile(
            r'^\s*export\s+default\s+(?:class|function)\s+([A-Za-z0-9_]+)',
            re.MULTILINE
        )
        
        lines = content.splitlines()
        for idx, line in enumerate(lines, 1):
            match = pattern.search(line)
            if not match:
                match = default_pattern.search(line)
                
            if match:
                name = match.group(1).strip()
                if name.startswith('_'):
                    continue
                # Determine type
                sym_type = "export"
                if "class" in line:
                    sym_type = "class"
                elif "function" in line:
                    sym_type = "function"
                elif "interface" in line or "type" in line:
                    sym_type = "interface"
                    
                symbols.append({
                    "name": name,
                    "type": sym_type,
                    "file_abs": file_path,
                    "file_rel": rel_path,
                    "line_number": idx
                })
