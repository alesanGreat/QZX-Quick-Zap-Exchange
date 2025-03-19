#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
AnalyzeComplexity Command - Analyzes code complexity for development environments
Using the centralized recursive file finder utility
"""

import os
import re
import math
import ast
from Core.command_base import CommandBase
from Core.recursive_findfiles_utils import find_files, parse_recursive_parameter

class AnalyzeComplexityCommand(CommandBase):
    """
    Command to analyze code complexity metrics for development environments
    
    This version uses the centralized recursive file finder utility.
    """
    
    name = "analyzeComplexity"
    description = "Analyzes code complexity metrics for files or projects"
    category = "dev"
    
    parameters = [
        {
            'name': 'file_path',
            'description': 'Path to the file or directory to analyze',
            'required': True
        },
        {
            'name': 'recursive',
            'description': 'Whether to recursively analyze directories: -r/--recursive for unlimited, -rN/--recursiveN for N levels',
            'required': False,
            'default': False
        },
        {
            'name': 'format',
            'description': 'Output format: "detailed" or "summary"',
            'required': False,
            'default': 'detailed'
        }
    ]
    
    examples = [
        {
            'command': 'qzx analyzeComplexity "main.py"',
            'description': 'Analyze complexity of a single Python file'
        },
        {
            'command': 'qzx analyzeComplexity "src/components" -r',
            'description': 'Recursively analyze all code files in a directory'
        },
        {
            'command': 'qzx analyzeComplexity "project/" -r2 "summary"',
            'description': 'Generate a summary report analyzing up to 2 levels deep'
        }
    ]
    
    # File extensions to analyze
    SUPPORTED_EXTENSIONS = {
        '.py': 'python',
        '.js': 'javascript',
        '.jsx': 'javascript',
        '.ts': 'typescript',
        '.tsx': 'typescript',
        '.java': 'java',
        '.c': 'c',
        '.cpp': 'cpp',
        '.h': 'c',
        '.hpp': 'cpp',
        '.cs': 'csharp',
        '.php': 'php',
        '.rb': 'ruby',
        '.go': 'go',
        '.rs': 'rust'
    }
    
    def execute(self, file_path, recursive=False, format='detailed'):
        """
        Analyzes code complexity of files or directories
        
        Args:
            file_path: Path to file or directory to analyze
            recursive: Whether to recursively analyze directories: -r/--recursive for unlimited, -rN/--recursiveN for N levels
            format: Output format (detailed or summary)
            
        Returns:
            Analysis results as string
        """
        # Check if path exists
        if not os.path.exists(file_path):
            return f"Error: Path '{file_path}' does not exist"
        
        results = []
        total_files = 0
        analyzed_files = 0
        
        # Process flags in command arguments if they exist
        import sys
        args = sys.argv
        recursive_flags = ['-r', '-R', '--recursive']
        recursive_found = any(flag in args for flag in recursive_flags)
        
        # Parse recursive parameter - convert string flags
        if isinstance(recursive, str):
            recursive = parse_recursive_parameter(recursive)
        elif recursive_found:
            recursive = True
        elif recursive is True:
            # Boolean True means unlimited recursion
            recursive = None
        
        # Process a single file
        if os.path.isfile(file_path):
            analysis = self._analyze_file(file_path)
            if analysis:
                analyzed_files += 1
                results.append(analysis)
            total_files = 1
        
        # Process a directory
        elif os.path.isdir(file_path):
            # Set up a callback to analyze each found file
            def analyze_callback(file_path):
                nonlocal total_files, analyzed_files
                total_files += 1
                analysis = self._analyze_file(file_path)
                if analysis:
                    analyzed_files += 1
                    results.append(analysis)
                return True
            
            # Create a filter function to only process supported file types
            def file_filter(path):
                _, ext = os.path.splitext(path)
                return ext.lower() in self.SUPPORTED_EXTENSIONS
            
            # Use the centralized find_files function
            find_files(
                file_path,
                recursive=recursive,
                file_callback=analyze_callback,
                file_filter=file_filter
            )
        
        # Format and return results
        if not results:
            return f"No analyzable files found in '{file_path}'"
        
        return self._format_results(results, total_files, analyzed_files, format)
    
    def _analyze_file(self, file_path):
        """
        Analyzes a single file for complexity metrics
        
        Args:
            file_path: Path to the file to analyze
            
        Returns:
            Dict with analysis results or None if file can't be analyzed
        """
        # Check if file type is supported
        _, ext = os.path.splitext(file_path)
        if ext.lower() not in self.SUPPORTED_EXTENSIONS:
            return None
        
        language = self.SUPPORTED_EXTENSIONS[ext.lower()]
        
        try:
            # Read file content
            with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
                content = f.read()
            
            # Get basic metrics
            metrics = {
                'file_path': file_path,
                'language': language,
                'size_bytes': os.path.getsize(file_path),
                'line_count': content.count('\n') + 1,
                'character_count': len(content)
            }
            
            # Get language-specific metrics
            metrics.update(self._get_language_metrics(content, language))
            
            # Calculate complexity score
            metrics['complexity_score'] = self._calculate_complexity_score(metrics)
            
            return metrics
        except Exception as e:
            return {
                'file_path': file_path,
                'language': language,
                'error': str(e)
            }
    
    def _get_language_metrics(self, content, language):
        """
        Gets language-specific metrics for code
        
        Args:
            content: File content
            language: Programming language
            
        Returns:
            Dict with language-specific metrics
        """
        metrics = {
            'comment_count': 0,
            'function_count': 0,
            'class_count': 0,
            'condition_count': 0,
            'loop_count': 0,
            'avg_line_length': 0,
            'max_line_length': 0,
            'cyclomatic_complexity': 1,  # Base complexity
            'halstead_metrics': {},
            'maintainability_index': 0
        }
        
        # Count non-empty lines
        lines = [line for line in content.split('\n') if line.strip()]
        metrics['non_empty_lines'] = len(lines)
        
        if not lines:
            return metrics
        
        # Calculate line length metrics
        line_lengths = [len(line) for line in lines]
        metrics['avg_line_length'] = sum(line_lengths) / len(line_lengths)
        metrics['max_line_length'] = max(line_lengths)
        
        # Python-specific analysis
        if language == 'python':
            return self._analyze_python(content, metrics)
        
        # JavaScript/TypeScript analysis
        elif language in ['javascript', 'typescript']:
            return self._analyze_js_ts(content, metrics)
        
        # Generic analysis for other languages
        else:
            return self._analyze_generic(content, metrics, language)
    
    def _analyze_python(self, content, metrics):
        """
        Analyzes Python code metrics
        
        Args:
            content: File content
            metrics: Metrics dictionary to update
            
        Returns:
            Updated metrics dictionary
        """
        try:
            # Parse Python code
            tree = ast.parse(content)
            
            # Count functions and classes
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef) or isinstance(node, ast.AsyncFunctionDef):
                    metrics['function_count'] += 1
                    
                    # Count conditions and loops within function
                    for child in ast.walk(node):
                        if isinstance(child, (ast.If, ast.IfExp)):
                            metrics['condition_count'] += 1
                            metrics['cyclomatic_complexity'] += 1
                        elif isinstance(child, (ast.For, ast.AsyncFor, ast.While)):
                            metrics['loop_count'] += 1
                            metrics['cyclomatic_complexity'] += 1
                        elif isinstance(child, ast.BoolOp):
                            # Each boolean operator (and, or) adds complexity
                            metrics['cyclomatic_complexity'] += len(child.values) - 1
                
                elif isinstance(node, ast.ClassDef):
                    metrics['class_count'] += 1
            
            # Count comments (approximate)
            comment_pattern = r'^\s*#.*$'
            metrics['comment_count'] = len(re.findall(comment_pattern, content, re.MULTILINE))
            
            # Calculate Halstead metrics
            metrics['halstead_metrics'] = self._calculate_halstead_metrics(content, 'python')
            
            # Calculate maintainability index
            metrics['maintainability_index'] = self._calculate_maintainability_index(
                metrics['cyclomatic_complexity'],
                metrics['halstead_metrics'].get('volume', 0),
                metrics['line_count']
            )
            
            return metrics
        except SyntaxError:
            # If unable to parse, fall back to generic analysis
            return self._analyze_generic(content, metrics, 'python')
    
    def _analyze_js_ts(self, content, metrics):
        """
        Analyzes JavaScript/TypeScript code metrics
        
        Args:
            content: File content
            metrics: Metrics dictionary to update
            
        Returns:
            Updated metrics dictionary
        """
        # Count functions
        function_patterns = [
            r'function\s+\w+\s*\(',  # Named functions
            r'const\s+\w+\s*=\s*function',  # Function expressions
            r'const\s+\w+\s*=\s*\([^)]*\)\s*=>',  # Arrow functions
            r'\w+\s*:\s*function',  # Object methods
        ]
        for pattern in function_patterns:
            metrics['function_count'] += len(re.findall(pattern, content))
        
        # Count classes
        class_pattern = r'class\s+\w+'
        metrics['class_count'] = len(re.findall(class_pattern, content))
        
        # Count conditionals
        condition_patterns = [r'\bif\s*\(', r'\bswitch\s*\(', r'\?']
        for pattern in condition_patterns:
            count = len(re.findall(pattern, content))
            metrics['condition_count'] += count
            metrics['cyclomatic_complexity'] += count
        
        # Count loops
        loop_patterns = [r'\bfor\s*\(', r'\bwhile\s*\(', r'\bdo\s*\{']
        for pattern in loop_patterns:
            count = len(re.findall(pattern, content))
            metrics['loop_count'] += count
            metrics['cyclomatic_complexity'] += count
        
        # Count boolean operators
        bool_op_count = len(re.findall(r'&&|\|\|', content))
        metrics['cyclomatic_complexity'] += bool_op_count
        
        # Count comments
        comment_patterns = [r'\/\/.*$', r'\/\*[\s\S]*?\*\/']
        for pattern in comment_patterns:
            metrics['comment_count'] += len(re.findall(pattern, content, re.MULTILINE))
        
        # Calculate Halstead metrics
        metrics['halstead_metrics'] = self._calculate_halstead_metrics(content, 'javascript')
        
        # Calculate maintainability index
        metrics['maintainability_index'] = self._calculate_maintainability_index(
            metrics['cyclomatic_complexity'],
            metrics['halstead_metrics'].get('volume', 0),
            metrics['line_count']
        )
        
        return metrics
    
    def _analyze_generic(self, content, metrics, language):
        """
        Performs generic code analysis for unsupported languages
        
        Args:
            content: File content
            metrics: Metrics dictionary to update
            language: Programming language
            
        Returns:
            Updated metrics dictionary
        """
        # Generic patterns for various languages
        patterns = {
            'function': {
                'python': r'def\s+\w+\s*\(',
                'javascript': r'function\s+\w+|const\s+\w+\s*=\s*function|\w+\s*:\s*function|\([^)]*\)\s*=>',
                'typescript': r'function\s+\w+|const\s+\w+\s*=\s*function|\w+\s*:\s*function|\([^)]*\)\s*=>',
                'java': r'(public|private|protected|static|\s) +[\w\<\>\[\]]+\s+(\w+) *\([^\)]*\)',
                'c': r'\w+\s+\w+\s*\([^;]*\)\s*\{',
                'cpp': r'[\w\<\>\[\]]+\s+\w+\s*\([^;]*\)\s*\{',
                'csharp': r'(public|private|protected|static|\s) +[\w\<\>\[\]]+\s+(\w+) *\([^\)]*\)',
                'php': r'function\s+\w+\s*\(',
                'ruby': r'def\s+\w+',
                'go': r'func\s+\w+',
                'rust': r'fn\s+\w+'
            },
            'class': {
                'python': r'class\s+\w+',
                'javascript': r'class\s+\w+',
                'typescript': r'class\s+\w+|interface\s+\w+',
                'java': r'class\s+\w+|interface\s+\w+',
                'cpp': r'class\s+\w+',
                'csharp': r'class\s+\w+|interface\s+\w+',
                'php': r'class\s+\w+',
                'ruby': r'class\s+\w+',
                'rust': r'struct\s+\w+|enum\s+\w+|trait\s+\w+'
            },
            'condition': {
                'generic': r'\bif\s*\(|\bswitch\s*\(|\?|else\s+if'
            },
            'loop': {
                'generic': r'\bfor\s*\(|\bwhile\s*\(|\bdo\s*\{|\bforeach'
            },
            'comment': {
                'python': r'#.*$',
                'c_style': r'\/\/.*$|\/\*[\s\S]*?\*\/',
                'ruby': r'#.*$',
            }
        }
        
        # Count functions
        func_pattern = patterns['function'].get(language, r'\b\w+\s+\w+\s*\(')
        metrics['function_count'] = len(re.findall(func_pattern, content, re.MULTILINE))
        
        # Count classes
        class_pattern = patterns['class'].get(language, r'class\s+\w+')
        metrics['class_count'] = len(re.findall(class_pattern, content, re.MULTILINE))
        
        # Count conditions and update cyclomatic complexity
        condition_count = len(re.findall(patterns['condition']['generic'], content))
        metrics['condition_count'] = condition_count
        metrics['cyclomatic_complexity'] += condition_count
        
        # Count loops and update cyclomatic complexity
        loop_count = len(re.findall(patterns['loop']['generic'], content))
        metrics['loop_count'] = loop_count
        metrics['cyclomatic_complexity'] += loop_count
        
        # Count comments
        if language == 'python' or language == 'ruby':
            comment_pattern = patterns['comment']['python']
        else:
            comment_pattern = patterns['comment']['c_style']
        
        metrics['comment_count'] = len(re.findall(comment_pattern, content, re.MULTILINE))
        
        # Approximate Halstead metrics
        metrics['halstead_metrics'] = self._calculate_halstead_metrics(content, language)
        
        # Calculate maintainability index
        metrics['maintainability_index'] = self._calculate_maintainability_index(
            metrics['cyclomatic_complexity'],
            metrics['halstead_metrics'].get('volume', 0),
            metrics['line_count']
        )
        
        return metrics
    
    def _calculate_halstead_metrics(self, content, language):
        """
        Calculates Halstead complexity metrics
        
        Args:
            content: File content
            language: Programming language
            
        Returns:
            Dict with Halstead metrics
        """
        # Define operators and operands based on language
        operators = {
            'python': ['+', '-', '*', '/', '%', '**', '//', '=', '+=', '-=', '*=', '/=', '%=', '**=', '//=', 
                      '==', '!=', '>', '<', '>=', '<=', 'and', 'or', 'not', 'in', 'is', 'lambda'],
            'javascript': ['+', '-', '*', '/', '%', '**', '=', '+=', '-=', '*=', '/=', '%=', '**=',
                           '==', '===', '!=', '!==', '>', '<', '>=', '<=', '&&', '||', '!', 'typeof', 'instanceof']
        }
        
        # Get appropriate operators or use a generic set
        op_list = operators.get(language, operators['javascript'])
        
        # Count unique operators
        n1 = len(set(re.findall('|'.join(re.escape(op) for op in op_list), content)))
        if n1 == 0:
            n1 = 1  # Avoid division by zero
        
        # Count total operators
        N1 = len(re.findall('|'.join(re.escape(op) for op in op_list), content))
        
        # Approximate unique operands (identifiers and literals)
        identifier_pattern = r'\b[a-zA-Z_]\w*\b'
        string_literal_pattern = r'"[^"]*"|\'[^\']*\''
        number_pattern = r'\b\d+(\.\d+)?\b'
        
        identifiers = set(re.findall(identifier_pattern, content))
        strings = set(re.findall(string_literal_pattern, content))
        numbers = set(re.findall(number_pattern, content))
        
        # Remove keywords from identifiers based on language
        keywords = {
            'python': ['def', 'class', 'if', 'else', 'elif', 'for', 'while', 'try', 'except', 'finally',
                       'with', 'as', 'import', 'from', 'return', 'yield', 'break', 'continue', 'pass',
                       'True', 'False', 'None'],
            'javascript': ['function', 'class', 'if', 'else', 'for', 'while', 'try', 'catch', 'finally',
                           'with', 'switch', 'case', 'default', 'break', 'continue', 'return', 'throw',
                           'typeof', 'instanceof', 'new', 'this', 'super', 'true', 'false', 'null', 'undefined']
        }
        
        lang_keywords = keywords.get(language, keywords['javascript'])
        identifiers = identifiers - set(lang_keywords)
        
        n2 = len(identifiers) + len(strings) + len(numbers)
        if n2 == 0:
            n2 = 1  # Avoid division by zero
        
        # Count total operands (approximate)
        N2 = len(re.findall(identifier_pattern, content)) + len(re.findall(string_literal_pattern, content)) + len(re.findall(number_pattern, content))
        
        # Calculate metrics
        N = N1 + N2
        n = n1 + n2
        
        # Calculate volume
        volume = N * math.log2(n) if n > 0 else 0
        
        # Calculate difficulty
        difficulty = (n1 / 2) * (N2 / n2) if n2 > 0 else 0
        
        # Calculate effort
        effort = difficulty * volume
        
        return {
            'unique_operators': n1,
            'unique_operands': n2,
            'total_operators': N1,
            'total_operands': N2,
            'vocabulary': n,
            'length': N,
            'volume': volume,
            'difficulty': difficulty,
            'effort': effort
        }
    
    def _calculate_maintainability_index(self, cyclomatic_complexity, halstead_volume, line_count):
        """
        Calculates the Maintainability Index
        
        Args:
            cyclomatic_complexity: Cyclomatic complexity
            halstead_volume: Halstead volume
            line_count: Number of lines of code
            
        Returns:
            Maintainability Index (0-100)
        """
        # Original formula: 171 - 5.2 * ln(V) - 0.23 * G - 16.2 * ln(LOC)
        # Normalized to 0-100 scale
        
        if halstead_volume <= 0 or line_count <= 0:
            return 100  # Perfect score for empty files
        
        mi = 171 - 5.2 * math.log(halstead_volume) - 0.23 * cyclomatic_complexity - 16.2 * math.log(line_count)
        
        # Normalize to 0-100
        normalized_mi = max(0, min(100, mi * 100 / 171))
        
        return normalized_mi
    
    def _calculate_complexity_score(self, metrics):
        """
        Calculates an overall complexity score based on multiple metrics
        
        Args:
            metrics: Dictionary of code metrics
            
        Returns:
            Complexity score from 0-10
        """
        # Define weights for each metric
        weights = {
            'cyclomatic_complexity': 0.3,
            'halstead_effort': 0.2,
            'line_count': 0.1,
            'function_count': 0.1,
            'class_count': 0.1,
            'maintainability': 0.2
        }
        
        # Normalize metrics to 0-10 scale
        normalized = {
            'cyclomatic_complexity': min(10, metrics['cyclomatic_complexity'] / 5),
            'halstead_effort': min(10, metrics['halstead_metrics'].get('effort', 0) / 10000),
            'line_count': min(10, metrics['line_count'] / 300),
            'function_count': min(10, metrics['function_count'] / 20),
            'class_count': min(10, metrics['class_count'] / 10),
            'maintainability': 10 - (metrics['maintainability_index'] / 10)
        }
        
        # Calculate weighted score
        score = 0
        for key, weight in weights.items():
            score += normalized[key] * weight
        
        return score
    
    def _format_results(self, results, total_files, analyzed_files, format_type):
        """
        Formats the analysis results
        
        Args:
            results: List of analysis results
            total_files: Total number of files found
            analyzed_files: Number of files successfully analyzed
            format_type: Output format type (detailed or summary)
            
        Returns:
            Formatted analysis results as string
        """
        # Sort results by complexity score (descending)
        results.sort(key=lambda x: x.get('complexity_score', 0), reverse=True)
        
        if format_type.lower() == 'summary':
            return self._format_summary(results, total_files, analyzed_files)
        else:
            return self._format_detailed(results, total_files, analyzed_files)
    
    def _format_detailed(self, results, total_files, analyzed_files):
        """
        Formats results in detailed format
        
        Args:
            results: List of analysis results
            total_files: Total number of files found
            analyzed_files: Number of files successfully analyzed
            
        Returns:
            Detailed formatted analysis results
        """
        output = [
            "Code Complexity Analysis Report (Detailed)",
            "=" * 50,
            f"Files Analyzed: {analyzed_files}/{total_files}",
            ""
        ]
        
        for i, result in enumerate(results, 1):
            # Skip files with errors
            if 'error' in result:
                output.append(f"File {i}: {result['file_path']}")
                output.append(f"Error: {result['error']}")
                output.append("")
                continue
            
            # Add file info
            output.append(f"File {i}: {result['file_path']}")
            output.append(f"Language: {result['language']}")
            output.append(f"Complexity Score: {result['complexity_score']:.2f}/10")
            
            # Complexity classification
            score = result['complexity_score']
            if score < 2:
                complexity = "Very Low"
            elif score < 4:
                complexity = "Low"
            elif score < 6:
                complexity = "Moderate"
            elif score < 8:
                complexity = "High"
            else:
                complexity = "Very High"
            
            output.append(f"Complexity Rating: {complexity}")
            
            # Add basic metrics
            output.append("")
            output.append("Basic Metrics:")
            output.append(f"- Lines of Code: {result['line_count']}")
            output.append(f"- Non-Empty Lines: {result.get('non_empty_lines', 'N/A')}")
            output.append(f"- File Size: {result['size_bytes']} bytes")
            output.append(f"- Average Line Length: {result['avg_line_length']:.2f} characters")
            output.append(f"- Maximum Line Length: {result['max_line_length']} characters")
            
            # Add structural metrics
            output.append("")
            output.append("Structural Metrics:")
            output.append(f"- Functions/Methods: {result['function_count']}")
            output.append(f"- Classes/Interfaces: {result['class_count']}")
            output.append(f"- Conditional Statements: {result['condition_count']}")
            output.append(f"- Loops: {result['loop_count']}")
            output.append(f"- Comments: {result['comment_count']}")
            
            # Add complexity metrics
            output.append("")
            output.append("Complexity Metrics:")
            output.append(f"- Cyclomatic Complexity: {result['cyclomatic_complexity']}")
            output.append(f"- Maintainability Index: {result['maintainability_index']:.2f}/100")
            
            # Add Halstead metrics
            halstead = result['halstead_metrics']
            output.append("")
            output.append("Halstead Metrics:")
            output.append(f"- Vocabulary: {halstead.get('vocabulary', 'N/A')}")
            output.append(f"- Length: {halstead.get('length', 'N/A')}")
            output.append(f"- Volume: {halstead.get('volume', 'N/A'):.2f}")
            output.append(f"- Difficulty: {halstead.get('difficulty', 'N/A'):.2f}")
            output.append(f"- Effort: {halstead.get('effort', 'N/A'):.2f}")
            
            # Add recommendations
            output.append("")
            output.append("Recommendations:")
            
            if result['complexity_score'] >= 7:
                output.append("- Consider refactoring complex sections into smaller functions")
                output.append("- Reduce nesting levels in conditional statements")
                
            if result['function_count'] > 0 and result['comment_count'] / result['function_count'] < 0.5:
                output.append("- Add more comments to improve code documentation")
                
            if result['avg_line_length'] > 80:
                output.append("- Reduce average line length for better readability")
                
            if result['max_line_length'] > 100:
                output.append("- Break up long lines of code")
                
            if result['maintainability_index'] < 65:
                output.append("- Improve maintainability by simplifying complex methods")
            
            # Separator between files
            output.append("")
            output.append("-" * 50)
            output.append("")
        
        # Add overall summary
        output.append("")
        output.append("Overall Summary:")
        
        if results:
            avg_complexity = sum(r.get('complexity_score', 0) for r in results) / len(results)
            avg_maintainability = sum(r.get('maintainability_index', 0) for r in results if 'maintainability_index' in r) / len([r for r in results if 'maintainability_index' in r]) if any('maintainability_index' in r for r in results) else 0
            
            output.append(f"- Average Complexity Score: {avg_complexity:.2f}/10")
            output.append(f"- Average Maintainability Index: {avg_maintainability:.2f}/100")
            
            # Most complex file
            most_complex = max(results, key=lambda x: x.get('complexity_score', 0))
            output.append(f"- Most Complex File: {most_complex['file_path']} (Score: {most_complex['complexity_score']:.2f})")
        
        return "\n".join(output)
    
    def _format_summary(self, results, total_files, analyzed_files):
        """
        Formats results in summary format
        
        Args:
            results: List of analysis results
            total_files: Total number of files found
            analyzed_files: Number of files successfully analyzed
            
        Returns:
            Summary formatted analysis results
        """
        output = [
            "Code Complexity Analysis Report (Summary)",
            "=" * 50,
            f"Files Analyzed: {analyzed_files}/{total_files}",
            ""
        ]
        
        # Calculate overall metrics
        if results:
            total_loc = sum(r.get('line_count', 0) for r in results)
            total_functions = sum(r.get('function_count', 0) for r in results)
            total_classes = sum(r.get('class_count', 0) for r in results)
            
            avg_complexity = sum(r.get('complexity_score', 0) for r in results) / len(results)
            avg_cyclomatic = sum(r.get('cyclomatic_complexity', 0) for r in results) / len(results)
            avg_maintainability = sum(r.get('maintainability_index', 0) for r in results if 'maintainability_index' in r) / len([r for r in results if 'maintainability_index' in r]) if any('maintainability_index' in r for r in results) else 0
            
            # Add overall metrics
            output.append("Overall Metrics:")
            output.append(f"- Total Lines of Code: {total_loc}")
            output.append(f"- Total Functions/Methods: {total_functions}")
            output.append(f"- Total Classes/Interfaces: {total_classes}")
            output.append(f"- Average Complexity Score: {avg_complexity:.2f}/10")
            output.append(f"- Average Cyclomatic Complexity: {avg_cyclomatic:.2f}")
            output.append(f"- Average Maintainability Index: {avg_maintainability:.2f}/100")
            output.append("")
            
            # Distribution by complexity
            low = len([r for r in results if r.get('complexity_score', 0) < 4])
            medium = len([r for r in results if 4 <= r.get('complexity_score', 0) < 7])
            high = len([r for r in results if r.get('complexity_score', 0) >= 7])
            
            output.append("Complexity Distribution:")
            output.append(f"- Low Complexity (0-3.99): {low} files ({low/len(results)*100:.1f}%)")
            output.append(f"- Medium Complexity (4-6.99): {medium} files ({medium/len(results)*100:.1f}%)")
            output.append(f"- High Complexity (7-10): {high} files ({high/len(results)*100:.1f}%)")
            output.append("")
            
            # Top 5 most complex files
            output.append("Top 5 Most Complex Files:")
            
            for i, result in enumerate(results[:5], 1):
                score = result.get('complexity_score', 0)
                cyclomatic = result.get('cyclomatic_complexity', 'N/A')
                maintainability = result.get('maintainability_index', 'N/A')
                
                if isinstance(maintainability, (int, float)):
                    maintainability = f"{maintainability:.2f}/100"
                
                output.append(f"{i}. {result['file_path']}")
                output.append(f"   Score: {score:.2f}/10, Cyclomatic: {cyclomatic}, Maintainability: {maintainability}")
                
                # Add specific recommendations for top files
                if score >= 7:
                    output.append("   Recommendation: Consider refactoring into smaller components")
                elif cyclomatic != 'N/A' and cyclomatic > 10:
                    output.append("   Recommendation: Reduce complexity by simplifying conditional logic")
            
            # Add general recommendations
            output.append("")
            output.append("General Recommendations:")
            
            if high > 0:
                output.append("- Refactor highly complex files to improve maintainability")
            
            if avg_maintainability < 65:
                output.append("- Improve documentation and code structure to increase maintainability")
            
            if avg_cyclomatic > 15:
                output.append("- Reduce conditional logic complexity by extracting methods")
            
            if high / len(results) > 0.3:
                output.append("- Consider a code quality review process for complex components")
        
        return "\n".join(output) 