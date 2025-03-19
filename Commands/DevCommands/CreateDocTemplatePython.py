#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
CreateDocTemplatePython Command - Generates documentation templates for Python code
"""

import os
import re
import ast
import inspect
from typing import List, Dict, Any, Tuple
from Core.command_base import CommandBase

class CreateDocTemplatePythonCommand(CommandBase):
    """
    Command to generate documentation templates for Python code
    """
    
    name = "CreateDocTemplatePython"
    description = "Creates basic documentation templates for Python code that lacks docstrings"
    category = "dev"
    
    parameters = [
        {
            'name': 'file_path',
            'description': 'Path to the Python file to process',
            'required': True
        },
        {
            'name': 'style',
            'description': 'Documentation style (google, numpy, sphinx)',
            'required': False,
            'default': 'google'
        },
        {
            'name': 'overwrite',
            'description': 'Whether to overwrite existing docstrings',
            'required': False,
            'default': False
        },
        {
            'name': 'preview',
            'description': 'Preview changes without modifying the file',
            'required': False,
            'default': False
        }
    ]
    
    examples = [
        {
            'command': 'qzx CreateDocTemplatePython myfile.py',
            'description': 'Create Google-style documentation templates for myfile.py'
        },
        {
            'command': 'qzx CreateDocTemplatePython myfile.py sphinx',
            'description': 'Create Sphinx-style documentation templates for myfile.py'
        },
        {
            'command': 'qzx CreateDocTemplatePython myfile.py google true false',
            'description': 'Create Google-style documentation templates, overwriting existing ones'
        },
        {
            'command': 'qzx CreateDocTemplatePython myfile.py google false true',
            'description': 'Preview Google-style documentation templates without modifying the file'
        }
    ]
    
    def execute(self, file_path, style='google', overwrite=False, preview=False):
        """
        Generates documentation templates for Python code
        
        Args:
            file_path (str): Path to the Python file to process
            style (str, optional): Documentation style (google, numpy, sphinx)
            overwrite (bool, optional): Whether to overwrite existing docstrings
            preview (bool, optional): Preview changes without modifying the file
            
        Returns:
            Dictionary with the result of the operation
        """
        try:
            # Validate file exists
            if not os.path.exists(file_path):
                return {
                    "success": False,
                    "error": f"File '{file_path}' does not exist"
                }
            
            # Validate it's a Python file
            if not file_path.endswith('.py'):
                return {
                    "success": False,
                    "error": f"File '{file_path}' is not a Python file"
                }
            
            # Convert parameters to appropriate types
            if isinstance(style, str):
                style = style.lower()
                if style not in ['google', 'numpy', 'sphinx']:
                    return {
                        "success": False,
                        "error": f"Invalid style: '{style}'. Must be one of: google, numpy, sphinx"
                    }
            
            if isinstance(overwrite, str):
                overwrite = overwrite.lower() in ('true', 'yes', 'y', '1')
            
            if isinstance(preview, str):
                preview = preview.lower() in ('true', 'yes', 'y', '1')
            
            # Read the file
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Parse the Python code
            try:
                tree = ast.parse(content)
            except SyntaxError as e:
                return {
                    "success": False,
                    "error": f"Syntax error in file: {str(e)}"
                }
            
            # Process the AST to find functions and classes
            visitor = DocstringVisitor(content, style, overwrite)
            visitor.visit(tree)
            
            # Get the new content with docstrings added
            new_content = visitor.get_modified_content()
            
            # Generate statistics
            stats = {
                "functions_processed": visitor.stats["functions_processed"],
                "functions_updated": visitor.stats["functions_updated"],
                "classes_processed": visitor.stats["classes_processed"],
                "classes_updated": visitor.stats["classes_updated"],
                "methods_processed": visitor.stats["methods_processed"],
                "methods_updated": visitor.stats["methods_updated"]
            }
            
            # Get a preview of changes if requested
            changes_preview = []
            if preview or len(visitor.updates) > 0:
                changes_preview = visitor.get_changes_preview()
            
            # Write the new content to the file if not in preview mode
            if not preview and content != new_content:
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(new_content)
            
            # Prepare the result
            result = {
                "success": True,
                "file_path": os.path.abspath(file_path),
                "style": style,
                "overwrite": overwrite,
                "preview": preview,
                "stats": stats,
                "changes_made": content != new_content,
                "changes_preview": changes_preview
            }
            
            # Add a message
            if preview:
                if len(changes_preview) > 0:
                    result["message"] = f"Preview of documentation templates for '{file_path}' generated"
                else:
                    result["message"] = f"No documentation templates needed for '{file_path}'"
            else:
                if content != new_content:
                    result["message"] = f"Documentation templates generated for '{file_path}'"
                else:
                    result["message"] = f"No documentation templates needed for '{file_path}'"
            
            return result
            
        except Exception as e:
            return {
                "success": False,
                "file_path": file_path,
                "error": str(e)
            }

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