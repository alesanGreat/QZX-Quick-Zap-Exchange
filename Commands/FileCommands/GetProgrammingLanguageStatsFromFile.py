#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
GetProgrammingLanguageStatsFromFile Command - Analyzes files to determine the programming language and statistics. Supports wildcards and recursive directory searches.
Using the centralized recursive file finder utility
"""

import os
import re
import json
from collections import Counter, defaultdict
import math
from pathlib import Path
from Core.command_base import CommandBase
from Core.recursive_findfiles_utils import find_files, parse_recursive_parameter

class GetProgrammingLanguageStatsFromFileCommand(CommandBase):
    """
    Command to identify programming language in one or more files and get code statistics.
    Supports wildcards and recursive directory searching.
    
    Supports flags:
    -r, -R, --recursive: Enable unlimited recursive directory search
    -rN, --recursiveN: Enable recursive directory search up to N levels deep
    
    This version uses the centralized recursive file finder utility.
    """
    
    name = "getProgrammingLanguageStatsFromFile"
    description = "Analyzes files to determine the programming language and provides statistics about the code. Supports wildcards and recursive directory search."
    category = "file"
    
    parameters = [
        {
            'name': 'file_path',
            'description': 'Path to the file(s) to analyze. Supports wildcards like *.py',
            'required': True
        },
        {
            'name': 'detailed',
            'description': 'Whether to provide detailed statistics',
            'required': False,
            'default': False
        },
        {
            'name': 'languages',
            'description': 'Comma-separated list of languages to detect (default: all available)',
            'required': False,
            'default': None
        },
        {
            'name': 'recursive',
            'description': 'Recursion level: -r/--recursive for unlimited depth, -rN/--recursiveN for N levels deep',
            'required': False,
            'default': None
        }
    ]
    
    examples = [
        {
            'command': 'qzx getProgrammingLanguageStatsFromFile script.py',
            'description': 'Analyze a Python file to determine language statistics'
        },
        {
            'command': 'qzx getProgrammingLanguageStatsFromFile app.js true',
            'description': 'Analyze a JavaScript file with detailed statistics'
        },
        {
            'command': 'qzx getProgrammingLanguageStatsFromFile code.cpp false "cpp,c,python"',
            'description': 'Analyze a C++ file specifically checking for C++, C and Python patterns'
        },
        {
            'command': 'qzx getProgrammingLanguageStatsFromFile "*.js" -r',
            'description': 'Analyze all JavaScript files in current directory and all subdirectories'
        },
        {
            'command': 'qzx getProgrammingLanguageStatsFromFile "src/**/*.py" -r',
            'description': 'Analyze all Python files in src directory and subdirectories with detailed stats'
        },
        {
            'command': 'qzx getProgrammingLanguageStatsFromFile "*.py" true null -r2',
            'description': 'Analyze all Python files in current directory and up to 2 levels of subdirectories with detailed stats'
        }
    ]
    
    # Mapping of file extensions to language names
    LANGUAGE_EXTENSIONS = {
        '.py': 'Python',
        '.js': 'JavaScript',
        '.html': 'HTML',
        '.css': 'CSS',
        '.php': 'PHP',
        '.java': 'Java',
        '.c': 'C',
        '.cpp': 'C++',
        '.h': 'C/C++ Header',
        '.cs': 'C#',
        '.go': 'Go',
        '.rb': 'Ruby',
        '.rs': 'Rust',
        '.ts': 'TypeScript',
        '.swift': 'Swift',
        '.kt': 'Kotlin',
        '.sh': 'Shell',
        '.bat': 'Batch',
        '.ps1': 'PowerShell',
        '.sql': 'SQL',
        '.r': 'R',
        '.pas': 'Pascal',
        '.pl': 'Perl',
        '.lua': 'Lua',
        '.vb': 'Visual Basic',
    }
    
    # Directory containing programming language dictionaries
    LANGUAGES_DIR = "Resources/ProgrammingLanguages"
    
    def _load_language_dictionaries(self, languages=None):
        """
        Load language dictionaries from JSON files
        
        Args:
            languages (list, optional): List of language names to load
            
        Returns:
            dict: Dictionary with language data
        """
        language_data = {}
        available_languages = []
        
        # Map some common case variations to standard names
        language_name_map = {
            'python': 'python',
            'javascript': 'javascript',
            'js': 'javascript',
            'java': 'java',
            'c++': 'cpp',
            'cpp': 'cpp',
            'c#': 'csharp',
            'csharp': 'csharp',
            'html': 'html',
            'css': 'css',
            'php': 'php',
            'ruby': 'ruby',
            'rust': 'rust',
            'typescript': 'typescript',
            'ts': 'typescript',
            'go': 'go',
            'golang': 'go',
            'sql': 'sql'
        }
        
        # Get list of available language files
        try:
            for file in os.listdir(self.LANGUAGES_DIR):
                if file.endswith('.json'):
                    lang_name = os.path.splitext(file)[0]
                    available_languages.append(lang_name)
        except FileNotFoundError:
            print(f"Warning: Languages directory '{self.LANGUAGES_DIR}' not found")
            return self._get_default_language_data()
            
        # If no languages specified, load all available
        if not languages:
            languages_to_load = available_languages
        else:
            # Normalize language names and map to available files
            languages_to_load = []
            for lang in languages:
                normalized = lang.lower()
                if normalized in language_name_map:
                    normalized = language_name_map[normalized]
                
                if normalized in available_languages:
                    languages_to_load.append(normalized)
                else:
                    print(f"Warning: Language '{lang}' not found in languages directory")
        
        # Load dictionaries for each language
        for lang in languages_to_load:
            try:
                dict_path = os.path.join(self.LANGUAGES_DIR, f"{lang}.json")
                if os.path.exists(dict_path):
                    with open(dict_path, 'r', encoding='utf-8') as f:
                        lang_data = json.load(f)
                    
                    # Standardize language name to title case
                    lang_name = lang.title()
                    language_data[lang_name] = lang_data
            except Exception as e:
                print(f"Error loading language data for '{lang}': {str(e)}")
        
        # If no languages were loaded, use defaults
        if not language_data:
            return self._get_default_language_data()
                
        return language_data
    
    def _get_default_language_data(self):
        """
        Fallback method to provide default language data
        
        Returns:
            dict: Dictionary with default language data
        """
        # Just include a few common languages
        return {
            'Python': {
                'keywords': [
                    'def', 'class', 'import', 'from', 'if', 'else', 'elif', 'for', 'while', 
                    'try', 'except', 'finally', 'with', 'as', 'lambda', 'return', 'yield'
                ],
                'comments': {
                    'single_line': [r'^\s*#'], 
                    'multi_line': [r'^\s*""".*?"""', r"^\s*'''.*?'''"]
                },
                'patterns': {
                    'function_definition': [r'^\s*def\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*\('],
                    'class_definition': [r'^\s*class\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*[:\(]']
                }
            },
            'JavaScript': {
                'keywords': [
                    'function', 'var', 'let', 'const', 'if', 'else', 'for', 'while', 'switch', 
                    'case', 'break', 'return', 'try', 'catch', 'finally', 'class', 'extends',
                    'import', 'export', 'this', 'async', 'await'
                ],
                'comments': {
                    'single_line': [r'^\s*//'],
                    'multi_line': [r'/\*.*?\*/']
                },
                'patterns': {
                    'function_definition': [
                        r'function\s+([a-zA-Z_$][a-zA-Z0-9_$]*)\s*\(',
                        r'([a-zA-Z_$][a-zA-Z0-9_$]*)\s*=\s*function\s*\(',
                        r'([a-zA-Z_$][a-zA-Z0-9_$]*)\s*:\s*function\s*\('
                    ],
                    'class_definition': [r'class\s+([a-zA-Z_$][a-zA-Z0-9_$]*)']
                }
            }
        }
        
    def _analyze_file(self, file_path, detailed=False, language_data=None):
        """
        Analyze a single file for programming language and code statistics
        
        Args:
            file_path (str): Path to the file to analyze
            detailed (bool): Whether to include detailed statistics
            language_data (dict): Pre-loaded language dictionaries
            
        Returns:
            dict: Analysis results for this file
        """
        try:
            # Check if the file exists and is a file
            if not os.path.exists(file_path) or not os.path.isfile(file_path):
                return {
                    "success": False,
                    "file_path": file_path,
                    "error": f"File does not exist or is not a regular file: {file_path}"
                }
            
            # Read file content
            try:
                with open(file_path, 'r', encoding='utf-8') as file:
                    content = file.read()
                    lines = content.splitlines()
            except UnicodeDecodeError:
                # Try with different encoding if UTF-8 fails
                try:
                    with open(file_path, 'r', encoding='latin-1') as file:
                        content = file.read()
                        lines = content.splitlines()
                except Exception as e:
                    return {
                        "success": False,
                        "file_path": file_path,
                        "error": f"Failed to read file: {str(e)}"
                    }
            
            # Basic file stats
            file_size = os.path.getsize(file_path)
            line_count = len(lines)
            empty_lines = sum(1 for line in lines if not line.strip())
            
            # Detect language based on file extension
            _, file_extension = os.path.splitext(file_path)
            detected_language = self.LANGUAGE_EXTENSIONS.get(file_extension.lower(), 'Unknown')
            
            language_scores = {}
            
            # If language is still unknown or we want detailed analysis, analyze content
            if detected_language == 'Unknown' or detailed:
                language_scores = self._analyze_content(lines, content, language_data)
                
                # If language was unknown from extension, use the highest scoring one
                if detected_language == 'Unknown' and language_scores:
                    detected_language = max(language_scores.items(), key=lambda x: x[1])[0]
            
            # Get comment statistics if we know the language
            comment_stats = self._analyze_comments(lines, detected_language, language_data)
            
            # Get function/class count if we know the language
            functions = self._identify_functions(lines, detected_language, language_data)
            
            # Prepare the result
            result = {
                "success": True,
                "file_path": os.path.abspath(file_path),
                "file_name": os.path.basename(file_path),
                "file_extension": file_extension,
                "file_size": file_size,
                "file_size_readable": self._format_bytes(file_size),
                "detected_language": detected_language,
                "line_count": line_count,
                "empty_lines": empty_lines,
                "code_lines": line_count - empty_lines - comment_stats['comment_lines'],
                "comment_lines": comment_stats['comment_lines'],
                "comment_percentage": round((comment_stats['comment_lines'] / line_count * 100) if line_count > 0 else 0, 2),
                "functions_count": len(functions),
                "functions": functions if detailed else [],
            }
            
            # Add detailed language scores if available
            if language_scores and detailed:
                # Normalize scores for easier comparison
                total_score = sum(language_scores.values())
                normalized_scores = {}
                
                if total_score > 0:
                    for lang, score in language_scores.items():
                        normalized_scores[lang] = round((score / total_score) * 100, 2)
                
                result["language_confidence"] = normalized_scores
            
            # Add keyword stats if detailed
            if detailed:
                result["keyword_stats"] = self._analyze_keywords(content, detected_language, language_data)
                
                # Add complexity metrics
                result["complexity"] = self._estimate_complexity(lines, detected_language, functions)
            
            return result
            
        except Exception as e:
            return {
                "success": False,
                "file_path": file_path,
                "error": str(e)
            }
    
    def execute(self, file_path, detailed=False, languages=None, recursive=None):
        """
        Analyzes one or more files to determine programming language and code statistics.
        Supports wildcards and recursive directory search.
        
        Args:
            file_path (str): Path to the file(s) to analyze. Supports wildcards like *.py
            detailed (bool, optional): Whether to include detailed statistics
            languages (str, optional): Comma-separated list of languages to detect
            recursive: Recursion level: none by default, -r/--recursive for unlimited, -rN/--recursiveN for N levels
            
        Returns:
            Dictionary with analysis results for each file and aggregated statistics
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
                
            # Handle parameter conversions
            if isinstance(detailed, str):
                detailed = detailed.lower() in ('true', 'yes', 'y', '1')
                
            # Load language dictionaries
            if languages:
                languages = [lang.strip().lower() for lang in languages.split(',') if lang.strip()]
            language_data = self._load_language_dictionaries(languages)
            
            # Find matching files using centralized file finder
            matching_files = []
            
            def on_file_found(found_file):
                matching_files.append(found_file)
                
            # Use the centralized file finder to get all matching files
            for _ in find_files(
                file_path_pattern=file_path,
                recursive=recursive,
                file_type='f',  # Only search for files, not directories
                on_file_found=on_file_found
            ):
                pass  # The callback already tracks the files
            
            # Get a descriptive recursion string for the result message
            recursion_message = ""
            if recursive is True or recursive is None:
                recursion_message = " (including all subdirectories)"
            elif isinstance(recursive, int) and recursive > 0:
                recursion_message = f" (including subdirectories up to {recursive} level{'s' if recursive > 1 else ''})"
            
            if not matching_files:
                return {
                    "success": True,
                    "files_found": 0,
                    "message": f"No files found matching '{file_path}'{recursion_message}"
                }
            
            # Process each file
            file_results = {}
            aggregated_stats = defaultdict(int)
            languages_found = Counter()
            extensions_found = Counter()
            
            for file_path in matching_files:
                try:
                    print(f"Analyzing {file_path}...")
                    result = self._analyze_file(file_path, detailed, language_data)
                    
                    # Skip unsupported file types
                    if result["language"] == "Unknown":
                        file_results[file_path] = result
                        continue
                    
                    # Update counters
                    languages_found[result["language"]] += 1
                    
                    # Count extensions
                    ext = os.path.splitext(file_path)[1].lower()
                    if ext:
                        extensions_found[ext] += 1
                    else:
                        extensions_found["(no extension)"] += 1
                    
                    # Aggregate statistics
                    aggregated_stats["total_files"] += 1
                    aggregated_stats["total_lines"] += result["total_lines"]
                    aggregated_stats["code_lines"] += result["code_lines"]
                    aggregated_stats["comment_lines"] += result["comment_lines"]
                    aggregated_stats["blank_lines"] += result["blank_lines"]
                    aggregated_stats["total_size"] += result["file_size"]
                    
                    # Add to complexity calculation if available
                    if "complexity" in result:
                        if "cyclomatic_complexity" in aggregated_stats:
                            aggregated_stats["cyclomatic_complexity"] += result["complexity"]["cyclomatic_complexity"]
                        else:
                            aggregated_stats["cyclomatic_complexity"] = result["complexity"]["cyclomatic_complexity"]
                    
                    file_results[file_path] = result
                except Exception as e:
                    file_results[file_path] = {
                        "error": str(e),
                        "language": "Error",
                        "file_size": 0,
                        "total_lines": 0
                    }
            
            # Prepare summary stats
            supported_files = [r for r in file_results.values() if "error" not in r and r["language"] != "Unknown"]
            
            if not supported_files:
                return {
                    "success": True,
                    "files_found": len(matching_files),
                    "files_analyzed": 0,
                    "message": f"No supported files found among {len(matching_files)} files matching '{file_path}'{recursion_message}",
                    "file_results": file_results
                }
            
            # Calculate percentages
            if aggregated_stats["total_lines"] > 0:
                code_percent = (aggregated_stats["code_lines"] / aggregated_stats["total_lines"]) * 100
                comment_percent = (aggregated_stats["comment_lines"] / aggregated_stats["total_lines"]) * 100
                blank_percent = (aggregated_stats["blank_lines"] / aggregated_stats["total_lines"]) * 100
            else:
                code_percent = comment_percent = blank_percent = 0
            
            # Add percentages to stats
            aggregated_stats["code_percent"] = code_percent
            aggregated_stats["comment_percent"] = comment_percent
            aggregated_stats["blank_percent"] = blank_percent
            
            # Format size
            aggregated_stats["total_size_formatted"] = self._format_bytes(aggregated_stats["total_size"])
            
            # Prepare return object
            result = {
                "success": True,
                "files_found": len(matching_files),
                "files_analyzed": len(supported_files),
                "language_counts": dict(languages_found),
                "extension_counts": dict(extensions_found),
                "aggregated_stats": dict(aggregated_stats),
                "file_results": file_results
            }
            
            # Add summary message
            if len(supported_files) == 1:
                file_path = next(iter(file_results.keys()))
                result["message"] = f"File {file_path} is written in {file_results[file_path]['language']} with {file_results[file_path]['total_lines']} lines"
            else:
                top_language = languages_found.most_common(1)[0][0] if languages_found else "Unknown"
                result["message"] = (f"Analyzed {len(supported_files)} files ({aggregated_stats['total_lines']} lines total). "
                                   f"Most common language: {top_language} ({languages_found[top_language]} files)")
            
            return result
                
        except Exception as e:
            return {
                "success": False,
                "message": f"Error analyzing files: {str(e)}"
            }
    
    def _analyze_content(self, lines, content, language_data):
        """
        Analyze file content to determine language based on keywords
        
        Args:
            lines (list): List of file lines
            content (str): Full file content
            language_data (dict): Dictionary with language data
            
        Returns:
            dict: Dictionary with language scores
        """
        language_scores = {}
        
        # Check for language-specific keywords
        for language, lang_dict in language_data.items():
            # Calculate a score based on keyword matches
            score = 0
            
            # Check all types of language elements, not just keywords
            for element_type in ['keywords', 'builtins', 'global_functions', 'dom_objects']:
                if element_type in lang_dict:
                    keywords = lang_dict[element_type]
                    for keyword in keywords:
                        # Create a regex pattern that matches the keyword as a whole word
                        pattern = r'\b' + re.escape(keyword) + r'\b'
                        matches = re.findall(pattern, content, re.IGNORECASE)
                        score += len(matches)
            
            # Check patterns
            if 'patterns' in lang_dict:
                for pattern_type, patterns in lang_dict['patterns'].items():
                    for pattern in patterns:
                        matches = re.findall(pattern, content, re.IGNORECASE)
                        score += len(matches) * 2  # Give more weight to patterns
            
            if score > 0:
                language_scores[language] = score
            
        return language_scores
    
    def _analyze_comments(self, lines, language, language_data):
        """
        Analyze code comments in the file
        
        Args:
            lines (list): List of file lines
            language (str): Detected programming language
            language_data (dict): Dictionary with language data
            
        Returns:
            dict: Dictionary with comment statistics
        """
        comment_lines = 0
        
        # Get language data
        lang_dict = language_data.get(language, {})
        
        # Get comment patterns for the language
        patterns = lang_dict.get('comments', {'single_line': [], 'multi_line': []})
        
        # If no patterns found in the language data, use the old way
        if not patterns.get('single_line') and not patterns.get('multi_line'):
            # Fall back to original method
            return self._analyze_comments_legacy(lines, language)
        
        # Join all lines for multi-line comment detection
        full_content = "\n".join(lines)
        
        # First check for multi-line comments with regex
        for pattern in patterns.get('multi_line', []):
            # Find all multi-line comments
            for match in re.finditer(pattern, full_content, re.DOTALL):
                # Count newlines in the match
                comment_lines += match.group(0).count('\n') + 1
        
        # Then check for single-line comments
        for i, line in enumerate(lines):
            line_is_comment = False
            
            # Check if line matches any single-line comment pattern
            for pattern in patterns.get('single_line', []):
                if re.search(pattern, line):
                    line_is_comment = True
                    break
            
            if line_is_comment:
                comment_lines += 1
        
        return {
            "comment_lines": comment_lines
        }
    
    def _analyze_comments_legacy(self, lines, language):
        """
        Legacy method for analyzing comments
        
        Args:
            lines (list): List of file lines
            language (str): Detected programming language
            
        Returns:
            dict: Dictionary with comment statistics
        """
        comment_lines = 0
        in_multiline_comment = False
        multiline_comment_text = ""
        
        # Old comment patterns dictionary
        comment_patterns = {
            'Python': {
                'single_line': [r'^\s*#'],
                'multi_line': [r'^\s*""".*?"""', r"^\s*'''.*?'''"]
            },
            'JavaScript': {
                'single_line': [r'^\s*//'],
                'multi_line': [r'/\*.*?\*/']
            },
            'Java': {
                'single_line': [r'^\s*//'],
                'multi_line': [r'/\*.*?\*/']
            },
            'C++': {
                'single_line': [r'^\s*//'],
                'multi_line': [r'/\*.*?\*/']
            },
            'PHP': {
                'single_line': [r'^\s*(//|#)'],
                'multi_line': [r'/\*.*?\*/']
            },
            'Pascal': {
                'single_line': [r'^\s*//'],
                'multi_line': [r'\{.*?\}', r'\(\*.*?\*\)']
            },
            'HTML': {
                'single_line': [],
                'multi_line': [r'<!--.*?-->']
            },
            'CSS': {
                'single_line': [],
                'multi_line': [r'/\*.*?\*/']
            },
            'SQL': {
                'single_line': [r'^\s*--'],
                'multi_line': [r'/\*.*?\*/']
            }
        }
        
        # Get comment patterns for the language
        patterns = comment_patterns.get(language, {'single_line': [], 'multi_line': []})
        
        # Join all lines for multi-line comment detection
        full_content = "\n".join(lines)
        
        # First check for multi-line comments with regex
        for pattern in patterns.get('multi_line', []):
            # Find all multi-line comments
            for match in re.finditer(pattern, full_content, re.DOTALL):
                # Count newlines in the match
                comment_lines += match.group(0).count('\n') + 1
        
        # Then check for single-line comments
        for i, line in enumerate(lines):
            line_is_comment = False
            
            # Check if line matches any single-line comment pattern
            for pattern in patterns.get('single_line', []):
                if re.search(pattern, line):
                    line_is_comment = True
                    break
            
            if line_is_comment:
                comment_lines += 1
        
        return {
            "comment_lines": comment_lines
        }
    
    def _identify_functions(self, lines, language, language_data):
        """
        Identify function declarations in the file
        
        Args:
            lines (list): List of file lines
            language (str): Detected programming language
            language_data (dict): Dictionary with language data
            
        Returns:
            list: List of identified function names
        """
        functions = []
        
        # Get language data
        lang_dict = language_data.get(language, {})
        
        # Get patterns for the language
        pattern_dict = lang_dict.get('patterns', {})
        
        # Combine function and class definition patterns
        patterns = pattern_dict.get('function_definition', []) + pattern_dict.get('class_definition', [])
        
        # If no patterns found in the language data, use the legacy approach
        if not patterns:
            return self._identify_functions_legacy(lines, language)
        
        # Check each line for function declarations
        for i, line in enumerate(lines):
            for pattern in patterns:
                match = re.search(pattern, line)
                if match:
                    # Get the function name from the regex group
                    if len(match.groups()) >= 1:
                        # The function name might be in different group indexes depending on the pattern
                        # Try to get the last group which is usually the name
                        func_name = match.groups()[-1]
                        
                        # Determine if it's a class or function based on pattern
                        func_type = "class" if "class" in pattern.lower() else "function"
                        
                        functions.append({
                            "name": func_name,
                            "line": i + 1,
                            "type": func_type
                        })
        
        return functions
    
    def _identify_functions_legacy(self, lines, language):
        """
        Legacy method for identifying functions
        
        Args:
            lines (list): List of file lines
            language (str): Detected programming language
            
        Returns:
            list: List of identified function names
        """
        functions = []
        
        # Legacy function patterns
        function_patterns = {
            'Python': [
                r'^\s*def\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*\(',
                r'^\s*class\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*[:\(]'
            ],
            'JavaScript': [
                r'function\s+([a-zA-Z_$][a-zA-Z0-9_$]*)\s*\(',
                r'([a-zA-Z_$][a-zA-Z0-9_$]*)\s*=\s*function\s*\(',
                r'([a-zA-Z_$][a-zA-Z0-9_$]*)\s*:\s*function\s*\(',
                r'class\s+([a-zA-Z_$][a-zA-Z0-9_$]*)',
                r'(async\s+)?([a-zA-Z_$][a-zA-Z0-9_$]*)\s*\(\s*[^)]*\)\s*{',
                r'(get|set|async)\s+([a-zA-Z_$][a-zA-Z0-9_$]*)\s*\('
            ],
            'Java': [
                r'(public|private|protected|static|\s) +[\w\<\>\[\]]+\s+(\w+) *\([^\)]*\)',
                r'class\s+([a-zA-Z_$][a-zA-Z0-9_$]*)'
            ],
            'C++': [
                r'([\w\*]+\s+)+(\w+)\s*\([^)]*\)\s*(\{|:)',
                r'class\s+([a-zA-Z_][a-zA-Z0-9_]*)'
            ],
            'PHP': [
                r'function\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*\(',
                r'class\s+([a-zA-Z_][a-zA-Z0-9_]*)'
            ],
            'Pascal': [
                r'procedure\s+([a-zA-Z_][a-zA-Z0-9_]*)',
                r'function\s+([a-zA-Z_][a-zA-Z0-9_]*)',
                r'program\s+([a-zA-Z_][a-zA-Z0-9_]*)',
                r'unit\s+([a-zA-Z_][a-zA-Z0-9_]*)'
            ]
        }
        
        # Get patterns for the language
        patterns = function_patterns.get(language, [])
        
        # Check each line for function declarations
        for i, line in enumerate(lines):
            for pattern in patterns:
                match = re.search(pattern, line)
                if match:
                    # Get the function name from the regex group
                    if len(match.groups()) >= 1:
                        # Try to get the most likely function name
                        # Usually the last group is the actual name
                        func_name = match.groups()[-1]
                        
                        functions.append({
                            "name": func_name,
                            "line": i + 1,
                            "type": "class" if 'class' in pattern else "function"
                        })
        
        return functions
    
    def _analyze_keywords(self, content, language, language_data):
        """
        Analyze keyword usage in the file
        
        Args:
            content (str): File content
            language (str): Detected programming language
            language_data (dict): Dictionary with language data
            
        Returns:
            dict: Dictionary with keyword statistics
        """
        keyword_stats = {}
        
        # Get language data
        lang_dict = language_data.get(language, {})
        
        # Combine all word lists that are worth counting
        all_keywords = []
        for key in ['keywords', 'builtins', 'global_functions']:
            if key in lang_dict:
                all_keywords.extend(lang_dict[key])
        
        # If no keywords found, return empty stats
        if not all_keywords:
            return keyword_stats
        
        # Count occurrences of each keyword
        for keyword in all_keywords:
            # Create a regex pattern that matches the keyword as a whole word
            pattern = r'\b' + re.escape(keyword) + r'\b'
            matches = re.findall(pattern, content, re.IGNORECASE)
            count = len(matches)
            
            if count > 0:
                keyword_stats[keyword] = count
        
        # Sort by frequency
        return dict(sorted(keyword_stats.items(), key=lambda item: item[1], reverse=True))
    
    def _estimate_complexity(self, lines, language, functions):
        """
        Estimate code complexity metrics
        
        Args:
            lines (list): List of file lines
            language (str): Detected programming language
            functions (list): Identified functions
            
        Returns:
            dict: Dictionary with complexity metrics
        """
        # Basic cyclomatic complexity estimation
        complexity_keywords = [
            r'\bif\b', r'\belse\b', r'\bfor\b', r'\bwhile\b', r'\bcase\b',
            r'\bcatch\b', r'\b\|\|\b', r'\b&&\b', r'\?', r':\s*\w+'
        ]
        
        # Count branching statements
        branching_count = 0
        for line in lines:
            for keyword in complexity_keywords:
                matches = re.findall(keyword, line)
                branching_count += len(matches)
        
        # Calculate average function length
        avg_function_length = 0
        if functions:
            # Sort functions by line number
            sorted_funcs = sorted(functions, key=lambda x: x['line'])
            
            # Estimate function lengths
            lengths = []
            for i in range(len(sorted_funcs)):
                if i < len(sorted_funcs) - 1:
                    length = sorted_funcs[i+1]['line'] - sorted_funcs[i]['line']
                else:
                    # For the last function, assume it extends to the end
                    length = len(lines) - sorted_funcs[i]['line'] + 1
                
                # Apply a reasonable cap to avoid outliers
                length = min(length, 200)
                lengths.append(length)
            
            avg_function_length = sum(lengths) / len(lengths) if lengths else 0
        
        # Calculate a rough maintainability index
        # Based on a simplified version of the Microsoft metric
        # MI = 171 - 5.2 * ln(aveV) - 0.23 * aveV(g') - 16.2 * ln(aveLOC)
        loc = len(lines)
        avg_loc_per_function = avg_function_length if avg_function_length > 0 else loc
        
        halstead_volume = math.log(len(set(("".join(lines)).split()))) * len(lines) if lines else 0
        cyclomatic_complexity = 1 + branching_count
        
        maintainability = 171
        maintainability -= 5.2 * math.log(halstead_volume + 1)
        maintainability -= 0.23 * cyclomatic_complexity
        maintainability -= 16.2 * math.log(avg_loc_per_function + 1)
        
        # Normalize to 0-100 scale
        maintainability = max(0, min(100, maintainability))
        
        return {
            "cyclomatic_complexity": cyclomatic_complexity,
            "branching_statements": branching_count,
            "avg_function_length": round(avg_function_length, 2),
            "maintainability_index": round(maintainability, 2),
            "complexity_rating": self._get_complexity_rating(maintainability)
        }
    
    def _get_complexity_rating(self, maintainability):
        """
        Convert maintainability index to a human-readable rating
        
        Args:
            maintainability (float): Maintainability index
            
        Returns:
            str: Complexity rating
        """
        if maintainability >= 85:
            return "Highly Maintainable"
        elif maintainability >= 65:
            return "Maintainable"
        elif maintainability >= 40:
            return "Moderately Maintainable"
        else:
            return "Difficult to Maintain"
    
    def _format_bytes(self, size):
        """
        Format bytes to human-readable size
        
        Args:
            size (int): Size in bytes
            
        Returns:
            str: Human-readable size string
        """
        for unit in ['B', 'KB', 'MB', 'GB', 'TB', 'PB']:
            if size < 1024.0 or unit == 'PB':
                break
            size /= 1024.0
        return f"{size:.2f} {unit}" 