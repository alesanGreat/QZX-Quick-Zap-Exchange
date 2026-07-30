#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
CreateDocTemplatePython Command - Generates documentation templates for Python code
"""

import os
import re
import ast
import inspect
import stat
import tempfile
from typing import List, Dict, Any, Tuple

from qzx.core.command_base import CommandBase


class CreateDocTemplatePythonCommand(CommandBase):
    """
    Command to generate documentation templates for Python code
    """
    
    name = "createDocTemplatePython"
    description = (
        "Previews or adds generated docstring templates to functions, methods, "
        "and classes in one Python file"
    )
    category = "development"
    requires_explicit_approval = True
    backup_target_parameter = "file_path"

    parameters = [
        {
            'name': 'file_path',
            'description': 'Path to the Python file to process',
            'required': True,
            'type': 'str',
        },
        {
            'name': 'style',
            'description': 'Documentation style (google, numpy, sphinx)',
            'required': False,
            'default': 'google',
            'type': 'str',
        },
        {
            'name': 'overwrite',
            'description': 'Whether to overwrite existing docstrings',
            'required': False,
            'default': False,
            'type': 'bool',
        },
        {
            'name': 'preview',
            'description': 'Compatibility option: preview changes without modifying the file',
            'required': False,
            'default': None,
            'type': 'bool',
        },
        {
            'name': 'dry_run',
            'description': 'Preview changes without modifying the file',
            'required': False,
            'default': True,
            'type': 'bool',
        }
    ]

    examples = [
        {
            'command': 'qzx createDocTemplatePython myfile.py',
            'description': 'Preview Google-style docstring templates for myfile.py'
        },
        {
            'command': 'qzx createDocTemplatePython myfile.py sphinx',
            'description': 'Preview Sphinx-style docstring templates for myfile.py'
        },
        {
            'command': 'qzx createDocTemplatePython myfile.py --dry-run false',
            'description': 'Back up myfile.py, then add missing Google-style docstrings'
        },
        {
            'command': 'qzx createDocTemplatePython myfile.py --overwrite --dry-run false',
            'description': 'Back up myfile.py, then replace existing docstrings'
        }
    ]

    def _requested_high_risk_mutation(self, values):
        """Treat the legacy preview flag and the canonical dry-run alike."""
        preview = values.get("preview")
        if preview is not None:
            parsed_preview = self._parse_bool(preview)
            if parsed_preview is not None:
                return not parsed_preview
        return not bool(values.get("dry_run", True))

    def validate_safety_backup_target(self, target, values):
        """Require one existing regular Python source file."""
        return self._validate_file_path(target, preview=False)

    def execute(
        self,
        file_path,
        style='google',
        overwrite=False,
        preview=None,
        dry_run=True,
    ):
        """
        Generates documentation templates for Python code
        
        Args:
            file_path (str): Path to the Python file to process
            style (str, optional): Documentation style (google, numpy, sphinx)
            overwrite (bool, optional): Whether to overwrite existing docstrings
            preview (bool, optional): Legacy preview switch
            dry_run (bool, optional): Preview changes without modifying the file
            
        Returns:
            Dictionary with the result of the operation
        """
        try:
            absolute_path = os.path.abspath(os.fspath(file_path))
            path_failure = self._validate_file_path(
                absolute_path,
                preview=True,
            )
            if path_failure is not None:
                return path_failure

            style = str(style).strip().lower()
            if style not in {'google', 'numpy', 'sphinx'}:
                return self._error_result(
                    "invalid_style",
                    (
                        f"Invalid style '{style}'. Choose google, numpy, or "
                        "sphinx."
                    ),
                    absolute_path,
                )

            overwrite_value = self._strict_bool(overwrite)
            if overwrite_value is None:
                return self._error_result(
                    "invalid_overwrite",
                    f"overwrite must be true or false, got {overwrite!r}.",
                    absolute_path,
                )
            dry_run_value = self._strict_bool(dry_run)
            if dry_run_value is None:
                return self._error_result(
                    "invalid_dry_run",
                    f"dry_run must be true or false, got {dry_run!r}.",
                    absolute_path,
                )
            preview_value = None
            if preview is not None:
                preview_value = self._strict_bool(preview)
                if preview_value is None:
                    return self._error_result(
                        "invalid_preview",
                        f"preview must be true or false, got {preview!r}.",
                        absolute_path,
                    )
            effective_preview = (
                preview_value
                if preview_value is not None
                else dry_run_value
            )
            live_path_failure = self._validate_file_path(
                absolute_path,
                preview=effective_preview,
            )
            if live_path_failure is not None:
                return live_path_failure

            with open(
                absolute_path,
                'r',
                encoding='utf-8',
                newline='',
            ) as f:
                content = f.read()

            try:
                tree = ast.parse(content)
            except SyntaxError as exc:
                result = self._error_result(
                    "invalid_python_syntax",
                    f"Python syntax error: {exc}",
                    absolute_path,
                )
                result["details"].update({
                    "line": exc.lineno,
                    "offset": exc.offset,
                })
                return result

            visitor = DocstringVisitor(content, style, overwrite_value)
            visitor.visit(tree)
            new_content = visitor.get_modified_content()
            new_content = self._preserve_file_endings(content, new_content)

            stats = {
                "functions_processed": visitor.stats["functions_processed"],
                "functions_updated": visitor.stats["functions_updated"],
                "classes_processed": visitor.stats["classes_processed"],
                "classes_updated": visitor.stats["classes_updated"],
                "methods_processed": visitor.stats["methods_processed"],
                "methods_updated": visitor.stats["methods_updated"]
            }

            changes_preview = (
                visitor.get_changes_preview()
                if visitor.updates
                else []
            )
            changes_detected = content != new_content
            changes_applied = False
            if not effective_preview and changes_detected:
                self._atomic_write_text(absolute_path, new_content)
                changes_applied = True

            result = {
                "success": True,
                "status": (
                    "preview"
                    if effective_preview
                    else ("updated" if changes_applied else "unchanged")
                ),
                "file_path": absolute_path,
                "style": style,
                "overwrite": overwrite_value,
                "preview": effective_preview,
                "dry_run": effective_preview,
                "stats": stats,
                "changes_detected": changes_detected,
                "changes_applied": changes_applied,
                "changes_made": changes_applied,
                "changes_preview": changes_preview
            }

            if effective_preview:
                if changes_preview:
                    result["message"] = (
                        f"Previewed {len(changes_preview)} docstring change(s) "
                        f"for '{absolute_path}'. Nothing was written."
                    )
                else:
                    result["message"] = (
                        f"No docstring templates are needed for "
                        f"'{absolute_path}'."
                    )
            else:
                if changes_applied:
                    result["message"] = (
                        f"Applied {len(changes_preview)} docstring change(s) "
                        f"atomically to '{absolute_path}'."
                    )
                else:
                    result["message"] = (
                        f"No docstring templates were needed for "
                        f"'{absolute_path}'; the file was not rewritten."
                    )

            return result

        except Exception as exc:
            return {
                "success": False,
                "error_code": "docstring_generation_failed",
                "file_path": os.path.abspath(os.fspath(file_path)),
                "error": f"{type(exc).__name__}: {exc}",
                "message": (
                    f"Could not generate docstring templates for "
                    f"'{file_path}': {exc}"
                ),
            }

    @staticmethod
    def _strict_bool(value):
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            normalized = value.strip().lower()
            if normalized in {"true", "yes", "y", "1", "on"}:
                return True
            if normalized in {"false", "no", "n", "0", "off"}:
                return False
        return None

    @classmethod
    def _validate_file_path(cls, file_path, preview):
        absolute_path = os.path.abspath(os.fspath(file_path))
        if not os.path.lexists(absolute_path):
            return cls._error_result(
                "file_not_found",
                f"File '{absolute_path}' does not exist.",
                absolute_path,
            )
        if os.path.islink(absolute_path):
            return cls._error_result(
                "symbolic_link_refused",
                (
                    f"File '{absolute_path}' is a symbolic link. QZX refuses "
                    "to replace an ambiguous target."
                ),
                absolute_path,
            )
        if not os.path.isfile(absolute_path):
            return cls._error_result(
                "path_not_file",
                f"Path '{absolute_path}' is not a regular file.",
                absolute_path,
            )
        if not absolute_path.lower().endswith('.py'):
            return cls._error_result(
                "not_python_file",
                f"File '{absolute_path}' does not have a .py extension.",
                absolute_path,
            )
        if not preview and not os.access(absolute_path, os.W_OK):
            return cls._error_result(
                "file_not_writable",
                f"File '{absolute_path}' is not writable.",
                absolute_path,
            )
        return None

    @staticmethod
    def _error_result(error_code, message, file_path):
        return {
            "success": False,
            "error_code": error_code,
            "error": message,
            "message": message,
            "details": {"file_path": file_path},
        }

    @staticmethod
    def _preserve_file_endings(original, generated):
        newline = '\r\n' if '\r\n' in original else '\n'
        if newline != '\n':
            generated = generated.replace('\n', newline)
        had_terminal_newline = original.endswith(('\n', '\r'))
        if had_terminal_newline and not generated.endswith(newline):
            generated += newline
        return generated

    @staticmethod
    def _atomic_write_text(file_path, content):
        """Replace one file from a fully written sibling temporary file."""
        original_mode = stat.S_IMODE(os.stat(file_path).st_mode)
        directory = os.path.dirname(file_path) or os.curdir
        descriptor, temporary_path = tempfile.mkstemp(
            dir=directory,
            prefix=f".{os.path.basename(file_path)}.qzx-",
            suffix=".tmp",
        )
        try:
            with os.fdopen(
                descriptor,
                'w',
                encoding='utf-8',
                newline='',
            ) as temporary:
                descriptor = None
                temporary.write(content)
                temporary.flush()
                os.fsync(temporary.fileno())
            os.chmod(temporary_path, original_mode)
            os.replace(temporary_path, file_path)
        except Exception:
            if descriptor is not None:
                os.close(descriptor)
            if os.path.exists(temporary_path):
                os.unlink(temporary_path)
            raise


class DocstringVisitor(ast.NodeVisitor):
    """
    AST visitor to process functions and classes and add docstrings
    """
    
    def __init__(self, content, style, overwrite):
        """
        Initialize the visitor
        
        Args:
            content (str): Original file content
            style (str): Documentation style
            overwrite (bool): Whether to overwrite existing docstrings
        """
        self.content = content
        self.style = style
        self.overwrite = overwrite
        self.lines = content.splitlines()
        self.updates = []  # List of (start_line, end_line, docstring) tuples
        self.stats = {
            "functions_processed": 0,
            "functions_updated": 0,
            "classes_processed": 0,
            "classes_updated": 0,
            "methods_processed": 0,
            "methods_updated": 0
        }
    
    def visit_FunctionDef(self, node):
        """
        Visit a function definition and add docstring if needed
        
        Args:
            node (ast.FunctionDef): Function node
        """
        # Track whether this is a method or a function
        is_method = False
        for ancestor in self.get_ancestors(node):
            if isinstance(ancestor, ast.ClassDef):
                is_method = True
                break
        
        # Update statistics
        if is_method:
            self.stats["methods_processed"] += 1
        else:
            self.stats["functions_processed"] += 1
        
        # Check if function already has a docstring
        has_docstring = ast.get_docstring(node) is not None
        
        # If it has a docstring and we're not overwriting, skip
        if has_docstring and not self.overwrite:
            return
        
        # Get function details
        func_name = node.name
        args = self._get_function_args(node)
        returns = self._get_function_returns(node)
        
        # Generate docstring
        docstring = self._generate_function_docstring(func_name, args, returns)
        
        # Find where to insert the docstring
        line_num = node.body[0].lineno - 1 if node.body else node.lineno
        current_indent = self._get_indent(self.lines[node.lineno - 1])
        
        # If there's an existing docstring, get its start and end lines
        if has_docstring:
            # Find the first non-docstring node in the body
            for i, item in enumerate(node.body):
                if not isinstance(item, ast.Expr) or not isinstance(item.value, ast.Str):
                    break
            # The docstring is everything before that node
            start_line = node.lineno
            end_line = node.body[i].lineno - 1 if i < len(node.body) else node.body[-1].lineno
            # Add the update
            self.updates.append((start_line, end_line, docstring, current_indent))
        else:
            # Insert after the function definition
            self.updates.append((line_num, line_num, docstring, current_indent + "    "))
        
        # Update statistics
        if is_method:
            self.stats["methods_updated"] += 1
        else:
            self.stats["functions_updated"] += 1
        
        # Visit children
        self.generic_visit(node)
    
    def visit_ClassDef(self, node):
        """
        Visit a class definition and add docstring if needed
        
        Args:
            node (ast.ClassDef): Class node
        """
        # Update statistics
        self.stats["classes_processed"] += 1
        
        # Check if class already has a docstring
        has_docstring = ast.get_docstring(node) is not None
        
        # If it has a docstring and we're not overwriting, skip
        if has_docstring and not self.overwrite:
            # Still visit children
            self.generic_visit(node)
            return
        
        # Get class details
        class_name = node.name
        
        # Generate docstring
        docstring = self._generate_class_docstring(class_name, node)
        
        # Find where to insert the docstring
        line_num = node.body[0].lineno - 1 if node.body else node.lineno
        current_indent = self._get_indent(self.lines[node.lineno - 1])
        
        # If there's an existing docstring, get its start and end lines
        if has_docstring:
            # Find the first non-docstring node in the body
            for i, item in enumerate(node.body):
                if not isinstance(item, ast.Expr) or not isinstance(item.value, ast.Str):
                    break
            # The docstring is everything before that node
            start_line = node.lineno
            end_line = node.body[i].lineno - 1 if i < len(node.body) else node.body[-1].lineno
            # Add the update
            self.updates.append((start_line, end_line, docstring, current_indent))
        else:
            # Insert after the class definition
            self.updates.append((line_num, line_num, docstring, current_indent + "    "))
        
        # Update statistics
        self.stats["classes_updated"] += 1
        
        # Visit children
        self.generic_visit(node)
    
    def get_ancestors(self, node):
        """
        Get a list of ancestor nodes
        
        Args:
            node (ast.AST): The node to get ancestors for
            
        Returns:
            list: List of ancestor nodes
        """
        ancestors = []
        parent = getattr(node, 'parent', None)
        while parent:
            ancestors.append(parent)
            parent = getattr(parent, 'parent', None)
        return ancestors
    
    def get_modified_content(self):
        """
        Get the content with all docstrings added
        
        Returns:
            str: Modified content
        """
        # Sort updates by start line in reverse order
        self.updates.sort(key=lambda x: x[0], reverse=True)
        
        # Apply updates
        new_lines = self.lines.copy()
        for start_line, end_line, docstring, indent in self.updates:
            # Format the docstring with proper indentation
            docstring_lines = docstring.splitlines()
            indented_docstring = f'{indent}{docstring_lines[0]}\n'
            for line in docstring_lines[1:]:
                indented_docstring += f'{indent}{line}\n'
            indented_docstring = indented_docstring.rstrip()
            
            # Replace or insert the docstring
            if start_line == end_line:
                # Insert new docstring
                new_lines.insert(start_line, indented_docstring)
            else:
                # Replace existing docstring
                new_lines[start_line - 1:end_line] = [indented_docstring]
        
        return '\n'.join(new_lines)
    
    def get_changes_preview(self):
        """
        Get a preview of the changes
        
        Returns:
            list: List of changes (original, new)
        """
        result = []
        content_lines = self.content.splitlines()
        
        for start_line, end_line, docstring, indent in self.updates:
            # Get the original content
            original = "\n".join(content_lines[start_line - 1:end_line])
            
            # Format the docstring with proper indentation
            docstring_lines = docstring.splitlines()
            indented_docstring = f'{indent}{docstring_lines[0]}\n'
            for line in docstring_lines[1:]:
                indented_docstring += f'{indent}{line}\n'
            indented_docstring = indented_docstring.rstrip()
            
            # Add to result
            result.append({
                "start_line": start_line,
                "end_line": end_line,
                "original": original,
                "new": indented_docstring
            })
        
        return result
    
    def _get_indent(self, line):
        """
        Get the indentation of a line
        
        Args:
            line (str): Line to get indentation from
            
        Returns:
            str: Indentation
        """
        return re.match(r'^(\s*)', line).group(1)
    
    def _get_function_args(self, node):
        """
        Get the arguments of a function
        
        Args:
            node (ast.FunctionDef): Function node
            
        Returns:
            list: List of argument details
        """
        args = []
        
        # Process arguments
        for arg in node.args.args:
            arg_dict = {
                'name': arg.arg,
                'annotation': self._get_annotation(arg.annotation)
            }
            args.append(arg_dict)
        
        # Process vararg (e.g., *args)
        if node.args.vararg:
            args.append({
                'name': '*' + node.args.vararg.arg,
                'annotation': self._get_annotation(node.args.vararg.annotation)
            })
        
        # Process kwonlyargs (e.g., *, arg=value)
        for arg in node.args.kwonlyargs:
            arg_dict = {
                'name': arg.arg,
                'annotation': self._get_annotation(arg.annotation)
            }
            args.append(arg_dict)
        
        # Process kwarg (e.g., **kwargs)
        if node.args.kwarg:
            args.append({
                'name': '**' + node.args.kwarg.arg,
                'annotation': self._get_annotation(node.args.kwarg.annotation)
            })
        
        return args
    
    def _get_function_returns(self, node):
        """
        Get the return annotation of a function
        
        Args:
            node (ast.FunctionDef): Function node
            
        Returns:
            str: Return annotation
        """
        if node.returns:
            return self._get_annotation(node.returns)
        return None
    
    def _get_annotation(self, annotation):
        """
        Get the annotation as a string
        
        Args:
            annotation (ast.AST): Annotation node
            
        Returns:
            str: Annotation as a string
        """
        if annotation is None:
            return None
        
        if isinstance(annotation, ast.Name):
            return annotation.id
        elif isinstance(annotation, ast.Attribute):
            return self._format_attribute(annotation)
        elif isinstance(annotation, ast.Subscript):
            value = self._get_annotation(annotation.value)
            slice_value = self._get_annotation(annotation.slice)
            return f"{value}[{slice_value}]"
        elif isinstance(annotation, ast.Index):  # Python 3.8 and below
            return self._get_annotation(annotation.value)
        elif hasattr(ast, 'Constant') and isinstance(annotation, ast.Constant):  # Python 3.8+
            return str(annotation.value)
        elif isinstance(annotation, ast.Str):  # Python 3.7 and below
            return annotation.s
        elif isinstance(annotation, ast.Tuple):
            elts = [self._get_annotation(elt) for elt in annotation.elts]
            return ', '.join(elts)
        elif isinstance(annotation, ast.List):
            elts = [self._get_annotation(elt) for elt in annotation.elts]
            return f"[{', '.join(elts)}]"
        else:
            # For more complex annotations, this is a simplified representation
            return "Any"
    
    def _format_attribute(self, node):
        """
        Format an attribute node as a string
        
        Args:
            node (ast.Attribute): Attribute node
            
        Returns:
            str: Attribute as a string
        """
        if isinstance(node.value, ast.Name):
            return f"{node.value.id}.{node.attr}"
        elif isinstance(node.value, ast.Attribute):
            return f"{self._format_attribute(node.value)}.{node.attr}"
        return f"?.{node.attr}"
    
    def _generate_function_docstring(self, func_name, args, returns):
        """
        Generate a docstring for a function based on the style
        
        Args:
            func_name (str): Function name
            args (list): Function arguments
            returns (str): Return annotation
            
        Returns:
            str: Docstring
        """
        if self.style == 'google':
            return self._generate_google_function_docstring(func_name, args, returns)
        elif self.style == 'numpy':
            return self._generate_numpy_function_docstring(func_name, args, returns)
        else:  # sphinx
            return self._generate_sphinx_function_docstring(func_name, args, returns)
    
    def _generate_google_function_docstring(self, func_name, args, returns):
        """
        Generate a Google-style docstring for a function
        
        Args:
            func_name (str): Function name
            args (list): Function arguments
            returns (str): Return annotation
            
        Returns:
            str: Docstring
        """
        docstring = f'"""\n{func_name}\n\n'
        
        if args:
            docstring += 'Args:\n'
            for arg in args:
                if arg['name'].startswith('*'):
                    # For *args and **kwargs
                    name = arg['name']
                else:
                    name = arg['name']
                
                annotation = f" ({arg['annotation']})" if arg['annotation'] else ""
                docstring += f"    {name}{annotation}: Description\n"
        
        if returns:
            docstring += '\nReturns:\n'
            docstring += f"    {returns}: Description\n"
        
        docstring += '"""'
        return docstring
    
    def _generate_numpy_function_docstring(self, func_name, args, returns):
        """
        Generate a NumPy-style docstring for a function
        
        Args:
            func_name (str): Function name
            args (list): Function arguments
            returns (str): Return annotation
            
        Returns:
            str: Docstring
        """
        docstring = f'"""\n{func_name}\n\n'
        
        if args:
            docstring += 'Parameters\n----------\n'
            for arg in args:
                if arg['name'].startswith('*'):
                    # For *args and **kwargs
                    name = arg['name']
                else:
                    name = arg['name']
                
                annotation = f" : {arg['annotation']}" if arg['annotation'] else ""
                docstring += f"{name}{annotation}\n    Description\n"
        
        if returns:
            docstring += '\nReturns\n-------\n'
            docstring += f"{returns}\n    Description\n"
        
        docstring += '"""'
        return docstring
    
    def _generate_sphinx_function_docstring(self, func_name, args, returns):
        """
        Generate a Sphinx-style docstring for a function
        
        Args:
            func_name (str): Function name
            args (list): Function arguments
            returns (str): Return annotation
            
        Returns:
            str: Docstring
        """
        docstring = f'"""\n{func_name}\n\n'
        
        if args:
            for arg in args:
                if arg['name'].startswith('*'):
                    # For *args and **kwargs
                    name = arg['name']
                else:
                    name = arg['name']
                
                annotation = f" ({arg['annotation']})" if arg['annotation'] else ""
                docstring += f":param {name}: Description\n"
                if arg['annotation']:
                    docstring += f":type {name}: {arg['annotation']}\n"
        
        if returns:
            docstring += f":return: Description\n"
            docstring += f":rtype: {returns}\n"
        
        docstring += '"""'
        return docstring
    
    def _generate_class_docstring(self, class_name, node):
        """
        Generate a docstring for a class based on the style
        
        Args:
            class_name (str): Class name
            node (ast.ClassDef): Class node
            
        Returns:
            str: Docstring
        """
        if self.style == 'google':
            return self._generate_google_class_docstring(class_name, node)
        elif self.style == 'numpy':
            return self._generate_numpy_class_docstring(class_name, node)
        else:  # sphinx
            return self._generate_sphinx_class_docstring(class_name, node)
    
    def _generate_google_class_docstring(self, class_name, node):
        """
        Generate a Google-style docstring for a class
        
        Args:
            class_name (str): Class name
            node (ast.ClassDef): Class node
            
        Returns:
            str: Docstring
        """
        docstring = f'"""\n{class_name}\n\n'
        
        # Add base classes if any
        if node.bases:
            bases = []
            for base in node.bases:
                if isinstance(base, ast.Name):
                    bases.append(base.id)
                elif isinstance(base, ast.Attribute):
                    bases.append(self._format_attribute(base))
            
            if bases:
                docstring += f"Inherits from: {', '.join(bases)}\n\n"
        
        # Add class attributes (simplified approach: look for assignments in the class body)
        attrs = []
        for item in node.body:
            if isinstance(item, ast.Assign) and all(isinstance(target, ast.Name) for target in item.targets):
                for target in item.targets:
                    attrs.append(target.id)
        
        if attrs:
            docstring += 'Attributes:\n'
            for attr in attrs:
                docstring += f"    {attr}: Description\n"
        
        docstring += '"""'
        return docstring
    
    def _generate_numpy_class_docstring(self, class_name, node):
        """
        Generate a NumPy-style docstring for a class
        
        Args:
            class_name (str): Class name
            node (ast.ClassDef): Class node
            
        Returns:
            str: Docstring
        """
        docstring = f'"""\n{class_name}\n\n'
        
        # Add base classes if any
        if node.bases:
            bases = []
            for base in node.bases:
                if isinstance(base, ast.Name):
                    bases.append(base.id)
                elif isinstance(base, ast.Attribute):
                    bases.append(self._format_attribute(base))
            
            if bases:
                docstring += f"Inherits from: {', '.join(bases)}\n\n"
        
        # Add class attributes (simplified approach: look for assignments in the class body)
        attrs = []
        for item in node.body:
            if isinstance(item, ast.Assign) and all(isinstance(target, ast.Name) for target in item.targets):
                for target in item.targets:
                    attrs.append(target.id)
        
        if attrs:
            docstring += 'Attributes\n----------\n'
            for attr in attrs:
                docstring += f"{attr}\n    Description\n"
        
        docstring += '"""'
        return docstring
    
    def _generate_sphinx_class_docstring(self, class_name, node):
        """
        Generate a Sphinx-style docstring for a class
        
        Args:
            class_name (str): Class name
            node (ast.ClassDef): Class node
            
        Returns:
            str: Docstring
        """
        docstring = f'"""\n{class_name}\n\n'
        
        # Add base classes if any
        if node.bases:
            bases = []
            for base in node.bases:
                if isinstance(base, ast.Name):
                    bases.append(base.id)
                elif isinstance(base, ast.Attribute):
                    bases.append(self._format_attribute(base))
            
            if bases:
                docstring += f"Inherits from: {', '.join(bases)}\n\n"
        
        # Add class attributes (simplified approach: look for assignments in the class body)
        attrs = []
        for item in node.body:
            if isinstance(item, ast.Assign) and all(isinstance(target, ast.Name) for target in item.targets):
                for target in item.targets:
                    attrs.append(target.id)
        
        if attrs:
            for attr in attrs:
                docstring += f":var {attr}: Description\n"
        
        docstring += '"""'
        return docstring
