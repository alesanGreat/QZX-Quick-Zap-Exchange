#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
FindFiles Command - Advanced file search utility
Using the centralized recursive file finder utility
"""

import os
import re
import fnmatch
import time
import datetime
import json
from pathlib import Path
from typing import List, Dict, Any, Union, Optional, Tuple, Set
from Core.command_base import CommandBase
from Core.recursive_findfiles_utils import find_files, parse_recursive_parameter

class FindFilesCommand(CommandBase):
    """
    Command for advanced file searching with multiple filtering options
    
    Supports flags:
    -r, -R, --recursive: Enable unlimited recursive directory search
    -rN, --recursiveN: Enable recursive directory search up to N levels deep
    
    This version uses the centralized recursive file finder utility.
    """
    
    name = "findFiles"
    description = "Advanced file search with multiple filtering options (like find + grep combined)"
    category = "file"
    
    parameters = [
        {
            'name': 'search_path',
            'description': 'Path to start the search from',
            'required': False,
            'default': "."
        },
        {
            'name': 'pattern',
            'description': 'File name pattern to search for (supports glob syntax: *.txt, data-???.csv)',
            'required': False,
            'default': "*"
        },
        {
            'name': 'recursive',
            'description': 'Recursion level: -r/--recursive for unlimited depth, -rN/--recursiveN for N levels deep',
            'required': False,
            'default': '-r'
        },
        {
            'name': 'max_depth',
            'description': 'Maximum directory depth to search (null for unlimited)',
            'required': False,
            'default': None
        },
        {
            'name': 'type',
            'description': 'Filter by type: "f" (files), "d" (directories), or "l" (links)',
            'required': False,
            'default': None
        },
        {
            'name': 'size',
            'description': 'Filter by size (e.g., +1M for >1MB, -500K for <500KB, 10K for exactly 10KB)',
            'required': False,
            'default': None
        },
        {
            'name': 'min_size',
            'description': 'Minimum file size in bytes or with KB/MB/GB suffix',
            'required': False,
            'default': None
        },
        {
            'name': 'max_size',
            'description': 'Maximum file size in bytes or with KB/MB/GB suffix',
            'required': False,
            'default': None
        },
        {
            'name': 'mtime',
            'description': 'Filter by modification time (e.g., +7 for >7 days old, -2 for <2 days old)',
            'required': False,
            'default': None
        },
        {
            'name': 'newer_than',
            'description': 'Files newer than specified date (YYYY-MM-DD) or "today", "yesterday"',
            'required': False,
            'default': None
        },
        {
            'name': 'older_than',
            'description': 'Files older than specified date (YYYY-MM-DD) or "today", "yesterday"',
            'required': False,
            'default': None
        },
        {
            'name': 'contains',
            'description': 'Only include files containing this text',
            'required': False,
            'default': None
        },
        {
            'name': 'contains_regex',
            'description': 'Only include files matching this regex pattern',
            'required': False,
            'default': None
        },
        {
            'name': 'case_sensitive',
            'description': 'Make content searches case sensitive (true/false)',
            'required': False,
            'default': False
        },
        {
            'name': 'exclude',
            'description': 'Exclude file/directory patterns (comma-separated: *.bak,*.tmp)',
            'required': False,
            'default': None
        },
        {
            'name': 'exclude_dir',
            'description': 'Exclude directory patterns (comma-separated: .git,.vscode)',
            'required': False,
            'default': None
        },
        {
            'name': 'follow_symlinks',
            'description': 'Follow symbolic links (true/false)',
            'required': False,
            'default': False
        },
        {
            'name': 'sort_by',
            'description': 'Sort by: name, path, size, mtime (modification time), or none',
            'required': False,
            'default': 'path'
        },
        {
            'name': 'reverse_sort',
            'description': 'Reverse the sorting order (true/false)',
            'required': False,
            'default': False
        },
        {
            'name': 'format',
            'description': 'Output format: "full" (default), "name" (filename only), "detailed" (full details), "json", "csv"',
            'required': False,
            'default': 'full'
        },
        {
            'name': 'limit',
            'description': 'Maximum number of results to return',
            'required': False,
            'default': None
        }
    ]
    
    examples = [
        {
            'command': 'qzx findFiles . *.py',
            'description': 'Find all Python files in current directory and subdirectories'
        },
        {
            'command': 'qzx findFiles /src *.js false',
            'description': 'Find all JavaScript files in /src without searching subdirectories'
        },
        {
            'command': 'qzx findFiles . * true 2 f',
            'description': 'Find all files up to 2 levels deep'
        },
        {
            'command': 'qzx findFiles . *.txt null f +1M',
            'description': 'Find all text files larger than 1MB'
        },
        {
            'command': 'qzx findFiles . * null null null null null null -7',
            'description': 'Find files modified within the last 7 days'
        },
        {
            'command': 'qzx findFiles . *.log null null null null null today null',
            'description': 'Find log files created or modified today'
        },
        {
            'command': 'qzx findFiles . *.py null null null null null null null TODO',
            'description': 'Find Python files containing the word "TODO"'
        },
        {
            'command': 'qzx findFiles . * null null null null null null null null "def\\s+\\w+"',
            'description': 'Find files containing function definitions using regex'
        },
        {
            'command': 'qzx findFiles . * null null null null null null null null null false "*.tmp,*.bak"',
            'description': 'Find all files excluding temp and backup files'
        },
        {
            'command': 'qzx findFiles . * true null null null null null null null null null null .git,node_modules',
            'description': 'Find all files excluding .git and node_modules directories'
        }
    ]
    
    def execute(self, search_path=".", pattern="*", recursive="-r", max_depth=None, type=None,
                size=None, min_size=None, max_size=None, mtime=None, newer_than=None, older_than=None,
                contains=None, contains_regex=None, case_sensitive=False, exclude=None, exclude_dir=None,
                follow_symlinks=False, sort_by='path', reverse_sort=False, format='full', limit=None):
        """
        Advanced file search with multiple filtering options
        
        Args:
            search_path (str): Path to start the search from
            pattern (str): File name pattern to search for (supports glob syntax)
            recursive: Recursion level: -r/--recursive for unlimited depth, -rN/--recursiveN for N levels deep
            max_depth (int): Maximum directory depth to search (None for unlimited)
            type (str): Filter by type: "f" (files), "d" (directories), or "l" (links)
            size (str): Filter by size (e.g., +1M for >1MB, -500K for <500KB)
            min_size (str): Minimum file size in bytes or with KB/MB/GB suffix
            max_size (str): Maximum file size in bytes or with KB/MB/GB suffix
            mtime (str): Filter by modification time (e.g., +7 for >7 days old)
            newer_than (str): Files newer than specified date (YYYY-MM-DD)
            older_than (str): Files older than specified date (YYYY-MM-DD)
            contains (str): Only include files containing this text
            contains_regex (str): Only include files matching this regex pattern
            case_sensitive (bool): Make content searches case sensitive
            exclude (str): Exclude file/directory patterns (comma-separated)
            exclude_dir (str): Exclude directory patterns (comma-separated)
            follow_symlinks (bool): Follow symbolic links
            sort_by (str): Sort by: name, path, size, mtime, or none
            reverse_sort (bool): Reverse the sorting order
            format (str): Output format: "full", "name", "detailed", "json", "csv"
            limit (int): Maximum number of results to return
            
        Returns:
            Search results based on specified format
        """
        try:
            # Process flags in command arguments if they exist
            import sys
            args = sys.argv
            recursive_flags = ['-r', '-R', '--recursive']
            recursive_found = any(flag in args for flag in recursive_flags)
            
            # Normalizar parámetros
            if search_path is None:
                search_path = "."
            
            if pattern is None:
                pattern = "*"
                
            if recursive is None:
                recursive = "-r"
            
            # Parse recursive parameter - convert string flags or handle boolean
            if isinstance(recursive, str):
                recursive = parse_recursive_parameter(recursive)
            elif recursive_found:
                recursive = True
            
            # Para compatibilidad: si recursion_depth y max_depth están definidos, usar el más restrictivo
            if recursive is not None and max_depth is not None and max_depth != "null":
                try:
                    max_depth = int(max_depth)
                    # Usar el menor de los dos valores
                    if isinstance(recursive, int) and recursive > 0:
                        recursive = min(recursive, max_depth)
                    elif recursive is True:
                        recursive = max_depth
                except ValueError:
                    pass  # If max_depth is invalid, just use recursive as is
            elif max_depth is not None and max_depth != "null":
                try:
                    recursive = int(max_depth)
                except ValueError:
                    pass  # If max_depth is invalid, keep original recursive value
                
            # Convertir parámetros a tipos apropiados
            if isinstance(case_sensitive, str):
                case_sensitive = case_sensitive.lower() in ('true', 'yes', 'y', '1')
            
            if isinstance(follow_symlinks, str):
                follow_symlinks = follow_symlinks.lower() in ('true', 'yes', 'y', '1')
            
            if isinstance(reverse_sort, str):
                reverse_sort = reverse_sort.lower() in ('true', 'yes', 'y', '1')
            
            if limit == "null":
                limit = None
            elif limit is not None:
                try:
                    limit = int(limit)
                except ValueError:
                    limit = None

            # Parsear todos los demás parámetros
            size_constraint = self._parse_size(size)
            min_size_constraint = self._parse_size(min_size)
            max_size_constraint = self._parse_size(max_size)
            mtime_constraint = self._parse_mtime(mtime)
            newer_than_timestamp = self._parse_date(newer_than)
            older_than_timestamp = self._parse_date(older_than)
            
            # Compilar expresión regular si se proporciona
            compiled_regex = None
            if contains_regex and contains_regex != "null":
                try:
                    flags = 0 if case_sensitive else re.IGNORECASE
                    compiled_regex = re.compile(contains_regex, flags)
                except re.error:
                    return {'success': False, 'error': f"Invalid regex pattern: {contains_regex}"}
            
            # Procesamiento de patrones de exclusión
            exclude_patterns = self._parse_patterns(exclude)
            exclude_dir_patterns = self._parse_patterns(exclude_dir)
            
            # Inicializar variables para resultados
            results = []
            total_size = 0
            
            # Verificar que el directorio existe
            if not os.path.exists(search_path):
                return {'success': False, 'error': f"Path not found: {search_path}"}
            
            # Determinar qué tipo de entradas buscar
            file_type = None
            if type == 'f':
                file_type = 'f'  # Sólo archivos
            elif type == 'd':
                file_type = 'd'  # Sólo directorios
            elif type == 'l':
                file_type = 'l'  # Sólo enlaces simbólicos
            # Si type no está especificado, buscaremos todos los tipos
            
            # Crear el patrón de búsqueda completo combinando ruta y patrón
            search_pattern = os.path.join(search_path, pattern)
            
            # Definir callbacks para procesar los archivos y directorios encontrados
            def on_file_found(file_path):
                file_name = os.path.basename(file_path)
                
                # Verificar si el archivo debe ser excluido
                if self._should_exclude(file_name, exclude_patterns):
                    return
                
                try:
                    # Para enlaces simbólicos, necesitamos un manejo especial
                    if type == 'l' and not os.path.islink(file_path):
                        return
                    
                    file_stat = os.stat(file_path) if not type == 'l' else os.lstat(file_path)
                    
                    # Calcular la profundidad relativa
                    rel_path = os.path.relpath(os.path.dirname(file_path), search_path)
                    current_depth = 0 if rel_path == '.' else rel_path.count(os.sep) + 1
                
                    # Verificar si cumple con todas las restricciones
                    if self._check_constraints(file_path, file_stat, size_constraint, min_size_constraint, max_size_constraint, 
                                              mtime_constraint, newer_than_timestamp, older_than_timestamp,
                                              contains, compiled_regex, case_sensitive):
                        # Crear información detallada del archivo
                        file_info = self._create_entry_info(file_path, file_name, "file", file_stat, current_depth)
                        results.append(file_info)
                        nonlocal total_size
                        total_size += file_stat.st_size
                        
                except (PermissionError, FileNotFoundError):
                    # Ignorar archivos a los que no podemos acceder
                    pass
            
            def on_dir_found(dir_path):
                dir_name = os.path.basename(dir_path)
                
                # Si estamos excluyendo este directorio y no lo estamos buscando específicamente, ignorarlo
                if self._should_exclude(dir_name, exclude_dir_patterns) and type != 'd':
                    return
                
                # Si estamos buscando sólo archivos, no procesar directorios
                if type == 'f':
                    return
                
                try:
                    # Para enlaces simbólicos, necesitamos un manejo especial
                    if type == 'l' and not os.path.islink(dir_path):
                        return
                    
                    dir_stat = os.stat(dir_path) if not type == 'l' else os.lstat(dir_path)
                    
                    # Calcular la profundidad relativa
                    rel_path = os.path.relpath(os.path.dirname(dir_path), search_path)
                    current_depth = 0 if rel_path == '.' else rel_path.count(os.sep) + 1
                    
                    # Si estamos buscando directorios específicamente o todos los tipos, verificar restricciones
                    if type == 'd' or type is None or type == 'l':
                        if self._check_constraints(dir_path, dir_stat, size_constraint, min_size_constraint, max_size_constraint, 
                                                 mtime_constraint, newer_than_timestamp, older_than_timestamp,
                                                 contains, compiled_regex, case_sensitive):
                            # Crear información detallada del directorio
                            dir_info = self._create_entry_info(dir_path, dir_name, "directory", dir_stat, current_depth)
                            results.append(dir_info)
                except (PermissionError, FileNotFoundError):
                    # Ignorar directorios a los que no podemos acceder
                    pass
            
            # Usar la función find_files centralizada para buscar archivos y directorios
            for _ in find_files(
                file_path_pattern=search_pattern,
                recursive=recursive,
                file_type=file_type,
                exclude_patterns=exclude_patterns,
                exclude_dirs=exclude_dir_patterns,
                on_file_found=on_file_found,
                on_dir_found=on_dir_found
            ):
                # Si tenemos un límite de resultados y lo hemos alcanzado, detener la búsqueda
                if limit is not None and len(results) >= limit:
                    break
            
            # Ordenar resultados según se solicite
            if sort_by != 'none':
                results = self._sort_results(results, sort_by, reverse_sort)
                
            # Aplicar límite si está configurado
            if limit is not None and limit > 0:
                results = results[:limit]
            
            # Preparar mensaje para el resultado
            recursion_message = ""
            if recursive is True:
                recursion_message = " (buscando recursivamente)"
            elif isinstance(recursive, int) and recursive > 0:
                recursion_message = f" (buscando hasta {recursive} niveles de profundidad)"
            
            if len(results) == 0:
                message = f"No se encontraron archivos coincidentes en '{search_path}'{recursion_message}"
            else:
                message = f"Se encontraron {len(results)} elementos en '{search_path}'{recursion_message}"
                
                # Formatear a tamaño legible
                total_size_readable = self._format_bytes(total_size)
                message += f", tamaño total: {total_size_readable}"
            
            # Formatear resultados según el formato solicitado
            formatted_results = self._format_results(results, format)
            
            return {
                'success': True,
                'message': message,
                'count': len(results),
                'total_size': total_size,
                'total_size_readable': self._format_bytes(total_size),
                'results': formatted_results
            }
        
        except Exception as e:
            import traceback
            return {
                'success': False,
                'error': f"Error during file search: {str(e)}",
                'traceback': traceback.format_exc()
            }
    
    def _create_entry_info(self, path, name, entry_type, stat, depth):
        """
        Crea un objeto con la información del archivo o directorio
        
        Args:
            path (str): Ruta del archivo o directorio
            name (str): Nombre del archivo o directorio
            entry_type (str): Tipo de entrada (file, directory, link)
            stat (os.stat_result): Estadísticas del archivo o directorio
            depth (int): Profundidad relativa al directorio de búsqueda inicial
            
        Returns:
            dict: Información del archivo o directorio
        """
        return {
            "name": name,
            "path": path,
            "type": entry_type,
            "depth": depth,
            "size": stat.st_size,
            "size_readable": self._format_bytes(stat.st_size),
            "mtime": stat.st_mtime,
            "mtime_readable": datetime.datetime.fromtimestamp(stat.st_mtime).strftime('%Y-%m-%d %H:%M:%S')
        }
    
    def _check_constraints(self, file_path, file_stat, size_constraint, min_size, max_size, 
                          mtime_constraint, newer_than, older_than, contains, contains_regex, case_sensitive):
        """Verificar si un archivo cumple con todas las restricciones especificadas"""
        # Check size constraints
        if not self._check_size_constraint(file_stat.st_size, size_constraint, min_size, max_size):
            return False
            
        # Check modification time constraints
        if not self._check_time_constraint(file_stat.st_mtime, mtime_constraint, newer_than, older_than):
            return False
            
        # Check content constraints (only for files, not directories)
        if (contains or contains_regex) and os.path.isfile(file_path):
            if not self._check_content(file_path, contains, contains_regex, case_sensitive):
                return False
                
        return True
    
    def _parse_size(self, size_str):
        """
        Parse a size string to bytes
        
        Args:
            size_str (str): Size string (e.g., "+1M", "-500K")
            
        Returns:
            tuple: (operation, size_in_bytes) or None if invalid
        """
        if not size_str or size_str == "null":
            return None
        
        # Determine operation
        op = None
        if size_str.startswith('+'):
            op = '>'
            size_str = size_str[1:]
        elif size_str.startswith('-'):
            op = '<'
            size_str = size_str[1:]
        else:
            op = '='
        
        # Parse size value
        size_value = 0
        try:
            if size_str.lower().endswith('k'):
                size_value = float(size_str[:-1]) * 1024
            elif size_str.lower().endswith('kb'):
                size_value = float(size_str[:-2]) * 1024
            elif size_str.lower().endswith('m'):
                size_value = float(size_str[:-1]) * 1024 * 1024
            elif size_str.lower().endswith('mb'):
                size_value = float(size_str[:-2]) * 1024 * 1024
            elif size_str.lower().endswith('g'):
                size_value = float(size_str[:-1]) * 1024 * 1024 * 1024
            elif size_str.lower().endswith('gb'):
                size_value = float(size_str[:-2]) * 1024 * 1024 * 1024
            else:
                size_value = float(size_str)
            
            return (op, int(size_value))
        except ValueError:
            return None
    
    def _parse_mtime(self, mtime_str):
        """
        Parse an mtime string to days
        
        Args:
            mtime_str (str): mtime string (e.g., "+7", "-2")
            
        Returns:
            tuple: (operation, days) or None if invalid
        """
        if not mtime_str or mtime_str == "null":
            return None
        
        # Determine operation
        op = None
        if mtime_str.startswith('+'):
            op = '>'  # Older than
            mtime_str = mtime_str[1:]
        elif mtime_str.startswith('-'):
            op = '<'  # Newer than
            mtime_str = mtime_str[1:]
        else:
            op = '='  # Exactly
        
        # Parse days value
        try:
            days = float(mtime_str)
            return (op, days)
        except ValueError:
            return None
    
    def _parse_date(self, date_str):
        """
        Parse a date string to timestamp
        
        Args:
            date_str (str): Date string (e.g., "2023-01-01", "today", "yesterday")
            
        Returns:
            float: Timestamp or None if invalid
        """
        if not date_str or date_str == "null":
            return None
        
        try:
            if date_str.lower() == 'today':
                # Get start of today
                today = datetime.datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
                return today.timestamp()
            elif date_str.lower() == 'yesterday':
                # Get start of yesterday
                yesterday = datetime.datetime.now().replace(hour=0, minute=0, second=0, microsecond=0) - datetime.timedelta(days=1)
                return yesterday.timestamp()
            else:
                # Parse YYYY-MM-DD format
                year, month, day = map(int, date_str.split('-'))
                date = datetime.datetime(year, month, day)
                return date.timestamp()
        except (ValueError, TypeError):
            return None
    
    def _parse_patterns(self, patterns_string):
        """
        Parse comma-separated patterns into a list
        
        Args:
            patterns_string: Comma-separated patterns (e.g., "*.txt,*.py")
            
        Returns:
            list: List of parsed patterns or empty list if input is invalid
        """
        try:
            if not patterns_string:
                return []
                
            if isinstance(patterns_string, list):
                return [p for p in patterns_string if p and isinstance(p, str)]
                
            if isinstance(patterns_string, str):
                # Dividir por comas y quitar espacios
                patterns = [p.strip() for p in patterns_string.split(',')]
                # Filtrar patrones vacíos
                patterns = [p for p in patterns if p]
                return patterns
                
            return []
        except Exception:
            # En caso de error, devolver lista vacía
            return []
    
    def _should_exclude(self, name, exclude_patterns):
        """
        Check if a name matches any of the exclude patterns
        
        Args:
            name (str): File or directory name to check
            exclude_patterns (list): List of patterns to exclude
            
        Returns:
            bool: True if the name should be excluded
        """
        try:
            if not name or not exclude_patterns:
                return False
                
            # Asegurar que name es string
            if not isinstance(name, str):
                try:
                    name = str(name)
                except:
                    return False
                    
            # Iterar sobre los patrones
            for pattern in exclude_patterns:
                try:
                    if pattern and fnmatch.fnmatch(name, pattern):
                        return True
                except Exception:
                    # Ignorar errores en patterns individuales
                    continue
                    
            return False
        except Exception:
            # En caso de cualquier excepción, no excluir
            return False
    
    def _check_size_constraint(self, file_size, size_constraint, min_size, max_size):
        """
        Check if a file size meets the size constraints
        
        Args:
            file_size (int): File size in bytes
            size_constraint (tuple): (operation, size_in_bytes) or None
            min_size (tuple): (operation, size_in_bytes) or None
            max_size (tuple): (operation, size_in_bytes) or None
            
        Returns:
            bool: True if size meets constraints
        """
        # Check size constraint
        if size_constraint:
            op, value = size_constraint
            if op == '>' and file_size <= value:
                return False
            elif op == '<' and file_size >= value:
                return False
            elif op == '=' and file_size != value:
                return False
        
        # Check min size
        if min_size:
            _, value = min_size
            if file_size < value:
                return False
        
        # Check max size
        if max_size:
            _, value = max_size
            if file_size > value:
                return False
        
        return True
    
    def _check_time_constraint(self, file_mtime, mtime_constraint, newer_than, older_than):
        """
        Check if a file mtime meets the time constraints
        
        Args:
            file_mtime (float): File modification time
            mtime_constraint (tuple): (operation, days) or None
            newer_than (float): Newer than timestamp or None
            older_than (float): Older than timestamp or None
            
        Returns:
            bool: True if mtime meets constraints
        """
        now = time.time()
        
        # Check mtime constraint
        if mtime_constraint:
            op, days = mtime_constraint
            days_in_seconds = days * 24 * 60 * 60
            file_age_in_seconds = now - file_mtime
            
            if op == '>' and file_age_in_seconds <= days_in_seconds:
                return False
            elif op == '<' and file_age_in_seconds >= days_in_seconds:
                return False
            elif op == '=' and abs(file_age_in_seconds - days_in_seconds) > 24 * 60 * 60:  # Within one day
                return False
        
        # Check newer than
        if newer_than and file_mtime < newer_than:
            return False
        
        # Check older than
        if older_than and file_mtime > older_than:
            return False
        
        return True
    
    def _check_content(self, file_path, contains, contains_regex, case_sensitive):
        """
        Check if a file contains specified text or matches regex
        
        Args:
            file_path (str): Path to the file
            contains (str): Text to search for
            contains_regex (re.Pattern): Compiled regex pattern
            case_sensitive (bool): Whether search is case sensitive
            
        Returns:
            bool: True if content matches constraints
        """
        try:
            # Skip binary files
            if self._is_binary(file_path):
                return False
            
            # Read file content
            with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
                content = f.read()
            
            # Check text search
            if contains:
                if case_sensitive:
                    return contains in content
                else:
                    return contains.lower() in content.lower()
            
            # Check regex search
            if contains_regex:
                return bool(contains_regex.search(content))
            
            return True
        except (PermissionError, FileNotFoundError, UnicodeDecodeError):
            return False
    
    def _is_binary(self, file_path, sample_size=4096):
        """
        Check if a file is binary by reading a sample
        
        Args:
            file_path (str): Path to the file
            sample_size (int): Sample size to check
            
        Returns:
            bool: True if file appears to be binary
        """
        try:
            with open(file_path, 'rb') as f:
                sample = f.read(sample_size)
                
            # Check for null bytes or high proportion of non-printable chars
            text_chars = bytearray({7, 8, 9, 10, 12, 13, 27} | set(range(0x20, 0x7F)))
            return bool(sample.translate(None, text_chars))
        except (PermissionError, FileNotFoundError):
            return True  # Assume binary if we can't read it
    
    def _format_results(self, results, format_type):
        """
        Format results based on specified format
        
        Args:
            results (list): List of result dictionaries
            format_type (str): Format type
            
        Returns:
            Formatted results
        """
        if format_type == 'full':
            return [item['path'] for item in results]
        
        elif format_type == 'name':
            return [item['name'] for item in results]
        
        elif format_type == 'detailed':
            formatted = []
            for item in results:
                item_type = item['type']
                size_str = item['size_readable'] if item_type == 'file' else ''
                mtime_str = item['mtime_readable']
                formatted.append(f"{item_type[:1]}\t{size_str}\t{mtime_str}\t{item['path']}")
            return formatted
        
        elif format_type == 'json':
            return results
        
        elif format_type == 'csv':
            formatted = ['type,name,path,size,size_readable,mtime,mtime_readable']
            for item in results:
                formatted.append(f"{item['type']},{item['name']},{item['path']},{item['size']},{item['size_readable']},{item['mtime']},{item['mtime_readable']}")
            return formatted
        
        return results
    
    def _format_bytes(self, bytes_value):
        """
        Format bytes to a readable form
        
        Args:
            bytes_value (int): Bytes to format
            
        Returns:
            str: Formatted string with appropriate unit
        """
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if bytes_value < 1024 or unit == 'TB':
                return f"{bytes_value:.2f} {unit}"
            bytes_value /= 1024 
    
    def _sort_results(self, results, sort_by, reverse_sort):
        """
        Sort results based on specified sort criteria
        
        Args:
            results (list): List of result dictionaries
            sort_by (str): Sort by: name, path, size, mtime, or none
            reverse_sort (bool): Reverse the sorting order
        """
        if sort_by == 'name':
            results.sort(key=lambda x: x['name'], reverse=reverse_sort)
        elif sort_by == 'path':
            results.sort(key=lambda x: x['path'], reverse=reverse_sort)
        elif sort_by == 'size':
            results.sort(key=lambda x: x['size'], reverse=reverse_sort)
        elif sort_by == 'mtime':
            results.sort(key=lambda x: x['mtime'], reverse=reverse_sort)
        else:
            # Continue without sorting if an invalid sort_by is provided
            pass 