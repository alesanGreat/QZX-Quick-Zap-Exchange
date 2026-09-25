#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
getHumanLanguageStatsFromFile Command - Analyzes text files to determine the percentage of content in different languages
Using the centralized recursive file finder utility
"""

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
FUNCTION_WORDS_DIR = PROJECT_ROOT / "resources" / "function_words"
from qzx.commands.file._human_language_analysis import (
    aggregate_stats,
    analyze_file,
    analyze_mixed_languages_file,
    detect_word_language,
    extract_words,
    filter_code,
    get_file_type,
    remove_comments,
)
from qzx.commands.file._human_language_dictionaries import load_function_words
from qzx.commands.file._human_language_workflow import execute_human_language_stats
from qzx.core.command_base import CommandBase

class GetHumanLanguageStatsFromFileCommand(CommandBase):
    """
    Command to analyze a file or multiple files and determine the percentage of text in different languages,
    intelligently filtering out programming code. Supports wildcards and recursive directory search.
    
    Supports flags:
    -r, -R, --recursive: Enable recursive directory search
    -i, --ignore-comments: Ignore code comments when analyzing text
    
    This version uses the centralized recursive file finder utility.
    """
    
    name = "getHumanLanguageStats"
    description = (
        "Analyzes files to estimate human-language distribution, with "
        "wildcard and recursive search support."
    )
    category = "file"
    
    parameters = [
        {
            'name': 'file_path',
            'description': 'Path to the file(s) to analyze. Supports wildcards like *.txt',
            'required': True
        },
        {
            'name': 'ignore_comments',
            'description': 'Whether to ignore code comments when analyzing text. Can use -i or --ignore-comments flag.',
            'required': False,
            'default': False
        },
        {
            'name': 'min_word_length',
            'description': 'Minimum length of words to consider for language detection',
            'required': False,
            'default': 4
        },
        {
            'name': 'languages',
            'description': 'Comma-separated list of languages to detect (default: all available)',
            'required': False,
            'default': None
        },
        {
            'name': 'recursive',
            'description': 'Whether to search recursively in directories. Can use -r, -R, or --recursive flag.',
            'required': False,
            'default': False
        },
        {
            'name': 'show_files_match',
            'description': 'Whether to show the list of files found. Can use --show_files_match flag.',
            'required': False,
            'default': False
        }
    ]
    
    examples = [
        {
            'command': 'qzx getHumanLanguageStats myfile.txt',
            'description': 'Analyze language distribution in a text file'
        },
        {
            'command': 'qzx getHumanLanguageStats code.py -i',
            'description': 'Analyze a Python file, ignoring code comments using flag'
        },
        {
            'command': 'qzx getHumanLanguageStats "*.md" false 3',
            'description': 'Analyze all Markdown files in current directory'
        },
        {
            'command': 'qzx getHumanLanguageStats "docs/*.txt" -i',
            'description': 'Analyze text files in docs directory, ignoring comments'
        },
        {
            'command': 'qzx getHumanLanguageStats "src/**/*.py" -r',
            'description': 'Analyze all Python files recursively in src directory using -r flag'
        },
        {
            'command': 'qzx getHumanLanguageStats "**/*.py" -r -i',
            'description': 'Analyze all Python files recursively, ignoring comments, using flags'
        },
        {
            'command': 'qzx getHumanLanguageStats "**/*.py" -r --show_files_match',
            'description': 'Analyze all Python files recursively and show the list of files found'
        }
    ]
    
    # Common programming language patterns to filter out
    CODE_PATTERNS = {
        'python': [
            r'def\s+\w+\s*\(.*?\):',  # Function definitions
            r'class\s+\w+(\s*\(.*?\))?:',  # Class definitions
            r'import\s+[\w\.]+',  # Import statements
            r'from\s+[\w\.]+\s+import',  # From import statements
            r'if\s+.*?:',  # If statements
            r'elif\s+.*?:',  # Elif statements
            r'else:',  # Else statements
            r'while\s+.*?:',  # While loops
            r'for\s+.*?\s+in\s+.*?:',  # For loops
            r'try:',  # Try blocks
            r'except(\s+.*?)?:',  # Except blocks
            r'finally:',  # Finally blocks
            r'with\s+.*?:',  # With statements
            r'@\w+',  # Decorators
            r'return\s+.*',  # Return statements
            r'yield\s+.*',  # Yield statements
            r'self\.',  # Self references
            r'super\(',  # Super calls
            r'lambda\s+.*?:',  # Lambda expressions
            r'raise\s+.*',  # Raise statements
            r'assert\s+.*',  # Assert statements
            r'print\(',  # Print functions
        ],
        'javascript': [
            r'function\s+\w+\s*\(.*?\)',  # Function definitions
            r'const\s+\w+\s*=',  # Const declarations
            r'let\s+\w+\s*=',  # Let declarations
            r'var\s+\w+\s*=',  # Var declarations
            r'class\s+\w+\s*{',  # Class definitions
            r'import\s+.*?from',  # Import statements
            r'export\s+',  # Export statements
            r'if\s*\(.*?\)',  # If statements
            r'else\s+if\s*\(.*?\)',  # Else if statements
            r'else\s*{',  # Else statements
            r'for\s*\(.*?\)',  # For loops
            r'while\s*\(.*?\)',  # While loops
            r'switch\s*\(.*?\)',  # Switch statements
            r'case\s+.*?:',  # Case statements
            r'try\s*{',  # Try blocks
            r'catch\s*\(.*?\)',  # Catch blocks
            r'finally\s*{',  # Finally blocks
            r'new\s+\w+',  # New operator
            r'return\s+.*',  # Return statements
            r'this\.',  # This references
            r'=>\s*{',  # Arrow functions
            r'console\.',  # Console statements
            r'document\.',  # Document references
            r'window\.',  # Window references
        ],
        # ... other language patterns (same as original)
    }
    
    # Common regex patterns for code comments
    COMMENT_PATTERNS = {
        'python': [r'#.*$', r'""".*?"""', r"'''.*?'''"],
        'javascript': [r'//.*$', r'/\*.*?\*/'],
        'c': [r'//.*$', r'/\*.*?\*/'],
        'html': [r'<!--.*?-->'],
        'css': [r'/\*.*?\*/'],
        'ruby': [r'#.*$', r'=begin.*?=end'],
        'php': [r'//.*$', r'#.*$', r'/\*.*?\*/'],
        'sql': [r'--.*$', r'/\*.*?\*/'],
        'powershell': [r'#.*$', r'<#.*?#>'],
        'bash': [r'#.*$'],
        'java': [r'//.*$', r'/\*.*?\*/'],
        'go': [r'//.*$', r'/\*.*?\*/'],
        'rust': [r'//.*$', r'/\*.*?\*/'],
    }
    
    def __init__(self):
        """Initialize the command and load function words from JSON files"""
        super().__init__()
        self.dictionary_warnings = []
        # Load function words from JSON files
        self.function_words = self._load_function_words()
    
    def _load_function_words(self):
        return load_function_words(self, FUNCTION_WORDS_DIR)

    def execute(
        self,
        file_path,
        ignore_comments=False,
        min_word_length=4,
        languages=None,
        recursive=False,
        show_files_match=False,
    ):
        return execute_human_language_stats(
            self,
            file_path,
            ignore_comments,
            min_word_length,
            languages,
            recursive,
            show_files_match,
        )

    def _analyze_file(
        self,
        file_path,
        ignore_comments=False,
        min_word_length=4,
        function_words=None,
    ):
        return analyze_file(
            self,
            file_path,
            ignore_comments,
            min_word_length,
            function_words,
        )

    def _analyze_mixed_languages_file(
        self,
        content,
        min_word_length,
        function_words,
    ):
        return analyze_mixed_languages_file(
            self,
            content,
            min_word_length,
            function_words,
        )

    def _get_file_type(self, extension):
        return get_file_type(extension)

    def _remove_comments(self, content, file_type):
        return remove_comments(self, content, file_type)

    def _filter_code(self, content):
        return filter_code(self, content)

    def _extract_words(self, content, min_length=4):
        return extract_words(content, min_length)

    def _detect_word_language(self, word):
        return detect_word_language(word)

    def _aggregate_stats(self, file_stats):
        return aggregate_stats(file_stats)
