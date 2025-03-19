#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import sys
import glob
import re
from Commands.FileCommands.FindFiles import FindFilesCommand

# Monkey patch para debug
original_process_entry = FindFilesCommand._process_entry

def debug_process_entry(self, entry, pattern, type, size_constraint, min_size, max_size, mtime_constraint, newer_than, older_than, contains, contains_regex, case_sensitive, results):
    print(f"DEBUG_PROCESS: Processing entry: {getattr(entry, 'name', 'unknown')}")
    print(f"DEBUG_PROCESS: Pattern: {pattern}")
    
    # Verificar el patrón directamente con fnmatch
    import fnmatch
    if hasattr(entry, 'name'):
        match = fnmatch.fnmatch(entry.name, pattern)
        print(f"DEBUG_PROCESS: fnmatch result: {match}")
    
    result = original_process_entry(self, entry, pattern, type, size_constraint, min_size, max_size, mtime_constraint, newer_than, older_than, contains, contains_regex, case_sensitive, results)
    print(f"DEBUG_PROCESS: Result of _process_entry: {result}")
    return result

# Reemplazar el método original con nuestra versión de depuración
FindFilesCommand._process_entry = debug_process_entry

# También veamos cómo se procesan los directorios
if hasattr(FindFilesCommand, '_should_exclude'):
    original_should_exclude = FindFilesCommand._should_exclude
    
    def debug_should_exclude(self, name, exclude_patterns):
        result = original_should_exclude(self, name, exclude_patterns)
        print(f"DEBUG_EXCLUDE: Checking if '{name}' should be excluded: {result}")
        return result
    
    FindFilesCommand._should_exclude = debug_should_exclude

def debug_find_files():
    print("\nDEBUG: Testing most basic FindFiles with current directory")
    cmd = FindFilesCommand()
    
    current_directory = "."
    simple_pattern = "*"
    
    # Prueba el caso más simple: archivos en el directorio actual
    try:
        print(f"\nDEBUG: Executing FindFilesCommand.execute({current_directory!r}, {simple_pattern!r})")
        result = cmd.execute(current_directory, simple_pattern)
        print(f"DEBUG: Result: {result}")
    except Exception as e:
        print(f"DEBUG: Exception: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    debug_find_files() 