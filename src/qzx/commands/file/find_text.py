#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
FindText Command - Advanced text search in files
Using the centralized recursive file finder utility
"""

from qzx.commands.file._text_search_engine import execute_text_search
from qzx.commands.file._text_search_file import safe_string, search_text_file
from qzx.core.command_base import CommandBase
from qzx.core.recursive_findfiles_utils import parse_recursive_parameter


class FindTextCommand(CommandBase):
    """
    Command to search for text patterns in files with advanced options
    
    Supports flags:
    -r, -R, --recursive: Enable unlimited recursive directory search
    -rN, --recursiveN: Enable recursive directory search up to N levels deep
    
    This version uses the centralized recursive file finder utility.
    """
    
    name = "findText"
    description = "Searches for text patterns in files with advanced filtering options"
    category = "file"
    
    parameters = [
        {
            'name': 'pattern',
            'description': 'Text pattern to search for (supports regular expressions)',
            'required': True
        },
        {
            'name': 'target',
            'description': 'File or directory (or space-separated list of files/directories) to search in',
            'required': True
        },
        {
            'name': 'recursive',
            'description': 'Recursion level: -r/--recursive for unlimited depth, -rN/--recursiveN for N levels deep',
            'required': False,
            'default': None
        },
        {
            'name': 'regex',
            'description': 'Use regular expressions for pattern matching (true/false)',
            'required': False,
            'default': False
        },
        {
            'name': 'case_sensitive',
            'description': 'Perform case-sensitive search (true/false)',
            'required': False,
            'default': True
        },
        {
            'name': 'file_pattern',
            'description': 'Only search in files matching this pattern (e.g., "*.py" or "*.{py,js}")',
            'required': False,
            'default': "*"
        },
        {
            'name': 'context_lines',
            'description': 'Number of lines to show before and after each match',
            'required': False,
            'default': 0
        },
        {
            'name': 'invert_match',
            'description': 'Show lines that do NOT match the pattern (true/false)',
            'required': False,
            'default': False
        },
        {
            'name': 'count_only',
            'description': 'Only show count of matches per file (true/false)',
            'required': False,
            'default': False
        },
        {
            'name': 'max_matches',
            'description': 'Maximum number of matches to display (0 for unlimited)',
            'required': False,
            'default': 0
        },
        {
            'name': 'colored',
            'description': 'Highlight matches with color (true/false)',
            'required': False,
            'default': True
        }
    ]
    
    examples = [
        {
            'command': 'qzx findText "function" "script.js"',
            'description': 'Find all occurrences of "function" in a JavaScript file'
        },
        {
            'command': 'qzx findText "error" "logs" true',
            'description': 'Find all occurrences of "error" in all files under logs directory'
        },
        {
            'command': 'qzx findText "def\\s+\\w+" "src" true true',
            'description': 'Find all function definitions in Python files using regex'
        },
        {
            'command': 'qzx findText "WARNING|ERROR" "logs" true true false "*.log"',
            'description': 'Find warnings or errors in log files'
        },
        {
            'command': 'qzx findText "TODO" "src" true false true "*.{py,js,ts}" 2',
            'description': 'Find TODOs in source files with 2 lines of context'
        },
        {
            'command': 'qzx findText "function" "file1.js file2.js lib/utils.js"',
            'description': 'Find all occurrences of "function" in multiple specific files'
        }
    ]

    _parse_recursive_parameter = staticmethod(parse_recursive_parameter)
    
    def execute(self, pattern, target, recursive=None, regex=False, case_sensitive=True,
                file_pattern="*", context_lines=0, invert_match=False, count_only=False,
                max_matches=0, colored=True):
        """Search text while preserving the public findText contract."""
        return execute_text_search(
            pattern,
            target,
            recursive,
            regex,
            case_sensitive,
            file_pattern,
            context_lines,
            invert_match,
            count_only,
            max_matches,
            colored,
        )

    def _search_file(self, file_path, pattern, regex, case_sensitive, context_lines,
                     invert_match, count_only, colored):
        """Compatibility wrapper for single-file search tests and callers."""
        return search_text_file(
            file_path,
            pattern,
            regex,
            case_sensitive,
            context_lines,
            invert_match,
            count_only,
            colored,
        )

    def _ensure_safe_string(self, text):
        """Compatibility wrapper for safe terminal rendering."""
        return safe_string(text)
