#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
FindText Command - Advanced text search in files
Using the centralized recursive file finder utility
"""

import os
import re
import fnmatch
import colorama
import sys
from pathlib import Path
from typing import List, Dict, Any, Union, Optional
from Core.command_base import CommandBase
from Core.recursive_findfiles_utils import find_files, parse_recursive_parameter

# Initialize colorama for cross-platform colored terminal output
colorama.init(autoreset=True)

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
    
    def execute(self, pattern, target, recursive=None, regex=False, case_sensitive=True, 
                file_pattern="*", context_lines=0, invert_match=False, count_only=False, 
                max_matches=0, colored=True):
        """
        Searches for text patterns in files with advanced options
        
        Args:
            pattern (str): Text pattern to search for
            target (str): File or directory to search in (space-separated for multiple)
            recursive: Recursion level: none by default, -r/--recursive for unlimited, -rN/--recursiveN for N levels
            regex (bool): Whether to use regular expressions for pattern matching
            case_sensitive (bool): Whether the search should be case-sensitive
            file_pattern (str): Only search in files matching this pattern (e.g., "*.py")
            context_lines (int): Number of lines to show before and after each match
            invert_match (bool): Show lines that do NOT match the pattern
            count_only (bool): Only show count of matches per file
            max_matches (int): Maximum number of matches to display (0 for unlimited)
            colored (bool): Whether to colorize the output
            
        Returns:
            Dictionary with search results
        """
        try:
            # Process flags in command arguments if they exist
            import sys
            args = sys.argv
            recursive_flags = ['-r', '-R', '--recursive']
            recursive_found = any(flag in args for flag in recursive_flags)
            
            # Parse recursive parameter - convert string flags or handle boolean
            if isinstance(recursive, str):
                recursive = parse_recursive_parameter(recursive)
            elif recursive_found:
                recursive = True
            
            # Convert other parameters to proper types
            if isinstance(regex, str):
                regex = regex.lower() in ('true', 'yes', 'y', '1')
            
            if isinstance(case_sensitive, str):
                case_sensitive = case_sensitive.lower() in ('true', 'yes', 'y', '1')
            
            if isinstance(context_lines, str):
                try:
                    context_lines = int(context_lines)
                except ValueError:
                    return {"success": False, "error": f"Invalid context_lines value: {context_lines}. Must be a number."}
            
            if isinstance(invert_match, str):
                invert_match = invert_match.lower() in ('true', 'yes', 'y', '1')
            
            if isinstance(count_only, str):
                count_only = count_only.lower() in ('true', 'yes', 'y', '1')
            
            if isinstance(max_matches, str):
                try:
                    max_matches = int(max_matches)
                except ValueError:
                    return {"success": False, "error": f"Invalid max_matches value: {max_matches}. Must be a number."}
            
            if isinstance(colored, str):
                colored = colored.lower() in ('true', 'yes', 'y', '1')
                
            # Disable colored output on Windows if there are encoding issues
            if colored and sys.platform == 'win32' and sys.stdout.encoding != 'utf-8':
                try:
                    # Try a simple colored output
                    test_colored_string = f"{colorama.Fore.RED}Test{colorama.Style.RESET_ALL}"
                    print(test_colored_string, end='')
                    # If no error, clear the line and continue
                    print('\r' + ' ' * len("Test") + '\r', end='')
                except UnicodeEncodeError:
                    # If we got an encoding error, disable colored output
                    colored = False
                    print("Warning: Colored output disabled due to terminal encoding limitations")
                    
            # Split target into individual paths
            target_paths = target.split()
            
            # Prepare regex pattern if needed
            if regex:
                try:
                    flags = 0 if case_sensitive else re.IGNORECASE
                    search_pattern = re.compile(pattern, flags)
                except re.error as e:
                    return {"success": False, "error": f"Invalid regular expression: {str(e)}"}
            else:
                search_pattern = pattern
            
            # Track results
            all_results = []
            total_matches = 0
            files_with_matches = 0
            files_searched = 0
            
            # Get a descriptive recursion string for the result message
            recursion_message = ""
            if recursive is True or recursive is None:
                recursion_message = " (including all subdirectories)"
            elif isinstance(recursive, int) and recursive > 0:
                recursion_message = f" (including subdirectories up to {recursive} level{'s' if recursive > 1 else ''})"
            
            # Process each target
            for path in target_paths:
                if os.path.isfile(path):
                    # Process a single file
                    files_searched += 1
                    file_matches = self._search_file(path, search_pattern, regex, case_sensitive, 
                                                  context_lines, invert_match, count_only, colored)
                    if file_matches:
                        all_results.append(file_matches)
                        total_matches += file_matches["matches"]
                        files_with_matches += 1
                        
                        # Stop if we've reached the max matches limit
                        if max_matches > 0 and total_matches >= max_matches:
                            break
                elif os.path.isdir(path):
                    # Process directory using the centralized file finder
                    search_path = os.path.join(path, file_pattern)
                    
                    def on_file_found(file_path):
                        nonlocal files_searched, total_matches, files_with_matches
                        
                        # Skip if we've reached the max matches limit
                        if max_matches > 0 and total_matches >= max_matches:
                            return
                            
                        files_searched += 1
                        file_matches = self._search_file(file_path, search_pattern, regex, case_sensitive, 
                                                      context_lines, invert_match, count_only, colored)
                        
                        if file_matches:
                            all_results.append(file_matches)
                            total_matches += file_matches["matches"]
                            files_with_matches += 1
                    
                    # Use the centralized file finder to search for matching files
                    for _ in find_files(
                        file_path_pattern=search_path,
                        recursive=recursive,
                        file_type='f',  # Only search in files
                        on_file_found=on_file_found
                    ):
                        # Stop if we've reached the max matches limit
                        if max_matches > 0 and total_matches >= max_matches:
                            break
            
            # Prepare result message
            if files_with_matches == 0:
                message = f"No matches found for '{pattern}' in {files_searched} file{'s' if files_searched != 1 else ''}{recursion_message}"
            else:
                message = f"Found {total_matches} match{'es' if total_matches != 1 else ''} in {files_with_matches} file{'s' if files_with_matches != 1 else ''}{recursion_message}"
                if max_matches > 0 and total_matches >= max_matches:
                    message += f" (stopped after {max_matches} matches)"
            
            # Return the results
            return {
                "success": True,
                "pattern": pattern,
                "regex": regex,
                "case_sensitive": case_sensitive,
                "file_pattern": file_pattern,
                "recursive": recursive,
                "context_lines": context_lines,
                "invert_match": invert_match,
                "files_searched": files_searched,
                "files_with_matches": files_with_matches,
                "total_matches": total_matches,
                "results": all_results,
                "message": message
            }
                
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
    
    def _search_file(self, file_path, pattern, regex, case_sensitive, context_lines, invert_match, count_only, colored):
        """
        Search for patterns in a single file
        
        Args:
            file_path (str): Path to the file to search in
            pattern: Pattern to search for (string or compiled regex)
            regex (bool): Whether pattern is a regex
            case_sensitive (bool): Whether the search is case sensitive
            context_lines (int): Number of lines to show before and after match
            invert_match (bool): Show lines that don't match the pattern
            count_only (bool): Only count matches, don't return content
            colored (bool): Whether to colorize output
            
        Returns:
            dict: Match results for the file or None if no matches
        """
        try:
            # Read file content
            try:
                with open(file_path, 'r', encoding='utf-8', errors='replace') as file:
                    lines = file.readlines()
            except UnicodeDecodeError:
                # If UTF-8 fails, try the system's default encoding as fallback
                with open(file_path, 'r', encoding=sys.getdefaultencoding(), errors='replace') as file:
                    lines = file.readlines()
            except Exception as e:
                return {
                    "file": file_path,
                    "error": f"Could not read file: {str(e)}",
                    "matches": 0
                }
            
            # Find matches
            matches = []
            for i, line in enumerate(lines):
                if regex:
                    match = pattern.search(line)
                else:
                    # For non-regex searches
                    if case_sensitive:
                        match = pattern in line
                    else:
                        match = pattern.lower() in line.lower()
                
                if (match and not invert_match) or (not match and invert_match):
                    matches.append((i, line))
            
            if not matches:
                return None
                
            # Prepare colors for output
            if colored:
                try:
                    highlight_color = colorama.Fore.RED + colorama.Style.BRIGHT
                    line_num_color = colorama.Fore.GREEN
                    reset_color = colorama.Style.RESET_ALL
                except:
                    # If there's any issue with colorama, disable colors
                    highlight_color = ""
                    line_num_color = ""
                    reset_color = ""
            else:
                highlight_color = ""
                line_num_color = ""
                reset_color = ""
            
            match_count = len(matches)
            
            # If only counting, return count data
            if count_only:
                return {
                    "file": file_path,
                    "matches": match_count,
                    "count_only": True
                }
            
            # Format matches with context
            match_lines = []
            
            for i, (line_num, line_text) in enumerate(matches):
                # Add separator between match groups
                if i > 0 and context_lines > 0:
                    match_lines.append("---")
                
                # Add context before
                context_start = max(0, line_num - context_lines)
                for ctx_line_num in range(context_start, line_num):
                    # Use safe strings for content to prevent encoding issues
                    content = self._ensure_safe_string(lines[ctx_line_num].rstrip())
                    match_lines.append({
                        "line_num": ctx_line_num + 1,
                        "content": content,
                        "is_match": False
                    })
                
                # Add the matching line
                try:
                    if colored and not invert_match and regex:
                        # Highlight the matching part for regex patterns
                        highlighted_line = pattern.sub(
                            lambda m: f"{highlight_color}{m.group(0)}{reset_color}", 
                            line_text.rstrip()
                        )
                        match_lines.append({
                            "line_num": line_num + 1,
                            "content": self._ensure_safe_string(highlighted_line),
                            "is_match": True
                        })
                    elif colored and not invert_match and not regex:
                        # Highlight for non-regex patterns
                        if case_sensitive:
                            idx = line_text.find(pattern)
                            if idx >= 0:
                                before = line_text[:idx]
                                matched = line_text[idx:idx+len(pattern)]
                                after = line_text[idx+len(pattern):]
                                highlighted_line = f"{before}{highlight_color}{matched}{reset_color}{after}".rstrip()
                            else:
                                highlighted_line = line_text.rstrip()
                        else:
                            idx = line_text.lower().find(pattern.lower())
                            if idx >= 0:
                                before = line_text[:idx]
                                matched = line_text[idx:idx+len(pattern)]
                                after = line_text[idx+len(pattern):]
                                highlighted_line = f"{before}{highlight_color}{matched}{reset_color}{after}".rstrip()
                            else:
                                highlighted_line = line_text.rstrip()
                                
                        match_lines.append({
                            "line_num": line_num + 1,
                            "content": self._ensure_safe_string(highlighted_line),
                            "is_match": True
                        })
                    else:
                        match_lines.append({
                            "line_num": line_num + 1,
                            "content": self._ensure_safe_string(line_text.rstrip()),
                            "is_match": True
                        })
                except Exception as e:
                    # If highlighting fails, use plain version
                    match_lines.append({
                        "line_num": line_num + 1,
                        "content": self._ensure_safe_string(line_text.rstrip()),
                        "is_match": True,
                        "highlight_error": str(e)
                    })
                
                # Add context after
                context_end = min(len(lines), line_num + context_lines + 1)
                for ctx_line_num in range(line_num + 1, context_end):
                    # Use safe strings for content
                    content = self._ensure_safe_string(lines[ctx_line_num].rstrip())
                    match_lines.append({
                        "line_num": ctx_line_num + 1,
                        "content": content,
                        "is_match": False
                    })
            
            return {
                "file": file_path,
                "matches": match_count,
                "lines": match_lines
            }
            
        except Exception as e:
            return {
                "file": file_path,
                "error": str(e),
                "matches": 0
            }
            
    def _ensure_safe_string(self, text):
        """
        Ensure that a string is safe for output in the current environment
        
        Args:
            text (str): The text to make safe
            
        Returns:
            str: A safely encoded/decoded string
        """
        if text is None:
            return ""
            
        try:
            # Try to encode with the current stdout encoding, replace problematic chars
            if hasattr(sys.stdout, 'encoding') and sys.stdout.encoding:
                return text.encode(sys.stdout.encoding, errors='replace').decode(sys.stdout.encoding)
            # Default fallback
            return text.encode('ascii', errors='replace').decode('ascii')
        except Exception:
            # Last resort: remove all non-ASCII chars
            return ''.join(c if ord(c) < 128 else '?' for c in text) 