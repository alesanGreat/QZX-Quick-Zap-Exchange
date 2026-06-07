#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
TraceEnvVar Command - Scans the project workspace for references to a specific environment variable,
validates its presence in .env/.env.example, and extracts default/fallback values in code.
"""

import os
import re
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from qzx.core.command_base import CommandBase
from qzx.core.recursive_findfiles_utils import find_files, parse_recursive_parameter

class TraceEnvVarCommand(CommandBase):
    """
    Command to trace environment variable usage across files, templates, and codebases.
    """
    
    name = "traceEnvVar"
    description = "Traces usage of an environment variable across code files, .env, and .env.example templates"
    category = "dev"
    
    parameters = [
        {
            'name': 'var_name',
            'description': 'Name of the environment variable to search for (e.g. DATABASE_URL, PORT)',
            'required': True
        },
        {
            'name': 'project_path',
            'description': 'Path to the project root directory (defaults to current directory)',
            'required': False,
            'default': '.'
        },
        {
            'name': 'recursive',
            'description': 'Whether to search directories recursively (defaults to True)',
            'required': False,
            'default': True
        }
    ]
    
    examples = [
        {
            'command': 'qzx traceEnvVar "PORT"',
            'description': 'Trace usage of the PORT environment variable in the current directory'
        },
        {
            'command': 'qzx traceEnvVar "STRIPE_API_KEY" "C:/my-project"',
            'description': 'Trace usage of STRIPE_API_KEY in C:/my-project'
        }
    ]
    
    # Supported code extensions to inspect
    SUPPORTED_EXTENSIONS = {
        '.py', '.js', '.jsx', '.ts', '.tsx', '.json', '.java', '.cs',
        '.php', '.rb', '.go', '.rs', '.sh', '.bat', '.yaml', '.yml'
    }
    
    def execute(self, var_name, project_path='.', recursive=True):
        """
        Executes the trace environment variable diagnostic
        
        Args:
            var_name (str): Name of environment variable
            project_path (str): Path to search
            recursive (bool/str): Recursive search setting
            
        Returns:
            Dictionary with trace diagnostic details
        """
        var_name = var_name.strip()
        if not var_name:
            return {
                "success": False,
                "error": "Environment variable name cannot be empty.",
                "message": "Environment variable name cannot be empty."
            }
            
        abs_project_path = os.path.abspath(project_path)
        if not os.path.exists(abs_project_path):
            return {
                "success": False,
                "error": f"Project path '{project_path}' does not exist.",
                "message": f"Project path '{project_path}' does not exist."
            }
            
        # Parse recursive parameter
        if isinstance(recursive, str):
            recursive = parse_recursive_parameter(recursive)
            
        # 1. Look for .env and templates
        env_files = {}
        possible_envs = ['.env', '.env.example', '.env.template', '.env.local', '.env.development']
        
        for env_name in possible_envs:
            path = os.path.join(abs_project_path, env_name)
            if os.path.isfile(path):
                env_files[env_name] = self._parse_env_file_for_var(path, var_name)
                
        # 2. Search in code files
        code_references = []
        
        # Regex to match variable name as a full word, potentially in quotes
        pattern = re.compile(r'\b' + re.escape(var_name) + r'\b')
        
        # Helper callback for recursive find
        def file_callback(file_path):
            try:
                # Skip massive files
                if os.path.getsize(file_path) > 1 * 1024 * 1024:
                    return True
                    
                with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
                    for line_num, line in enumerate(f, 1):
                        if pattern.search(line):
                            # Try to extract fallback/default value in code if any
                            fallback = self._detect_fallback_in_line(line, var_name)
                            rel_path = os.path.relpath(file_path, abs_project_path)
                            code_references.append({
                                "file": rel_path.replace(os.path.sep, '/'),
                                "line_number": line_num,
                                "line_content": line.strip(),
                                "fallback_detected": fallback
                            })
            except Exception:
                pass
            return True
            
        # Filter files by extension
        def file_filter(file_path):
            _, ext = os.path.splitext(file_path)
            return ext.lower() in self.SUPPORTED_EXTENSIONS
            
        if os.path.isdir(abs_project_path):
            for file_path in find_files(abs_project_path, recursive=recursive, file_type='f'):
                if file_filter(file_path):
                    file_callback(file_path)
        elif os.path.isfile(abs_project_path):
            file_callback(abs_project_path)
            
        # Formulate output message (Verbose is Gold)
        msg = f"Environment Variable Trace completed for '{var_name}':\n"
        msg += f"- Project directory: {abs_project_path}\n"
        
        # Env files summary
        msg += "\nEnv File Status:\n"
        for name, info in env_files.items():
            status = "DEFINED" if info["defined"] else "NOT DEFINED"
            val_str = f" (Value: {info['masked_value']})" if info["defined"] else ""
            msg += f"  - {name}: {status}{val_str}\n"
            
        # Code reference summary
        msg += f"\nCode Usages found: {len(code_references)}\n"
        for ref in code_references[:10]:
            fallback_str = f" [Fallback: {ref['fallback_detected']}]" if ref['fallback_detected'] else ""
            msg += f"  - {ref['file']}:{ref['line_number']}: '{ref['line_content']}'{fallback_str}\n"
        if len(code_references) > 10:
            msg += f"  ... and {len(code_references) - 10} more usage references.\n"
            
        return {
            "success": True,
            "var_name": var_name,
            "project_path": abs_project_path,
            "env_files_diagnostics": env_files,
            "references_count": len(code_references),
            "references": code_references,
            "message": msg
        }
        
    def _parse_env_file_for_var(self, filepath, var_name):
        """Parses an env file looking for a specific variable and returns definition status"""
        defined = False
        raw_val = None
        masked_val = None
        
        try:
            with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
                for line in f:
                    line = line.strip()
                    if line.startswith('#') or not line:
                        continue
                    # Match VAR_NAME=VALUE or export VAR_NAME=VALUE
                    match = re.match(r'^(?:export\s+)?([A-Za-z0-9_]+)\s*=\s*(.*)$', line)
                    if match:
                        k, v = match.groups()
                        if k == var_name:
                            defined = True
                            raw_val = v.strip()
                            # Clean quotes
                            if (raw_val.startswith('"') and raw_val.endswith('"')) or \
                               (raw_val.startswith("'") and raw_val.endswith("'")):
                                raw_val = raw_val[1:-1].strip()
                            # Mask values for security
                            if not raw_val:
                                masked_val = "<empty>"
                            elif len(raw_val) <= 3:
                                masked_val = "****"
                            else:
                                masked_val = f"{raw_val[:2]}...{raw_val[-2:]}"
                            break
        except Exception:
            pass
            
        return {
            "defined": defined,
            "value_found": raw_val is not None,
            "masked_value": masked_val
        }
        
    def _detect_fallback_in_line(self, line, var_name):
        """Attempts to find fallback values on the line (e.g. process.env.VAR || 'default')"""
        # Python: os.getenv('VAR', 'fallback') or os.environ.get('VAR', 'fallback')
        py_match = re.search(r'(?:getenv|environ\.get)\(\s*[\'"]' + re.escape(var_name) + r'[\'"]\s*,\s*([^\)]+)\)', line)
        if py_match:
            return py_match.group(1).strip()
            
        # JS/TS: process.env.VAR || 'fallback'
        js_match = re.search(re.escape(var_name) + r'\s*(?:\|\||\?\?)\s*([^\n;]+)', line)
        if js_match:
            return js_match.group(1).strip()
            
        # PHP: getenv('VAR') ?: 'fallback' or $_ENV['VAR'] ?? 'fallback' or $_SERVER['VAR'] ?? 'fallback'
        php_match = re.search(
            r'(?:getenv\(\s*[\'"]' + re.escape(var_name) + r'[\'"]\s*\)|(?:\$_ENV|\$_SERVER)\[\s*[\'"]' + re.escape(var_name) + r'[\'"]\s*\])\s*(?:\?\?:|\?:|\?\?)\s*([^\n;]+)',
            line
        )
        if php_match:
            return php_match.group(1).strip()
            
        return None
