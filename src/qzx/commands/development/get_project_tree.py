#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
GetProjectTree Command - Generates a filtered, customizable directory tree structure in ASCII and JSON formats.
"""

import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from qzx.core.command_base import CommandBase

class GetProjectTreeCommand(CommandBase):
    """
    Command to visualize a directory structure as a clean text-based tree or JSON model, excluding heavy or private files.
    """
    
    name = "getProjectTree"
    description = "Generates a clean visual directory tree (ASCII and JSON) excluding heavy directories like node_modules"
    category = "development"
    
    parameters = [
        {
            'name': 'dir_path',
            'description': 'Path to the directory to visualize (defaults to current directory)',
            'required': False,
            'default': '.'
        },
        {
            'name': 'max_depth',
            'description': 'Maximum depth level of the tree (defaults to 2)',
            'required': False,
            'default': '2'
        },
        {
            'name': 'exclude_dirs',
            'description': 'Comma-separated directory names to exclude (defaults to standard caches and configs)',
            'required': False,
            'default': '.git,node_modules,__pycache__,.venv,env,dist,build,artifacts,.next,.nuxt,.idea,.vscode'
        },
        {
            'name': 'include_files',
            'description': 'Whether to list files as well as directories (true/false)',
            'required': False,
            'default': 'true'
        }
    ]
    
    examples = [
        {
            'command': 'qzx getProjectTree',
            'description': 'Show directory tree for the current folder up to 2 levels deep'
        },
        {
            'command': 'qzx getProjectTree src 3',
            'description': 'Show directory tree for the src folder up to 3 levels deep'
        },
        {
            'command': 'qzx getProjectTree . 2 .git,node_modules false',
            'description': 'Show directory tree excluding only .git and node_modules, showing folders only'
        }
    ]
    
    def execute(self, dir_path='.', max_depth='2', exclude_dirs=None, include_files='true'):
        """
        Executes directory tree generation
        
        Args:
            dir_path (str): The starting directory path
            max_depth (str/int): Maximum depth to traverse
            exclude_dirs (str, optional): Commas separated exclude folder list
            include_files (str/bool): Whether to include files in the tree
            
        Returns:
            Dictionary containing ASCII tree text and JSON tree model
        """
        abs_path = os.path.abspath(dir_path)
        
        if not os.path.exists(abs_path):
            return {
                "success": False,
                "error": f"Path '{dir_path}' does not exist.",
                "message": f"Path '{dir_path}' does not exist."
            }
            
        if not os.path.isdir(abs_path):
            return {
                "success": False,
                "error": f"'{dir_path}' is not a directory. Trees require a directory path.",
                "message": f"'{dir_path}' is not a directory."
            }
            
        # Parse depth
        try:
            limit_depth = int(max_depth)
        except ValueError:
            limit_depth = 2
            
        # Parse include files
        if isinstance(include_files, str):
            show_files = include_files.lower() in ('true', 'yes', 'y', '1', 't')
        else:
            show_files = bool(include_files)
            
        # Parse exclude dirs
        if exclude_dirs is None:
            excludes = {
                '.git', 'node_modules', '__pycache__', '.venv', 'env', 
                'dist', 'build', 'artifacts', '.next', '.nuxt', '.idea', '.vscode'
            }
        else:
            excludes = {d.strip() for d in exclude_dirs.split(',') if d.strip()}
            
        try:
            # Build structures recursively
            json_tree = self._build_json_tree(abs_path, limit_depth, 0, excludes, show_files)
            ascii_lines = []
            
            base_name = os.path.basename(abs_path) or abs_path
            ascii_lines.append(base_name)
            self._build_ascii_tree(abs_path, "", limit_depth, 0, excludes, show_files, ascii_lines)
            
            tree_text = "\n".join(ascii_lines)
            
            # Formulate the response message
            msg = f"Directory Tree for '{abs_path}' (Max Depth: {limit_depth}, Files: {'Included' if show_files else 'Excluded'}):\n"
            msg += "---------------------------------------------------------\n"
            msg += tree_text + "\n"
            msg += "---------------------------------------------------------"
            
            return {
                "success": True,
                "dir_path": abs_path,
                "max_depth": limit_depth,
                "exclude_dirs": list(excludes),
                "include_files": show_files,
                "tree_text": tree_text,
                "tree_structure": json_tree,
                "message": msg
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "message": f"Failed to generate project tree: {str(e)}"
            }
            
    def _build_json_tree(self, current_path, max_depth, current_depth, excludes, show_files):
        """Recursively builds the JSON structure of the tree"""
        name = os.path.basename(current_path) or current_path
        
        if os.path.isfile(current_path):
            return {
                "name": name,
                "type": "file",
                "size_bytes": os.path.getsize(current_path)
            }
            
        node = {
            "name": name,
            "type": "directory",
            "children": []
        }
        
        if current_depth >= max_depth:
            return node
            
        try:
            items = os.listdir(current_path)
        except Exception:
            node["children"].append({"name": "[Access Denied]", "type": "error"})
            return node
            
        # Group items into folders and files, sorted alphabetically
        dirs_list = []
        files_list = []
        
        for item in items:
            full_path = os.path.join(current_path, item)
            if os.path.isdir(full_path):
                if item not in excludes:
                    dirs_list.append(item)
            else:
                if show_files:
                    files_list.append(item)
                    
        dirs_list.sort()
        files_list.sort()
        
        # Recurse subdirectories
        for d in dirs_list:
            child_path = os.path.join(current_path, d)
            child_node = self._build_json_tree(child_path, max_depth, current_depth + 1, excludes, show_files)
            node["children"].append(child_node)
            
        # Append files
        for f in files_list:
            child_path = os.path.join(current_path, f)
            try:
                size = os.path.getsize(child_path)
            except OSError:
                size = 0
            node["children"].append({
                "name": f,
                "type": "file",
                "size_bytes": size
            })
            
        return node
        
    def _build_ascii_tree(self, current_path, prefix, max_depth, current_depth, excludes, show_files, lines):
        """Recursively compiles lines for the ASCII tree representation"""
        if current_depth >= max_depth:
            return
            
        try:
            items = os.listdir(current_path)
        except Exception:
            lines.append(prefix + "└── [Access Denied]")
            return
            
        # Filter and separate directories and files
        dirs_list = []
        files_list = []
        
        for item in items:
            full_path = os.path.join(current_path, item)
            if os.path.isdir(full_path):
                if item not in excludes:
                    dirs_list.append(item)
            else:
                if show_files:
                    files_list.append(item)
                    
        dirs_list.sort()
        files_list.sort()
        
        all_children = [(d, True) for d in dirs_list] + [(f, False) for f in files_list]
        count = len(all_children)
        
        for index, (name, is_dir) in enumerate(all_children):
            is_last = (index == count - 1)
            connector = "└── " if is_last else "├── "
            
            lines.append(prefix + connector + name)
            
            if is_dir:
                new_prefix = prefix + ("    " if is_last else "│   ")
                child_path = os.path.join(current_path, name)
                self._build_ascii_tree(
                    child_path, new_prefix, max_depth, current_depth + 1, 
                    excludes, show_files, lines
                )
